from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True)
    complaint_id = Column(String(30), nullable=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    notif_type = Column(String(40), default="status_update")
    channel = Column(String(20), default="in_app")  # in_app | sms | whatsapp | email | push (future)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
