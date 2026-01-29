from datetime import datetime
from pydantic import BaseModel
from typing import Any

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
    status: str | None = "completed"
    audio_file_path: str | None = None
    
    # Nested Models (Lazy Loading resolved by logic or ORM)
    # Circular dependency 방지를 위해 여기서 간단히 정의하거나, API endpoints에서 별도 처리
    # 하지만 response_model=MeetingSchema 로 되어 있으므로 여기서 정의해야 함.
    # Pydantic에서는 ForwardRef 등을 쓸 수 있으나 복잡함.
    # 일단 list[dict]나 Any로 열어두거나, 별도 스키마 정의.
    
    # 간단한 구조체 정의
    # 목록 조회 시에는 이 데이터가 없을 수도 있음 (Lazy Loading)
    # Pydantic이 ORM 객체를 dict로 변환할 수 있도록 typing.Any 사용 또는 별도 모델 정의 필요
    # 여기서는 빠른 해결을 위해 Any 사용 (from typing import Any 필요)
    transcripts: list[Any] | None = []
    summaries: list[Any] | None = []
    
    class Config:
        from_attributes = True
