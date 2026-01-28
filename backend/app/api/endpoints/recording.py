from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api import deps
from app.models.user import User

router = APIRouter()

# WebSocket 연결 관리자
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    실시간 녹음 WebSocket 엔드포인트
    
    - 클라이언트에서 오디오 청크를 전송받음
    - STT 서비스(Deepgram/Whisper)로 전달 (추후 구현)
    - 실시간 전사 결과를 클라이언트에게 반환
    """
    # 1. 인증 검증 (Query Parameter로 토큰 수신)
    # WebSocket은 헤더 인증이 까다로우므로 쿼리 파라미터 사용
    user = None
    try:
        user = deps.get_current_user(db, token=token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    
    try:
        await manager.send_message(f"Connected: {user.email}", websocket)
        
        while True:
            # 오디오 데이터 수신 (bytes)
            data = await websocket.receive_bytes()
            
            # TODO: 여기에 STT 처리 로직 추가
            # stt_service.process_audio(data) ...
            
            # 임시 에코 응답
            await manager.send_message(f"Server received {len(data)} bytes", websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client #{client_id} disconnected")
