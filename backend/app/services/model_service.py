"""Model path management, DB helpers, and serializers."""
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.db import models
from app.workers.camera_runner import preload_model_async

_backend_dir = Path(__file__).parent.parent.parent
MODEL_PATH = os.getenv("MODEL_PATH") or str(_backend_dir.parent / "model" / "weights" / "best.pt")

ACTIVE_MODEL_PATH: Optional[str] = MODEL_PATH
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
    else:
        ACTIVE_MODEL_PATH = path
        if Path(path).exists():
            preload_model_async(path)


def get_active_model_path() -> Optional[str]:
    return ACTIVE_MODEL_PATH


async def get_camera_active_models(db: AsyncSession, company_id: int, camera_id: int) -> list[dict]:
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


async def get_active_model_paths_for_camera(
    db: AsyncSession, company_id: int, camera_id: int
) -> list[str]:
    active_models = await get_camera_active_models(db, company_id, camera_id)
    return [m["path"] for m in active_models if m.get("path")]


async def get_violation_check_interval_for_camera(
    db: AsyncSession, company_id: int, camera_id: int
) -> float:
    result = await db.execute(
        select(models.CompanyModelCamera.priority)
        .where(
            (models.CompanyModelCamera.company_id == company_id)
            & (models.CompanyModelCamera.camera_id == camera_id)
            & (models.CompanyModelCamera.is_active == True)
        )
    )
    priorities = [p.value for p in result.scalars().all() if p]
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
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS model_id INTEGER"))
        await conn.execute(text("ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS enabled_at TIMESTAMPTZ DEFAULT NOW()"))
        await conn.execute(text("UPDATE company_model_cameras SET is_active = FALSE WHERE is_active IS NULL"))
        await conn.execute(text("ALTER TABLE IF EXISTS company_model_cameras ADD COLUMN IF NOT EXISTS priority VARCHAR DEFAULT 'medium'"))
        await conn.execute(text("UPDATE company_model_cameras SET priority = 'medium' WHERE priority IS NULL"))
