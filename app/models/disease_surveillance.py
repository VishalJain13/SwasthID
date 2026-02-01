from sqlalchemy import Column, Integer, String, Date, DateTime
from datetime import date, datetime
from app.database.base import Base


class DiseaseSurveillance(Base):
    __tablename__ = "disease_surveillance"

    id = Column(Integer, primary_key=True, index=True)

    district = Column(String, index=True)
    state = Column(String, index=True)

    disease_name = Column(String, index=True)
    case_count = Column(Integer)

    severity_level = Column(String)  # mild / moderate / severe
    alert_level = Column(String)     # LOW / MEDIUM / HIGH

    date = Column(Date, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow)
