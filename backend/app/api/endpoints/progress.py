
from fastapi import APIRouter
from app.services.progress_service import progress_service

router = APIRouter()

@router.get("/{meeting_id}")
async def get_progress(meeting_id: int):
    """
    회의 분석 진행률(%) 조회
    """
    percent = progress_service.get_progress(meeting_id)
    return {"progress": percent}
