"""Camera CRUD and streaming endpoints."""
import asyncio
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security.http import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenData, decode_access_token
from camera_runner import get_latest_frame
from config import is_admin_company_code
from database import AsyncSessionLocal, get_db
from dependencies import get_admin_user, get_current_user, optional_security, verify_company_access
import globals as g
import models
from services.camera_service import (
    camera_to_dict,
    ensure_company_cameras_started,
    is_local_camera_source,
    start_camera_thread,
    stop_camera_thread,
)
from services.model_service import get_active_model_paths_for_camera, get_camera_active_models

router = APIRouter()


class CameraCreateRequest(BaseModel):
    name: str
    location: Optional[str] = None
    rtsp_url: str = "0"
    company_code: Optional[str] = None


@router.post("/api/cameras")
async def create_camera(
    camera_create: CameraCreateRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_company_code = camera_create.company_code

    if current_user.role != "admin":
        if target_company_code and target_company_code.upper() != current_user.company_code.upper():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to create camera for this company",
            )
        target_company_code = current_user.company_code
    else:
        if not target_company_code or is_admin_company_code(target_company_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin must provide a valid non-admin company_code",
            )

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(target_company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    camera_name = (camera_create.name or "").strip()
    if not camera_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Camera name is required")

    source = (camera_create.rtsp_url or "").strip()
    if not source:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rtsp_url is required")

    if is_local_camera_source(source):
        existing_result = await db.execute(
            select(models.Camera).where(models.Camera.rtsp_url == source)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Local camera source '{source}' is already assigned to camera "
                    f"'{existing.name}' (id={existing.id}). "
                    "Use a different RTSP source or delete the existing local camera first."
                ),
            )

    new_camera = models.Camera(
        name=camera_name,
        location=(camera_create.location or "").strip() or "-",
        rtsp_url=source,
        status="online",
        company_id=company.id,
    )
    db.add(new_camera)
    await db.commit()
    await db.refresh(new_camera)

    model_paths = await get_active_model_paths_for_camera(db, company.id, new_camera.id)
    start_camera_thread(new_camera.id, new_camera.rtsp_url, model_paths=model_paths, use_default_model=not model_paths)

    active_models = await get_camera_active_models(db, company.id, new_camera.id)
    return camera_to_dict(new_camera, active_models=active_models)


@router.get("/api/cameras")
async def get_cameras(
    current_user: TokenData = Depends(get_current_user),
    company_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    verified_code = await verify_company_access(current_user, company_code)

    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(verified_code))
    )
    company = company_result.scalar_one_or_none()

    if not company and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if current_user.role == "admin" and company is None:
        result = await db.execute(select(models.Camera))
        return [camera_to_dict(cam, model_is_active=False, active_models=[]) for cam in result.scalars().all()]

    result = await db.execute(select(models.Camera).where(models.Camera.company_id == company.id))
    cameras = result.scalars().all()
    response = []
    for cam in cameras:
        active_models = await get_camera_active_models(db, company.id, cam.id)
        response.append(camera_to_dict(cam, active_models=active_models))
    return response


@router.delete("/api/cameras/{camera_id}")
async def delete_camera(
    camera_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    if current_user.role != "admin":
        company_result = await db.execute(
            select(models.Company).where(
                func.upper(models.Company.code) == func.upper(current_user.company_code)
            )
        )
        company = company_result.scalar_one_or_none()
        if not company or cam.company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this camera"
            )

    await db.execute(delete(models.CompanyModelCamera).where(models.CompanyModelCamera.camera_id == camera_id))
    await db.execute(delete(models.Detection).where(models.Detection.camera_id == camera_id))
    await db.execute(delete(models.Camera).where(models.Camera.id == camera_id))
    await db.commit()

    if camera_id in g.camera_threads:
        stop_camera_thread(camera_id)

    await ensure_company_cameras_started(db, cam.company_id, trigger=f"delete:{camera_id}")
    return {"status": "success", "camera_id": camera_id, "message": "Camera deleted"}


@router.post("/api/camera/{camera_id}/start-local")
async def api_start_local_camera(
    camera_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async with AsyncSessionLocal() as session:
        cam = await session.get(models.Camera, camera_id)
        if not cam:
            return {"error": "camera not found"}

        if current_user.role != "admin":
            company_result = await session.execute(
                select(models.Company).where(
                    func.upper(models.Company.code) == func.upper(current_user.company_code)
                )
            )
            company = company_result.scalar_one_or_none()
            if not company or cam.company_id != company.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this camera"
                )

        model_paths = await get_active_model_paths_for_camera(session, cam.company_id, cam.id)
        start_camera_thread(cam.id, "0", model_paths=model_paths, use_default_model=not model_paths)
    return {"status": "started with local camera", "camera_id": camera_id}


@router.post("/api/camera/{camera_id}/stop")
async def api_stop_camera(
    camera_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    if current_user.role != "admin":
        company_result = await db.execute(
            select(models.Company).where(
                func.upper(models.Company.code) == func.upper(current_user.company_code)
            )
        )
        company = company_result.scalar_one_or_none()
        if not company or cam.company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this camera"
            )

    if camera_id not in g.camera_threads:
        return {"status": "not running"}
    stop_camera_thread(camera_id)
    return {"status": "stopped", "camera_id": camera_id}


@router.get("/api/camera/{camera_id}/frame-status")
async def get_frame_status(
    camera_id: int,
    current_user: TokenData = Depends(get_current_user),
):
    frame_bytes = get_latest_frame(camera_id)
    has_frame = frame_bytes is not None
    is_running = camera_id in g.camera_threads
    return {
        "camera_id": camera_id,
        "has_frame": has_frame,
        "frame_size": len(frame_bytes) if has_frame else 0,
        "thread_running": is_running,
        "thread_info": {
            "thread_alive": g.camera_threads[camera_id]['thread'].is_alive()
        } if is_running else None,
    }


@router.get("/api/debug/camera-status")
async def debug_camera_status(admin_user: TokenData = Depends(get_admin_user)):
    result = {
        "camera_threads": {},
        "frame_storage": {},
        "total_threads": len(g.camera_threads),
    }
    for cam_id, info in g.camera_threads.items():
        result["camera_threads"][cam_id] = {
            "thread_alive": info['thread'].is_alive(),
            "stop_event_set": info['stop_event'].is_set(),
        }
        frame_bytes = get_latest_frame(cam_id)
        result["frame_storage"][cam_id] = {
            "has_frame": frame_bytes is not None,
            "frame_size": len(frame_bytes) if frame_bytes else 0,
        }
    return result


@router.get("/api/camera/{camera_id}/stream")
async def stream_camera(
    camera_id: int,
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
):
    """MJPEG stream endpoint for live camera feed."""
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
                status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this camera"
            )

    placeholder_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(placeholder_frame, "No frame available", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    _, buffer = cv2.imencode('.jpg', placeholder_frame)
    placeholder_bytes = buffer.tobytes()

    async def generate_frames():
        consecutive_empty = 0
        while True:
            frame_bytes = get_latest_frame(camera_id)
            if frame_bytes:
                consecutive_empty = 0
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
            else:
                consecutive_empty += 1
                if consecutive_empty > 10:
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + placeholder_bytes + b'\r\n'
            await asyncio.sleep(0.033)  # ~30 FPS

    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
