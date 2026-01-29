from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from app.schemas.transcript import Transcript as TranscriptSchema

# 공통 속성
class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None

# 회의 생성 요청 (Create)
class MeetingCreate(MeetingBase):
    pass

# 회의 업데이트 요청 (Update)
class MeetingUpdate(MeetingBase):
    title: Optional[str] = None
    description: Optional[str] = None

# 요약 조회 응답
class SummarySchema(BaseModel):
    id: int
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 회의 조회 응답 (Response)
class Meeting(MeetingBase):
    id: int
    owner_id: int
    created_at: datetime
    status: Optional[str] = "completed"
    audio_file_path: Optional[str] = None
    
    # 전사 및 요약 정보 (SQLAlchemy 관계명과 일치시켜야 함)
    transcripts: List[TranscriptSchema] = []
    summary: Optional[SummarySchema] = None
    
    class Config:
        from_attributes = True
