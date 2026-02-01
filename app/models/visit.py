from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from datetime import datetime
from app.database.base import Base

class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(String, unique=True, index=True)

    # Linkage
    health_id = Column(String, index=True)
    mobile = Column(String, nullable=True)

    # Facility & location
    facility_name = Column(String)
    district = Column(String)
    state = Column(String)
    
    # Provider details
    doctor_name = Column(String, nullable=True)
    specialization = Column(String, nullable=True) # e.g. Cardiologist
    attachments = Column(String, nullable=True)    # JSON string of URLs

    # Medical details
    visit_type = Column(String)               # OPD / Emergency / Follow-up
    chief_complaint = Column(String)
    symptoms = Column(String)                 # comma separated
    temperature_c = Column(Float, nullable=True)
    bp = Column(String, nullable=True)
    spo2 = Column(Integer, nullable=True)

    # Vaccination during visit
    vaccine_given = Column(Boolean, default=False)
    vaccine_name = Column(String, nullable=True)
    next_dose_due_date = Column(String, nullable=True)

    # Referral
    referred = Column(Boolean, default=False)
    referred_to = Column(String, nullable=True)
    referral_reason = Column(String, nullable=True)

    # System fields
    created_at = Column(DateTime, default=datetime.utcnow)
    synced = Column(Boolean, default=False)
