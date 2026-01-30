import os
from app.core.config import settings
from app.services.whisper_stt_service import whisper_stt_service

class STTService:
    def __init__(self):
        self.whisper_url = f"{settings.LOCAL_STT_URL}/asr"
        self.deepgram_key = settings.DEEPGRAM_API_KEY

    async def transcribe_file_local(self, file_path: str, language: str = "ko") -> str:
        """
        Whisper 모델을 직접 사용하여 파일 전사 (GPU 최적화)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        try:
            # 새로운 WhisperSTTService 사용
            transcript_text = await whisper_stt_service.transcribe_file(file_path, language)
            return transcript_text
                    
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
