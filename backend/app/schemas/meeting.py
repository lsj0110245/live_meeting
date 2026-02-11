from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from app.schemas.transcript import Transcript as TranscriptSchema

# 공통 속성
class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    meeting_type: Optional[str] = None
    meeting_date: Optional[datetime] = None
    attendees: Optional[str] = None
    writer: Optional[str] = None
    duration: Optional[int] = 0

# 회의 생성 요청 (Create)
class MeetingCreate(MeetingBase):
    pass

# 회의 업데이트 요청 (Update)
class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    meeting_type: Optional[str] = None
    meeting_date: Optional[datetime] = None
    attendees: Optional[str] = None
    writer: Optional[str] = None
    status: Optional[str] = None
    duration: Optional[int] = None

# 요약 조회 응답
class SummarySchema(BaseModel):
    id: int
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 중간 요약 조회 응답
class IntermediateSummarySchema(BaseModel):
    id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

# 회의 조회 응답 (Response)
class Meeting(MeetingBase):
    id: int
    owner_id: int
    created_at: datetime
    status: Optional[str] = "completed"
    audio_file_path: Optional[str] = None
    folder_id: Optional[int] = None # 폴더 ID 추가
    
    # 전사 및 요약 정보 (SQLAlchemy 관계명과 일치시켜야 함)
    transcripts: List[TranscriptSchema] = []
    summary: Optional[SummarySchema] = None
    intermediate_summaries: List[IntermediateSummarySchema] = []
    
    class Config:
        from_attributes = True
