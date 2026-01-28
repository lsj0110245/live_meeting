from pydantic import BaseModel

# 공통 속성
class TranscriptBase(BaseModel):
    segment_index: int
    start_time: float
    end_time: float
    text: str
    speaker: str | None = None

# 전사 생성 요청 (Create)
class TranscriptCreate(TranscriptBase):
    meeting_id: int

# 전사 조회 응답 (Response)
class Transcript(TranscriptBase):
    id: int
    meeting_id: int

    class Config:
        from_attributes = True
