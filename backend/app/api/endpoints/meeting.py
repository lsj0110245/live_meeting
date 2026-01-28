from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.summary import Summary
from app.models.user import User
from app.schemas.meeting import Meeting as MeetingSchema, MeetingCreate, MeetingUpdate
from app.services.llm_service import llm_service
import asyncio

router = APIRouter()

async def process_meeting_summary(meeting_id: int, db: Session):
    """
    백그라운드 작업: 회의록 생성 및 저장
    """
    try:
        # 1. 전사 데이터 조회
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        transcripts = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).order_by(Transcript.start_time).all()
        
        if not transcripts:
            print(f"전사 데이터가 없습니다. 회의 ID: {meeting_id}")
            return

        # 전사 텍스트 합치기
        full_text = "\n".join([f"{t.speaker}: {t.text}" for t in transcripts])
        
        # 2. LLM 요약 생성
        print(f"회의록 생성 중... 회의 ID: {meeting_id}")
        summary_text = await llm_service.generate_summary(meeting.title, full_text)
        
        # 3. 요약 결과 저장 (Summary)
        summary = Summary(
            meeting_id=meeting_id,
            summary_type="final",
            content=summary_text,
            # key_points, action_items 등은 추후 JSON 파싱 구현 시 추가
        )
        db.add(summary)
        db.commit()
        print(f"회의록 생성 완료. 회의 ID: {meeting_id}")
        
    except Exception as e:
        print(f"회의록 생성 실패. 회의 ID: {meeting_id}, 오류: {str(e)}")

router = APIRouter()

@router.get("/", response_model=List[MeetingSchema])
def read_meetings(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의 목록 조회 (내 회의만)
    """
    meetings = (
        db.query(Meeting)
        .filter(Meeting.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return meetings


@router.get("/{meeting_id}", response_model=MeetingSchema)
def read_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의 상세 조회
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다.")
    if meeting.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="권한이 없습니다.")
    return meeting


@router.post("/", response_model=MeetingSchema)
def create_meeting(
    *,
    db: Session = Depends(get_db),
    meeting_in: MeetingCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    새로운 회의 생성 (수동 시작)
    """
    meeting = Meeting(
        title=meeting_in.title,
        description=meeting_in.description,
        owner_id=current_user.id
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@router.post("/{meeting_id}/summarize")
def generate_summary(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의록(요약) 생성 요청
    - LLM 서비스 호출 (Async)
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다.")
    if meeting.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="권한이 없습니다.")
        
    # Background Task로 LLM 서비스 호출 (Llama 3)
    background_tasks.add_task(process_meeting_summary, meeting.id, db)
    
    return {"message": "회의록 생성이 요청되었습니다. 잠시 후 확인해주세요."}
