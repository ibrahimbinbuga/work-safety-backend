# backend/main.py
import asyncio
import threading
import uuid
import cv2
import numpy as np
import os
from pathlib import Path
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials

from sqlalchemy import select, update, func
from sqlalchemy.orm import joinedload
from database import engine, Base, AsyncSessionLocal, get_db
import models
from camera_runner import run_camera_thread, get_latest_frame
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

# CORS (dev için geniş izin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

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

from model_loader import preload_model_async, get_model, get_models_base_dir

# Model path - cross-platform compatible, pointing into backend/models
MODEL_PATH = os.getenv("MODEL_PATH")
if not MODEL_PATH:
    backend_dir = Path(__file__).parent
    MODEL_PATH = str(backend_dir / "models" / "best.pt")

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
        
        # 📌 Yeni modeli arka planda ön-yükle (kamera thread'lerini bloke etmez)
        if Path(path).exists():
            print(f"[model] 🚀 Model arka planda ön-yükleniyor: {path}")
            preload_model_async(path)
        else:
            print(f"[model] ⚠️ Model dosyası bulunamadı: {path}")

def get_active_model_path() -> str:
    """
    Aktif model yolunu döndürür.
    """
    return ACTIVE_MODEL_PATH



def start_camera_thread(
    camera_id: int,
    rtsp_url: str,
    model_path: Optional[str] = None,
    model_task: Optional[str] = None,
    use_default_model: bool = True,
):
    """Start a blocking camera loop in a separate thread."""
    # 📌 Model yolunu al (arka planda yükleniyor olabilir)
    if model_path is None and use_default_model:
        model_path = get_active_model_path()
    
    # Eğer model yoksa, kullanıcı bilgilendir ama kamera yine de başlat
    # (raw camera feed gösterecek, detection olmadan)
    if not model_path:
        print(f"[start_camera_thread] ⚠️ Model yoksa bile kamera başlatılıyor (raw feed): camera_id={camera_id}")
        # Model yoksa bile devam et - kamera en az raw feed'i gösterecek
    else:
        if not Path(model_path).exists():
            print(f"[start_camera_thread] ⚠️ Model dosyası bulunamadı: {model_path}")
            print(f"[start_camera_thread] Kamera raw feed ile başlatılıyor (detection olmadan)")
    
    if camera_id in camera_threads:  # It is used to check if the camera thread is already running
        print(f"[start_camera_thread] Camera {camera_id} already running")
        return
    
    if main_loop is None:  # It is used to check if the main loop is already running
        print(f"[start_camera_thread] ERROR: main_loop is None, cannot start camera {camera_id}")
        return
    
    if violation_queue is None:  # It is used to check if the violation queue is already running
        print(f"[start_camera_thread] ERROR: violation_queue is None, cannot start camera {camera_id}")
        return
    
    print(f"[start_camera_thread] Creating thread for camera {camera_id} with rtsp_url='{rtsp_url}' and model_path='{model_path}' task='{model_task}'")
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_camera_thread,
        args=(camera_id, rtsp_url, model_path, model_task, main_loop, violation_queue, stop_event),
        daemon=True
    )
    camera_threads[camera_id] = {'thread': thread, 'stop_event': stop_event}
    thread.start()
    print(f"[start_camera_thread] Started camera thread for {camera_id}")

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
    Eski db_config.py'deki save_violation fonksiyonunun mantığına uygun olarak yazıldı.
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
                    print(f"[consumer] ⚠️ Camera {camera_id} has no company_id, skipping violation save")
                    return
                company_id = cam.company_id
            else:
                print(f"[consumer] ⚠️ payload has no camera_id, skipping violation save")
                return

            # Create Detection rows for each violation type (head/vest etc.)
            camera_id = payload.get('camera_id')
            if camera_id is not None:
                cam = await session.get(models.Camera, camera_id)
                if cam is None or cam.company_id is None:
                    print(f"[consumer] ⚠️ Camera {camera_id} has no company_id, skipping violation save")
                    return
                company_id = cam.company_id
            else:
                print(f"[consumer] ⚠️ payload has no camera_id, skipping violation save")
                return
            for v in payload.get('violations', []):
                # Validate violation type (eski kodun mantığına uygun)
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

                # Create Violation record (eski db_config.py save_violation fonksiyonunun mantığına uygun)
                # violation_id: worker_id kullanılıyor (eski kodda parametre olarak alınıyordu: violation_id: int)
                # tarih_saat: otomatik olarak server_default=func.now() ile kaydedilecek (CURRENT_TIMESTAMP gibi)
                worker_id = payload.get('worker_id')
                if worker_id is None:
                    print(f"[consumer] ⚠️ Warning: worker_id is None for violation {v}, using 0 as default")
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
            print(f"[consumer] ✅ Saved violation(s) for camera {payload.get('camera_id')} - {payload.get('violations')}, worker_id={payload.get('worker_id')}")
        except Exception as e:
            await session.rollback()
            print(f"[consumer] ❌ Error saving violation: {e}")
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
async def logout(current_user: TokenData = Depends(get_current_user)):
    """
    Logout endpoint (token invalidation should be handled on client side).
    """
    return {"status": "success", "message": "Logged out successfully"}


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

