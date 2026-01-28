from datetime import datetime
from pydantic import BaseModel

# 공통 속성
class MeetingBase(BaseModel):
    title: str
    description: str | None = None

# 회의 생성 요청 (Create)
class MeetingCreate(MeetingBase):
    pass

# 회의 업데이트 요청 (Update)
class MeetingUpdate(MeetingBase):
    title: str | None = None
    description: str | None = None

# 회의 조회 응답 (Response)
class Meeting(MeetingBase):
    id: int
    owner_id: int
    created_at: datetime
    # 전사 및 요약 정보 포함 (Lazy Loading 주의 -> Eager Loading 필요)
    status: str | None = "completed" # status 필드 추가 (DB 모델에도 있어야 함)
    audio_file_path: str | None = None
    
    class Config:
        from_attributes = True
