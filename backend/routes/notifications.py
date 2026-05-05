"""Company notification settings endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List

from auth import TokenData
from database import get_db
from dependencies import get_current_user
import models

router = APIRouter()


class NotificationSettingsSchema(BaseModel):
    email_enabled: bool = False
    report_period: str = "weekly"        # daily / weekly / monthly
    report_formats: List[str] = ["pdf"]  # ["pdf", "excel", "csv"]
    push_enabled: bool = True
    alert_critical: bool = True
    alert_camera_offline: bool = True
    alert_model_updates: bool = False

    class Config:
        from_attributes = True


async def _get_company(company_code: str, db: AsyncSession) -> models.Company:
    result = await db.execute(
        select(models.Company).where(models.Company.code == company_code)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


async def _get_or_create_settings(
    company_id: int, db: AsyncSession
) -> models.CompanyNotificationSettings:
    result = await db.execute(
        select(models.CompanyNotificationSettings).where(
            models.CompanyNotificationSettings.company_id == company_id
        )
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = models.CompanyNotificationSettings(company_id=company_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.get("/api/company/{company_code}/notification-settings", response_model=NotificationSettingsSchema)
async def get_notification_settings(
    company_code: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(company_code, db)
    return await _get_or_create_settings(company.id, db)


@router.put("/api/company/{company_code}/notification-settings", response_model=NotificationSettingsSchema)
async def update_notification_settings(
    company_code: str,
    payload: NotificationSettingsSchema,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.report_period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="Invalid report_period")
    valid_formats = {"pdf", "excel", "csv"}
    if not all(f in valid_formats for f in payload.report_formats):
        raise HTTPException(status_code=400, detail="Invalid report format")

    company = await _get_company(company_code, db)
    settings = await _get_or_create_settings(company.id, db)

    settings.email_enabled = payload.email_enabled
    settings.report_period = payload.report_period
    settings.report_formats = payload.report_formats
    settings.push_enabled = payload.push_enabled
    settings.alert_critical = payload.alert_critical
    settings.alert_camera_offline = payload.alert_camera_offline
    settings.alert_model_updates = payload.alert_model_updates

    await db.commit()
    await db.refresh(settings)
    return settings


