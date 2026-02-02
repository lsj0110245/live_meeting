import shutil
import os
import uuid
import hashlib
from typing import Any
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.core.config import settings
from app.models.user import User
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.services.stt_service import stt_service
import asyncio

router = APIRouter()

from app.db.session import SessionLocal

from app.services.meeting_tasks import process_meeting_summary

async def process_audio_file(meeting_id: int, file_path: str):
    """
    백그라운드 작업: 오디오 파일 전사 및 결과 저장
    """
    db = SessionLocal()
    try:
        # 1. STT 전사 (Local Whisper)
        text = await stt_service.transcribe_file_local(file_path)
        
        # 2. 전사 결과 저장 (Transcript)
        # 통짜 텍스트로 저장 (Whisper JSON 결과 파싱해서 세그먼트 나누는 것은 추후 고도화)
        transcript = Transcript(
            meeting_id=meeting_id,
            start_time=0.0,
            end_time=0.0, # 전체 길이는 오디오 메타데이터 필요
            text=text,
            speaker="Speaker",
            segment_index=0 # 통짜 텍스트이므로 0번 세그먼트로 지정
        )
        db.add(transcript)
        
        # 3. 회의 상태 업데이트
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = "completed"
            
        db.commit()
        print(f"Meeting {meeting_id} transcription completed.")

        # 4. (추가) 자동 요약 생성
        # 전사 완료 후 바로 요약 생성 작업 시작
        await process_meeting_summary(meeting_id)
        
    except Exception as e:
        print(f"Transcription failed for meeting {meeting_id}: {str(e)}")
        # 에러 상태 업데이트 로직 추가 가능
    finally:
        db.close()

router = APIRouter()

@router.post("/file", status_code=201)
async def upload_file(
    *,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    오디오 파일 업로드 및 STT 처리 요청
    
    1. 파일 확장자 검증
    2. 파일 해시(SHA-256) 계산
    3. 중복 확인: 동일한 해시가 있으면 기존 파일 재사용
    4. 신규 파일이면 로컬 스토리지(media/recordings/audio)에 저장
    5. Meeting DB 레코드 생성
    6. 비동기 백그라운드 작업으로 STT 요청
    """
    
    # 1. 파일 확장자 검증
    filename = file.filename
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. (허용: {settings.ALLOWED_EXTENSIONS})",
        )
    
    # 2. 파일 해시 계산 (SHA-256)
    file_content = await file.read()
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    # 파일 포인터를 처음으로 되돌림 (저장을 위해)
    await file.seek(0)
    
    # 3. 중복 확인
    existing_meeting = db.query(Meeting).filter(Meeting.file_hash == file_hash).first()
    
    if existing_meeting and os.path.exists(existing_meeting.audio_file_path):
        # 중복 파일: 기존 파일 경로 재사용 (실제 파일이 존재하는 경우에만)
        file_path = existing_meeting.audio_file_path
        print(f"중복 파일 감지: {file_hash[:16]}... 기존 파일 재사용: {file_path}")
        is_duplicate = True
    else:
        # 신규 파일(또는 DB에는 있지만 실제 파일이 없는 경우): 저장
        upload_dir = "media/recordings/audio"
        os.makedirs(upload_dir, exist_ok=True)
        
        safe_filename = f"{uuid.uuid4()}.{ext}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            print(f"신규 파일 저장: {file_path}")
            is_duplicate = False
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"파일 저장 실패: {str(e)}")
        finally:
            file.file.close()

    # 4. Meeting 레코드 생성 (file_hash 포함)
    meeting = Meeting(
        title=filename,
        owner_id=current_user.id,
        audio_file_path=file_path,
        file_hash=file_hash,  # 해시값 저장
        description="파일 업로드된 회의"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    
    # 5. Background Task로 STT 서비스 호출 (중복이어도 전사는 수행)
    background_tasks.add_task(process_audio_file, meeting.id, file_path)
    
    return {
        "meeting_id": meeting.id,
        "filename": filename,
        "status": "uploaded",
        "is_duplicate": is_duplicate,
        "message": "기존 파일을 재사용합니다. 분석이 곧 시작됩니다." if is_duplicate else "파일이 성공적으로 업로드되었습니다. 분석이 곧 시작됩니다."
    }
