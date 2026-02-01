from sqlalchemy import Column, Integer, String, Float
from app.database.base import Base

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    mobile = Column(String, unique=True)

    # PAGE 1 – Personal details
    name = Column(String)
    age = Column(Integer)
    gender = Column(String)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    pincode = Column(String)

    # PAGE 2 – Medical details
    height_cm = Column(Float)
    weight_kg = Column(Float)
    bmi = Column(Float)
    blood_group = Column(String)
    vaccination_status = Column(String)
    allergies = Column(String)

    # Emergency Contact
    emergency_contact_name = Column(String)
    emergency_contact_phone = Column(String)
    emergency_contact_relation = Column(String)

    # Insurance Details
    insurance_provider = Column(String)
    insurance_policy_no = Column(String)
    insurance_valid_till = Column(String)
    insurance_tpa = Column(String)
