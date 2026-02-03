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
        긴 파일은 자동으로 청킹 적용
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        try:
            # 파일 길이 체크 (60초 이상이면 청킹 적용)
            from pydub import AudioSegment
            audio = AudioSegment.from_file(file_path)
            duration_sec = len(audio) / 1000.0
            
            if duration_sec > 60:
                print(f"[긴 파일 감지] {duration_sec:.1f}초 - 청킹 모드 사용")
                result = await faster_whisper_stt_service.transcribe_file_chunked(file_path, language, progress_callback)
            else:
                print(f"[일반 파일] {duration_sec:.1f}초 - 표준 모드 사용")
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
