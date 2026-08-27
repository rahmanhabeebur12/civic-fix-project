from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """Citizen identity. Guest reporting never requires a password — a
    User row is created/reused by mobile number alone (see
    report_pipeline._get_or_create_user). password_hash is nullable and
    only set once a citizen chooses to register/secure that mobile
    number with a password (see routers/auth.py citizen endpoints);
    a guest can "claim" their existing report history this way."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    mobile = Column(String(20), index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
