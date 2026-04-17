"""Authentication and company-selection endpoints."""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.config import is_admin_company_code
from app.core.dependencies import get_admin_user, get_current_user
from app.schemas.auth import CompanyResponse, LoginRequest, Token, TokenData
from app.core.security import create_access_token, verify_password
from app.db import models
from app.services.camera_service import ensure_company_cameras_started, stop_company_cameras

router = APIRouter()


@router.post("/api/auth/login", response_model=Token)
async def login(login_request: LoginRequest, db: AsyncSession = Depends(get_db)):
    is_admin_login = is_admin_company_code(login_request.company_code)
    company_id = None

    if not is_admin_login:
        company_result = await db.execute(
            select(models.Company).where(
                func.upper(models.Company.code) == func.upper(login_request.company_code)
            )
        )
        company = company_result.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid company code")
        company_id = company.id

    if company_id:
        user_result = await db.execute(
            select(models.User).where(
                (models.User.email == login_request.email)
                & (models.User.company_id == company_id)
            )
        )
    else:
        user_result = await db.execute(
            select(models.User).where(models.User.email == login_request.email)
        )

    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(login_request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        company_code=login_request.company_code,
    )

    if user.role == "user" and user.company_id is not None:
        await ensure_company_cameras_started(db, user.company_id, trigger=f"user-login:{user.id}")

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=user.role,
        company_code=login_request.company_code,
    )


@router.get("/api/auth/me")
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(models.User, current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "user" and user.company_id is not None:
        await ensure_company_cameras_started(
            db, user.company_id, trigger=f"auth-me:user-{user.id}"
        )
    return user


@router.post("/api/auth/logout")
async def logout(
    payload: Optional[dict] = Body(default=None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_company_code: Optional[str] = None

    if current_user.role == "user":
        target_company_code = current_user.company_code
    elif current_user.role == "admin":
        requested_code = (payload or {}).get("company_code")
        if requested_code and not is_admin_company_code(requested_code):
            target_company_code = requested_code

    stopped_count = 0
    if target_company_code:
        company_result = await db.execute(
            select(models.Company).where(
                func.upper(models.Company.code) == func.upper(target_company_code)
            )
        )
        company = company_result.scalar_one_or_none()
        if company:
            stopped_count = await stop_company_cameras(
                db, company.id, trigger=f"logout:{current_user.user_id}"
            )

    return {"status": "success", "message": "Logged out successfully", "stopped_cameras": stopped_count}


@router.post("/api/auth/select-company/{company_code}")
async def select_company_for_admin(
    company_code: str,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    company_result = await db.execute(
        select(models.Company).where(func.upper(models.Company.code) == func.upper(company_code))
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    started_count = await ensure_company_cameras_started(
        db, company.id, trigger=f"admin-select:{admin_user.user_id}"
    )
    return {"status": "success", "company_code": company.code, "started_cameras": started_count}


@router.get("/api/companies", response_model=list[CompanyResponse])
async def get_companies(
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Company).order_by(models.Company.name))
    return result.scalars().all()
