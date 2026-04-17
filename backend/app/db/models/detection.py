from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    detection_type = Column(String)
    confidence = Column(Float)
    is_violation = Column(Boolean)
    snapshot_path = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    camera = relationship("Camera", back_populates="detections")
    company = relationship("Company")
