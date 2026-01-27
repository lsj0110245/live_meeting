from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

class Transcript(Base):
    """
    전사(Transcript) 모델
    
    회의의 음성을 텍스트로 변환한 세그먼트 데이터를 저장합니다.
    """
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    segment_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    speaker = Column(String, nullable=True)
    
    # 관계 정의
    meeting = relationship("Meeting", back_populates="transcripts")
