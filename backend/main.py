# backend/main.py
import asyncio
import threading
import uuid
import cv2
import numpy as np
import os
from pathlib import Path
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials

from sqlalchemy import select, update, func, delete, text
from database import engine, Base, AsyncSessionLocal, get_db
import models
from camera_runner import run_camera_thread, get_latest_frame, preload_model_async
from sqlalchemy.ext.asyncio import AsyncSession
import time
from dotenv import load_dotenv
from typing import Optional
import base64
from datetime import datetime
from auth import (
    hash_password, verify_password, create_access_token, decode_access_token,
    LoginRequest, Token, UserCreate, UserResponse, TokenData, is_admin, CompanyResponse
)
from config import is_admin_company_code

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS (dev i├ğin geni┼ş izin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

# Global structures to manage camera threads and queue
camera_threads = {}  # camera_id -> {'thread': Thread, 'stop_event': Event}
violation_queue = None  # asyncio.Queue set at startup
consumer_task = None
main_loop = None

# ===== Authentication Dependencies =====

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: AsyncSession = Depends(get_db)) -> TokenData:
    """
    Extract and validate JWT token from Authorization header.
    Returns the token data (user_id, email, role).
    """
    token = credentials.credentials
    token_data = decode_access_token(token)
    
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify user still exists and is active
    user = await db.get(models.User, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return token_data


async def get_admin_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """
    Dependency to ensure user is admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can perform this action"
        )
    return current_user


async def verify_company_access(
    current_user: TokenData = Depends(get_current_user),
    company_code: Optional[str] = None
) -> str:
    """
    Verify that the user has access to the requested company.
    
    - Admins (with admin company codes): Can access any company
    - Regular users: Can only access their assigned company
    
    Args:
        current_user: The current authenticated user
        company_code: The company code being requested (optional)
    
    Returns:
        The verified company code
    """
    # If no specific company code is requested, use the user's company code
    if company_code is None:
        company_code = current_user.company_code
    
    # Check if user is admin (role-based)
    if current_user.role == "admin":
        return company_code
    
    # Regular users can only access their own company
    if company_code != current_user.company_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this company's data"
        )
    
    return company_code

# Model path - cross-platform compatible
# First try from environment variable, then use relative path
MODEL_PATH = os.getenv("MODEL_PATH")
if not MODEL_PATH:
    # Get the backend directory and construct path relative to it
    backend_dir = Path(__file__).parent
    MODEL_PATH = str(backend_dir.parent / "model" / "weights" / "best.pt")

# Aktif model yolunu yönetmek için global değişken
ACTIVE_MODEL_PATH = MODEL_PATH

def set_active_model_path(path: str):
    """
    Aktif model yolunu günceller. Boş path verilirse devre dışı bırakır.
    Yeni model aktif yapıldığında arka planda ön-yükleme yapılır.
    """
    global ACTIVE_MODEL_PATH
    if not path:
        ACTIVE_MODEL_PATH = None
        print(f"[model] ❌ Aktif model devre dışı bırakıldı.")
    else:
        ACTIVE_MODEL_PATH = path
        print(f"[model] ✅ Aktif model yolu güncellendi: {ACTIVE_MODEL_PATH}")

        if Path(path).exists():
            print(f"[model] 🚀 Model arka planda ön-yükleniyor: {path}")
            preload_model_async(path)
        else:
            print(f"[model] ⚠️ Model dosyası bulunamadı: {path}")


def get_active_model_path() -> str:
    """Aktif model yolunu döndürür."""
    return ACTIVE_MODEL_PATH


async def get_active_model_paths_for_camera(db: AsyncSession, company_id: int, camera_id: int) -> list[str]:
    """Resolve active model paths for a camera, falling back to global default model."""
    active_models = await get_camera_active_models(db, company_id, camera_id)
    paths = [model.get("path") for model in active_models if model.get("path")]
    if paths:
        return paths

    fallback_path = get_active_model_path()
    return [fallback_path] if fallback_path else []


def stop_camera_thread(camera_id: int):
    """Stop a running camera thread if present."""
    info = camera_threads.get(camera_id)
    if not info:
        return

    info['stop_event'].set()
    info['thread'].join(timeout=2.0)
    camera_threads.pop(camera_id, None)


async def stop_company_cameras(db: AsyncSession, company_id: int, trigger: str = "manual") -> int:
    """Stop running camera threads for a company."""
    result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company_id)
    )
    cameras = result.scalars().all()

    stopped_count = 0
    for cam in cameras:
        if cam.id in camera_threads:
            stop_camera_thread(cam.id)
            stopped_count += 1

    print(
        f"[camera-stop] trigger={trigger} company_id={company_id} "
        f"total={len(cameras)} stopped={stopped_count}"
    )
    return stopped_count


async def restart_camera_with_current_models(db: AsyncSession, camera: models.Camera, force_local: bool = False):
    """Restart camera thread with current active model mapping."""
    stop_camera_thread(camera.id)
    model_paths = await get_active_model_paths_for_camera(db, camera.company_id, camera.id)
    source = "0" if force_local else camera.rtsp_url
    start_camera_thread(camera.id, source, model_paths=model_paths, use_default_model=not model_paths)


async def restart_company_cameras(db: AsyncSession, company_id: int):
    """Restart all company cameras so assignment changes apply immediately."""
    cameras_result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company_id)
    )
    for camera in cameras_result.scalars().all():
        await restart_camera_with_current_models(db, camera)


async def sync_company_model_activation_summary(db: AsyncSession, company_id: int):
    """Sync legacy CompanyModel.is_active from camera-level active mappings."""
    active_model_ids_result = await db.execute(
        select(models.CompanyModelCamera.model_id)
        .where(
            (models.CompanyModelCamera.company_id == company_id) &
            (models.CompanyModelCamera.is_active == True)
        )
        .distinct()
    )
    active_model_ids = set(active_model_ids_result.scalars().all())

    company_models_result = await db.execute(
        select(models.CompanyModel).where(models.CompanyModel.company_id == company_id)
    )
    for company_model in company_models_result.scalars().all():
        company_model.is_active = company_model.model_id in active_model_ids


async def ensure_company_model_cameras_schema():
    """Patch legacy DBs where company_model_cameras exists without new columns."""
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS model_id INTEGER"))
        await conn.execute(text("ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS enabled_at TIMESTAMPTZ DEFAULT NOW()"))

        # Ensure expected foreign keys exist (safe no-op when already present).
        await conn.execute(text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'company_model_cameras_model_id_fkey'
                ) THEN
                    ALTER TABLE company_model_cameras
                    ADD CONSTRAINT company_model_cameras_model_id_fkey
                    FOREIGN KEY (model_id) REFERENCES models(id);
                END IF;
            END$$;
            """
        ))

        # Legacy schema may have unique(camera_id) or unique(company_id, camera_id).
        # Drop those so one camera can hold multiple model rows.
        await conn.execute(text(
            """
            DO $$
            DECLARE
                c RECORD;
            BEGIN
                FOR c IN
                    SELECT conname
                    FROM pg_constraint
                    WHERE conrelid = 'company_model_cameras'::regclass
                      AND contype = 'u'
                      AND (
                          pg_get_constraintdef(oid) ILIKE 'UNIQUE (camera_id)%'
                          OR pg_get_constraintdef(oid) ILIKE 'UNIQUE (company_id, camera_id)%'
                          OR pg_get_constraintdef(oid) ILIKE 'UNIQUE (camera_id, company_id)%'
                      )
                LOOP
                    EXECUTE format('ALTER TABLE company_model_cameras DROP CONSTRAINT IF EXISTS %I', c.conname);
                END LOOP;
            END$$;
            """
        ))

        # Keep data clean: one row per (company, camera, model).
        await conn.execute(text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_company_model_cameras_company_camera_model
            ON company_model_cameras (company_id, camera_id, model_id)
            """
        ))

        # Legacy rows may miss model_id; assign a deterministic company model as fallback.
        await conn.execute(text(
            """
            UPDATE company_model_cameras cmc
            SET model_id = sub.model_id
            FROM (
                SELECT company_id, MIN(model_id) AS model_id
                FROM company_models
                GROUP BY company_id
            ) AS sub
            WHERE cmc.model_id IS NULL
              AND cmc.company_id = sub.company_id
            """
        ))

        await conn.execute(text("UPDATE company_model_cameras SET is_active = FALSE WHERE is_active IS NULL"))


def start_camera_thread(
    camera_id: int,
    rtsp_url: str,
    model_path: Optional[str] = None,
    use_default_model: bool = True,
    model_paths: Optional[list[str]] = None,
):
    """Start a blocking camera loop in a separate thread."""
    resolved_model_paths = [path for path in (model_paths or []) if path]

    if not resolved_model_paths and model_path:
        resolved_model_paths = [model_path]

    if not resolved_model_paths and use_default_model:
        fallback_path = get_active_model_path()
        if fallback_path:
            resolved_model_paths = [fallback_path]

    if not resolved_model_paths:
        print(f"[start_camera_thread] ⚠️ Model yoksa bile kamera başlatılıyor (raw feed): camera_id={camera_id}")
    else:
        for path in resolved_model_paths:
            if not Path(path).exists():
                print(f"[start_camera_thread] ⚠️ Model dosyası bulunamadı: {path}")
                print(f"[start_camera_thread] Kamera raw feed veya kalan modeller ile başlatılıyor")

    if camera_id in camera_threads:
        print(f"[start_camera_thread] Camera {camera_id} already running")
        return

    if main_loop is None:
        print(f"[start_camera_thread] ERROR: main_loop is None, cannot start camera {camera_id}")
        return

    if violation_queue is None:
        print(f"[start_camera_thread] ERROR: violation_queue is None, cannot start camera {camera_id}")
        return

    print(
        f"[start_camera_thread] Creating thread for camera {camera_id} with rtsp_url='{rtsp_url}' "
        f"and model_paths='{resolved_model_paths}'"
    )
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_camera_thread,
        args=(camera_id, rtsp_url, resolved_model_paths, main_loop, violation_queue, stop_event),
        daemon=True
    )
    camera_threads[camera_id] = {'thread': thread, 'stop_event': stop_event}
    thread.start()
    print(f"[start_camera_thread] Started camera thread for {camera_id}")


async def ensure_company_cameras_started(db: AsyncSession, company_id: int, trigger: str = "manual") -> int:
    """Start camera threads for a company only if they are not already running."""
    result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company_id)
    )
    cameras = result.scalars().all()

    started_count = 0
    for cam in cameras:
        existing = camera_threads.get(cam.id)
        if existing:
            if existing['thread'].is_alive():
                continue
            # Clean stale thread entries before restarting.
            camera_threads.pop(cam.id, None)

        model_paths = await get_active_model_paths_for_camera(db, cam.company_id, cam.id)
        start_camera_thread(cam.id, cam.rtsp_url, model_paths=model_paths, use_default_model=not model_paths)
        started_count += 1

    print(
        f"[camera-start] trigger={trigger} company_id={company_id} "
        f"total={len(cameras)} started={started_count}"
    )
    return started_count

async def violation_consumer_task(queue: asyncio.Queue):
    """
    Consumes violation payloads from the queue and writes to DB (async).
    """
    print("[consumer] Violation consumer started.")
    while True:
        payload = await queue.get()
        try:
            await save_violation_async(payload)
        except Exception as e:
            print(f"[consumer] Error saving violation: {e}")
        finally:
            queue.task_done()

async def save_violation_async(payload: dict):
    """
    Save the payload as Detection (and Violation) to DB using AsyncSession.
    Eski db_config.py'deki save_violation fonksiyonunun mant─▒─ş─▒na uygun olarak yaz─▒ld─▒.
    Detection.company_id is set from the camera's company_id.
    
    Args:
        payload: dict containing:
            - violations: list of violation types ('head' or 'vest')
            - camera_id: camera ID
            - worker_id: worker ID (used as violation_id)
            - snapshot_path: optional snapshot path
    """
    async with AsyncSessionLocal() as session:
        try:
            camera_id = payload.get('camera_id')
            if camera_id is not None:
                cam = await session.get(models.Camera, camera_id)
                if cam is None or cam.company_id is None:
                    print(f"[consumer] ÔÜá´©Å Camera {camera_id} has no company_id, skipping violation save")
                    return
                company_id = cam.company_id
            else:
                print(f"[consumer] ÔÜá´©Å payload has no camera_id, skipping violation save")
                return

            # Create Detection rows for each violation type (head/vest etc.)
            camera_id = payload.get('camera_id')
            if camera_id is not None:
                cam = await session.get(models.Camera, camera_id)
                if cam is None or cam.company_id is None:
                    print(f"[consumer] ÔÜá´©Å Camera {camera_id} has no company_id, skipping violation save")
                    return
                company_id = cam.company_id
            else:
                print(f"[consumer] ÔÜá´©Å payload has no camera_id, skipping violation save")
                return
            for v in payload.get('violations', []):
                # Validate violation type (eski kodun mant─▒─ş─▒na uygun)
                if v not in ['head', 'vest']:
                    print(f"[consumer] Invalid violation type: {v}, skipping...")
                    continue

                # Create Detection record (company_id from camera)
                det = models.Detection(
                    camera_id=camera_id,
                    company_id=company_id,
                    detection_type=v,
                    confidence=None,
                    is_violation=True,
                    snapshot_path=payload.get('snapshot_path'),
                )
                session.add(det)

                # Create Violation record (eski db_config.py save_violation fonksiyonunun mant─▒─ş─▒na uygun)
                # violation_id: worker_id kullan─▒l─▒yor (eski kodda parametre olarak al─▒n─▒yordu: violation_id: int)
                # tarih_saat: otomatik olarak server_default=func.now() ile kaydedilecek (CURRENT_TIMESTAMP gibi)
                worker_id = payload.get('worker_id')
                if worker_id is None:
                    print(f"[consumer] ÔÜá´©Å Warning: worker_id is None for violation {v}, using 0 as default")
                    worker_id = 0
                
                violation_area = str(payload.get('camera_id')) if payload.get('camera_id') is not None else None  # ihlal_yapilan_bolge (optional, can be None)
                
                vio = models.Violations(
                    company_id=company_id,
                    ihlal_cesidi=v,
                    ihlal_yapilan_bolge=violation_area,
                    violation_id=int(worker_id),
                )
                session.add(vio)

            await session.commit()
            print(f"[consumer] Ô£à Saved violation(s) for camera {payload.get('camera_id')} - {payload.get('violations')}, worker_id={payload.get('worker_id')}")
        except Exception as e:
            await session.rollback()
            print(f"[consumer] ÔØî Error saving violation: {e}")
            import traceback
            traceback.print_exc()
            raise

# Simple endpoints
@app.get("/")
async def root():
    return {"message": "SafetyWatch API running"}

# ===== CORS Preflight Handler =====
@app.options("/{path:path}")
async def preflight_handler():
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )

# ===== Authentication Endpoints =====

@app.post("/api/auth/login", response_model=Token)
async def login(login_request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login endpoint: validates email, password, and company code.
    
    Admin users: company_code must be an admin code (e.g., ADMIN, SUPERADMIN)
    Regular users: company_code must exist in the companies table
    
    Returns JWT token if credentials are valid.
    """
    # Check if this is an admin code
    is_admin_login = is_admin_company_code(login_request.company_code)
    
    company_id = None
    
    if is_admin_login:
        # For admin codes, we don't need to find a company in the database
        # Admin can access all companies
        company_id = None
    else:
        # For regular company codes, find the company in the database
        company_result = await db.execute(
            select(models.Company).where(func.upper(models.Company.code) == func.upper(login_request.company_code))
        )
        company = company_result.scalar_one_or_none()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid company code"
            )
        company_id = company.id
    
    # Find user by email
    if company_id:
        # Regular user: must belong to the specific company
        user_result = await db.execute(
            select(models.User).where(
                (models.User.email == login_request.email) &
                (models.User.company_id == company_id)
            )
        )
    else:
        # Admin login: find user with this email (admin can have any email)
        user_result = await db.execute(
            select(models.User).where(models.User.email == login_request.email)
        )
    
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    password_valid = verify_password(login_request.password, user.hashed_password)
    
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Create access token with company code
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        company_code=login_request.company_code
    )

    # Start company cameras only for regular user logins.
    if user.role == "user" and user.company_id is not None:
        await ensure_company_cameras_started(
            db,
            user.company_id,
            trigger=f"user-login:{user.id}",
        )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=user.role,
        company_code=login_request.company_code
    )


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: TokenData = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get current authenticated user information.
    """
    user = await db.get(models.User, current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/auth/logout")
async def logout(
    payload: Optional[dict] = Body(default=None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout endpoint (token invalidation should be handled on client side).
    """
    target_company_code: Optional[str] = None

    # Regular users always stop their own company cameras on logout.
    if current_user.role == "user":
        target_company_code = current_user.company_code
    elif current_user.role == "admin":
        requested_code = (payload or {}).get("company_code")
        if requested_code and not is_admin_company_code(requested_code):
            target_company_code = requested_code

    stopped_count = 0
    if target_company_code:
        company_result = await db.execute(
            select(models.Company).where(func.upper(models.Company.code) == func.upper(target_company_code))
        )
        company = company_result.scalar_one_or_none()
        if company:
            stopped_count = await stop_company_cameras(
                db,
                company.id,
                trigger=f"logout:{current_user.user_id}",
            )

    return {
        "status": "success",
        "message": "Logged out successfully",
        "stopped_cameras": stopped_count,
    }


