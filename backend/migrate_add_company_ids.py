#!/usr/bin/env python3
"""
Migration script to add company_id to Camera, Detection, and Violations tables
Run this after updating the models but before starting the application
"""

import asyncio
from sqlalchemy import select, update
from database import AsyncSessionLocal
import models


async def migrate_add_company_ids():
    """
    Add company_id to Camera, Detection, and Violations tables.
    This assumes cameras/detections/violations should be assigned to COMPANY001
    Modify the company_code as needed for your setup.
    """
    
    async with AsyncSessionLocal() as session:
        try:
            # Find COMPANY001 to get its ID
            company_result = await session.execute(
                select(models.Company).where(models.Company.code == "COMPANY001")
            )
            company = company_result.scalar_one_or_none()
            
            if not company:
                print("ERROR: COMPANY001 not found in database!")
                print("Please create a company first:")
                print("  - Company Code: COMPANY001")
                print("  - Company Name: Company 001")
                return False
            
            company_id = company.id
            print(f"Found COMPANY001 with ID: {company_id}")
            
            # Update Camera table
            cameras_result = await session.execute(
                update(models.Camera)
                .where(models.Camera.company_id == None)  # Only update NULL values
                .values(company_id=company_id)
            )
            cameras_updated = cameras_result.rowcount
            print(f"Updated {cameras_updated} cameras with company_id={company_id}")
            
            # Update Detection table
            detections_result = await session.execute(
                update(models.Detection)
                .where(models.Detection.company_id == None)  # Only update NULL values
                .values(company_id=company_id)
            )
            detections_updated = detections_result.rowcount
            print(f"Updated {detections_updated} detections with company_id={company_id}")
            
            # Update Violations table
            violations_result = await session.execute(
                update(models.Violations)
                .where(models.Violations.company_id == None)  # Only update NULL values
                .values(company_id=company_id)
            )
            violations_updated = violations_result.rowcount
            print(f"Updated {violations_updated} violations with company_id={company_id}")
            
            await session.commit()
            print("\n✅ Migration completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            await session.rollback()
            return False


if __name__ == "__main__":
    print("Starting migration: Adding company_id to Camera, Detection, and Violations tables")
    print("-" * 80)
    
    success = asyncio.run(migrate_add_company_ids())
    exit(0 if success else 1)
