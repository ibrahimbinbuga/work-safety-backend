from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

# 1. Kameralar Tablosu
class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)            # Örn: "Depo Girişi"
    location = Column(String)        # Örn: "Bölge 1"
    rtsp_url = Column(String)        # Kamera IP Adresi
    status = Column(String)          # online, offline
    last_active = Column(DateTime(timezone=True), onupdate=func.now())
    
    # İlişki: Bir kameranın birden çok tespiti olabilir
    detections = relationship("Detection", back_populates="camera")

# 2. Tespitler (İhlaller) Tablosu
class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    
    detection_type = Column(String)  # no_helmet, no_vest
    confidence = Column(Float)       # 0.95
    is_violation = Column(Boolean)   # True
    
    snapshot_path = Column(String)   # Resim yolu
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # İlişki: Tespit bir kameraya aittir
    camera = relationship("Camera", back_populates="detections")

# 3. Sistem Sağlığı Tablosu
class SystemLog(Base):
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String)    # AI Model, Database vb.
    status = Column(String)          # online, error
    uptime = Column(Float)           # %99.9
    last_check = Column(DateTime(timezone=True), server_default=func.now())

# 4. Kullanıcılar (Opsiyonel - Login için)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Violation(Base):
    __tablename__ = "violations"
    id = Column(Integer, primary_key=True, index=True)
    tarih_saat = Column(DateTime(timezone=True), server_default=func.now())
    ihlal_cesidi = Column(String)            # helmet, vest, both vb.
    ihlal_yapilan_bolge = Column(String)    # kamera konumu veya bölge
    violation_id = Column(String, unique=True, index=True)