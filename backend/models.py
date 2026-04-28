from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Sequence, Computed, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

# It is used to define the tables for the database

# Role Enum
class RoleEnum(str, enum.Enum):
    admin = "admin"
    user = "user"

# Priority Enum - detection kayıt sıklığını belirler
class PriorityEnum(str, enum.Enum):
    critical = "critical"   # 30 sn
    high = "high"           # 2 dk
    medium = "medium"       # 10 dk
    low = "low"             # 30 dk

# 1. Şirket Tablosu
class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)  # Şirket kodu (örn: "COMPANY001")
    name = Column(String, nullable=False)  # Şirket adı
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # İlişki: Bir şirketin birden çok kullanıcısı olabilir
    users = relationship("User", back_populates="company")
    # İlişki: Bir şirketin birden çok modeli olabilir
    models = relationship("CompanyModel", back_populates="company")


# 2. Kullanıcılar Tablosu (Güncellendi)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.user, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)  # Şirket (company) ilişkisi
    # İlişki: Kullanıcı bir şirkete aittir
    company = relationship("Company", back_populates="users")


class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)            # Örn: "Depo Girişi"
    location = Column(String)        # Örn: "Bölge 1"
    rtsp_url = Column(String)        # Kamera IP Adresi
    status = Column(String)          # online, offline
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)  # Kamera hangi şirkete ait
    last_active = Column(DateTime(timezone=True), onupdate=func.now())
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)  # Şirket (company) ilişkisi

    # İlişki: Bir kameranın birden çok tespiti olabilir
    detections = relationship("Detection", back_populates="camera")
    company = relationship("Company")
    model_assignments = relationship("CompanyModelCamera", back_populates="camera")

# 2. Tespitler (İhlaller) Tablosu
class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)  # Kameradan alınır

    detection_type = Column(String)  # no_helmet, no_vest
    confidence = Column(Float)       # 0.95
    is_violation = Column(Boolean)   # True

    snapshot_path = Column(String)   # Resim yolu
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # İlişki: Tespit bir kameraya aittir
    camera = relationship("Camera", back_populates="detections")
    company = relationship("Company")

# 3. Sistem Sağlığı Tablosu
class SystemLog(Base):
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String)    # AI Model, Database vb.
    status = Column(String)          # online, error
    uptime = Column(Float)           # %99.9
    last_check = Column(DateTime(timezone=True), server_default=func.now())


# 4. İhlaller Tablosu
class Violations(Base):
    __tablename__ = "violations"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)  # Kameradan alınır
    tarih_saat = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # Otomatik kayıt zamanı - CURRENT_TIMESTAMP gibi çalışır
    ihlal_cesidi = Column(String, nullable=False)            # 'head' or 'vest' (eski kodun mantığına uygun)
    ihlal_yapilan_bolge = Column(String)    # kamera konumu veya bölge (optional, can be None)
    violation_id = Column(Integer, nullable=False)  # Worker ID olarak kullanılıyor (eski kodun mantığına uygun - manuel olarak set edilir)
    review_status = Column(String, default='pending', nullable=False, server_default='pending')  # pending | reviewed | resolved

    company = relationship("Company")


# 5. Model Meta Verileri Tablosu
class ModelMeta(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, nullable=False)
    version = Column(String, nullable=False)
    description = Column(String)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=False)
    
    # İlişki: Bir modelin birden çok şirkete ataması olabilir
    company_assignments = relationship("CompanyModel", back_populates="model")
    camera_assignments = relationship("CompanyModelCamera", back_populates="model")


# 6. Şirket-Model İlişki Tablosu (Many-to-Many)
class CompanyModel(Base):
    __tablename__ = "company_models"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    is_active = Column(Boolean, default=False)  # Bu company için model aktif mi?
    enabled_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # İlişkiler
    company = relationship("Company", back_populates="models")
    model = relationship("ModelMeta", back_populates="company_assignments")


class CompanyModelCamera(Base):
    __tablename__ = "company_model_cameras"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    enabled_at = Column(DateTime(timezone=True), server_default=func.now())
    priority = Column(Enum(PriorityEnum), default=PriorityEnum.medium, nullable=False, server_default="medium")

    company = relationship("Company")
    camera = relationship("Camera", back_populates="model_assignments")
    model = relationship("ModelMeta", back_populates="camera_assignments")


class CompanyNotificationSettings(Base):
    __tablename__ = "company_notification_settings"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True, nullable=False)
    email_enabled = Column(Boolean, default=False, nullable=False)
    report_period = Column(String, default="weekly", nullable=False)   # daily / weekly / monthly
    report_formats = Column(JSON, default=["pdf"], nullable=False)     # ["pdf","excel","csv"]
    push_enabled = Column(Boolean, default=True, nullable=False)
    alert_critical = Column(Boolean, default=True, nullable=False)
    alert_camera_offline = Column(Boolean, default=True, nullable=False)
    alert_model_updates = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company = relationship("Company", backref="notification_settings")
