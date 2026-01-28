# backend/reset_db.py
"""
Database reset script.
Drops all tables and recreates them with fresh data.

Usage:
    python reset_db.py
"""

import asyncio
import os
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


async def reset_db():
    """Reset database: drop all tables and recreate."""
    
    print("⚠️  DROPPING ALL TABLES...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("✅ All tables dropped")
    
    print("\n🔄 Creating all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created successfully")
    
    # Create companies and users
    async with AsyncSessionLocal() as session:
        try:
            # Define companies and their users
            companies_data = [
                {
                    "code": "COMPANY001",
                    "name": "ABC İnşaat",
                    "users": [
                        {"email": "user1@abc.com", "password": "password123", "role": "user"},
                        {"email": "manager1@abc.com", "password": "password123", "role": "admin"},
                    ]
                },
                {
                    "code": "COMPANY002",
                    "name": "XYZ Fabrika",
                    "users": [
                        {"email": "user2@xyz.com", "password": "password123", "role": "user"},
                        {"email": "manager2@xyz.com", "password": "password123", "role": "admin"},
                    ]
                },
                {
                    "code": "COMPANY003",
                    "name": "DEF Lojistik",
                    "users": [
                        {"email": "user3@def.com", "password": "password123", "role": "user"},
                        {"email": "manager3@def.com", "password": "password123", "role": "admin"},
                    ]
                },
                {
                    "code": "COMPANY004",
                    "name": "GHI Mayın",
                    "users": [
                        {"email": "user4@ghi.com", "password": "password123", "role": "user"},
                        {"email": "manager4@ghi.com", "password": "password123", "role": "admin"},
                    ]
                }
            ]
            
            # Create companies and users
            for company_data in companies_data:
                print(f"\n📝 Creating company: {company_data['code']} ({company_data['name']})...")
                company = models.Company(
                    code=company_data["code"],
                    name=company_data["name"]
                )
                session.add(company)
                await session.flush()  # Get the company ID
                
                print(f"✅ Company created: {company_data['code']}")
                
                # Create users for this company
                for user_data in company_data["users"]:
                    print(f"  👤 Creating user: {user_data['email']}...")
                    user = models.User(
                        email=user_data["email"],
                        hashed_password=hash_password(user_data["password"]),
                        company_id=company.id,
                        role=user_data["role"],
                        is_active=True
                    )
                    session.add(user)
                
            # Create super admin user (not assigned to any company, can access all)
            print(f"\n📝 Creating super admin user...")
            super_admin = models.Company(
                code="SUPERADMIN",
                name="System Admin"
            )
            session.add(super_admin)
            await session.flush()
            
            super_admin_user = models.User(
                email="superadmin@system.com",
                hashed_password=hash_password("admin123"),
                company_id=super_admin.id,
                role="admin",
                is_active=True
            )
            session.add(super_admin_user)
            
            # Create system admin user (ADMIN code)
            admin_company = models.Company(
                code="ADMIN",
                name="System Administration"
            )
            session.add(admin_company)
            await session.flush()
            
            admin_user = models.User(
                email="admin@system.com",
                hashed_password=hash_password("admin123"),
                company_id=admin_company.id,
                role="admin",
                is_active=True
            )
            session.add(admin_user)
            
            await session.commit()
            
            print("\n✅ All users created successfully!")
            
        except Exception as e:
            print(f"❌ Error during initialization: {e}")
            await session.rollback()
            import traceback
            traceback.print_exc()
    
    await engine.dispose()
    print("\n✨ Database reset complete!")
    print("\n📋 Test Credentials:")
    print("\n  🔓 SUPER ADMIN Login (All Companies):")
    print("    - Company Code: ADMIN")
    print("    - Email: admin@system.com")
    print("    - Password: admin123")
    
    print("\n  🏢 COMPANY001 (ABC İnşaat):")
    print("    - User: user1@abc.com / password123")
    print("    - Manager: manager1@abc.com / password123")
    
    print("\n  🏢 COMPANY002 (XYZ Fabrika):")
    print("    - User: user2@xyz.com / password123")
    print("    - Manager: manager2@xyz.com / password123")
    
    print("\n  🏢 COMPANY003 (DEF Lojistik):")
    print("    - User: user3@def.com / password123")
    print("    - Manager: manager3@def.com / password123")
    
    print("\n  🏢 COMPANY004 (GHI Mayın):")
    print("    - User: user4@ghi.com / password123")
    print("    - Manager: manager4@ghi.com / password123")
    
    print("\n⚠️  IMPORTANT: Change these default passwords in production!")


if __name__ == "__main__":
    asyncio.run(reset_db())
