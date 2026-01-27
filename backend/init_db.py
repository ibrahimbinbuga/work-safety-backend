# backend/init_db.py
"""
Database initialization script.
Creates all tables and seeds initial data (admin user and sample company).

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
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "work_safety")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create async engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, future=True
)


async def init_db():
    """Initialize database: create tables and seed initial data."""
    
    print("🔄 Creating all tables...")
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
    
    # Create sample company and admin user
    async with AsyncSessionLocal() as session:
        try:
            # Check if company already exists
            from sqlalchemy import select
            existing_company = await session.execute(
                select(models.Company).where(models.Company.code == "COMPANY001")
            )
            
            if existing_company.scalar_one_or_none() is None:
                print("\n📝 Creating sample company...")
                company = models.Company(
                    code="COMPANY001",
                    name="Sample Company"
                )
                session.add(company)
                await session.flush()  # Get the company ID
                
                print("✅ Sample company created: COMPANY001")
                
                # Create admin user
                print("👤 Creating admin user...")
                admin_user = models.User(
                    email="admin@company.com",
                    hashed_password=hash_password("admin123"),  # Change this password!
                    company_id=company.id,
                    role="admin",
                    is_active=True
                )
                session.add(admin_user)
                
                # Create sample regular user
                print("👤 Creating sample user...")
                regular_user = models.User(
                    email="user@company.com",
                    hashed_password=hash_password("user123"),  # Change this password!
                    company_id=company.id,
                    role="user",
                    is_active=True
                )
                session.add(regular_user)
                
                await session.commit()
                
                print("✅ Admin user created: admin@company.com (password: admin123)")
                print("✅ Sample user created: user@company.com (password: user123)")
            else:
                print("⚠️  Sample company already exists. Skipping seeding.")
            
        except Exception as e:
            print(f"❌ Error during initialization: {e}")
            await session.rollback()
            import traceback
            traceback.print_exc()
    
    await engine.dispose()
    print("\n✨ Database initialization complete!")
    print("\n📋 Test Credentials:")
    print("  Company Code: COMPANY001")
    print("  Admin Email: admin@company.com")
    print("  Admin Password: admin123")
    print("  User Email: user@company.com")
    print("  User Password: user123")
    print("\n⚠️  IMPORTANT: Change these default passwords in production!")


if __name__ == "__main__":
    asyncio.run(init_db())
