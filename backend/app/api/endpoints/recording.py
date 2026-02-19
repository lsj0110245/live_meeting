"""
실시간 녹음 및 STT WebSocket 엔드포인트
"""

import io
import json
from typing import List, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.api import deps
from app.models.user import User
from app.services.stt_service import stt_service
from app.services.llm_service import llm_service
from app.models.transcript import Transcript
from app.models.meeting import Meeting
from app.models.summary import Summary
from app.models.enums import MeetingStatus
import time
import asyncio

import threading
import os
import subprocess # FFmpeg 호출용

# [Optimization] DB 작업을 위한 동기 헬퍼 함수들 (스레드 풀에서 실행)
_model_lock = threading.Lock() # 모델 로딩용 전역 락

def _repair_audio_duration_sync(file_path: str):
    """FFmpeg를 사용하여 오디오 파일의 Duration 정보를 복구 (Remuxing)"""
    if not file_path or not os.path.exists(file_path):
        return
    
    try:
        dir_name = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        temp_path = os.path.join(dir_name, f"temp_{file_name}")
        
        # FFmpeg 명령: 재인코딩 없이(-c copy) 컨테이너만 재생성하여 헤더 복구
        # -y: 덮어쓰기 허용
        cmd = [
            "ffmpeg", "-y", 
            "-i", file_path, 
            "-c", "copy", 
            temp_path
        ]
        
        # subprocess 실행
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0 and os.path.exists(temp_path):
            # 성공 시 원본 교체
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_path, file_path)
            print(f"[Audio Repair] Successfully repaired duration for {file_name}")
        else:
            print(f"[Audio Repair] FFmpeg failed: {result.stderr}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        print(f"[Audio Repair] Exception: {e}")


def _write_audio_sync(path: str, chunk: bytes):
    """파일 쓰기 작업을 별도 스레드에서 수행 (Blocking 방지)"""
    try:
        with open(path, "ab") as f:
            f.write(chunk)
    except Exception as e:
        print(f"Audio write failed: {e}")

def _update_transcript_db_sync(tid: int, corrected_text: str):
    """자막 교정 내용을 DB에 업데이트 (동기)"""
    db = SessionLocal()
    try:
        t_item = db.query(Transcript).filter(Transcript.id == tid).first()
        if t_item:
            t_item.text = corrected_text
            db.commit()
    except Exception as e:
        print(f"DB Update Error (Transcript): {e}")
    finally:
        db.close()

def _update_meeting_duration_sync(mid: int, duration: int):
    """회의 시간 업데이트 (동기)"""
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == mid).first()
        if meeting:
            meeting.duration = duration
            db.commit()
    except Exception as e:
        print(f"DB Update Error (Duration): {e}")
    finally:
        db.close()

def _save_summary_and_metadata_sync(mid: int, summary_json: dict):
    """요약 및 메타데이터 저장 및 완료 처리 (동기)"""
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == mid).first()
        if not meeting:
            return

        # 1. 메타데이터 업데이트
        metadata = summary_json.get("metadata", {})
        updated = False
        if meeting.title.startswith("실시간 회의") and metadata.get("title_suggestion"):
            meeting.title = metadata["title_suggestion"]
            updated = True
        if not meeting.meeting_type and metadata.get("meeting_type"):
            meeting.meeting_type = metadata["meeting_type"]
            updated = True
        if not meeting.attendees and metadata.get("attendees"):
            meeting.attendees = metadata["attendees"]
            updated = True
        
        # 2. 상태 완료 처리
        meeting.status = MeetingStatus.COMPLETED
        updated = True
        
        if updated:
            db.commit()
            print(f"Meeting {mid} status updated to COMPLETED.")

        # 3. 요약 저장
        if "summary" in summary_json:
            s_data = summary_json["summary"]
            
            # 필드들을 하나의 마크다운 문서로 합침
            formatted_parts = []
            final_title = metadata.get("title_suggestion", meeting.title)
            formatted_parts.append(f"# {final_title} 회의록\n")
            
            if s_data.get("purpose"):
                formatted_parts.append(f"{s_data['purpose']}")
            if s_data.get("content"):
                formatted_parts.append(f"\n{s_data['content']}")
            if s_data.get("conclusion"):
                formatted_parts.append(f"\n{s_data['conclusion']}")
            if s_data.get("action_items"):
                formatted_parts.append(f"\n{s_data['action_items']}")
            
            summary_content = "\n".join(formatted_parts)
            
            existing = db.query(Summary).filter(Summary.meeting_id == mid).first()
            if existing:
                existing.content = summary_content
            else:
                db.add(Summary(meeting_id=mid, content=summary_content))
            db.commit()
            print(f"Final structured summary saved for meeting {mid}.")
            
    except Exception as e:
        print(f"DB Update Error (Summary): {e}")
    finally:
        db.close()

