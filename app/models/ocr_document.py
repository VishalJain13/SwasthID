from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.database.base import Base


class OCRDocument(Base):
    __tablename__ = "ocr_documents"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(String, unique=True, index=True)
    visit_id = Column(String, index=True)
    health_id = Column(String, index=True)

    document_type = Column(String)  # prescription / lab / discharge
    file_path = Column(String)

    ocr_text = Column(String)
    language = Column(String, default="en")

    created_at = Column(DateTime, default=datetime.utcnow)
    synced = Column(Boolean, default=False)
