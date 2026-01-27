from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base

class User(Base):
    """
    사용자 모델
    
    시스템 사용자의 정보를 저장합니다.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    # 관계 정의
    meetings = relationship("Meeting", back_populates="owner", cascade="all, delete-orphan")
