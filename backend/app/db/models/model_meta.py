import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class PriorityEnum(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class ModelMeta(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, nullable=False)
    version = Column(String, nullable=False)
    description = Column(String)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=False)

    company_assignments = relationship("CompanyModel", back_populates="model")
    camera_assignments = relationship("CompanyModelCamera", back_populates="model")


class CompanyModel(Base):
    __tablename__ = "company_models"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    is_active = Column(Boolean, default=False)
    enabled_at = Column(DateTime(timezone=True), server_default=func.now())

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
