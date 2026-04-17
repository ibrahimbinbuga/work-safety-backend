"""Database bootstrap script for app package."""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db import models
from app.db.session import AsyncSessionLocal, Base, engine


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        admin_company = (
            await session.execute(select(models.Company).where(models.Company.code == "ADMIN"))
        ).scalar_one_or_none()
        if admin_company is None:
            admin_company = models.Company(code="ADMIN", name="System Admin")
            session.add(admin_company)
            await session.flush()

        admin_user = (
            await session.execute(select(models.User).where(models.User.email == "admin@system.com"))
        ).scalar_one_or_none()
        if admin_user is None:
            session.add(
                models.User(
                    email="admin@system.com",
                    hashed_password=hash_password("admin123"),
                    company_id=admin_company.id,
                    role="admin",
                    is_active=True,
                )
            )
        await session.commit()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
