# backend/init_db.py
"""
Database initialization script.
Creates all tables and seeds initial data with super admin and multiple companies.

Usage:
    python init_db.py
"""

import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import models after loading environment
import models
from database import Base
from auth import hash_password

# Get database URL
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "safety_analysis_db")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create async engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, future=True
)

# Test data structure
COMPANIES = [
    {"code": "ADMIN", "name": "System Admin", "is_admin": True},
    {"code": "COMPANY001", "name": "ABC İnşaat", "is_admin": False},

]

USERS = [
    # Super Admin
    {"email": "admin@system.com", "password": "admin123", "company_code": "ADMIN", "role": "admin"},
    {"email": "test@test.com", "password": "test123", "company_code": "ADMIN", "role": "admin"},]
    


async def init_db():
    """Initialize database: create tables and seed initial data."""
    
    print("=" * 60)
    print("🔄 DATABASE INITIALIZATION STARTING...")
    print("=" * 60)
    
    # Create tables
    print("\n🔄 Creating all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created successfully")
    
    # Do NOT clear existing data by default
    print("\nℹ️  Skipping data wipe (preserving existing records).")
    
    # Create companies and users
    async with AsyncSessionLocal() as session:
        try:
            print("\n📝 Creating companies...")
            companies_dict = {}
            
            for company_data in COMPANIES:
                company = models.Company(
                    code=company_data["code"],
                    name=company_data["name"]
                )
                session.add(company)
                await session.flush()
                companies_dict[company_data["code"]] = company
                print(f"  ✅ {company_data['code']} - {company_data['name']}")
            
            print("\n👤 Creating users...")
            for user_data in USERS:
                company = companies_dict.get(user_data["company_code"])
                if company:
                    user = models.User(
                        email=user_data["email"],
                        hashed_password=hash_password(user_data["password"]),
                        company_id=company.id,
                        role=user_data["role"],
                        is_active=True
                    )
                    session.add(user)
                    print(f"  ✅ {user_data['email']} ({user_data['role']}) -> {user_data['company_code']}")

            # Seed general model (PPE Detection)
            print("\n🤖 Creating general model (PPE Detection)...")
            backend_dir = Path(__file__).parent
            default_model_path = backend_dir.parent / "model" / "weights" / "best.pt"
            general_model = models.GeneralModel(
                name="PPE Detection",
                description="Helmet + Vest",
                version="v1.0",
                path=str(default_model_path),
                is_active=True
            )
            session.add(general_model)
            await session.flush()

            # Seed cameras per company (dummy data)
            print("\n📷 Creating cameras and model-camera assignments...")
            camera_templates = [
                {"name": "Main Entrance", "location": "Gate A", "rtsp_url": "0", "status": "online"},
                {"name": "Warehouse", "location": "Zone 2", "rtsp_url": "0", "status": "online"},
                {"name": "Loading Dock", "location": "Dock 3", "rtsp_url": "0", "status": "offline"},
            ]

            for company_data in COMPANIES:
                if company_data["code"] in ["ADMIN", "SUPERADMIN", "SYSTEM"]:
                    continue
                company = companies_dict.get(company_data["code"])
                if not company:
                    continue

                # Assign model to company
                company_model = models.CompanyGeneralModel(
                    company_id=company.id,
                    model_id=general_model.id,
                    is_enabled=True
                )
                session.add(company_model)

                for idx, cam_tpl in enumerate(camera_templates):
                    cam = models.Camera(
                        name=f"{cam_tpl['name']} - {company_data['code']}",
                        location=cam_tpl["location"],
                        rtsp_url=cam_tpl["rtsp_url"],
                        status=cam_tpl["status"],
                        company_id=company.id
                    )
                    session.add(cam)
                    await session.flush()

                    # Assign model to camera with alternating active status
                    is_active = True if idx < 2 else False
                    assignment = models.CompanyModelCamera(
                        company_id=company.id,
                        camera_id=cam.id,
                        model_id=general_model.id,
                        is_active=is_active
                    )
                    session.add(assignment)
            
            await session.commit()
            print("\n✅ All users created successfully")
            
        except Exception as e:
            print(f"❌ Error during initialization: {e}")
            await session.rollback()
            import traceback
            traceback.print_exc()
    
    await engine.dispose()
    
    # Print summary
    print("\n" + "=" * 60)
    print("✨ DATABASE INITIALIZATION COMPLETE!")
    print("=" * 60)
    
    print("\n🔓 SUPER ADMIN Login (All Companies):")
    print("    - Company Code: ADMIN")
    print("    - Email: admin@system.com")
    print("    - Password: admin123")
    
    
    print("\n⚠️  IMPORTANT: Change these default passwords in production!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(init_db())
