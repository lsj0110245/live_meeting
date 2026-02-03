from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class IntermediateSummary(Base):
    """
    중간 요약(Intermediate Summary) 모델
    
    실시간 녹음 중 생성되는 중간 요약본을 저장합니다. (Meeting과 1:N 관계)
    """
    __tablename__ = "intermediate_summaries"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 정의
    meeting = relationship("Meeting", back_populates="intermediate_summaries")
