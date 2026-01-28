import httpx
import os
import json
from app.core.config import settings

class STTService:
    def __init__(self):
        self.whisper_url = f"{settings.LOCAL_STT_URL}/asr"
        self.deepgram_key = settings.DEEPGRAM_API_KEY

    async def transcribe_file_local(self, file_path: str, language: str = "ko") -> str:
        """
        로컬 Whisper 컨테이너를 사용하여 파일 전사
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        try:
            async with httpx.AsyncClient(timeout=300.0) as client: # 녹음 파일이 길 수 있으므로 타임아웃 길게 설정
                with open(file_path, "rb") as f:
                    files = {"audio_file": (os.path.basename(file_path), f, "audio/mpeg")}
                    # Whisper Webservice API: /asr?task=transcribe&language=ko
                    params = {
                        "task": "transcribe",
                        "language": language,
                        "output": "json"
                    }
                    
                    response = await client.post(
                        self.whisper_url,
                        files=files,
                        params=params
                    )
                    response.raise_for_status()
                    
                    result = response.json()
                    # Whisper 결과 포맷에 따라 'text' 필드 반환
                    return result.get("text", "")
                    
        except Exception as e:
            print(f"Local STT Error: {str(e)}")
            raise e

    async def transcribe_realtime_deepgram(self, audio_data: bytes):
        """
        Deepgram Nova-2를 사용한 실시간 전사 (WebSocket용)
        - 실제 구현은 recording.py의 WebSocket 핸들러 내에서 Deepgram SDK를 직접 비동기로 사용하는 것이 효율적임
        - 여기서는 SDK 초기화 및 설정 헬퍼를 제공
        """
        # Deepgram SDK는 WebSocket 연결을 직접 관리해야 하므로
        # 서비스 클래스에서는 설정값만 제공하거나 세션을 생성하는 역할을 함
        pass

stt_service = STTService()
