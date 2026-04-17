import asyncio

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text

import app.runtime.state as g
from app.api.router import router as api_router
from app.db import models as _models  # ensure model metadata is registered
from app.db.session import Base, engine
from app.services.model_service import ensure_company_model_cameras_schema
from app.services.violation_service import violation_consumer_task

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


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


@app.on_event("startup")
async def startup_event():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await ensure_company_model_cameras_schema()

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "ALTER TABLE IF EXISTS violations ADD COLUMN IF NOT EXISTS "
                    "review_status VARCHAR NOT NULL DEFAULT 'pending'"
                )
            )
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print("This may be expected if running without database connection initially")

    g.main_loop = asyncio.get_event_loop()
    g.violation_queue = asyncio.Queue()
    g.consumer_task = asyncio.create_task(violation_consumer_task(g.violation_queue))

    print("[startup] Camera auto-start disabled. Waiting for login/company selection trigger.")

