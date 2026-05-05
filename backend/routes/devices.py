"""FCM device token registration / unregistration endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenData
from database import get_db
from dependencies import get_current_user
import models

router = APIRouter()


class TokenPayload(BaseModel):
    token: str
    device_label: str | None = None


@router.post("/api/devices/register", status_code=201)
async def register_device_token(
    payload: TokenPayload,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register or refresh an FCM device token for the authenticated user."""
    user_row = await db.get(models.User, current_user.user_id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (await db.execute(
        select(models.DeviceToken).where(models.DeviceToken.token == payload.token)
    )).scalar_one_or_none()

    if existing:
        existing.user_id = user_row.id
        existing.company_id = user_row.company_id
        existing.device_label = payload.device_label or existing.device_label
        await db.commit()
        return {"status": "updated"}

    db.add(models.DeviceToken(
        user_id=user_row.id,
        company_id=user_row.company_id,
        token=payload.token,
        device_label=payload.device_label,
    ))
    await db.commit()
    return {"status": "registered"}


@router.delete("/api/devices/unregister")
async def unregister_device_token(
    payload: TokenPayload,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unregister an FCM token on logout or opt-out."""
    row = (await db.execute(
        select(models.DeviceToken).where(
            models.DeviceToken.token == payload.token,
            models.DeviceToken.user_id == current_user.user_id,
        )
    )).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Token not found")

    await db.delete(row)
    await db.commit()
    return {"status": "unregistered"}


@router.get("/api/devices")
async def list_device_tokens(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List registered FCM tokens for the current user."""
    result = await db.execute(
        select(models.DeviceToken).where(
            models.DeviceToken.user_id == current_user.user_id
        )
    )
    tokens = result.scalars().all()
    return [
        {
            "id": t.id,
            "token_preview": t.token[:20] + "...",
            "device_label": t.device_label,
            "created_at": t.created_at,
            "last_seen": t.last_seen,
        }
        for t in tokens
    ]
