from sqlalchemy import Column, Integer, String
from app.database.base import Base

class HealthID(Base):
    __tablename__ = "health_ids"

    id = Column(Integer, primary_key=True)
    mobile = Column(String, unique=True)
    id_type = Column(String)
    id_number = Column(String)
    health_id = Column(String, unique=True)
