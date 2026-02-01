from sqlalchemy import Column, Integer, String
from app.database.base import Base

class Migrant(Base):
    __tablename__ = "migrants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