@app.post("/api/auth/select-company/{company_code}")
async def select_company_for_admin(
    company_code: str,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin şirket seçtiğinde ilgili şirketin kamera thread'lerini başlatır."""
    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    started_count = await ensure_company_cameras_started(
        db,
        company.id,
        trigger=f"admin-select:{admin_user.user_id}",
    )
    return {
        "status": "success",
        "company_code": company.code,
        "started_cameras": started_count,
    }


@app.get("/api/companies", response_model=list[CompanyResponse])
async def get_companies(
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all companies from database.
    Only accessible by admin users.
    """
    result = await db.execute(select(models.Company).order_by(models.Company.name))
    companies = result.scalars().all()
    return companies


# ===== Admin User Management Endpoints =====

@app.post("/api/admin/users", response_model=UserResponse)
async def create_user(
    user_create: UserCreate,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin-only endpoint to create a new user.
    """
    # Find company by code
    company_result = await db.execute(
        select(models.Company).where(models.Company.code == user_create.company_code)
    )
    company = company_result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Check if user already exists
    existing_user = await db.execute(
        select(models.User).where(
            (models.User.email == user_create.email) &
            (models.User.company_id == company.id)
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists in this company"
        )
    
    # Validate role
    if user_create.role not in ["admin", "user"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'admin' or 'user'"
        )
    
    # Create new user
    new_user = models.User(
        email=user_create.email,
        hashed_password=hash_password(user_create.password),
        company_id=company.id,
        role=user_create.role,
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@app.get("/api/admin/users")
async def list_users(
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin-only endpoint to list all users.
    """
    result = await db.execute(select(models.User).order_by(models.User.created_at.desc()))
    users = result.scalars().all()
    return [UserResponse.from_orm(u) for u in users]


@app.get("/api/admin/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin-only endpoint to get a specific user.
    """
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/api/admin/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: dict,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin-only endpoint to update a user (role, active status).
    """
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update allowed fields
    if "role" in user_update and user_update["role"] in ["admin", "user"]:
        user.role = user_update["role"]
    
    if "is_active" in user_update:
        user.is_active = user_update["is_active"]
    
    await db.commit()
    await db.refresh(user)
    return user


@app.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin-only endpoint to delete a user.
    """
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    
    return {"status": "success", "message": "User deleted"}


# ===== Protected Camera Endpoints =====

async def get_camera_active_models(db: AsyncSession, company_id: int, camera_id: int) -> list[dict]:
    """
    Return active model metadata for the given company/camera.
    Camera-level mappings are authoritative; company-level activation is mirrored for compatibility.
    """
    result = await db.execute(
        select(models.ModelMeta)
        .join(models.CompanyModelCamera, models.CompanyModelCamera.model_id == models.ModelMeta.id)
        .where(
            (models.CompanyModelCamera.company_id == company_id) &
            (models.CompanyModelCamera.camera_id == camera_id) &
            (models.CompanyModelCamera.is_active == True)
        )
        .order_by(models.ModelMeta.uploaded_at.desc())
    )
    model_rows = result.scalars().all()

    return [
        {
            "id": m.id,
            "name": m.version,
            "version": m.version,
            "path": m.path,
            "description": m.description,
        }
        for m in model_rows
    ]


def camera_to_dict(cam: models.Camera, active_models: Optional[list[dict]] = None, model_is_active: Optional[bool] = None) -> dict:
    """Serialize camera row with model assignment info for frontend usage."""
    active_models = active_models or []
    if model_is_active is None:
        model_is_active = len(active_models) > 0

    return {
        "id": cam.id,
        "name": cam.name,
        "location": cam.location,
        "rtsp_url": cam.rtsp_url,
        "status": cam.status,
        "company_id": cam.company_id,
        "last_active": cam.last_active.isoformat() if cam.last_active else None,
        "model_is_active": model_is_active,
        "active_models": active_models,
    }


async def get_active_model_path_for_camera(db: AsyncSession, company_id: int, camera_id: int) -> Optional[str]:
    """
    Resolve model path for a camera.
    Priority: camera's active assigned model, then global ACTIVE_MODEL_PATH.
    """
    active_model_paths = await get_active_model_paths_for_camera(db, company_id, camera_id)
    if active_model_paths:
        model_path = active_model_paths[0]
        if model_path:
            return model_path
    return get_active_model_path()

@app.get("/api/cameras")
async def get_cameras(
    current_user: TokenData = Depends(get_current_user),
    company_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all cameras for a company."""
    # Verify access and get the company code to use
    verified_company_code = await verify_company_access(current_user, company_code)
    
    # Find the company by code
    company_result = await db.execute(
        select(models.Company).where(
            func.upper(models.Company.code) == func.upper(verified_company_code)
        )
    )
    company = company_result.scalar_one_or_none()
    
    if not company and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Admin without specific company: return all cameras
    if current_user.role == "admin" and (company is None):
        result = await db.execute(select(models.Camera))
        cameras = result.scalars().all()
        return [camera_to_dict(cam, model_is_active=False, active_models=[]) for cam in cameras]

    # Regular user or admin with specific company
    result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company.id)
    )
    cameras = result.scalars().all()

    # Attach active models per camera
    response = []
    for cam in cameras:
        active_models = await get_camera_active_models(db, company.id, cam.id)
        response.append(camera_to_dict(cam, active_models=active_models))

    return response


@app.get("/api/detections")
async def get_detections(
    current_user: TokenData = Depends(get_current_user),
    company_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all detections for a company."""
    # Verify access and get the company code to use
    verified_company_code = await verify_company_access(current_user, company_code)
    
    # Find the company by code
    company_result = await db.execute(
        select(models.Company).where(
            func.upper(models.Company.code) == func.upper(verified_company_code)
        )
    )
    company = company_result.scalar_one_or_none()
    
    if not company and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # If admin using admin code, get all detections
    if current_user.role == "admin":
        result = await db.execute(select(models.Detection))
    else:
        # Regular user: get detections for their company
        result = await db.execute(
            select(models.Detection).where(models.Detection.company_id == company.id)
        )
    
    return result.scalars().all()


@app.get("/api/violations")
async def get_violations(
    current_user: TokenData = Depends(get_current_user),
    company_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all violations for a company."""
    # Verify access and get the company code to use
    verified_company_code = await verify_company_access(current_user, company_code)
    
    # Find the company by code
    company_result = await db.execute(
        select(models.Company).where(
            func.upper(models.Company.code) == func.upper(verified_company_code)
        )
    )
    company = company_result.scalar_one_or_none()
    
    if not company and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # If admin using admin code, get all violations
    if current_user.role == "admin":
        result = await db.execute(
            select(models.Violations).order_by(models.Violations.tarih_saat.desc())
        )
    else:
        # Regular user: get violations for their company
        result = await db.execute(
            select(models.Violations)
            .where(models.Violations.company_id == company.id)
            .order_by(models.Violations.tarih_saat.desc())
        )
    
    violations = result.scalars().all()
    return [
        {
            "id": v.id,
            "violation_id": v.violation_id,
            "ihlal_cesidi": v.ihlal_cesidi,
            "ihlal_yapilan_bolge": v.ihlal_yapilan_bolge,
            "tarih_saat": v.tarih_saat,
            "review_status": v.review_status if v.review_status else "pending",
        }
        for v in violations
    ]

@app.patch("/api/violations/{violation_id}/status")
async def update_violation_status(
    violation_id: int,
    body: dict,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update the review status of a violation (pending | reviewed | resolved)."""
    review_status = body.get("review_status", "")
    allowed = {'pending', 'reviewed', 'resolved'}
    if review_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {allowed}")

    if current_user.role == "admin":
        result = await db.execute(
            update(models.Violations)
            .where(models.Violations.id == violation_id)
            .values(review_status=review_status)
        )
    else:
        # Single query: update only if the violation belongs to the user's company
        result = await db.execute(
            update(models.Violations)
            .where(
                models.Violations.id == violation_id,
                models.Violations.company_id == select(models.Company.id).where(
                    func.upper(models.Company.code) == func.upper(current_user.company_code)
                ).scalar_subquery()
            )
            .values(review_status=review_status)
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Violation not found or access denied")

    await db.commit()
    return {"id": violation_id, "review_status": review_status}


@app.post("/api/camera/{camera_id}/start-local")
async def api_start_local_camera(
    camera_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start camera thread with local camera (0) instead of RTSP URL."""
    async with AsyncSessionLocal() as session:
        cam = await session.get(models.Camera, camera_id)
        if not cam:
            return {"error": "camera not found"}
        
        # Verify company access to this camera
        if current_user.role != "admin":
            # Check if the camera belongs to the user's company
            company_result = await session.execute(
                select(models.Company).where(
                    func.upper(models.Company.code) == func.upper(current_user.company_code)
                )
            )
            company = company_result.scalar_one_or_none()
            if not company or cam.company_id != company.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this camera"
                )
        
        # Use "0" for local camera
        print(f"[api_start_local_camera] Starting local camera for camera_id={camera_id}")
        model_paths = await get_active_model_paths_for_camera(session, cam.company_id, cam.id)
        start_camera_thread(cam.id, "0", model_paths=model_paths, use_default_model=not model_paths)
    return {"status": "started with local camera", "camera_id": camera_id}


@app.post("/api/camera/{camera_id}/stop")
async def api_stop_camera(
    camera_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Stop camera thread."""
    # Verify access to camera
    cam = await db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
    
    if current_user.role != "admin":
        # Check if the camera belongs to the user's company
        company_result = await db.execute(
            select(models.Company).where(
                func.upper(models.Company.code) == func.upper(current_user.company_code)
            )
        )
        company = company_result.scalar_one_or_none()
        if not company or cam.company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this camera"
            )
    
    if camera_id not in camera_threads:
        return {"status": "not running"}
    stop_camera_thread(camera_id)
    return {"status": "stopped", "camera_id": camera_id}

@app.get("/api/camera/{camera_id}/frame-status")
async def get_frame_status(camera_id: int, current_user: TokenData = Depends(get_current_user)):
    """Check if frames are available for a camera (for debugging)."""
    frame_bytes = get_latest_frame(camera_id)
    has_frame = frame_bytes is not None
    frame_size = len(frame_bytes) if has_frame else 0
    is_running = camera_id in camera_threads
    
    return {
        "camera_id": camera_id,
        "has_frame": has_frame,
        "frame_size": frame_size,
        "thread_running": is_running,
        "thread_info": {
            "thread_alive": camera_threads[camera_id]['thread'].is_alive() if is_running else False
        } if is_running else None
    }

@app.get("/api/debug/camera-status")
async def debug_camera_status(admin_user: TokenData = Depends(get_admin_user)):
    """Debug endpoint to check all camera threads."""
    status = {
        "camera_threads": {},
        "frame_storage": {},
        "total_threads": len(camera_threads)
    }
    
    for cam_id, info in camera_threads.items():
        status["camera_threads"][cam_id] = {
            "thread_alive": info['thread'].is_alive(),
            "stop_event_set": info['stop_event'].is_set()
        }
        
        # Check frame storage for this camera
        frame_bytes = get_latest_frame(cam_id)
        status["frame_storage"][cam_id] = {
            "has_frame": frame_bytes is not None,
            "frame_size": len(frame_bytes) if frame_bytes else 0
        }
    
    return status

@app.get("/api/camera/{camera_id}/stream")
async def stream_camera(
    camera_id: int,
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
):
    """
    MJPEG stream endpoint for live camera feed with detections.
    """
    raw_token = token or (credentials.credentials if credentials else None)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")

    token_data = decode_access_token(raw_token)
    if token_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await db.get(models.User, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    cam = await db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    if token_data.role != "admin":
        company_result = await db.execute(
            select(models.Company).where(
                func.upper(models.Company.code) == func.upper(token_data.company_code)
            )
        )
        company = company_result.scalar_one_or_none()
        if not company or cam.company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this camera",
            )

    # Create a placeholder black frame
    placeholder_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(placeholder_frame, "No frame available", (150, 240), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    _, buffer = cv2.imencode('.jpg', placeholder_frame)
    placeholder_bytes = buffer.tobytes()
    
    async def generate_frames():
        consecutive_empty = 0
        while True:
            frame_bytes = get_latest_frame(camera_id)
            if frame_bytes:
                consecutive_empty = 0
                # MJPEG format: frame boundary + frame data
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                consecutive_empty += 1
                # Only send placeholder after a few empty frames to avoid spam
                if consecutive_empty > 10:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + placeholder_bytes + b'\r\n')
            await asyncio.sleep(0.033)  # ~30 FPS
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

def modelmeta_to_dict(model):
    """ModelMeta nesnesini dict'e ├ğevirir (JSON serializable)."""
    return {
        "id": model.id,
        "path": model.path,
        "version": model.version,
        "description": model.description,
        "uploaded_at": model.uploaded_at.isoformat() if model.uploaded_at else "",
        "is_active": model.is_active,
    }



@app.post("/api/model/upload")
async def upload_model(
    file: UploadFile = File(...),
    version: str = Form(...),
    description: Optional[str] = Form(None),
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Yeni bir model dosyas─▒n─▒ y├╝kler ve kaydeder. (Admin only)
    """
    allowed_ext = ('.pt', '.weights', '.onnx')
    if not any(file.filename.endswith(ext) for ext in allowed_ext):
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya uzant─▒s─▒.")

    try:
        models_dir = Path(__file__).parent.parent / "model" / "weights"
        models_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{version}_{uuid.uuid4().hex}_{file.filename}"
        file_path = models_dir / filename

        # Store the path as project-root-relative with forward slashes so it
        # works on every team member's machine regardless of OS or clone location.
        project_root = Path(__file__).parent.parent
        relative_path = file_path.relative_to(project_root).as_posix()  # e.g. "model/weights/v1_best.pt"

        # Dosya boyutu kontrolü (örnek: 200MB sınır)
        MAX_SIZE = 200 * 1024 * 1024
        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="Model dosyası çok büyük (max 200MB).")

        with open(file_path, "wb") as f:
            f.write(content)
        print(f"[model] Model dosyası yüklendi: {file_path} (stored as: {relative_path})")

        # DB'ye model meta verisini kaydet
        async with AsyncSessionLocal() as session:
            # Aynı path varsa ekleme!
            existing = await session.execute(select(models.ModelMeta).where(models.ModelMeta.path == relative_path))
            if existing.scalars().first():
                raise HTTPException(status_code=409, detail="Bu path ile model zaten var.")
            model_meta = models.ModelMeta(
                path=relative_path,
                version=version,
                description=description,
                is_active=False
            )
            session.add(model_meta)
            await session.commit()
        return {"status": "success", "path": relative_path, "version": version, "description": description}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[model] Model y├╝kleme hatas─▒: {e}")
        raise HTTPException(status_code=500, detail=f"Model y├╝kleme hatas─▒: {str(e)}")

@app.post("/api/model/activate")
async def activate_model(
    path: str = Form(...),
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Y├╝klenen bir modeli aktif hale getirir veya devre d─▒┼ş─▒ b─▒rak─▒r.
    """
    # E─şer path bo┼şsa, aktif modeli devre d─▒┼ş─▒ b─▒rak
    if not path:
        set_active_model_path("")
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(models.Camera))
            for cam in result.scalars().all():
                print(f"[model] Varsayilan model kapatildi, kamera yeniden baslatiliyor: {cam.id}")
                await restart_camera_with_current_models(session, cam)
        return {"status": "active", "model_path": None}

    if not Path(path).exists():
        raise HTTPException(status_code=404, detail="Model dosyas─▒ bulunamad─▒.")
    set_active_model_path(path)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(models.Camera))
        for cam in result.scalars().all():
            print(f"[model] Varsayilan model guncellendi, kamera yeniden baslatiliyor: {cam.id}")
            await restart_camera_with_current_models(session, cam)
    
    async with AsyncSessionLocal() as session:
        # T├╝m modelleri pasif yap
        await session.execute(update(models.ModelMeta).values(is_active=False))
        # E─şer path bo┼ş de─şilse, ilgili modeli aktif yap
        if path:
            await session.execute(update(models.ModelMeta).where(models.ModelMeta.path == path).values(is_active=True))
        await session.commit()
    return {"status": "active", "model_path": path}

@app.get("/api/model/active")
async def get_active_model(current_user: TokenData = Depends(get_current_user)):
    """
    Aktif model yolunu d├Ând├╝r├╝r.
    """
    return {"active_model_path": get_active_model_path()}

@app.get("/api/models")
async def get_models(current_user: TokenData = Depends(get_current_user)):
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(models.ModelMeta).order_by(models.ModelMeta.uploaded_at.desc()))
            models_list = result.scalars().all()
            return [modelmeta_to_dict(m) for m in models_list]
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model listesi al─▒namad─▒: {str(e)}")


def general_model_to_dict(model: models.ModelMeta) -> dict:
    """Frontend'in general model format─▒ i├ğin ModelMeta'y─▒ normalize eder."""
    return {
        "id": model.id,
        "name": model.version,
        "version": model.version,
        "description": model.description,
        "path": model.path,
        "uploaded_at": model.uploaded_at.isoformat() if model.uploaded_at else "",
        "is_active": model.is_active,
    }


@app.get("/api/general-models")
async def get_general_models(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """T├╝m genel modelleri d├Ând├╝r├╝r."""
    result = await db.execute(select(models.ModelMeta).order_by(models.ModelMeta.uploaded_at.desc()))
    models_list = result.scalars().all()
    return [general_model_to_dict(m) for m in models_list]


@app.get("/api/company/{company_code}/general-models")
async def get_company_general_models(
    company_code: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """┼Şirkete atanm─▒┼ş genel modelleri d├Ând├╝r├╝r."""
    await verify_company_access(current_user, company_code)

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="┼Şirket bulunamad─▒")

    result = await db.execute(
        select(models.ModelMeta)
        .join(models.CompanyModel, models.CompanyModel.model_id == models.ModelMeta.id)
        .where(models.CompanyModel.company_id == company.id)
        .order_by(models.ModelMeta.uploaded_at.desc())
    )
    models_list = result.scalars().all()
    return [general_model_to_dict(m) for m in models_list]


@app.put("/api/company/{company_code}/general-models")
async def set_company_general_models(
    company_code: str,
    payload: dict,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """┼Şirkete atanacak model listesini toplu g├╝nceller. Body: { model_ids: number[] }"""
    model_ids = payload.get("model_ids", []) if isinstance(payload, dict) else []
    if not isinstance(model_ids, list):
        raise HTTPException(status_code=400, detail="model_ids list olmal─▒d─▒r")
    normalized_model_ids = list(dict.fromkeys(int(model_id) for model_id in model_ids))

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="┼Şirket bulunamad─▒")

    valid_model_ids = set()
    if normalized_model_ids:
        valid_models_result = await db.execute(
            select(models.ModelMeta.id).where(models.ModelMeta.id.in_(normalized_model_ids))
        )
        valid_model_ids = set(valid_models_result.scalars().all())

    existing_company_models_result = await db.execute(
        select(models.CompanyModel).where(models.CompanyModel.company_id == company.id)
    )
    existing_company_models = existing_company_models_result.scalars().all()
    existing_model_ids = {company_model.model_id for company_model in existing_company_models}

    removed_model_ids = existing_model_ids - valid_model_ids
    added_model_ids = valid_model_ids - existing_model_ids

    if removed_model_ids:
        await db.execute(
            delete(models.CompanyModelCamera).where(
                (models.CompanyModelCamera.company_id == company.id) &
                (models.CompanyModelCamera.model_id.in_(removed_model_ids))
            )
        )
        await db.execute(
            delete(models.CompanyModel).where(
                (models.CompanyModel.company_id == company.id) &
                (models.CompanyModel.model_id.in_(removed_model_ids))
            )
        )

    for model_id in added_model_ids:
        db.add(models.CompanyModel(company_id=company.id, model_id=model_id, is_active=False))

    await sync_company_model_activation_summary(db, company.id)

    await db.commit()
    await restart_company_cameras(db, company.id)
    return {"status": "success", "assigned_count": len(valid_model_ids)}


@app.get("/api/company/{company_code}/model-cameras")
async def get_company_model_cameras(
    company_code: str,
    model_id: Optional[int] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """┼Şirket kameralar─▒n─▒ ve model bazl─▒ aktiflik durumunu d├Ând├╝r├╝r."""
    await verify_company_access(current_user, company_code)

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="┼Şirket bulunamad─▒")

    cameras_result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company.id)
    )
    cameras = cameras_result.scalars().all()

    active_model_ids_result = await db.execute(
        select(models.CompanyModelCamera.model_id)
        .where(
            (models.CompanyModelCamera.company_id == company.id) &
            (models.CompanyModelCamera.is_active == True)
        )
        .distinct()
    )
    active_model_ids = set(active_model_ids_result.scalars().all())

    response = []
    for cam in cameras:
        active_models = await get_camera_active_models(db, company.id, cam.id)
        active_model_id_set = {active_model["id"] for active_model in active_models}
        selected_model_is_active = (model_id in active_model_id_set) if model_id is not None else bool(active_model_id_set)
        response.append(
            camera_to_dict(
                cam,
                active_models=active_models,
                model_is_active=selected_model_is_active,
            )
        )
    return response


@app.put("/api/company/{company_code}/model-cameras")
async def set_company_model_cameras(
    company_code: str,
    payload: dict,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Model-kamera atamas─▒ g├╝nceller. Body: { model_id: number, camera_ids: number[] }"""
    await verify_company_access(current_user, company_code)

    model_id = payload.get("model_id") if isinstance(payload, dict) else None
    camera_ids = payload.get("camera_ids", []) if isinstance(payload, dict) else []

    if model_id is None:
        raise HTTPException(status_code=400, detail="model_id zorunludur")
    if not isinstance(camera_ids, list):
        raise HTTPException(status_code=400, detail="camera_ids list olmal─▒d─▒r")

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="┼Şirket bulunamad─▒")

    company_model_result = await db.execute(
        select(models.CompanyModel).where(
            (models.CompanyModel.company_id == company.id) &
            (models.CompanyModel.model_id == int(model_id))
        )
    )
    company_model = company_model_result.scalar_one_or_none()
    if not company_model:
        raise HTTPException(status_code=404, detail="Model bu ┼şirkete atanmam─▒┼ş")

    valid_camera_ids_result = await db.execute(
        select(models.Camera.id).where(models.Camera.company_id == company.id)
    )
    valid_camera_ids = set(valid_camera_ids_result.scalars().all())
    invalid_camera_ids = [camera_id for camera_id in camera_ids if int(camera_id) not in valid_camera_ids]
    if invalid_camera_ids:
        raise HTTPException(status_code=400, detail=f"Ge├ğersiz camera_ids: {invalid_camera_ids}")

    normalized_camera_ids = {int(camera_id) for camera_id in camera_ids}

    existing_assignments_result = await db.execute(
        select(models.CompanyModelCamera).where(
            (models.CompanyModelCamera.company_id == company.id) &
            (models.CompanyModelCamera.model_id == int(model_id))
        )
    )
    existing_assignments = existing_assignments_result.scalars().all()
    assignments_by_camera = {assignment.camera_id: assignment for assignment in existing_assignments}

    for camera_id in valid_camera_ids:
        should_be_active = camera_id in normalized_camera_ids
        assignment = assignments_by_camera.get(camera_id)

        if assignment:
            assignment.is_active = should_be_active
        elif should_be_active:
            db.add(
                models.CompanyModelCamera(
                    company_id=company.id,
                    camera_id=camera_id,
                    model_id=int(model_id),
                    is_active=True,
                )
            )

    await sync_company_model_activation_summary(db, company.id)

    await db.commit()
    await restart_company_cameras(db, company.id)

    return {
        "status": "success",
        "model_id": int(model_id),
        "selected_camera_count": len(normalized_camera_ids),
        "note": "Camera-level model mapping applied. Multiple models can run on the same camera."
    }

# ===== Company Model Management Endpoints =====

@app.get("/api/company/{company_code}/models")
async def get_company_models(
    company_code: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Belirli bir company i├ğin atanan modelleri d├Ând├╝r├╝r.
    Admin t├╝m ┼şirketlere, regular users kendi ┼şirketlerine eri┼şebilir.
    """
    # Company access kontrol├╝
    await verify_company_access(current_user, company_code)
    
    try:
        # Company'yi bul
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="┼Şirket bulunamad─▒")
        
        # Company'nin modellerini getir
        result = await db.execute(
            select(models.CompanyModel)
            .where(models.CompanyModel.company_id == company.id)
            .join(models.ModelMeta)
            .order_by(models.ModelMeta.version.desc())
        )
        company_models = result.scalars().all()
        
        # Response olu┼ştur
        response = []
        for cm in company_models:
            response.append({
                "id": cm.id,
                "model_id": cm.model_id,
                "company_id": cm.company_id,
                "is_active": cm.is_active,
                "enabled_at": cm.enabled_at.isoformat() if cm.enabled_at else "",
                "model": {
                    "id": cm.model.id,
                    "path": cm.model.path,
                    "version": cm.model.version,
                    "description": cm.model.description,
                    "uploaded_at": cm.model.uploaded_at.isoformat() if cm.model.uploaded_at else "",
                }
            })
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model listesi al─▒namad─▒: {str(e)}")


@app.post("/api/company/{company_code}/models/{model_id}/assign")
async def assign_model_to_company(
    company_code: str,
    model_id: int,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bir modeli bir ┼şirkete atar. (Admin only)
    """
    try:
        # Company ve Model'i bul
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="┼Şirket bulunamad─▒")
        
        model_result = await db.execute(
            select(models.ModelMeta).where(models.ModelMeta.id == model_id)
        )
        model = model_result.scalars().first()
        if not model:
            raise HTTPException(status_code=404, detail="Model bulunamad─▒")
        
        # Zaten atanm─▒┼ş m─▒ kontrol et
        existing = await db.execute(
            select(models.CompanyModel)
            .where(
                (models.CompanyModel.company_id == company.id) &
                (models.CompanyModel.model_id == model_id)
            )
        )
        if existing.scalars().first():
            raise HTTPException(status_code=409, detail="Model zaten bu ┼şirkete atanm─▒┼ş")
        
        # Yeni atama olu┼ştur
        company_model = models.CompanyModel(
            company_id=company.id,
            model_id=model_id,
            is_active=False
        )
        db.add(company_model)
        await db.commit()
        
        return {
            "status": "success",
            "message": f"Model {model.version} ┼şirkete {company.name} atand─▒"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model atama hatas─▒: {str(e)}")


@app.post("/api/company/{company_code}/models/{company_model_id}/activate")
async def activate_model_for_company(
    company_code: str,
    company_model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Belirli bir company i├ğin modeli t├╝m kameralarda aktifle┼ştir."""
    # Company access kontrol├╝
    await verify_company_access(current_user, company_code)
    
    try:
        # Company'yi bul
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="┼Şirket bulunamad─▒")
        
        # CompanyModel'i bul (model relationship ile)
        cm_result = await db.execute(
            select(models.CompanyModel)
            .where(
                (models.CompanyModel.id == company_model_id) &
                (models.CompanyModel.company_id == company.id)
            )
        )
        company_model = cm_result.scalars().first()
        if not company_model:
            raise HTTPException(status_code=404, detail="Model atamas─▒ bulunamad─▒")
        
        cameras_result = await db.execute(
            select(models.Camera).where(models.Camera.company_id == company.id)
        )
        cameras = cameras_result.scalars().all()
        if not cameras:
            raise HTTPException(status_code=400, detail="┼Şirkete ait kamera bulunamad─▒")

        assignments_result = await db.execute(
            select(models.CompanyModelCamera).where(
                (models.CompanyModelCamera.company_id == company.id) &
                (models.CompanyModelCamera.model_id == company_model.model_id)
            )
        )
        assignments_by_camera = {
            assignment.camera_id: assignment for assignment in assignments_result.scalars().all()
        }

        for camera in cameras:
            assignment = assignments_by_camera.get(camera.id)
            if assignment:
                assignment.is_active = True
            else:
                db.add(
                    models.CompanyModelCamera(
                        company_id=company.id,
                        camera_id=camera.id,
                        model_id=company_model.model_id,
                        is_active=True,
                    )
                )

        await sync_company_model_activation_summary(db, company.id)
        await db.commit()
        await restart_company_cameras(db, company.id)
        
        return {
            "status": "success",
            "message": f"Model {company_model.model.version} ┼şirkete ait t├╝m kameralarda aktifle┼ştirildi"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model aktivasyon hatas─▒: {str(e)}")


@app.post("/api/company/{company_code}/models/{company_model_id}/deactivate")
async def deactivate_model_for_company(
    company_code: str,
    company_model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Belirli bir company i├ğin modeli t├╝m kameralarda deaktifle┼ştir."""
    await verify_company_access(current_user, company_code)
    
    try:
        # Company'yi bul
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="┼Şirket bulunamad─▒")
        
        # CompanyModel'i bul
        cm_result = await db.execute(
            select(models.CompanyModel)
            .where(
                (models.CompanyModel.id == company_model_id) &
                (models.CompanyModel.company_id == company.id)
            )
        )
        company_model = cm_result.scalars().first()
        if not company_model:
            raise HTTPException(status_code=404, detail="Model atamas─▒ bulunamad─▒")
        
        await db.execute(
            update(models.CompanyModelCamera)
            .where(
                (models.CompanyModelCamera.company_id == company.id) &
                (models.CompanyModelCamera.model_id == company_model.model_id)
            )
            .values(is_active=False)
        )

        await sync_company_model_activation_summary(db, company.id)
        await db.commit()
        await restart_company_cameras(db, company.id)
        
        return {
            "status": "success",
            "message": f"Model {company_model.model.version} t├╝m company kameralar─▒nda deaktifle┼ştirildi"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model deaktivasyonu hatas─▒: {str(e)}")

@app.on_event("startup")
async def startup_event():
    global main_loop, violation_queue, consumer_task
    
    # T├╝m tablolar─▒ olu┼ştur (├Âzellikle models tablosu i├ğin)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Legacy DB compatibility: make sure company_model_cameras has expected columns.
        await ensure_company_model_cameras_schema()

        # Add review_status column to violations if missing (safe no-op when already present).
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE IF EXISTS violations ADD COLUMN IF NOT EXISTS review_status VARCHAR NOT NULL DEFAULT 'pending'"
            ))
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print("This may be expected if running without database connection initially")
    
    # AsyncIO loop'u global'e kaydet
    main_loop = asyncio.get_event_loop()
    
    # Violation queue'yu olu┼ştur
    violation_queue = asyncio.Queue()
    
    # Consumer task'─▒ ba┼şlat
    consumer_task = asyncio.create_task(violation_consumer_task(violation_queue))
    

    # Kamera thread'leri startup'ta otomatik başlatılmaz.
    # Başlatma tetikleri:
    # - Regular user login
    # - Admin company selection
    print("[startup] Camera auto-start disabled. Waiting for login/company selection trigger.")

# Detect endpoint'i ekleyin
@app.post("/api/detect")
async def detect(
    file: UploadFile = File(...),
    model_path: str = Form(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Y├╝klenen resmi aktif model ile analiz et
    """
    try:
        if not model_path or model_path == '':
            return {
                "status": "error",
                "message": "Model yolu ge├ğersiz. L├╝tfen bir model aktif edin."
            }
        
        # Modeli y├╝kle
        from ultralytics import YOLO
        
        model_full_path = model_path
        if not Path(model_full_path).exists():
            return {
                "status": "error",
                "message": f"Model dosyas─▒ bulunamad─▒: {model_full_path}"
            }
        
        # Resim dosyas─▒n─▒ oku
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {
                "status": "error",
                "message": "Resim dosyas─▒ okunamad─▒. L├╝tfen ge├ğerli bir resim se├ğin."
            }
        
        # YOLO modelini y├╝kle ve ├ğal─▒┼şt─▒r
        model = YOLO(model_full_path)
        results = model(img)
        
        # Sonu├ğlar─▒ i┼şle
        detections = []
        for r in results:
            for box in r.boxes:
                detections.append({
                    "class": model.names[int(box.cls)],
                    "confidence": float(box.conf),
                    "bbox": box.xyxy[0].tolist()
                })
        
        # Annotated image'─▒ olu┼ştur
        annotated_img = results[0].plot()
        _, buffer = cv2.imencode('.jpg', annotated_img)
        image_base64 = base64.b64encode(buffer).decode()
        
        return {
            "status": "success",
            "detections": len(detections),
            "objects": detections,
            "image_base64": image_base64,
            "processing_time": results[0].speed.get('inference', 0)
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Detection hatas─▒: {str(e)}"
        }

