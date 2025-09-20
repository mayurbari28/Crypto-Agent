#Description: SQLAlchemy engine/session factory and DB initializer.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from utils.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))

def get_session():
    return SessionLocal()

def init_db():
    from models.orm import Base
    Base.metadata.create_all(bind=engine)