def _force_complete_meeting_sync(mid: int):
    """에러 발생 시 강제로 완료 처리 (동기)"""
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == mid).first()
        if meeting and meeting.status != MeetingStatus.COMPLETED:
            meeting.status = MeetingStatus.COMPLETED
            db.commit()
            print(f"Meeting {mid} forced to COMPLETED after error.")
    except Exception as e:
        print(f"DB Force Complete Error: {e}")
    finally:
        db.close()

router = APIRouter()


class RealtimeSession:
    """실시간 STT 세션 관리"""
    def __init__(self, websocket: WebSocket, user: User):
        self.websocket = websocket
        self.user = user
        self.audio_buffer = io.BytesIO()
        self.buffer_duration = 0  # 초 단위
        self.transcript_history: List[str] = []
        self.metadata = None  # 회의 메타데이터 저장
        self.meeting_id = None  # 생성된 Meeting ID
        self.last_summary_time = time.time() # 마지막 요약 시간
        self.transcript_since_last_summary: List[str] = [] # 마지막 요약 이후 쌓인 텍스트
        self.segment_index = 0  # 전사 세그먼트 인덱스
        self.header_bytes = None # WebM 헤더 저장용
        self.audio_path = None # 오디오 파일 경로
        self.total_duration = 0.0 # 누적 전체 시간 (초)
        self.is_finalized = False # 최종 요약 완료 여부 (중복 방지)
        self.is_first_segment = True # 첫 번째 전사 구간 여부
        self.is_resume_session = False # 이어서 녹음 세션 여부
        self.original_audio_path = None # 이어서 녹음 시 기존 오디오 파일 경로
        
    def add_audio_chunk(self, chunk: bytes, chunk_duration: float = 0.5):
        """오디오 청크 추가"""
        if self.header_bytes is None:
            # 첫 청크는 WebM의 EBML 헤더를 포함함
            self.header_bytes = chunk 
            
        self.audio_buffer.write(chunk)
        self.buffer_duration += chunk_duration
        self.total_duration += chunk_duration
        
    def get_buffer_and_reset(self) -> tuple[bytes, bool]:
        """버퍼 데이터 반환 및 초기화 (데이터, 헤더스킵필요여부)"""
        current_data = self.audio_buffer.getvalue()
        skip_header = False
        
        if self.header_bytes:
            if self.is_first_segment:
                # 첫 세그먼트는 헤더가 이미 포함되어 있음
                data_to_process = current_data
                self.is_first_segment = False
            else:
                # 두 번째부터는 헤더를 붙여주되, 전사 시 중복 방지를 위해 스킵 표시
                data_to_process = self.header_bytes + current_data
                skip_header = True
        else:
            data_to_process = current_data

        self.audio_buffer = io.BytesIO()
        self.buffer_duration = 0
        return data_to_process, skip_header
    
    def add_transcript(self, text: str):
        """전사 결과 기록"""
        if text.strip():
            self.transcript_history.append(text)
            self.transcript_since_last_summary.append(text)
    
    def get_recent_transcript_and_reset(self) -> str:
        """최근(마지막 요약 이후) 전사 결과 반환 및 초기화"""
        text = " ".join(self.transcript_since_last_summary)
        self.transcript_since_last_summary = []
        return text
    
    def get_full_transcript(self) -> str:
        """전체 전사 결과 반환"""
        return " ".join(self.transcript_history)