@app.get("/api/company/{company_code}/model-cameras")
async def get_company_model_cameras(
    company_code: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin için: belirli bir şirketin kameralarını ve aktif modellerini döndürür.
    Cameras.jsx bu endpoint'i kullanır.
    """
    # Şirket erişim kontrolü
    await verify_company_access(current_user, company_code)

    company_result = await db.execute(
        select(models.Company).where(models.Company.code == company_code)
    )
    company = company_result.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company.id)
    )
    cameras = result.scalars().all()

    response = []
    for cam in cameras:
        active_models = await get_camera_active_models(db, company.id, cam.id)
        response.append(camera_to_dict(cam, active_models=active_models))

    return response


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
    return violations

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
        
        # If camera is offline, don't start it
        if (cam.status or "").lower() == "offline":
            return {
                "status": "not_started",
                "reason": "camera status is offline",
                "camera_id": camera_id,
            }
        
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
        model_meta = await get_active_model_for_camera(session, cam.company_id, cam.id)
        if model_meta:
            start_camera_thread(
                cam.id,
                "0",
                model_path=model_meta.path,
                model_task=(getattr(model_meta, "task_type", "ppe") or "ppe"),
                use_default_model=False,
            )
        else:
            start_camera_thread(cam.id, "0")
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
    
    info = camera_threads.get(camera_id)
    if not info:
        return {"status": "not running"}
    info['stop_event'].set()
    info['thread'].join(timeout=2.0)
    del camera_threads[camera_id]
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
async def stream_camera(camera_id: int):
    """
    MJPEG stream endpoint for live camera feed with detections.
    NOTE: This endpoint is intentionally left unauthenticated so it can be used as a raw <img> src.
    """
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
    """ModelMeta nesnesini dict'e çevirir (JSON serializable)."""
    return {
        "id": model.id,
        "path": model.path,
        "version": model.version,
        "description": model.description,
        "uploaded_at": model.uploaded_at.isoformat() if model.uploaded_at else "",
        "is_active": model.is_active,
        "task_type": getattr(model, "task_type", "ppe") or "ppe",
    }



@app.post("/api/model/upload")
async def upload_model(
    file: UploadFile = File(...),
    version: str = Form(...),
    description: Optional[str] = Form(None),
    task_type: str = Form("ppe"),
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Yeni bir model dosyasını yükler ve kaydeder. (Admin only)

    Not: DB'de tam dosya yolu yerine backend dizinine göre göreli bir yol
    (örn. "models/filename.pt") tutulur. Böylece proje başka bir makineye
    taşındığında path'ler geçerli kalır.
    """
    allowed_ext = ('.pt', '.weights', '.onnx')
    if not any(file.filename.endswith(ext) for ext in allowed_ext):
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya uzantısı.")

    try:
        backend_dir = Path(__file__).parent
        models_dir = get_models_base_dir()
        filename = f"{version}_{uuid.uuid4().hex}_{file.filename}"
        file_path = models_dir / filename
        # DB'de saklanacak göreli path (örn. "models/xxx.pt")
        relative_path = file_path.relative_to(backend_dir)

        # Dosya boyutu kontrolü (örnek: 200MB sınır)
        MAX_SIZE = 200 * 1024 * 1024
        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="Model dosyası çok büyük (max 200MB).")

        with open(file_path, "wb") as f:
            f.write(content)
        print(f"[model] Model dosyası yüklendi: {file_path}")

        # DB'ye model meta verisini kaydet
        async with AsyncSessionLocal() as session:
            # Aynı göreli path varsa ekleme!
            existing = await session.execute(
                select(models.ModelMeta).where(models.ModelMeta.path == str(relative_path))
            )
            if existing.scalars().first():
                raise HTTPException(status_code=409, detail="Bu path ile model zaten var.")
            # task_type: ppe, fall vb. - sadece temel doğrulama
            normalized_task = (task_type or "ppe").lower()
            if normalized_task not in ["ppe", "fall"]:
                normalized_task = "ppe"

            model_meta = models.ModelMeta(
                path=str(relative_path),
                version=version,
                description=description,
                is_active=False,
                task_type=normalized_task,
            )
            session.add(model_meta)
            await session.commit()
        return {
            "status": "success",
            "path": str(relative_path),
            "version": version,
            "description": description,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[model] Model yükleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Model yükleme hatası: {str(e)}")

@app.post("/api/model/activate")
async def activate_model(
    path: str = Form(...),
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Yüklenen bir modeli aktif hale getirir veya devre dışı bırakır.
    """
    # Eğer path boşsa, aktif modeli devre dışı bırak
    if not path:
        set_active_model_path("")
        # Tüm kamera thread'lerini durdur
        for cam_id, info in list(camera_threads.items()):
            print(f"[model] Kamerayı devre dışı bırak: {cam_id}")
            info['stop_event'].set()
            info['thread'].join(timeout=2.0)
            del camera_threads[cam_id]
        return {"status": "active", "model_path": None}

    if not Path(path).exists():
        raise HTTPException(status_code=404, detail="Model dosyası bulunamadı.")
    set_active_model_path(path)
    # Tüm çalışan kamera thread'lerini yeni model ile yeniden başlat
    for cam_id, info in list(camera_threads.items()):
        print(f"[model] Kamerayı yeni model ile yeniden başlat: {cam_id}")
        info['stop_event'].set()
        info['thread'].join(timeout=2.0)
        del camera_threads[cam_id]
        # Kamerayı yeni model ile başlat
        # Kamera bilgisi DB'den alınır
        async with AsyncSessionLocal() as session:
            cam = await session.get(models.Camera, cam_id)
            if cam and cam.status == "online":
                start_camera_thread(cam.id, cam.rtsp_url)
    
    async with AsyncSessionLocal() as session:
        # Tüm modelleri pasif yap
        await session.execute(update(models.ModelMeta).values(is_active=False))
        # Eğer path boş değilse, ilgili modeli aktif yap
        if path:
            await session.execute(update(models.ModelMeta).where(models.ModelMeta.path == path).values(is_active=True))
        await session.commit()
    return {"status": "active", "model_path": path}

@app.get("/api/model/active")
async def get_active_model(current_user: TokenData = Depends(get_current_user)):
    """
    Aktif model yolunu döndürür.
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
        raise HTTPException(status_code=500, detail=f"Model listesi alınamadı: {str(e)}")

# ===== Company Model Management Endpoints =====

@app.get("/api/company/{company_code}/models")
async def get_company_models(
    company_code: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Belirli bir company için atanan modelleri döndürür.
    Admin tüm şirketlere, regular users kendi şirketlerine erişebilir.
    """
    # Company access kontrolü
    await verify_company_access(current_user, company_code)
    
    try:
        # Company'yi bul
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Şirket bulunamadı")
        
        # Company'nin modellerini getir (ModelMeta ilişkisinin eager-load edilmesi önemli)
        result = await db.execute(
            select(models.CompanyModel)
            .options(joinedload(models.CompanyModel.model))
            .where(models.CompanyModel.company_id == company.id)
            .order_by(models.CompanyModel.id.desc())
        )
        company_models = result.scalars().unique().all()
        
        # Response oluştur
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
        raise HTTPException(status_code=500, detail=f"Model listesi alınamadı: {str(e)}")


@app.post("/api/company/{company_code}/models/{model_id}/assign")
async def assign_model_to_company(
    company_code: str,
    model_id: int,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bir modeli bir şirkete atar. (Admin only)
    """
    try:
        # Company ve Model'i bul
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Şirket bulunamadı")
        
        model_result = await db.execute(
            select(models.ModelMeta).where(models.ModelMeta.id == model_id)
        )
        model = model_result.scalars().first()
        if not model:
            raise HTTPException(status_code=404, detail="Model bulunamadı")
        
        # Zaten atanmış mı kontrol et
        existing = await db.execute(
            select(models.CompanyModel)
            .where(
                (models.CompanyModel.company_id == company.id) &
                (models.CompanyModel.model_id == model_id)
            )
        )
        if existing.scalars().first():
            raise HTTPException(status_code=409, detail="Model zaten bu şirkete atanmış")
        
        # Yeni atama oluştur
        company_model = models.CompanyModel(
            company_id=company.id,
            model_id=model_id,
            is_active=False
        )
        db.add(company_model)
        await db.commit()
        
        return {
            "status": "success",
            "message": f"Model {model.version} şirkete {company.name} atandı"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model atama hatası: {str(e)}")


@app.post("/api/company/{company_code}/models/{company_model_id}/activate")
async def activate_model_for_company(
    company_code: str,
    company_model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Belirli bir company için modeli aktifleştir.
    Aynı anda sadece bir model aktif olabilir.
    """
    # Company access kontrolü
    await verify_company_access(current_user, company_code)
    
    try:
        # Company'yi bul
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Şirket bulunamadı")
        
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
            raise HTTPException(status_code=404, detail="Model ataması bulunamadı")
        
        # Aynı şirketteki diğer aktif modelleri pasif yap
        await db.execute(
            update(models.CompanyModel)
            .where(
                (models.CompanyModel.company_id == company.id) &
                (models.CompanyModel.is_active == True)
            )
            .values(is_active=False)
        )
        
        # Bu modeli aktif yap
        company_model.is_active = True
        await db.commit()
        
        return {
            "status": "success",
            "message": f"Model {company_model.model.version} şirkete {company.name} aktifleştirildi"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model aktivasyon hatası: {str(e)}")


@app.post("/api/company/{company_code}/models/{company_model_id}/deactivate")
async def deactivate_model_for_company(
    company_code: str,
    company_model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Belirli bir company için modeli deaktifleştir.
    """
    # Company access kontrolü
    await verify_company_access(current_user, company_code)
    
    try:
        # Company'yi bul
        company_result = await db.execute(
            select(models.Company).where(models.Company.code == company_code)
        )
        company = company_result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Şirket bulunamadı")
        
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
            raise HTTPException(status_code=404, detail="Model ataması bulunamadı")
        
        # Modeli deaktif yap
        company_model.is_active = False
        await db.commit()
        
        set_active_model_path("")
        
        return {
            "status": "success",
            "message": f"Model {company_model.model.version} deaktifleştirildi"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model deaktivasyonu hatası: {str(e)}")


# ===== Camera-Model Management Endpoints (per camera model assignment) =====

@app.get("/api/camera/{camera_id}/models")
async def get_camera_models(
    camera_id: int,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Belirli bir kamera için atanmış modelleri döndürür. (Admin only)
    """
    from sqlalchemy import and_

    # Kamera var mı kontrol et
    cam = await db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    # CameraModel ilişkisi için ModelMeta'yı eager-load et (async lazy load hatasını önlemek için)
    result = await db.execute(
        select(models.CameraModel)
        .options(joinedload(models.CameraModel.model))
        .where(models.CameraModel.camera_id == camera_id)
    )
    camera_models = result.scalars().unique().all()

    response = []
    for cm in camera_models:
        m = cm.model
        response.append(
            {
                "id": cm.id,
                "camera_id": cm.camera_id,
                "model_id": cm.model_id,
                "is_active": cm.is_active,
                "enabled_at": cm.enabled_at.isoformat() if cm.enabled_at else "",
                "model": modelmeta_to_dict(m),
            }
        )

    return response


@app.post("/api/camera/{camera_id}/models/{model_id}/assign")
async def assign_model_to_camera(
    camera_id: int,
    model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Bir modeli belirli bir kameraya atar.
    Admin ve ilgili şirketin kullanıcıları kullanabilir.
    """
    # Kamera ve model var mı kontrol et
    cam = await db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    model = await db.get(models.ModelMeta, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Yetki kontrolü: admin her kamerayı yönetebilir, kullanıcı sadece kendi şirketindeki kameraları
    if current_user.role != "admin":
        company_result = await db.execute(
            select(models.Company).where(
                func.upper(models.Company.code) == func.upper(current_user.company_code)
            )
        )
        company = company_result.scalar_one_or_none()
        if not company or cam.company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this camera",
            )

    # Zaten atanmış mı kontrol et
    existing = await db.execute(
        select(models.CameraModel).where(
            (models.CameraModel.camera_id == camera_id)
            & (models.CameraModel.model_id == model_id)
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Model already assigned to this camera")

    camera_model = models.CameraModel(
        camera_id=camera_id,
        model_id=model_id,
        is_active=False,
    )
    db.add(camera_model)
    await db.commit()

    return {
        "status": "success",
        "message": f"Model {model.version} kameraya {cam.name} atandı",
    }


@app.post("/api/camera/{camera_id}/models/{camera_model_id}/activate")
async def activate_model_for_camera(
    camera_id: int,
    camera_model_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Bir kameradaki modellerden birini aktif yapar.
    Admin ve ilgili şirketin kullanıcıları kullanabilir.
    Aynı kamerada aynı anda sadece bir model aktif olabilir.
    """
    from sqlalchemy import and_

    cam = await db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Yetki kontrolü: admin her kamerayı yönetebilir, kullanıcı sadece kendi şirketindeki kameraları
    if current_user.role != "admin":
        company_result = await db.execute(
            select(models.Company).where(
                func.upper(models.Company.code) == func.upper(current_user.company_code)
            )
        )
        company = company_result.scalar_one_or_none()
        if not company or cam.company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this camera",
            )

    result = await db.execute(
        select(models.CameraModel).where(
            and_(
                models.CameraModel.id == camera_model_id,
                models.CameraModel.camera_id == camera_id,
            )
        )
    )
    camera_model = result.scalars().first()
    if not camera_model:
        raise HTTPException(status_code=404, detail="Camera model assignment not found")

    # Diğer aktif modelleri pasif yap
    await db.execute(
        update(models.CameraModel)
        .where(
            and_(
                models.CameraModel.camera_id == camera_id,
                models.CameraModel.is_active == True,  # noqa: E712
            )
        )
        .values(is_active=False)
    )

    # Bu modeli aktif yap
    camera_model.is_active = True
    await db.commit()

    # === Dinamik model değiştirme: mevcut kamera thread'ini durdur ve yeni model ile başlat ===
    # Çalışan kamera thread'i varsa durdur
    info = camera_threads.get(camera_id)
    if info:
        print(f"[activate_model_for_camera] Stopping running camera thread for camera {camera_id}")
        info["stop_event"].set()
        info["thread"].join(timeout=2.0)
        del camera_threads[camera_id]

    # Kamera online ise yeni model ile tekrar başlat
    model_meta = camera_model.model
    model_path = model_meta.path
    task_type = getattr(model_meta, "task_type", "ppe") or "ppe"

    if (cam.status or "").lower() != "offline":
        print(
            f"[activate_model_for_camera] Restarting camera {camera_id} with model "
            f"{model_meta.id} ({model_meta.version}) path='{model_path}' task='{task_type}'"
        )
        start_camera_thread(
            cam.id,
            cam.rtsp_url,
            model_path=model_path,
            model_task=task_type,
            use_default_model=False,
        )
    else:
        print(
            f"[activate_model_for_camera] Camera {camera_id} is offline, "
            "skipping automatic restart after model activation"
        )

    return {
        "status": "success",
        "message": f"Model {camera_model.model.version} kamera {cam.name} için aktifleştirildi",
    }

@app.on_event("startup")
async def startup_event():
    global main_loop, violation_queue, consumer_task
    
    # Tüm tabloları oluştur (özellikle models tablosu için)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print("This may be expected if running without database connection initially")
    
    # AsyncIO loop'u global'e kaydet
    main_loop = asyncio.get_event_loop()
    
    # Violation queue'yu oluştur
    violation_queue = asyncio.Queue()
    
    # Consumer task'ı başlat
    consumer_task = asyncio.create_task(violation_consumer_task(violation_queue))
    

    # 📌 Model'i arka planda ön-yükle (bloke etmez)
    model_path = get_active_model_path()
    if model_path and Path(model_path).exists():
        print(f"[startup] 🚀 Modeli arka planda ön-yüklüyoruz: {model_path}")
        preload_model_async(model_path)
        print(f"[startup] ✅ Model ön-yükleme başlatıldı (kamera donmayacak)")
    
    # 📌 Tüm kameraları otomatik başlat 
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(models.Camera))
            cameras = result.scalars().all()
            if cameras:
                print(f"[startup] 📹 {len(cameras)} kamera bulundu, başlatılıyor...")
                for cam in cameras:
                    # Skip cameras that are marked as offline
                    if (cam.status or "").lower() == "offline":
                        print(f"[startup] ⏭️ Skipping camera {cam.id} (name: {cam.name}) because status='{cam.status}'")
                        continue
                    print(f"[startup] Starting camera: {cam.id} (name: {cam.name}, rtsp: {cam.rtsp_url})")
                    # Kamera için aktif model (varsa) ile başlat
                    model_meta = await get_active_model_for_camera(session, cam.company_id, cam.id)
                    if model_meta:
                        start_camera_thread(
                            cam.id,
                            cam.rtsp_url,
                            model_path=model_meta.path,
                            model_task=(getattr(model_meta, "task_type", "ppe") or "ppe"),
                            use_default_model=False,
                        )
                    else:
                        # Varsayılan global model ile başlat
                        start_camera_thread(cam.id, cam.rtsp_url)
            else:
                print(f"[startup] ⚠️ Hiç kamera bulunamadı")
    except Exception as e:
        print(f"[startup] ❌ Kamera başlatma hatası: {e}")
        import traceback
        traceback.print_exc()

# Detect endpoint'i ekleyin
@app.post("/api/detect")
async def detect(
    file: UploadFile = File(...),
    model_path: str = Form(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Yüklenen resmi aktif model ile analiz et
    """
    try:
        if not model_path or model_path == '':
            return {
                "status": "error",
                "message": "Model yolu geçersiz. Lütfen bir model aktif edin."
            }
        
        model_full_path = model_path
        if not Path(model_full_path).exists():
            return {
                "status": "error",
                "message": f"Model dosyası bulunamadı: {model_full_path}"
            }
        
        # Resim dosyasını oku
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {
                "status": "error",
                "message": "Resim dosyası okunamadı. Lütfen geçerli bir resim seçin."
            }
        
        # YOLO modelini (cache'li) yükle ve çalıştır
        model = get_model(model_full_path)
        results = model(img)
        
        # Sonuçları işle
        detections = []
        for r in results:
            for box in r.boxes:
                detections.append({
                    "class": model.names[int(box.cls)],
                    "confidence": float(box.conf),
                    "bbox": box.xyxy[0].tolist()
                })
        
        # Annotated image'ı oluştur
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
            "message": f"Detection hatası: {str(e)}"
        }


def camera_to_dict(cam: models.Camera, active_models=None, model_is_active: bool | None = None):
    """
    Kamera nesnesini frontend için serileştirir.
    active_models: bu kamera için aktif modellerin listesi (dict listesi beklenir).
    """
    return {
        "id": cam.id,
        "name": cam.name,
        "location": cam.location,
        "rtsp_url": cam.rtsp_url,
        "status": cam.status or "offline",
        "company_id": cam.company_id,
        "last_active": cam.last_active.isoformat() if cam.last_active else None,
        "active_models": active_models or [],
    }


async def get_camera_active_models(db: AsyncSession, company_id: int, camera_id: int):
    """
    Belirli bir kamera için aktif modelleri döndürür.
    Önce camera_models tablosunu, sonra fallback olarak company_models tablosunu kontrol eder.
    """
    from sqlalchemy import and_

    # Kamera için aktif atanmış modeller
    result = await db.execute(
        select(models.CameraModel)
        .join(models.ModelMeta)
        .where(
            and_(
                models.CameraModel.camera_id == camera_id,
                models.CameraModel.is_active == True,  # noqa: E712
            )
        )
    )
    camera_models = result.scalars().all()

    active_models = []
    for cm in camera_models:
        m = cm.model
        task_type = getattr(m, "task_type", "ppe") or "ppe"
        active_models.append(
            {
                "id": cm.id,
                "model_id": cm.model_id,
                "version": m.version,
                "path": m.path,
                "task_type": task_type,
                "name": task_type.upper(),
            }
        )

    if active_models:
        return active_models

    # Fallback: şirket için aktif model(ler)
    result = await db.execute(
        select(models.CompanyModel)
        .join(models.ModelMeta)
        .where(
            and_(
                models.CompanyModel.company_id == company_id,
                models.CompanyModel.is_active == True,  # noqa: E712
            )
        )
    )
    company_models = result.scalars().all()

    for cm in company_models:
        m = cm.model
        task_type = getattr(m, "task_type", "ppe") or "ppe"
        active_models.append(
            {
                "id": cm.id,
                "model_id": cm.model_id,
                "version": m.version,
                "path": m.path,
                "task_type": task_type,
                "name": task_type.upper(),
            }
        )

    return active_models


async def get_active_model_for_camera(session: AsyncSession, company_id: int, camera_id: int) -> Optional[models.ModelMeta]:
    """
    Belirli bir kamera için aktif modeli döndürür.
    Önce camera_models, sonra company_models tablosunu kontrol eder.
    """
    from sqlalchemy import and_

    # Kamera için aktif atanmış model
    result = await session.execute(
        select(models.CameraModel)
        .join(models.ModelMeta)
        .where(
            and_(
                models.CameraModel.camera_id == camera_id,
                models.CameraModel.is_active == True,  # noqa: E712
            )
        )
    )
    camera_model = result.scalars().first()
    if camera_model:
        return camera_model.model

    # Fallback: şirket için aktif model
    result = await session.execute(
        select(models.CompanyModel)
        .join(models.ModelMeta)
        .where(
            and_(
                models.CompanyModel.company_id == company_id,
                models.CompanyModel.is_active == True,  # noqa: E712
            )
        )
    )
    company_model = result.scalars().first()
    if company_model:
        return company_model.model

    return None


async def get_active_model_path_for_camera(session: AsyncSession, company_id: int, camera_id: int) -> Optional[str]:
    """
    Eski kullanım için path döndüren yardımcı fonksiyon (compat).
    """
    model = await get_active_model_for_camera(session, company_id, camera_id)
    return model.path if model else None

