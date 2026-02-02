from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Folder(Base):
    """
    폴더 모델
    
    회의를 그룹화하는 폴더입니다.
    """
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 정의
    owner = relationship("User", back_populates="folders")
    meetings = relationship("Meeting", back_populates="folder")
