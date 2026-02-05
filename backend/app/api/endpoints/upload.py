import shutil
import os
import uuid
import hashlib
from typing import Any
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.core.config import settings
from app.models.user import User
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.transcript import Transcript
from app.services.stt_service import stt_service
from app.services.llm_service import llm_service
from app.services.progress_service import progress_service
import asyncio

router = APIRouter()

from app.db.session import SessionLocal

from app.services.meeting_tasks import process_meeting_summary


async def process_audio_file(meeting_id: int, file_path: str):
    """
    백그라운드 작업: 오디오 파일 전사 및 결과 저장
    """
    print(f"🚀 [BG TASK] Started for Meeting ID: {meeting_id}")
    
    db = SessionLocal()
    try:
        # 1. STT 전사 (Local Whisper)
        print(f"🎤 [BG TASK] Starting STT transcription...")
        
        # 진행률 콜백 함수 정의
        def update_progress(percent: int):
            # 0~90%까지만 STT 단계에서 표시 (나머지 10%는 요약 단계 등)
            adjusted_percent = int(percent * 0.9)
            progress_service.set_progress(meeting_id, adjusted_percent)
            # print(f"⏳ [Meeting {meeting_id}] Progress: {adjusted_percent}%") (너무 잦은 로그 방지)

        text = await stt_service.transcribe_file_local(file_path, progress_callback=update_progress)
        
        # STT 완료 시 90%로 설정
        progress_service.set_progress(meeting_id, 90)
        print(f"✅ [BG TASK] Transcription completed. Length: {len(text) if isinstance(text, str) else len(text)} segments")
        
        # 2. 전사 결과 저장 (Transcript)
        # 기존 전사 데이터 삭제 (재분석 시 중복 방지)
        db.query(Transcript).filter(Transcript.meeting_id == meeting_id).delete()
        
        # segments 리스트 순회 저장
        # text가 리스트(세그먼트)로 반환됨 (stt_service 수정됨)
        segments = text if isinstance(text, list) else [{'start': 0.0, 'end': 0.0, 'text': str(text)}]
        
        for idx, seg in enumerate(segments):
            original_text = seg.get('text', '')
            
            # [하이브리드 전략] LLM 문맥 교정 적용
            # 파일 업로드는 실시간성이 덜 중요하므로, 정확도를 위해 모든 세그먼트 교정 시도
            corrected_text = original_text
            if original_text and len(original_text.strip()) > 5: # 너무 짧은 문장은 스킵
                try:
                    # from app.services.llm_service import llm_service # 상단 import 확인 필요
                    corrected_text = await llm_service.correct_transcript(original_text)
                except Exception as e:
                    print(f"Correction failed for segment {idx}: {e}")

            transcript = Transcript(
                meeting_id=meeting_id,
                start_time=seg.get('start', 0.0),
                end_time=seg.get('end', 0.0),
                text=corrected_text,
                speaker="Speaker",
                segment_index=idx
            )
            db.add(transcript)
            
            # 10개마다 커밋하여 진행 상황 저장 (선택 사항)
            if idx % 10 == 0:
                 db.commit()
            
        # 요약 생성을 위한 전체 텍스트 재구성 (stt_service 결과가 리스트이므로)
        full_text_for_summary = "\n".join([s.get('text', '') for s in segments])
        
        # (주의: 아래 4번 단계에서 process_meeting_summary 호출 시 DB에서 다시 읽으므로 여기선 full_text 변수만 준비하면 됨, 
        # 하지만 process_meeting_summary 내부 로직은 DB의 Transcript를 읽어서 합치므로, 여기선 DB 저장만 잘하면 됨.) 
        
        # 3. 회의 상태 업데이트 및 총 재생 시간 저장
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            if segments:
                last_segment = segments[-1]
                duration_seconds = int(last_segment.get('end', 0) + 1) # 올림 처리
                meeting.duration = duration_seconds
                print(f"⏱️ 회의 총 시간 업데이트: {duration_seconds}초")
            
            meeting.status = "completed"
            
        db.commit()
        print(f"💾 [BG TASK] Meeting {meeting_id} transcription completed.")

        # 4. 자동 요약 생성 (90% ~ 100%)
        print(f"🤖 [BG TASK] Starting AI summary...")
        progress_service.set_progress(meeting_id, 95) # 요약 시작
        await process_meeting_summary(meeting_id)
        
        progress_service.set_progress(meeting_id, 100) # 완료
        print(f"✅ [BG TASK] AI summary completed for Meeting {meeting_id}")
        
    except Exception as e:
        print(f"❌ [BG TASK ERROR] Meeting {meeting_id}: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        # 에러 상태 업데이트
        try:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting:
                meeting.status = "error"
                db.commit()
        except:
            pass
    finally:
        db.close()
        print(f"🏁 [BG TASK] Ended for Meeting ID: {meeting_id}")

router = APIRouter()

@router.post("/file", status_code=201)
async def upload_file(
    *,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    title: str = Form(...),  # 회의명 (필수)
    meeting_type: str | None = Form(None),  # 회의유형 (선택)
    meeting_date: str | None = Form(None),  # ISO format string expected (선택)
    attendees: str | None = Form(None),  # 참석자 (선택)
    writer: str = Form(...),  # 작성자 (필수)
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    오디오 파일 업로드 및 STT 처리 요청
    """
    # ... (existing validation code) ...
    
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
        is_duplicate = True
        file_path = existing_meeting.audio_file_path  # 기존 파일 경로 사용
        # Note: We don't update metadata for existing meetings to avoid overwriting user history unintentionally
        # unless specifically requested. For now, just return existing.
        meeting = existing_meeting
        
    else:
        # 신규 파일(또는 DB에는 있지만 실제 파일이 없는 경우): 저장
        upload_dir = settings.MEDIA_ROOT / "recordings" / "audio"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        safe_filename = f"{uuid.uuid4()}.{ext}"
        # 실제 저장 경로는 절대 경로 사용
        abs_file_path = upload_dir / safe_filename
        file_path = str(abs_file_path)
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            is_duplicate = False
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"파일 저장 실패: {str(e)}")
        finally:
            file.file.close()

        # 4. Meeting 레코드 생성 (file_hash 포함)
        from datetime import datetime
        parsed_date = None
        if meeting_date:
            try:
                parsed_date = datetime.fromisoformat(meeting_date.replace('Z', '+00:00'))
            except:
                pass # Fail silently or handle error

        from app.utils import get_unique_title
        
        # 제목 중복 처리
        safe_title = get_unique_title(db, title)

        meeting = Meeting(
            title=safe_title,  # 중복 처리된 제목 사용
            owner_id=current_user.id,
            audio_file_path=f"media/recordings/audio/{safe_filename}", # DB에는 서빙용 상대 경로 저장
            file_hash=file_hash,
            description="파일 업로드된 회의",
            meeting_type=meeting_type,
            meeting_date=parsed_date,
            attendees=attendees,
            writer=writer,
            status="processing"  # 처리 중 상태로 시작
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
    
    # 5. Background Task로 STT 서비스 호출 (중복 여부와 관계없이 항상 실행)
    print(f"📋 [UPLOAD] Scheduling background task for Meeting ID: {meeting.id}")
    background_tasks.add_task(run_process_audio_file, meeting.id, file_path)
    
    return {
        "meeting_id": meeting.id,
        "filename": filename,
        "status": "uploaded",
        "is_duplicate": is_duplicate, 
        "message": "기존 파일을 재사용합니다." if is_duplicate else "파일이 성공적으로 업로드되었습니다."
    }
@router.post("/recording/{meeting_id}/finalize")
async def finalize_recording(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    실시간 녹음 종료 후 완성된 오디오 파일을 업로드하여 기존 파일을 교체하고,
    고품질 전사를 위해 Whisper로 전체 재분석을 수행합니다.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.owner_id == current_user.id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # 파일 확장자 및 타입 체크
    if not file.filename.endswith(('.webm', '.wav', '.mp3')):
        raise HTTPException(status_code=400, detail="Invalid audio format")

    try:
        # 파일 저장 경로
        filename = f"realtime_{meeting_id}.webm"
        file_path = settings.MEDIA_ROOT / filename
        
        # 실제 파일 시스템에 쓰기 (기존 조각 파일 덮어쓰기)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"✅ [Finalize] Audio file for meeting {meeting_id} saved. Starting re-transcription...")
        
        # DB 업데이트 및 상태를 'processing'으로 변경 (재분석 중임을 표시)
        meeting.audio_file_path = f"media/{filename}"
        meeting.status = "processing"
        db.commit()

        # [고도화 하이브리드] Whisper 엔진을 이용한 전체 오디오 정밀 재분석 시작
        background_tasks.add_task(run_process_audio_file, meeting_id, str(file_path))
        
        return {"status": "success", "message": "Recording finalized, re-transcription started"}
    except Exception as e:
        print(f"❌ [Finalize] Failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