class ConnectionManager:
    """WebSocket 연결 관리자"""
    def __init__(self):
        self.active_sessions: Dict[str, RealtimeSession] = {}
        self.disconnected_clients: set = set()  # 연결이 끊긴 클라이언트 추적

    async def connect(self, client_id: str, websocket: WebSocket, user: User):
        await websocket.accept()
        self.active_sessions[client_id] = RealtimeSession(websocket, user)
        # 재연결 시 disconnected에서 제거
        if client_id in self.disconnected_clients:
            self.disconnected_clients.remove(client_id)

    def disconnect(self, client_id: str):
        if client_id in self.active_sessions:
            del self.active_sessions[client_id]
        self.disconnected_clients.add(client_id)

    def get_session(self, client_id: str) -> RealtimeSession:
        return self.active_sessions.get(client_id)
    
    def is_connected(self, client_id: str) -> bool:
        """클라이언트 연결 상태 확인"""
        return client_id in self.active_sessions and client_id not in self.disconnected_clients

    async def send_json(self, client_id: str, data: dict) -> bool:
        """JSON 전송 시도, 성공 여부 반환"""
        session = self.active_sessions.get(client_id)
        if session:
            try:
                await session.websocket.send_json(data)
                return True
            except RuntimeError as e:
                # 이미 연결이 끊긴 경우
                print(f"[WebSocket] Send failed (RuntimeError): {e}")
                self.disconnected_clients.add(client_id)
                return False
            except Exception as e:
                print(f"[WebSocket] Send failed: {e}")
                self.disconnected_clients.add(client_id)
                return False
        return False



manager = ConnectionManager()

