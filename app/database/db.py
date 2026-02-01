from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.profile import Profile
from app.models.health_id import HealthID

DATABASE_URL = "sqlite:///./swasth_v2.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(bind=engine)
