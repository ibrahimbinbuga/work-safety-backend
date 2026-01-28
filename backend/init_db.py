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
    {"code": "COMPANY002", "name": "XYZ Fabrika", "is_admin": False},
    {"code": "COMPANY003", "name": "DEF Lojistik", "is_admin": False},
    {"code": "COMPANY004", "name": "GHI Mayın", "is_admin": False},
]

USERS = [
    # Super Admin
    {"email": "admin@system.com", "password": "admin123", "company_code": "ADMIN", "role": "admin"},
    
    # COMPANY001 (ABC İnşaat)
    {"email": "user1@abc.com", "password": "password123", "company_code": "COMPANY001", "role": "user"},
    {"email": "manager1@abc.com", "password": "password123", "company_code": "COMPANY001", "role": "admin"},
    
    # COMPANY002 (XYZ Fabrika)
    {"email": "user2@xyz.com", "password": "password123", "company_code": "COMPANY002", "role": "user"},
    {"email": "manager2@xyz.com", "password": "password123", "company_code": "COMPANY002", "role": "admin"},
    
    # COMPANY003 (DEF Lojistik)
    {"email": "user3@def.com", "password": "password123", "company_code": "COMPANY003", "role": "user"},
    {"email": "manager3@def.com", "password": "password123", "company_code": "COMPANY003", "role": "admin"},
    
    # COMPANY004 (GHI Mayın)
    {"email": "user4@ghi.com", "password": "password123", "company_code": "COMPANY004", "role": "user"},
    {"email": "manager4@ghi.com", "password": "password123", "company_code": "COMPANY004", "role": "admin"},
]


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
    
    # Clear existing data
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        try:
            print("\n🗑️  Clearing existing data...")
            await session.execute(delete(models.User))
            await session.execute(delete(models.Company))
            await session.commit()
            print("✅ Existing data cleared")
        except Exception as e:
            print(f"⚠️  No existing data to clear: {e}")
            await session.rollback()
    
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
    
    print("\n🏢 COMPANY001 (ABC İnşaat):")
    print("    - User: user1@abc.com / password123")
    print("    - Manager: manager1@abc.com / password123")
    
    print("\n🏢 COMPANY002 (XYZ Fabrika):")
    print("    - User: user2@xyz.com / password123")
    print("    - Manager: manager2@xyz.com / password123")
    
    print("\n🏢 COMPANY003 (DEF Lojistik):")
    print("    - User: user3@def.com / password123")
    print("    - Manager: manager3@def.com / password123")
    
    print("\n🏢 COMPANY004 (GHI Mayın):")
    print("    - User: user4@ghi.com / password123")
    print("    - Manager: manager4@ghi.com / password123")
    
    print("\n⚠️  IMPORTANT: Change these default passwords in production!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(init_db())
