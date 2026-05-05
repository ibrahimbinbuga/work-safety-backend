"""Detection and violation endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenData
from database import get_db
from dependencies import get_current_user, verify_company_access
import globals as g
import models

router = APIRouter()


@router.get("/api/detections")
async def get_detections(
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

    if current_user.role == "admin":
        result = await db.execute(select(models.Detection))
    else:
        result = await db.execute(
            select(models.Detection).where(models.Detection.company_id == company.id)
        )
    return result.scalars().all()


@router.get("/api/violations")
async def get_violations(
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

    if current_user.role == "admin":
        result = await db.execute(
            select(models.Violations).order_by(models.Violations.tarih_saat.desc())
        )
    else:
        result = await db.execute(
            select(models.Violations)
            .where(models.Violations.company_id == company.id)
            .order_by(models.Violations.tarih_saat.desc())
        )

    return [
        {
            "id": v.id,
            "violation_id": v.violation_id,
            "ihlal_cesidi": v.ihlal_cesidi,
            "ihlal_yapilan_bolge": v.ihlal_yapilan_bolge,
            "tarih_saat": v.tarih_saat,
            "review_status": v.review_status or "pending",
        }
        for v in result.scalars().all()
    ]


@router.patch("/api/violations/{violation_id}/status")
async def update_violation_status(
    violation_id: int,
    body: dict,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
        result = await db.execute(
            update(models.Violations)
            .where(
                models.Violations.id == violation_id,
                models.Violations.company_id == select(models.Company.id)
                .where(func.upper(models.Company.code) == func.upper(current_user.company_code))
                .scalar_subquery(),
            )
            .values(review_status=review_status)
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Violation not found or access denied")

    await db.commit()
    return {"id": violation_id, "review_status": review_status}


@router.post("/api/test/violation")
async def test_violation(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test endpoint: manually push a fake violation into the queue to verify notifications."""
    company_result = await db.execute(
        select(models.Company).where(
            func.upper(models.Company.code) == func.upper(current_user.company_code)
        )
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    cameras_result = await db.execute(
        select(models.Camera).where(models.Camera.company_id == company.id).limit(1)
    )
    camera = cameras_result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="No camera found for this company")

    if g.violation_queue is None:
        raise HTTPException(status_code=503, detail="Violation queue not ready")

    await g.violation_queue.put({
        "camera_id": camera.id,
        "violations": ["head"],
        "worker_id": 0,
        "snapshot_path": None,
    })

    return {"status": "ok", "message": f"Test violation queued for camera {camera.id}"}
