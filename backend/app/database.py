from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings


def build_engine_kwargs(database_url: str) -> dict:
    """SQLite (local dev) needs check_same_thread=False for FastAPI's
    threaded request handling. PostgreSQL (production) needs neither that
    nor any other special connect_args — pool_pre_ping instead guards
    against stale connections being handed out after a period of
    idleness/network blip, which matters for a long-lived server process
    but is a no-op for SQLite's file-based connections. Pulled out as a
    pure function so it's testable without a live database of either
    kind."""
    is_sqlite = database_url.startswith("sqlite")
    return {
        "connect_args": {"check_same_thread": False} if is_sqlite else {},
        "pool_pre_ping": not is_sqlite,
    }


engine = create_engine(settings.DATABASE_URL, **build_engine_kwargs(settings.DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
