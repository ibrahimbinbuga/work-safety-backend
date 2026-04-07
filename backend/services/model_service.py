"""Model path management, DB helpers, and serializers."""
import os
import traceback
from pathlib import Path
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine
import models
from camera_runner import preload_model_async

# Resolve default model path (can be overridden via MODEL_PATH env var)
_backend_dir = Path(__file__).parent.parent
MODEL_PATH = os.getenv("MODEL_PATH") or str(_backend_dir.parent / "model" / "weights" / "best.pt")

ACTIVE_MODEL_PATH: Optional[str] = MODEL_PATH

# Priority → violation kayıt aralığı (saniye)
PRIORITY_INTERVALS: dict = {
    "critical": 30.0,
    "high": 120.0,
    "medium": 600.0,
    "low": 1800.0,
}


def set_active_model_path(path: str):
    global ACTIVE_MODEL_PATH
    if not path:
        ACTIVE_MODEL_PATH = None
        print("[model] Active model disabled.")
    else:
        ACTIVE_MODEL_PATH = path
        print(f"[model] Active model path updated: {ACTIVE_MODEL_PATH}")
        if Path(path).exists():
            print(f"[model] Preloading model in background: {path}")
            preload_model_async(path)
        else:
            print(f"[model] Model file not found: {path}")


def get_active_model_path() -> Optional[str]:
    return ACTIVE_MODEL_PATH



async def get_camera_active_models(db: AsyncSession, company_id: int, camera_id: int) -> list[dict]:
    """Return active model metadata for a given company/camera pair."""
    result = await db.execute(
        select(models.ModelMeta)
        .join(models.CompanyModelCamera, models.CompanyModelCamera.model_id == models.ModelMeta.id)
        .where(
            (models.CompanyModelCamera.company_id == company_id)
            & (models.CompanyModelCamera.camera_id == camera_id)
            & (models.CompanyModelCamera.is_active == True)
        )
        .order_by(models.ModelMeta.uploaded_at.desc())
    )
    return [
        {
            "id": m.id,
            "name": m.version,
            "version": m.version,
            "path": m.path,
            "description": m.description,
        }
        for m in result.scalars().all()
    ]

"""
def camera_to_dict(cam: models.Camera, active_models: Optional[list[dict]] = None, model_is_active: Optional[bool] = None) -> dict:
    """"Serialize camera row with model assignment info for frontend usage.""""
    active_models = active_models or []
    if model_is_active is None:
        model_is_active = len(active_models) > 0

    thread_info = camera_threads.get(cam.id)
    has_running_thread = bool(thread_info and thread_info['thread'].is_alive())
    has_recent_frame = get_latest_frame(cam.id) is not None
    # Runtime status (API): not the DB column — reflects live thread + frames
    if has_running_thread and has_recent_frame:
        runtime_status = "online"
    elif has_running_thread:
        runtime_status = "connecting"  # thread up, waiting for first frame (e.g. HTTP/MJPEG)
    else:
        runtime_status = "offline"

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
"""
async def get_active_model_paths_for_camera(
    db: AsyncSession, company_id: int, camera_id: int
) -> list[str]:
    active_models = await get_camera_active_models(db, company_id, camera_id)
    return [m["path"] for m in active_models if m.get("path")]


async def get_violation_check_interval_for_camera(
    db: AsyncSession, company_id: int, camera_id: int
) -> float:
    """Kameranın aktif model atamalarındaki en yüksek önceliğe göre violation kayıt aralığını döndürür."""
    result = await db.execute(
        select(models.CompanyModelCamera.priority)
        .where(
            (models.CompanyModelCamera.company_id == company_id)
            & (models.CompanyModelCamera.camera_id == camera_id)
            & (models.CompanyModelCamera.is_active == True)
        )
    )
    priorities = [str(p) for p in result.scalars().all() if p]
    if not priorities:
        return PRIORITY_INTERVALS["medium"]
    return min(PRIORITY_INTERVALS.get(p, PRIORITY_INTERVALS["medium"]) for p in priorities)


async def get_active_model_path_for_camera(
    db: AsyncSession, company_id: int, camera_id: int
) -> Optional[str]:
    paths = await get_active_model_paths_for_camera(db, company_id, camera_id)
    return paths[0] if paths else None


def modelmeta_to_dict(model: models.ModelMeta) -> dict:
    return {
        "id": model.id,
        "path": model.path,
        "version": model.version,
        "description": model.description,
        "uploaded_at": model.uploaded_at.isoformat() if model.uploaded_at else "",
        "is_active": model.is_active,
    }


def general_model_to_dict(model: models.ModelMeta) -> dict:
    return {
        "id": model.id,
        "name": model.version,
        "version": model.version,
        "description": model.description,
        "path": model.path,
        "uploaded_at": model.uploaded_at.isoformat() if model.uploaded_at else "",
        "is_active": model.is_active,
    }


async def sync_company_model_activation_summary(db: AsyncSession, company_id: int):
    """Mirror camera-level active flags to the company-level CompanyModel.is_active."""
    active_model_ids_result = await db.execute(
        select(models.CompanyModelCamera.model_id)
        .where(
            (models.CompanyModelCamera.company_id == company_id)
            & (models.CompanyModelCamera.is_active == True)
        )
        .distinct()
    )
    active_model_ids = set(active_model_ids_result.scalars().all())

    company_models_result = await db.execute(
        select(models.CompanyModel).where(models.CompanyModel.company_id == company_id)
    )
    for cm in company_models_result.scalars().all():
        cm.is_active = cm.model_id in active_model_ids


async def ensure_company_model_cameras_schema():
    """Patch legacy DBs where company_model_cameras is missing newer columns."""
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS model_id INTEGER"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS enabled_at TIMESTAMPTZ DEFAULT NOW()"
        ))

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

        await conn.execute(text(
            """
            DO $$
            DECLARE c RECORD;
            BEGIN
                FOR c IN
                    SELECT conname FROM pg_constraint
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

        await conn.execute(text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_company_model_cameras_company_camera_model
            ON company_model_cameras (company_id, camera_id, model_id)
            """
        ))

        await conn.execute(text(
            """
            UPDATE company_model_cameras cmc
            SET model_id = sub.model_id
            FROM (
                SELECT company_id, MIN(model_id) AS model_id
                FROM company_models
                GROUP BY company_id
            ) AS sub
            WHERE cmc.model_id IS NULL AND cmc.company_id = sub.company_id
            """
        ))

        await conn.execute(text(
            "UPDATE company_model_cameras SET is_active = FALSE WHERE is_active IS NULL"
        ))

        await conn.execute(text(
            "ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS priority VARCHAR DEFAULT 'medium'"
        ))
        await conn.execute(text(
            "UPDATE company_model_cameras SET priority = 'medium' WHERE priority IS NULL"
        ))
