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
import time
import asyncio

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

    async def connect(self, client_id: str, websocket: WebSocket, user: User):
        await websocket.accept()
        self.active_sessions[client_id] = RealtimeSession(websocket, user)

    def disconnect(self, client_id: str):
        if client_id in self.active_sessions:
            del self.active_sessions[client_id]

    def get_session(self, client_id: str) -> RealtimeSession:
        return self.active_sessions.get(client_id)

    async def send_json(self, client_id: str, data: dict):
        session = self.active_sessions.get(client_id)
        if session:
            try:
                await session.websocket.send_json(data)
            except RuntimeError as e:
                # 이미 연결이 끊긴 경우
                print(f"[WebSocket] Send failed (RuntimeError): {e}")
            except Exception as e:
                print(f"[WebSocket] Send failed: {e}")
                # 연결이 끊긴 것으로 간주하고 처리할 수도 있음



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
                            
                            # Meeting 레코드 생성
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
                                status="recording"
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
                            print(f"Meeting creation failed: {e}")
                            await manager.send_json(client_id, {
                                "type": "error",
                                "message": "회의 생성 중 오류가 발생했습니다."
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
                                        
                                        # [하이브리드 전략 2단계] 비동기 LLM 교정 태스크 실행
                                        async def background_correction_task(tid: int, original_text: str, cid: str):
                                            try:
                                                # LLM 문맥 교정
                                                corrected = await llm_service.correct_transcript(original_text)
                                                
                                                if corrected and corrected != original_text:
                                                    # DB 업데이트
                                                    # 주의: 메인 루프의 db 세션과 충돌 방지를 위해 별도 세션 사용 권장
                                                    # 여기서는 간단히 메인 세션과 분리된 로직이 필요하므로 SessionLocal 사용
                                                    correction_db = SessionLocal()
                                                    try:
                                                        t_item = correction_db.query(Transcript).filter(Transcript.id == tid).first()
                                                        if t_item:
                                                            t_item.text = corrected
                                                            correction_db.commit()
                                                            print(f"Transcript {tid} corrected: {original_text} -> {corrected}")
                                                            
                                                            # 클라이언트에 업데이트 전송
                                                            await manager.send_json(cid, {
                                                                "type": "transcript_update",
                                                                "transcript_id": tid,
                                                                "text": corrected
                                                            })
                                                    finally:
                                                        correction_db.close()
                                            except Exception as e:
                                                print(f"Background correction failed: {e}")

                                        # 태스크 스폰
                                        asyncio.create_task(background_correction_task(current_transcript_id, transcript, client_id))
                                    
                                    # 클라이언트에 1차 전사 결과 전송 (ID 포함)
                                    await manager.send_json(client_id, {
                                        "type": "transcript",
                                        "transcript_id": current_transcript_id,
                                        "text": transcript,
                                        "is_final": True
                                    })
                                    
                            except Exception as e:
                                db.rollback()
                                print(f"실시간 전사 오류: {str(e)}")
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

            # 2. 백그라운드 태스크로 전사 완료 처리 및 요약 실행
            async def final_cleanup_and_summary(mid, full_text, duration):
                print(f"[Background Task] Starting final summary for meeting {mid}...")
                bg_db = SessionLocal()
                try:
                    # 상태 업데이트
                    from app.models.meeting import Meeting
                    meeting = bg_db.query(Meeting).filter(Meeting.id == mid).first()
                    if meeting:
                        meeting.status = "completed"
                        meeting.duration = int(duration)
                        bg_db.commit()
                        print(f"Meeting {mid} finalized.")

                    # 전사 내용이 어느 정도 있을 때만 요약
                    if full_text and len(full_text) > 10:
                        summary_json = await llm_service.generate_summary(meeting.title if meeting else "회의", full_text)
                        if summary_json:
                            # 메타데이터 업데이트
                            metadata = summary_json.get("metadata", {})
                            if meeting:
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
                                if updated:
                                    bg_db.commit()

                            # 요약 저장
                            if "summary" in summary_json:
                                from app.models.summary import Summary
                                s_data = summary_json["summary"]
                                
                                # 필드들을 하나의 마크다운 문서로 합침
                                formatted_parts = []
                                # 제목 추가 (메타데이터 활용)
                                final_title = metadata.get("title_suggestion", meeting.title if meeting else "회의")
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
                                
                                existing = bg_db.query(Summary).filter(Summary.meeting_id == mid).first()
                                if existing:
                                    existing.content = summary_content
                                else:
                                    bg_db.add(Summary(meeting_id=mid, content=summary_content))
                                bg_db.commit()
                                print(f"Final structured summary saved for meeting {mid}.")
                except Exception as e:
                    print(f"Final cleanup task failed: {e}")
                finally:
                    bg_db.close()

            # 비동기 태스크 시작
            asyncio.create_task(final_cleanup_and_summary(
                session.meeting_id, 
                session.get_full_transcript(), 
                session.total_duration
            ))

        if session:
            manager.disconnect(client_id)
            
    except Exception as e:
        print(f"[WebSocket] Critical error in WebSocket session: {str(e)}")
        import traceback
        traceback.print_exc()
        if client_id:
            manager.disconnect(client_id)
