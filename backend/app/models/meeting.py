from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Meeting(Base):
    """
    회의 모델
    
    개별 회의의 메타데이터와 상태를 저장합니다.
    """
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    audio_file_path = Column(String, nullable=True) # 오디오 파일 경로 추가
    status = Column(String, default="pending") # 회의 상태 (pending, processing, completed)
    
    # 관계 정의
    owner = relationship("User", back_populates="meetings")
    transcripts = relationship("Transcript", back_populates="meeting", cascade="all, delete-orphan")
    summary = relationship("Summary", uselist=False, back_populates="meeting", cascade="all, delete-orphan")
