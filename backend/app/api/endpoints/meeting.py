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
import os

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
    meeting.status = "processing"
    db.commit()
    
    # Background Task 실행
    background_tasks.add_task(process_meeting_summary, meeting.id)
    
    return {"message": "회의록 생성이 요청되었습니다. 잠시 후 확인해주세요."}


@router.post("/{meeting_id}/retry")
def retry_analysis(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의 재분석 요청 (오류 발생 시)
    - 오디오 파일을 다시 STT 처리하고 요약 생성
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다.")
    if meeting.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="권한이 없습니다.")
    
    # 오디오 파일 존재 확인
    if not meeting.audio_file_path or not os.path.exists(meeting.audio_file_path):
        raise HTTPException(status_code=400, detail="오디오 파일을 찾을 수 없습니다.")
    
    # 상태를 processing으로 변경
    meeting.status = "processing"
    db.commit()
    
    # 백그라운드 작업 재시작 (upload.py의 process_audio_file 재사용)
    from app.api.endpoints.upload import process_audio_file
    # 재분석 시작 (sync 래퍼 사용)
    background_tasks.add_task(run_process_audio_file, meeting.id, meeting.audio_file_path)
    
    return {"message": "재분석이 시작되었습니다. 잠시 후 확인해주세요."}


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

    if meeting_in.title is not None and meeting_in.title != meeting.title:
        # 파일명도 변경 (사용자 요청)
        if meeting.audio_file_path:
            import os
            from app.utils import get_unique_filename # 재사용하거나 새로 정의 필요. 일단 간단히 구현
            
            # 절대 경로 보정 (Docker path vs Local path issue handling)
            # audio_file_path가 절대경로가 아닐 수 있음 (/app/media/...)
            old_path = meeting.audio_file_path
            
            # 컨테이너 내부 경로 가정 (/app/)
            # 하지만 여기서 os.path.isabs 체크 후 작업
            # 개발환경이 윈도우라면 c:\... 일 수도 있음.
            # 가장 안전한 건 os.path.exists로 확인되면 진행.
            
            # 1. 파일 존재 확인
            if not os.path.exists(old_path):
                 # 만약 상대경로라면? (media/...)
                 potential_path = os.path.join(os.getcwd(), old_path) 
                 if os.path.exists(potential_path):
                     old_path = potential_path
            
            if os.path.exists(old_path):
                # 2. 새 파일명 생성
                import re
                dir_name = os.path.dirname(old_path)
                file_ext = os.path.splitext(old_path)[1]
                
                # 안전한 파일명 생성
                safe_title = re.sub(r'[\\/*?:"<>|]', "", meeting_in.title)
                safe_title = safe_title.replace(" ", "_")
                new_filename = f"{safe_title}{file_ext}"
                new_path = os.path.join(dir_name, new_filename)
                
                # 3. 이름 충돌 처리 (숫자 붙이기)
                counter = 1
                base_new_path = new_path
                while os.path.exists(new_path) and new_path != old_path:
                    new_path = os.path.join(dir_name, f"{safe_title}_{counter}{file_ext}")
                    counter += 1
                
                # 4. 파일명 변경 및 DB 업데이트
                try:
                    os.rename(old_path, new_path)
                    print(f"Renamed file: {old_path} -> {new_path}")
                    
                    # DB에는 다시 상대 경로로 저장해야 할 수도 있음.
                    # 기존 path가 'media/xxx.mp3' 였다면 새 path도 'media/new_xxx.mp3' 여야 함.
                    
                    # 원래 DB 값이 상대 경로였는지 체크
                    if not os.path.isabs(meeting.audio_file_path):
                        # old_path는 절대경로로 변환되었을 수 있음.
                        # new_path에서 working dir 부분을 떼어내거나, 그냥 new_filename만 남기고
                        # 기존 directory prefix를 붙여야 함.
                        
                        prefix = os.path.dirname(meeting.audio_file_path)
                        meeting.audio_file_path = os.path.join(prefix, os.path.basename(new_path)).replace("\\", "/")
                    else:
                        meeting.audio_file_path = new_path
                        
                except OSError as e:
                    print(f"File rename failed: {e}")
                    # 실패해도 DB 타이틀은 변경 허용 (Silent Fail or Log)
        
        meeting.title = meeting_in.title

    if meeting_in.description is not None:
        meeting.description = meeting_in.description
    if meeting_in.meeting_type is not None:
        meeting.meeting_type = meeting_in.meeting_type
    if meeting_in.meeting_date is not None:
        meeting.meeting_date = meeting_in.meeting_date
    if meeting_in.attendees is not None:
        meeting.attendees = meeting_in.attendees
    if meeting_in.writer is not None:
        meeting.writer = meeting_in.writer
    if meeting_in.status is not None:
        meeting.status = meeting_in.status
    if meeting_in.duration is not None:
        meeting.duration = meeting_in.duration
    
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
