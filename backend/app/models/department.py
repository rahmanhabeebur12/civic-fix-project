from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False)
    code = Column(String(40), unique=True, nullable=False)
    description = Column(Text, default="")
