from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import engine, Base, get_db, AsyncSessionLocal
import models
import datetime
import random

# --- BAŞLANGIÇTA ÇALIŞACAK KOD (LIFESPAN) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Veritabanı tablolarını oluştur
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Sahte Veri Kontrolü ve Ekleme
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(models.Camera))
        cameras = result.scalars().all()
        
        if not cameras:
            print("--- Veritabanı boş, sahte veriler yükleniyor... ---")
            
            # A. Kameralar
            cam1 = models.Camera(name="Warehouse A - Entry", location="Zone 1", rtsp_url="rtsp://192.168.1.10", status="online")
            cam2 = models.Camera(name="Construction Zone 3", location="Zone 3", rtsp_url="rtsp://192.168.1.11", status="online")
            cam3 = models.Camera(name="Loading Dock", location="Zone 2", rtsp_url="rtsp://192.168.1.12", status="offline")
            session.add_all([cam1, cam2, cam3])
            await session.commit()
            
            # B. Sistem Sağlığı
            logs = [
                models.SystemLog(service_name="AI Detection Model", status="online", uptime=99.8),
                models.SystemLog(service_name="Database Server", status="online", uptime=100.0),
                models.SystemLog(service_name="Camera Network", status="warning", uptime=95.2),
            ]
            session.add_all(logs)
            await session.commit()
            print("--- Sahte veriler başarıyla yüklendi! ---")
            
    yield

app = FastAPI(lifespan=lifespan)

# --- CORS AYARLARI (FRONTEND BAĞLANTISI İÇİN ŞART) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Geliştirme aşamasında herkese izin ver
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "SafetyWatch API Çalışıyor!"}

# Test Endpoint'i: Kameraları listele
@app.get("/api/cameras")
async def get_cameras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Camera))
    return result.scalars().all()