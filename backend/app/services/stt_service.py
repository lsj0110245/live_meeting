"""
STT 서비스 통합 모듈

Faster-Whisper를 사용하여 녹음 파일 및 실시간 전사를 처리합니다.
"""

import os
from app.services.faster_whisper_stt_service import faster_whisper_stt_service


class STTService:
    def __init__(self):
        pass  # Faster-Whisper만 사용

    async def transcribe_file_local(self, file_path: str, language: str = "ko", progress_callback=None) -> list | str:
        """
        Faster-Whisper를 사용하여 녹음 파일 전사 (GPU 최적화)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        try:
            # Faster-Whisper 사용 (이제 세그먼트 리스트 반환)
            result = await faster_whisper_stt_service.transcribe_file(file_path, language, progress_callback)
            return result
                    
        except Exception as e:
            print(f"Local STT Error: {str(e)}")
            raise e

    async def transcribe_realtime(self, audio_data: bytes, language: str = "ko") -> str:
        """
        Faster-Whisper를 사용한 실시간 전사 (WebSocket용)
        """
        try:
            transcript_text = await faster_whisper_stt_service.transcribe_realtime(audio_data, language)
            return transcript_text
        except Exception as e:
            print(f"Realtime STT Error: {str(e)}")
            raise e

    def cleanup(self):
        """GPU 메모리 정리"""
        faster_whisper_stt_service.cleanup()


stt_service = STTService()
