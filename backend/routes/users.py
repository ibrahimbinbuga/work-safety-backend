"""Admin user management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenData, UserCreate, UserResponse, hash_password
from database import get_db
from dependencies import get_admin_user
import models

router = APIRouter()


@router.post("/api/admin/users", response_model=UserResponse)
async def create_user(
    user_create: UserCreate,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    company_result = await db.execute(
        select(models.Company).where(models.Company.code == user_create.company_code)
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    existing = await db.execute(
        select(models.User).where(
            (models.User.email == user_create.email) & (models.User.company_id == company.id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists in this company",
        )

    if user_create.role not in ["admin", "user"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'admin' or 'user'",
        )

    new_user = models.User(
        email=user_create.email,
        hashed_password=hash_password(user_create.password),
        company_id=company.id,
        role=user_create.role,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.get("/api/admin/users")
async def list_users(
    company_code: str | None = None,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if company_code:
        company_id_sq = (
            select(models.Company.id)
            .where(func.upper(models.Company.code) == func.upper(company_code))
            .scalar_subquery()
        )
        query = (
            select(models.User)
            .where(models.User.company_id == company_id_sq)
            .order_by(models.User.created_at.desc())
        )
    else:
        query = select(models.User).order_by(models.User.created_at.desc())
    result = await db.execute(query)
    return [UserResponse.from_orm(u) for u in result.scalars().all()]


@router.get("/api/admin/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/api/admin/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: dict,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "role" in user_update and user_update["role"] in ["admin", "user"]:
        user.role = user_update["role"]
    if "is_active" in user_update:
        user.is_active = user_update["is_active"]

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: TokenData = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"status": "success", "message": "User deleted"}
