from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    location = Column(String)
    rtsp_url = Column(String)
    status = Column(String)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    last_active = Column(DateTime(timezone=True), onupdate=func.now())

    detections = relationship("Detection", back_populates="camera")
    company = relationship("Company")
    model_assignments = relationship("CompanyModelCamera", back_populates="camera")
