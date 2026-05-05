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
from routes import auth, cameras, detections, users, reports, notifications, devices as devices_router
from routes import models as models_router
from services.notification_service import WebSocketManager
from services.model_service import ensure_company_model_cameras_schema
from services.violation_service import violation_consumer_task
from services.report_scheduler import send_daily_reports, send_weekly_reports, send_monthly_reports

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
app.include_router(devices_router.router)


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
    g.ws_manager = WebSocketManager()
    print("[startup] WebSocket manager initialized.")

    # Daily   → every day at 17:30 Turkey time (14:30 UTC)
    scheduler.add_job(send_daily_reports,   "cron", hour=14, minute=30, id="daily_reports")
    # Weekly  → every Friday at 17:30 Turkey time (14:30 UTC)
    scheduler.add_job(send_weekly_reports,  "cron", day_of_week="fri", hour=14, minute=30, id="weekly_reports")
    # Monthly → last day of each month at 17:30 Turkey time (14:30 UTC)
    scheduler.add_job(send_monthly_reports, "cron", day="last", hour=14, minute=30, id="monthly_reports")
    scheduler.start()
    print("[startup] Report scheduler started (daily/weekly/monthly @ 17:30 TR / 14:30 UTC).")

    print("[startup] Camera auto-start disabled. Waiting for login/company selection trigger.")


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown(wait=False)
    print("[shutdown] Report scheduler stopped.")
