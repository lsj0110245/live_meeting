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

# [Optimization] DB 작업을 위한 동기 헬퍼 함수들 (스레드 풀에서 실행)
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
        self.is_intentional_stop = False # [New] 사용자가 명시적으로 중지했는지 여부
        
    def add_audio_chunk(self, chunk: bytes, chunk_duration: float = 0.5):
        """오디오 청크 추가"""
        if self.header_bytes is None:
            self.header_bytes = chunk # 첫 번째 청크(헤더 포함) 저장
            
        self.audio_buffer.write(chunk)
        # WebM 스트리밍: 각 청크는 독립적인 클러스터로 구성되어야 하며, 
        # 첫 번째 청크는 반드시 EBML 헤더와 세그먼트 정보를 포함해야 함 (클라이언트 전달 책임)
        self.buffer_duration += chunk_duration
        self.total_duration += chunk_duration
        
    def get_buffer_and_reset(self) -> bytes:
        """버퍼 데이터 반환 및 초기화"""
        current_buffer_data = self.audio_buffer.getvalue()
        
        # 헤더가 있고, 현재 버퍼가 헤더로 시작하지 않으면(즉 두 번째 이후 세그먼트면) 헤더를 붙여줌
        # io.BytesIO.getvalue()는 bytes를 반환하므로 startswith 사용 가능
        if self.header_bytes and not current_buffer_data.startswith(self.header_bytes):
            data_to_process = self.header_bytes + current_buffer_data
        else:
            data_to_process = current_buffer_data

        self.audio_buffer = io.BytesIO()
        self.buffer_duration = 0
        return data_to_process
    
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
        self.pending_cleanup_tasks: Dict[str, asyncio.Task] = {} # [New] 종료 대기 중인 태스크

    async def connect(self, client_id: str, websocket: WebSocket, user: User):
        await websocket.accept()
        
        # [New] 재연결 시 기존 종료 예약 태스크가 있다면 취소
        if client_id in self.pending_cleanup_tasks:
            self.pending_cleanup_tasks[client_id].cancel()
            del self.pending_cleanup_tasks[client_id]
            print(f"[WebSocket] Canceled pending cleanup for {client_id} due to reconnection.")

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
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    실시간 STT WebSocket 엔드포인트
    
    클라이언트에서 오디오 청크를 전송하면:
    1. 버퍼에 누적
    2. 5초 분량이 쌓이면 Faster-Whisper로 전사
    3. 전사 결과를 JSON으로 반환
    """
    print(f"[WebSocket] Connection attempt from client: {client_id}")
    # 1. 인증 검증
    user = None
    try:
        user = deps.get_current_user(db, token=token)
    except Exception as e:
        print(f"[WebSocket] Authentication failed for {client_id}: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        await manager.connect(client_id, websocket, user)
        session = manager.get_session(client_id)
        print(f"[WebSocket] Client {client_id} connected successfully.")
    except Exception as e:
        print(f"[WebSocket] Connection failed: {e}")
        return
    
    try:
        # 연결 성공 알림
        await manager.send_json(client_id, {
            "type": "connected",
            "message": f"실시간 STT 연결됨: {user.email}"
        })
        
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
                    
                    if message.get("type") == "metadata":
                        # 메타데이터 저장 및 Meeting 생성
                        from app.models.meeting import Meeting
                        from datetime import datetime
                        
                        try: 
                            metadata = message.get("data", {})
                            session.metadata = metadata
                            is_reconnect = metadata.get("reconnect", False)
                            existing_meeting_id = metadata.get("meeting_id")

                            if is_reconnect and existing_meeting_id:
                                # [New] 재연결 로직: 기존 회의 정보 로드
                                meeting = db.query(Meeting).filter(Meeting.id == existing_meeting_id).first()
                                if meeting:
                                    session.meeting_id = meeting.id
                                    print(f"[WebSocket] Reconnected to existing Meeting: ID={meeting.id}")
                                    
                                    # 다음 세그먼트 인덱스 계산 (중복 방지)
                                    segment_count = db.query(Transcript).filter(Transcript.meeting_id == meeting.id).count()
                                    session.segment_index = segment_count
                                    
                                    # 기존 오디오 파일 경로 재사용
                                    from app.core.config import settings
                                    file_filename = f"realtime_{meeting.id}.webm"
                                    session.audio_path = str(settings.MEDIA_ROOT / file_filename)
                                    
                                    await manager.send_json(client_id, {
                                        "type": "reconnected",
                                        "meeting_id": meeting.id,
                                        "next_segment": segment_count
                                    })
                                    continue
                            
                            # [New] 사용자의 명시적 중지 명령 (정상 종료)
                            if message.get("type") == "stop":
                                session.is_intentional_stop = True
                                print(f"[WebSocket] Client {client_id} requested intentional stop.")
                                break # 루프를 빠져나가 Disconnect 블록으로 이동
                            
                            # 신규 회의 생성 (재연결이 아니거나 기존 회의가 없는 경우)
                            from app.utils import get_unique_title
                            raw_title = metadata.get("title", "제목 없음")
                            safe_title = get_unique_title(db, raw_title)
                            
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
                            db.add(meeting)
                            db.commit()
                            db.refresh(meeting)
                            
                            session.meeting_id = meeting.id
                            print(f"Meeting created: ID={meeting.id}, Title={meeting.title}")
                            
                            # 오디오 파일 경로 설정 및 저장 (settings.MEDIA_ROOT 사용)
                            from app.core.config import settings
                            media_root = settings.MEDIA_ROOT
                            media_root.mkdir(parents=True, exist_ok=True)
                            
                            file_filename = f"realtime_{meeting.id}.webm"
                            # DB에는 서비스 서빙용 상대 경로 저장 (media/...)
                            relative_path = f"media/{file_filename}"
                            meeting.audio_file_path = relative_path
                            db.commit()
                            
                            # 세션에 실제 파일 시스템 상의 절대 경로 저장 (쓰기용)
                            abs_file_path = media_root / file_filename
                            session.audio_path = str(abs_file_path)
                            
                            await manager.send_json(client_id, {
                                "type": "meeting_created",
                                "meeting_id": meeting.id
                            })
                        except Exception as e:
                            db.rollback()
                            print(f"Meeting creation/resume failed: {e}")
                            await manager.send_json(client_id, {
                                "type": "error",
                                "message": "회의 생성 또는 복구 중 오류가 발생했습니다."
                            })
                        continue
                        
                elif "bytes" in data:
                    # 오디오 데이터
                    audio_chunk = data["bytes"]
                    
                    # 1. 파일에 저장 (Append)
                    if session.audio_path:
                        try:
                            with open(session.audio_path, "ab") as f:
                                f.write(audio_chunk)
                        except Exception as e:
                            print(f"Audio write failed: {e}")

                        # 2. 버퍼에 추가 (대략 0.5초 청크로 가정)
                        session.add_audio_chunk(audio_chunk, chunk_duration=0.5)
                        
                        # 버퍼 임계값 도달 시 전사
                        if session.buffer_duration >= BUFFER_THRESHOLD_SECONDS:
                            current_segment_duration = session.buffer_duration
                            audio_data = session.get_buffer_and_reset()
                        
                            try:
                                # Faster-Whisper로 전사
                                transcript = await stt_service.transcribe_realtime(audio_data)
                                
                                if transcript.strip():
                                    session.add_transcript(transcript)
                                    
                                    # Meeting에 전사 결과 저장
                                    if session.meeting_id:
                                        from app.models.transcript import Transcript
                                        
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
                                        db.add(transcript_record)
                                        db.commit()
                                        db.refresh(transcript_record) # ID 확보
                                        
                                        current_transcript_id = transcript_record.id
                                        session.segment_index += 1
                                        
                                        print(f"[STT] Transcript {current_transcript_id} saved to DB: {transcript[:50]}...")
                                        
                                        # [하이브리드 전략 2단계] 비동기 LLM 교정 태스크 실행
                                        async def background_correction_task(tid: int, original_text: str, cid: str):
                                            try:
                                                # LLM 문맥 교정 (비동기, 스레드 내부 실행됨)
                                                corrected = await llm_service.correct_transcript(original_text)
                                                
                                                if corrected and corrected != original_text:
                                                    # DB 업데이트 (Blocking 방지를 위해 별도 스레드 실행)
                                                    await asyncio.to_thread(_update_transcript_db_sync, tid, corrected)
                                                    print(f"Transcript {tid} corrected and saved to DB")
                                                    
                                                    # 클라이언트에 업데이트 전송 (연결 상태 확인)
                                                    if manager.is_connected(cid):
                                                        await manager.send_json(cid, {
                                                            "type": "transcript_update",
                                                            "transcript_id": tid,
                                                            "text": corrected
                                                        })
                                                    else:
                                                        print(f"[LLM] Client {cid} disconnected, skipping WebSocket send")
                                            except Exception as e:
                                                print(f"Background correction failed: {e}")

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
                                db.rollback()
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
                            async def background_summary_task(text, mid, cid):
                                try:
                                    # 요약 생성
                                    summary = await llm_service.generate_simple_summary(text)
                                    
                                    if summary and summary.strip():
                                        # 클라이언트에 전송
                                        await manager.send_json(cid, {
                                            "type": "intermediate_summary",
                                            "content": summary
                                        })
                                        
                                        # DB 저장
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
                                    else:
                                        print(f"Skipping empty intermediate summary for meeting {mid}")
                                        
                                except Exception as e:
                                    print(f"Background intermediate summary task failed: {e}")

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
        if session and session.meeting_id:
            # 1. 남은 오디오 버퍼 처리 (마지막 몇 초 전사)
            if session.buffer_duration > 0:
                print(f"[WebSocket] Processing remaining buffer ({session.buffer_duration:.1f}s) for Meeting {session.meeting_id}")
                audio_data = session.get_buffer_and_reset()
                try:
                    # 동기 호출로 마지막 전사 시도 (짧은 오디오이므로 금방 끝남)
                    last_transcript = await stt_service.transcribe_realtime(audio_data)
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
                                start_time=max(0, session.total_duration - session.buffer_duration), # 대략적 계산
                                end_time=session.total_duration,
                                segment_index=session.segment_index
                            )
                            db_cleanup.add(t_record)
                            db_cleanup.commit()
                        finally:
                            db_cleanup.close()
                except Exception as e:
                    print(f"Failed to transcribe final chunk: {e}")

            # 2. 백그라운드 태스크로 전사 완료 처리 및 요약 실행 (지연 전략 적용)
            async def final_cleanup_and_summary_task(mid, duration, cid, is_intentional):
                try:
                    if not is_intentional:
                        # [New] 네트워크 끊김인 경우 60초 대기 (재연결 기회 제공)
                        print(f"[WebSocket] Waiting 60s before finalizing meeting {mid} (Allow reconnection)...")
                        await asyncio.sleep(60)
                    
                    print(f"[Background Task] Starting final summary for meeting {mid}...")
                    # 1. 회의 시간 업데이트
                    await asyncio.to_thread(_update_meeting_duration_sync, mid, int(duration))
                    
                    # 2. 통합 요약 생성
                    from app.services.meeting_tasks import process_meeting_summary
                    await process_meeting_summary(mid)
                    print(f"Meeting {mid} finalized successfully.")

                except asyncio.CancelledError:
                    print(f"[WebSocket] Finalization of meeting {mid} was cancelled (Client reconnected).")
                except Exception as e:
                    print(f"Final cleanup task failed: {e}")
                    await asyncio.to_thread(_force_complete_meeting_sync, mid)
                finally:
                    # 매니저에서 태스크 제거
                    if cid in manager.pending_cleanup_tasks:
                        del manager.pending_cleanup_tasks[cid]

            # 태스크 생성 및 예약
            cleanup_task = asyncio.create_task(
                final_cleanup_and_summary_task(
                    session.meeting_id, 
                    session.total_duration, 
                    client_id, 
                    session.is_intentional_stop
                )
            )
            manager.pending_cleanup_tasks[client_id] = cleanup_task

        if session:
            manager.disconnect(client_id)
            
    except Exception as e:
        print(f"[WebSocket] Critical error in WebSocket session: {str(e)}")
        import traceback
        traceback.print_exc()
        if client_id:
            manager.disconnect(client_id)
