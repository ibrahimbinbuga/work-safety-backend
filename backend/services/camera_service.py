"""Camera thread lifecycle management and serialization helpers."""
import threading
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import globals as g
import models
from camera_runner import run_camera_thread, get_latest_frame
from services.model_service import get_active_model_paths_for_camera, get_camera_active_models


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------

def is_local_camera_source(source: Optional[str]) -> bool:
    if source is None:
        return False
    if isinstance(source, int):
        return True
    return str(source).strip().isdigit()


def normalize_camera_source(source: Optional[str]) -> str:
    if source is None:
        return ""
    return str(source).strip()


def find_running_camera_with_source(
    source: Optional[str], exclude_camera_id: Optional[int] = None
) -> Optional[int]:
    normalized = normalize_camera_source(source)
    if not normalized:
        return None
    for cam_id, info in g.camera_threads.items():
        if exclude_camera_id is not None and cam_id == exclude_camera_id:
            continue
        thread = info.get('thread')
        if not thread or not thread.is_alive():
            continue
        if info.get('source') == normalized:
            return cam_id
    return None


# ---------------------------------------------------------------------------
# Thread lifecycle
# ---------------------------------------------------------------------------

def stop_camera_thread(camera_id: int):
    info = g.camera_threads.get(camera_id)
    if not info:
        return
    info['stop_event'].set()
    info['thread'].join(timeout=2.0)
    g.camera_threads.pop(camera_id, None)


def start_camera_thread(
    camera_id: int,
    rtsp_url: str,
    model_path: Optional[str] = None,
    use_default_model: bool = True,
    model_paths: Optional[list[str]] = None,
):
    """Spawn a background thread for a camera. No-op if already running."""
    resolved = [p for p in (model_paths or []) if p]
    if not resolved and model_path:
        resolved = [model_path]

    if not resolved:
        print(f"[start_camera_thread] No model assigned, starting raw feed: camera_id={camera_id}")
    else:
        for path in resolved:
            if not Path(path).exists():
                print(f"[start_camera_thread] Model file not found: {path}")

    if camera_id in g.camera_threads:
        print(f"[start_camera_thread] Camera {camera_id} already running")
        return

    if g.main_loop is None:
        print(f"[start_camera_thread] ERROR: main_loop is None, cannot start camera {camera_id}")
        return

    if g.violation_queue is None:
        print(f"[start_camera_thread] ERROR: violation_queue is None, cannot start camera {camera_id}")
        return

    normalized_source = normalize_camera_source(rtsp_url)
    if is_local_camera_source(normalized_source):
        conflict = find_running_camera_with_source(normalized_source, exclude_camera_id=camera_id)
        if conflict is not None:
            print(
                f"[start_camera_thread] Skipping camera {camera_id}: "
                f"local source '{normalized_source}' already used by camera {conflict}"
            )
            return

    print(
        f"[start_camera_thread] Creating thread for camera {camera_id} "
        f"rtsp_url='{rtsp_url}' model_paths='{resolved}'"
    )
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_camera_thread,
        args=(camera_id, rtsp_url, resolved, g.main_loop, g.violation_queue, stop_event),
        daemon=True,
    )
    g.camera_threads[camera_id] = {
        'thread': thread,
        'stop_event': stop_event,
        'source': normalized_source,
    }
    thread.start()
    print(f"[start_camera_thread] Started camera thread for {camera_id}")


async def stop_company_cameras(db: AsyncSession, company_id: int, trigger: str = "manual") -> int:
    result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company_id)
    )
    cameras = result.scalars().all()
    stopped = 0
    for cam in cameras:
        if cam.id in g.camera_threads:
            stop_camera_thread(cam.id)
            stopped += 1
    print(f"[camera-stop] trigger={trigger} company_id={company_id} total={len(cameras)} stopped={stopped}")
    return stopped


async def restart_camera_with_current_models(
    db: AsyncSession, camera: models.Camera, force_local: bool = False
):
    stop_camera_thread(camera.id)
    model_paths = await get_active_model_paths_for_camera(db, camera.company_id, camera.id)
    source = "0" if force_local else camera.rtsp_url
    start_camera_thread(camera.id, source, model_paths=model_paths, use_default_model=not model_paths)


async def restart_company_cameras(db: AsyncSession, company_id: int):
    result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company_id)
    )
    for camera in result.scalars().all():
        await restart_camera_with_current_models(db, camera)


async def ensure_company_cameras_started(
    db: AsyncSession, company_id: int, trigger: str = "manual"
) -> int:
    result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company_id)
    )
    cameras = result.scalars().all()
    started_count = 0
    for cam in cameras:
        existing = g.camera_threads.get(cam.id)
        if existing:
            if existing['thread'].is_alive():
                continue
            g.camera_threads.pop(cam.id, None)
        model_paths = await get_active_model_paths_for_camera(db, cam.company_id, cam.id)
        start_camera_thread(cam.id, cam.rtsp_url, model_paths=model_paths, use_default_model=not model_paths)
        started_count += 1
    
    if started_count > 0:
        print(
            f"[camera-start] trigger={trigger} company_id={company_id} "
            f"total={len(cameras)} started={started_count}"
    )
    return started_count


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def camera_to_dict(
    cam: models.Camera,
    active_models: Optional[list[dict]] = None,
    model_is_active: Optional[bool] = None,
) -> dict:
    active_models = active_models or []
    if model_is_active is None:
        model_is_active = len(active_models) > 0
    thread_info = g.camera_threads.get(cam.id)
    has_thread = bool(thread_info and thread_info['thread'].is_alive())
    has_frame = get_latest_frame(cam.id) is not None
    runtime_status = "online" if (has_thread and has_frame) else "offline"
    return {
        "id": cam.id,
        "name": cam.name,
        "location": cam.location,
        "rtsp_url": cam.rtsp_url,
        "status": runtime_status,
        "db_status": cam.status,
        "company_id": cam.company_id,
        "last_active": cam.last_active.isoformat() if cam.last_active else None,
        "model_is_active": model_is_active,
        "active_models": active_models,
    }
