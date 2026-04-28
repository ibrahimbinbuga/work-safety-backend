# backend/main.py
import asyncio

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text

from database import Base, engine
import globals as g
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from routes import auth, cameras, detections, users, reports, notifications
from routes import models as models_router
from services.model_service import ensure_company_model_cameras_schema
from services.violation_service import violation_consumer_task
from services.report_scheduler import send_scheduled_reports

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(cameras.router)
app.include_router(detections.router)
app.include_router(models_router.router)
app.include_router(reports.router)
app.include_router(notifications.router)


@app.get("/")
async def root():
    return {"message": "SafetyWatch API running"}


@app.options("/{path:path}")
async def preflight_handler():
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


scheduler = AsyncIOScheduler(timezone="UTC")


@app.on_event("startup")
async def startup_event():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await ensure_company_model_cameras_schema()

        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE IF EXISTS violations ADD COLUMN IF NOT EXISTS "
                "review_status VARCHAR NOT NULL DEFAULT 'pending'"
            ))
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print("This may be expected if running without database connection initially")

    g.main_loop = asyncio.get_event_loop()
    g.violation_queue = asyncio.Queue()
    g.consumer_task = asyncio.create_task(violation_consumer_task(g.violation_queue))

    scheduler.add_job(send_scheduled_reports, "cron", hour=8, minute=0, id="daily_reports")
    scheduler.start()
    print("[startup] Report scheduler started (daily at 08:00 UTC).")

    print("[startup] Camera auto-start disabled. Waiting for login/company selection trigger.")


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown(wait=False)
    print("[shutdown] Report scheduler stopped.")
