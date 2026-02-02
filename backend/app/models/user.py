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
    username = Column(String, index=True) # 사용자 이름 추가
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # 프로필 추가 정보
    age = Column(Integer, nullable=True)
    phone_number = Column(String, nullable=True)
    team_name = Column(String, nullable=True)
    profile_image_path = Column(String, nullable=True)
    # 관계 정의
    meetings = relationship("Meeting", back_populates="owner", cascade="all, delete-orphan")
    folders = relationship("Folder", back_populates="owner", cascade="all, delete-orphan")