# 버퍼링 설정
BUFFER_THRESHOLD_SECONDS = 5  # 5초마다 전사


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...)
):
    """
    실시간 STT WebSocket 엔드포인트
    """
    from app.db.session import SessionLocal
    
    print(f"[WebSocket] Connection attempt from client: {client_id}")
    
    # 1. 인증 검증
    # 인증을 위해 일시적으로 DB 세션 사용
    auth_db = SessionLocal()
    user = None
    try:
        user = deps.get_current_user(auth_db, token=token)
    except Exception as e:
        print(f"[WebSocket] Authentication failed for {client_id}: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    finally:
        auth_db.close()

    try:
        await manager.connect(client_id, websocket, user)
        session = manager.get_session(client_id)
        print(f"[WebSocket] Client {client_id} connected successfully.")
        
        # [Pre-warm] 연결 즉시 STT 모델 미리 로드 (백그라운드)
        # 첫 5초 데이터가 수집되는 동안 모델을 미리 GPU에 올려 지연을 최소화함
        asyncio.create_task(asyncio.to_thread(stt_service.initialize_model))
        
    except Exception as e:
        print(f"[WebSocket] Connection failed: {e}")
        return
    
    try:
        # 연결 성공 알림
        await manager.send_json(client_id, {
            "type": "connected",
            "message": f"실시간 STT 연결됨: {user.email}"
        })

        # --- 내부 비동기 태스크 정의 (Hoisting 대응) ---
        
        # 1. LLM 교정 태스크
        async def background_correction_task(tid: int, original_text: str, cid: str):
            try:
                corrected = await llm_service.correct_transcript(original_text)
                if corrected and corrected != original_text:
                    await asyncio.to_thread(_update_transcript_db_sync, tid, corrected)
                    if manager.is_connected(cid):
                        await manager.send_json(cid, {
                            "type": "transcript_update",
                            "transcript_id": tid,
                            "text": corrected
                        })
            except Exception as e:
                print(f"Background correction failed: {e}")

        # 2. 중간 요약 태스크
        async def background_summary_task(text, mid, cid):
            try:
                summary = await llm_service.generate_simple_summary(text)
                if summary and summary.strip():
                    await manager.send_json(cid, {
                        "type": "intermediate_summary",
                        "content": summary
                    })
                    db_context = SessionLocal()
                    try:
                        from app.models.intermediate_summary import IntermediateSummary
                        new_is = IntermediateSummary(meeting_id=mid, content=summary)
                        db_context.add(new_is)
                        db_context.commit()
                    except Exception as e:
                        db_context.rollback()
                        print(f"Background intermediate summary DB save failed: {e}")
                    finally:
                        db_context.close()
            except Exception as e:
                print(f"Background intermediate summary task failed: {e}")

        # 3. 최종 정리 및 요약 태스크
        async def final_cleanup_and_summary(mid, duration, s_obj):
            if s_obj.is_finalized: return
            s_obj.is_finalized = True
            
            print(f"[Background Task] Starting final summary for meeting {mid}...")
            try:
                # [Fix] 오디오 파일 헤더(Duration) 갱신 (FFmpeg)
                # 이어서 녹음 세션은 클라이언트의 concat-resume 업로드가 처리하므로 여기서는 skip
                if s_obj.audio_path and not s_obj.is_resume_session:
                    print(f"[Background Task] Repairing audio duration for {s_obj.audio_path}...")
                    await asyncio.to_thread(_repair_audio_duration_sync, s_obj.audio_path)
                elif s_obj.is_resume_session:
                    print(f"[Background Task] Resume session: audio repair deferred to concat-resume endpoint.")

                await asyncio.to_thread(_update_meeting_duration_sync, mid, int(duration))
                from app.services.meeting_tasks import process_meeting_summary
                await process_meeting_summary(mid)
            except Exception as e:
                print(f"Final cleanup task failed: {e}")
                await asyncio.to_thread(_force_complete_meeting_sync, mid)

        # 4. 남은 버퍼 처리 태스크 (Helper)
        async def process_remaining_buffer():
            if session.buffer_duration > 0:
                print(f"[WebSocket] Processing remaining buffer ({session.buffer_duration:.1f}s) for Meeting {session.meeting_id}")
                audio_data, skip_header = session.get_buffer_and_reset()
                try:
                    last_transcript = await stt_service.transcribe_realtime(
                        audio_data,
                        skip_duration_ms=500 if skip_header else 0
                    )
                    if last_transcript.strip():
                        session.add_transcript(last_transcript)
                        # DB 저장
                        from app.models.transcript import Transcript
                        db_cleanup = SessionLocal()
                        try:
                            t_record = Transcript(
                                meeting_id=session.meeting_id,
                                text=last_transcript,
                                speaker="Unknown",
                                start_time=max(0, session.total_duration - session.buffer_duration),
                                end_time=session.total_duration,
                                segment_index=session.segment_index
                            )
                            db_cleanup.add(t_record)
                            db_cleanup.commit()
                            db_cleanup.refresh(t_record)
                            
                            print(f"[STT] Final transcript saved: {last_transcript[:30]}...")

                            # 클라이언트에 마지막 전사 결과 전송 시도
                            if manager.is_connected(client_id):
                                await manager.send_json(client_id, {
                                    "type": "transcript",
                                    "transcript_id": t_record.id,
                                    "text": last_transcript,
                                    "is_final": True
                                })
                        finally:
                            db_cleanup.close()
                except Exception as e:
                    print(f"Failed to transcribe final chunk: {e}")

        # --- 루프 시작 ---
        while True:
            # 데이터 수신 (bytes 또는 text)
            try:
                try:
                    # 먼저 텍스트로 받아보기 (메타데이터 메시지인 경우)
                    data = await websocket.receive()
                except RuntimeError:
                    # 연결이 이미 닫힌 경우
                    break
                
                if "text" in data:
                    # JSON 메타데이터 메시지
                    message = json.loads(data["text"])
                    
                    if message.get("type") == "stop_recording":
                        # 사용자가 명시적으로 '중지'를 누른 경우
                        if session.meeting_id:
                            print(f"[WebSocket] Stop recording requested for Meeting {session.meeting_id}")
                            
                            # [Fix] 잔여 버퍼 처리
                            await process_remaining_buffer()

                            # 즉시 최종 처리 태스크 실행
                            asyncio.create_task(final_cleanup_and_summary(session.meeting_id, session.total_duration, session))
                        continue

                    if message.get("type") == "metadata":
                        # 메타데이터 저장 및 Meeting 생성 (또는 기존 회의 불러오기)
                        from app.models.meeting import Meeting
                        from datetime import datetime
                        
                        db_meta = SessionLocal()
                        try: 
                            metadata = message.get("data", {})
                            session.metadata = metadata
                            
                            # [이어서 녹음하기] meeting_id가 전달된 경우 기존 회의 사용
                            existing_mid = metadata.get("meeting_id")
                            if existing_mid:
                                meeting = db_meta.query(Meeting).filter(Meeting.id == existing_mid, Meeting.owner_id == user.id).first()
                                if meeting:
                                    session.meeting_id = meeting.id
                                    # 기존 녹음 시간 불러오기 (자막 타임라인 연속성 확보)
                                    session.total_duration = float(meeting.duration or 0.0)
                                    
                                    # 기존 자막 인덱스 다음부터 시작
                                    from app.models.transcript import Transcript
                                    transcript_count = db_meta.query(Transcript).filter(Transcript.meeting_id == meeting.id).count()
                                    session.segment_index = transcript_count
                                    
                                    # [이어서 녹음] 임시 파일에 별도 저장 (기존 파일 corruption 방지)
                                    from app.core.config import settings
                                    import time as _time
                                    session.is_resume_session = True
                                    if meeting.audio_file_path:
                                        if meeting.audio_file_path.startswith("media/"):
                                            abs_file_path = settings.MEDIA_ROOT / meeting.audio_file_path.replace("media/", "", 1)
                                        else:
                                            abs_file_path = Path(meeting.audio_file_path)
                                        session.original_audio_path = str(abs_file_path)
                                    # 이어서 녹음 세션은 별도 임시 파일에 저장
                                    resume_filename = f"realtime_{meeting.id}_resume_{int(_time.time())}.webm"
                                    session.audio_path = str(settings.MEDIA_ROOT / resume_filename)
                                    print(f"[Resume] Audio will be saved to temp file: {resume_filename}")
                                    
                                    # 상태를 다시 RECORDING으로 변경
                                    meeting.status = MeetingStatus.RECORDING
                                    db_meta.commit()
                                    
                                    print(f"Resuming Meeting: ID={meeting.id}, Title={meeting.title}")
                                    await manager.send_json(client_id, {
                                        "type": "meeting_created", # 클라이언트 호환성을 위해 동일 타입 사용
                                        "meeting_id": meeting.id,
                                        "is_resumed": True
                                    })
                                    continue

                            # 기존 로직: 신규 회의 생성
                            from app.utils import get_unique_title
                            
                            raw_title = metadata.get("title", "제목 없음")
                            safe_title = get_unique_title(db_meta, raw_title)
                            
                            meeting = Meeting(
                                title=safe_title,
                                description="실시간 녹음",
                                meeting_type=metadata.get("meeting_type"),
                                meeting_date=datetime.fromisoformat(metadata.get("meeting_date").replace("Z", "+00:00")) if metadata.get("meeting_date") else datetime.now(),
                                attendees=metadata.get("attendees"),
                                writer=metadata.get("writer"),
                                owner_id=user.id,
                                status=MeetingStatus.RECORDING
                            )
                            db_meta.add(meeting)
                            db_meta.commit()
                            db_meta.refresh(meeting)
                            
                            session.meeting_id = meeting.id
                            print(f"Meeting created: ID={meeting.id}, Title={meeting.title}")
                            
                            # 오디오 파일 경로 설정 및 저장
                            from app.core.config import settings
                            media_root = settings.MEDIA_ROOT
                            media_root.mkdir(parents=True, exist_ok=True)
                            
                            file_filename = f"realtime_{meeting.id}.webm"
                            relative_path = f"media/{file_filename}"
                            meeting.audio_file_path = relative_path
                            db_meta.commit()
                            
                            # 세산에 실제 파일 시스템 상의 절대 경로 저장 (쓰기용)
                            abs_file_path = media_root / file_filename
                            session.audio_path = str(abs_file_path)
                            
                            await manager.send_json(client_id, {
                                "type": "meeting_created",
                                "meeting_id": meeting.id
                            })
                        except Exception as e:
                            db_meta.rollback()
                            print(f"Meeting creation failed: {e}")
                            await manager.send_json(client_id, {
                                "type": "error",
                                "message": "회의 생성 중 오류가 발생했습니다."
                            })
                        finally:
                            db_meta.close()
                        continue
                        
                elif "bytes" in data:
                    # 오디오 데이터
                    audio_chunk = data["bytes"]
                    
                    # 1. 파일에 저장 (Append) - 비동기 처리
                    if session.audio_path:
                        asyncio.create_task(asyncio.to_thread(_write_audio_sync, session.audio_path, audio_chunk))

                        # 2. 버퍼에 추가 (대략 0.5초 청크로 가정)
                        session.add_audio_chunk(audio_chunk, chunk_duration=0.5)
                        
                        # 버퍼 임계값 도달 시 전사
                        if session.buffer_duration >= BUFFER_THRESHOLD_SECONDS:
                            current_segment_duration = session.buffer_duration
                            audio_data, skip_header = session.get_buffer_and_reset()
                            
                            current_transcript_id = None # 초기화
                        
                            try:
                                # Faster-Whisper로 전사 (헤더 중복 방지 적용)
                                transcript = await stt_service.transcribe_realtime(
                                    audio_data, 
                                    skip_duration_ms=500 if skip_header else 0
                                )
                                
                                if transcript.strip():
                                    session.add_transcript(transcript)
                                    
                                    # Meeting에 전사 결과 저장 - 독립 세션 사용
                                    if session.meeting_id:
                                        from app.models.transcript import Transcript
                                        
                                        db_trans = SessionLocal()
                                        try:
                                            # 타임스탬프 계산
                                            end_time = session.total_duration
                                            start_time = max(0, end_time - current_segment_duration)
                                            
                                            transcript_record = Transcript(
                                                meeting_id=session.meeting_id,
                                                text=transcript,
                                                speaker="Unknown",
                                                start_time=start_time,
                                                end_time=end_time,
                                                segment_index=session.segment_index
                                            )
                                            db_trans.add(transcript_record)
                                            db_trans.commit()
                                            db_trans.refresh(transcript_record) # ID 확보
                                            
                                            current_transcript_id = transcript_record.id
                                            session.segment_index += 1
                                            
                                            print(f"[STT] Transcript {current_transcript_id} saved to DB: {transcript[:50]}...")
                                        except Exception as e:
                                            db_trans.rollback()
                                            print(f"Transcript DB save error: {e}")
                                            current_transcript_id = None
                                        finally:
                                            db_trans.close()
                                        
                                        # 태스크 스폰
                                        asyncio.create_task(background_correction_task(current_transcript_id, transcript, client_id))
                                    
                                    # 클라이언트에 1차 전사 결과 전송 (ID 포함)
                                    # 연결이 끊어져도 DB 저장은 이미 완료되었으므로 전송 실패는 무시
                                    send_success = await manager.send_json(client_id, {
                                        "type": "transcript",
                                        "transcript_id": current_transcript_id,
                                        "text": transcript,
                                        "is_final": True
                                    })
                                    
                                    if not send_success:
                                        print(f"[STT] Client {client_id} disconnected, transcript saved to DB but not sent")
                                    
                            except Exception as e:
                                # db.rollback()  # 정의되지 않은 변수 오류 수정
                                print(f"실시간 전사 오류: {str(e)}")
                                # 에러 전송 시도 (실패해도 무시)
                                await manager.send_json(client_id, {
                                    "type": "error",
                                    "message": str(e)
                                })
                    else:
                        # 버퍼링 중 상태 알림
                        await manager.send_json(client_id, {
                            "buffer_seconds": session.buffer_duration
                        })

                    # --- 중간 요약 트리거 (백그라운드 비동기 처리) ---
                    current_time = time.time()
                    if current_time - session.last_summary_time >= 180: # 3분마다 중간 요약
                        recent_text = session.get_recent_transcript_and_reset()
                        
                        if recent_text.strip():
                            # 백그라운드 태스크로 분리 (메인 루프를 멈추지 않음)
                            asyncio.create_task(background_summary_task(recent_text, session.meeting_id, client_id))
                        
                        session.last_summary_time = current_time
                        
            except json.JSONDecodeError:
                # JSON 파싱 실패 - 오디오 데이터로 간주
                pass
            except Exception as e:
                print(f"[WebSocket] Unexpected error in loop: {str(e)}")
                import traceback
                traceback.print_exc()
                break
            
    except WebSocketDisconnect:
        print(f"[WebSocket] Client {client_id} disconnected.")
        
        # 연결 종료 시 남은 버퍼 처리 및 최종 요약 시도
        if session and session.meeting_id and not session.is_finalized:
            # 1. 남은 오디오 버퍼 처리 (마지막 몇 초 전사)
            await process_remaining_buffer()

            # 2. 백그라운드 태스크로 전사 완료 처리 및 요약 실행
            # (함수가 상단에 정의되어 있으므로 그대로 호출 가능)
            pass

            # 태스크 실행
            asyncio.create_task(final_cleanup_and_summary(session.meeting_id, session.total_duration, session))

        if session:
            manager.disconnect(client_id)
            
    except Exception as e:
        print(f"[WebSocket] Critical error in WebSocket session: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 예외 발생 시에도 생성된 회의가 있다면 최소한의 정리 시도
        if session and session.meeting_id and not session.is_finalized:
            print(f"[WebSocket] Attempting emergency cleanup for meeting {session.meeting_id}")
            asyncio.create_task(final_cleanup_and_summary(session.meeting_id, session.total_duration, session))

        if client_id:
            manager.disconnect(client_id)
