from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.database.base import Base


class MedicalDocument(Base):
    __tablename__ = "medical_documents"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(String, unique=True, index=True)
    health_id = Column(String, index=True)
    visit_id = Column(String, nullable=True, index=True) # Optional link to a visit

    document_type = Column(String) # prescription, xray, labReport, notes
    file_url = Column(String)
    file_name = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    synced = Column(Boolean, default=False)
