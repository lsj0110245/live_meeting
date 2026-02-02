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
from typing import Any, List
import asyncio

router = APIRouter()

from app.db.session import SessionLocal

from app.services.meeting_tasks import process_meeting_summary

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
        .order_by(Meeting.id.desc())
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
        meeting_type=meeting_in.meeting_type,
        meeting_date=meeting_in.meeting_date,
        attendees=meeting_in.attendees,
        writer=meeting_in.writer,
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
    background_tasks.add_task(process_meeting_summary, meeting.id)
    
    return {"message": "회의록 생성이 요청되었습니다. 잠시 후 확인해주세요."}


@router.put("/{meeting_id}", response_model=MeetingSchema)
def update_meeting(
    meeting_id: int,
    meeting_in: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의 정보 수정 (제목 등)
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다.")
    if meeting.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="권한이 없습니다.")

    if meeting_in.title is not None:
        meeting.title = meeting_in.title
    if meeting_in.description is not None:
        meeting.description = meeting_in.description

    db.commit()
    db.refresh(meeting)
    return meeting


@router.delete("/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의 삭제
    - DB 데이터 삭제 (Cascade로 관련 데이터 자동 삭제)
    - 연결된 미디어 파일 삭제
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다.")
    if meeting.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="권한이 없습니다.")

    # 파일 삭제 시도
    if meeting.audio_file_path:
        import os
        # Docker 환경 경로 고려 (/app/...)
        # meeting.audio_file_path는 DB에 저장된 상대 경로일 수도 있고 절대 경로일 수도 있음.
        # 저장 로직을 확인해보면 "media/filename" 형태로 저장되는지 확인 필요하나, 
        # 일단 절대 경로로 간주하거나 working directory 기준 상대 경로로 처리 시도.
        
        # main.py에서 BASE_DIR 설정 등을 참고하여 실제 파일 경로 추론
        # 여기선 안전하게 절대 경로 처리를 위해 로직 추가보다는 os.remove 시도
        
        # NOTE: DB에 어떻게 저장되는지 확인하지 못했으므로, 
        # 만약 "media/xxx.mp3"로 저장된다면 현재 작업 디렉토리(backend) 기준인지 확인 필요.
        # Docker volume 매핑: ./media:/app/media
        # Python working dir: /app
        # 따라서 "media/xxx.mp3"라면 os.path.join("/app", meeting.audio_file_path) 일 것임.
        
        file_path = meeting.audio_file_path
        
        # 만약 절대 경로가 아니라면 /app/ (또는 현재 workdir)를 붙여줌
        if not os.path.isabs(file_path):
             file_path = os.path.join("/app", file_path) # Docker 내부 경로 기준

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
            else:
                 print(f"File not found, skipping delete: {file_path}")
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    db.delete(meeting)
    db.commit()
    
    db.delete(meeting)
    db.commit()
    
    return {"message": "회의가 삭제되었습니다."}

@router.delete("/")
def bulk_delete_meetings(
    meeting_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    여러 회의 일괄 삭제
    """
    meetings = db.query(Meeting).filter(Meeting.id.in_(meeting_ids), Meeting.owner_id == current_user.id).all()
    
    deleted_count = 0
    import os
    
    for meeting in meetings:
        # 파일 삭제 logic
        if meeting.audio_file_path:
            file_path = meeting.audio_file_path
            if not os.path.isabs(file_path):
                 file_path = os.path.join("/app", file_path)
            
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")
        
        db.delete(meeting)
        deleted_count += 1
        
    db.commit()
    return {"message": f"{deleted_count}개의 회의가 삭제되었습니다."}
