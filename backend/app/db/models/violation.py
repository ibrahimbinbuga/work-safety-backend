from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Violations(Base):
    __tablename__ = "violations"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    tarih_saat = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ihlal_cesidi = Column(String, nullable=False)
    ihlal_yapilan_bolge = Column(String)
    violation_id = Column(Integer, nullable=False)
    review_status = Column(String, default="pending", nullable=False, server_default="pending")

    company = relationship("Company")
