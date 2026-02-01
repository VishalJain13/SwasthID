from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from datetime import datetime
from app.database.base import Base


class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(Integer, primary_key=True, index=True)

    record_id = Column(String, unique=True, index=True)
    visit_id = Column(String, index=True)
    health_id = Column(String, index=True)

    symptoms = Column(String)
    diagnosis = Column(String)

    severity = Column(String)  # mild / moderate / severe
    suspected_disease = Column(String, nullable=True)

    is_infectious = Column(Boolean, default=False)

    temperature = Column(Float, nullable=True)
    spo2 = Column(Integer, nullable=True)

    notes = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    synced = Column(Boolean, default=False)
