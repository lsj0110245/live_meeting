"""
실시간 녹음 및 STT WebSocket 엔드포인트
"""

import io
import json
from typing import List, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api import deps
from app.models.user import User
from app.services.stt_service import stt_service

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
        
    def add_audio_chunk(self, chunk: bytes, chunk_duration: float = 0.5):
        """오디오 청크 추가"""
        self.audio_buffer.write(chunk)
        self.buffer_duration += chunk_duration
        
    def get_buffer_and_reset(self) -> bytes:
        """버퍼 데이터 반환 및 초기화"""
        data = self.audio_buffer.getvalue()
        self.audio_buffer = io.BytesIO()
        self.buffer_duration = 0
        return data
    
    def add_transcript(self, text: str):
        """전사 결과 기록"""
        if text.strip():
            self.transcript_history.append(text)
    
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
            await session.websocket.send_json(data)


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
    # 1. 인증 검증
    user = None
    try:
        user = deps.get_current_user(db, token=token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(client_id, websocket, user)
    session = manager.get_session(client_id)
    
    try:
        # 연결 성공 알림
        await manager.send_json(client_id, {
            "type": "connected",
            "message": f"실시간 STT 연결됨: {user.email}"
        })
        
        while True:
            # 데이터 수신 (bytes 또는 text)
            try:
                # 먼저 텍스트로 받아보기 (메타데이터 메시지인 경우)
                data = await websocket.receive()
                
                if "text" in data:
                    # JSON 메타데이터 메시지
                    message = json.loads(data["text"])
                    
                    if message.get("type") == "metadata":
                        # 메타데이터 저장 및 Meeting 생성
                        from app.models.meeting import Meeting
                        from datetime import datetime
                        
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
                        
                        await manager.send_json(client_id, {
                            "type": "metadata_saved",
                            "meeting_id": meeting.id
                        })
                        continue
                        
                elif "bytes" in data:
                    # 오디오 데이터
                    audio_chunk = data["bytes"]
                    
                    # 버퍼에 추가 (대략 0.5초 청크로 가정)
                    session.add_audio_chunk(audio_chunk, chunk_duration=0.5)
                    
                    # 버퍼 임계값 도달 시 전사
                    if session.buffer_duration >= BUFFER_THRESHOLD_SECONDS:
                        audio_data = session.get_buffer_and_reset()
                        
                        try:
                            # Faster-Whisper로 전사
                            transcript = await stt_service.transcribe_realtime(audio_data)
                            
                            if transcript.strip():
                                session.add_transcript(transcript)
                                
                                # Meeting에 전사 결과 저장 (선택적)
                                if session.meeting_id:
                                    from app.models.transcript import Transcript
                                    transcript_record = Transcript(
                                        meeting_id=session.meeting_id,
                                        text=transcript,
                                        speaker="Unknown",
                                        start_time=0,  # 실시간이므로 정확한 타임스탬프는 추후 개선
                                        end_time=0
                                    )
                                    db.add(transcript_record)
                                    db.commit()
                                
                                # 클라이언트에 전사 결과 전송
                                await manager.send_json(client_id, {
                                    "type": "transcript",
                                    "text": transcript,
                                    "is_final": True
                                })
                                
                        except Exception as e:
                            print(f"실시간 전사 오류: {str(e)}")
                            await manager.send_json(client_id, {
                                "type": "error",
                                "message": str(e)
                            })
                    else:
                        # 버퍼링 중 상태 알림
                        await manager.send_json(client_id, {
                            "type": "buffering",
                            "buffer_seconds": session.buffer_duration
                        })
                        
            except json.JSONDecodeError:
                # JSON 파싱 실패 - 오디오 데이터로 간주
                pass
            
    except WebSocketDisconnect:
        # 연결 종료 시 Meeting 상태 업데이트
        if session.meeting_id:
            from app.models.meeting import Meeting
            meeting = db.query(Meeting).filter(Meeting.id == session.meeting_id).first()
            if meeting:
                meeting.status = "completed"
                db.commit()
        
        full_transcript = session.get_full_transcript()
        print(f"Client #{client_id} disconnected. Full transcript: {full_transcript[:100]}...")
        manager.disconnect(client_id)
        
        # GPU 메모리 정리
        stt_service.cleanup()
