from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Resolution(Base):
    __tablename__ = "resolutions"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    officer_username = Column(String(60), nullable=False)
    image_path = Column(String(255), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    citizen_confirmed = Column(Boolean, nullable=True)  # None = pending, True = fixed, False = reopened
    citizen_feedback = Column(Text, default="")
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    issue = relationship("Issue", back_populates="resolutions")
