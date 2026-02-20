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
    
    # Check if user is admin (has admin company code)
    if is_admin(current_user.company_code):
        # Admins can access any company
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

def start_camera_thread(camera_id: int, rtsp_url: str):
    """Start a blocking camera loop in a separate thread."""
    # 📌 Model yolunu al (arka planda yükleniyor olabilir)
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
    
    print(f"[start_camera_thread] Creating thread for camera {camera_id} with rtsp_url='{rtsp_url}' and model_path='{model_path}'")
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_camera_thread,
        args=(camera_id, rtsp_url, model_path, main_loop, violation_queue, stop_event),
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
                
                vio = models.Violation(
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
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all companies from database.
    Only accessible by admin users (those with admin company codes).
    """
    # Check if user is admin
    if not is_admin(current_user.company_code):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access company list"
        )
    
    # Get all companies
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
    
    if not company and not is_admin(verified_company_code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # If admin using admin code, get all cameras
    if is_admin(verified_company_code):
        result = await db.execute(select(models.Camera))
    else:
        # Regular user: get cameras for their company
        result = await db.execute(
            select(models.Camera).where(models.Camera.company_id == company.id)
        )
    
    return result.scalars().all()


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
    
    if not company and not is_admin(verified_company_code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # If admin using admin code, get all detections
    if is_admin(verified_company_code):
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
    
    if not company and not is_admin(verified_company_code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # If admin using admin code, get all violations
    if is_admin(verified_company_code):
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
        
        # Verify company access to this camera
        if not is_admin(current_user.company_code):
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
    
    if not is_admin(current_user.company_code):
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
async def stream_camera(camera_id: int, current_user: TokenData = Depends(get_current_user)):
    """
    MJPEG stream endpoint for live camera feed with detections.
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
    Yeni bir model dosyasını yükler ve kaydeder. (Admin only)
    """
    allowed_ext = ('.pt', '.weights', '.onnx')
    if not any(file.filename.endswith(ext) for ext in allowed_ext):
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya uzantısı.")

    try:
        models_dir = Path(__file__).parent.parent / "model" / "weights"
        models_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{version}_{uuid.uuid4().hex}_{file.filename}"
        file_path = models_dir / filename

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
            # Aynı path varsa ekleme!
            existing = await session.execute(select(models.ModelMeta).where(models.ModelMeta.path == str(file_path)))
            if existing.scalars().first():
                raise HTTPException(status_code=409, detail="Bu path ile model zaten var.")
            model_meta = models.ModelMeta(
                path=str(file_path),
                version=version,
                description=description,
                is_active=False
            )
            session.add(model_meta)
            await session.commit()
        return {"status": "success", "path": str(file_path), "version": version, "description": description}
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
                    print(f"[startup] Starting camera: {cam.id} (name: {cam.name}, rtsp: {cam.rtsp_url})")
                    # Non-blocking kamera başlatma (thread'de çalışacak)
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
        
        # Modeli yükle
        from ultralytics import YOLO
        
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
        
        # YOLO modelini yükle ve çalıştır
        model = YOLO(model_full_path)
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

