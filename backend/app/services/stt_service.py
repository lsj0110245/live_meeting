"""
STT 서비스 통합 모듈

Faster-Whisper를 사용하여 녹음 파일 및 실시간 전사를 처리합니다.
"""

import os
from app.services.faster_whisper_stt_service import faster_whisper_stt_service


class STTService:
    def __init__(self):
        self.faster_whisper = faster_whisper_stt_service

    async def transcribe_file_local(self, file_path: str, language: str = "ko", progress_callback=None) -> list | str:
        """
        [Local] 파일 업로드는 로컬 GPU(Faster-Whisper)를 사용하여 처리
        - 메모리 효율을 위해 대용량 파일 체크 로직 최적화
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        print(f"🎙️ [STT:Hybrid] Using Faster-Whisper for File Upload")

        try:
            # 파일 크기로 1차 체크 (약 10MB 이상이면 긴 파일로 간주하여 메모리 로딩 회피)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            if file_size_mb > 10:
                # 10MB 초과 시 긴 파일로 간주, 바로 청킹 전사 시도 (pydub 내부에서 처리)
                return await self.faster_whisper.transcribe_file_chunked(file_path, language, progress_callback)
            else:
                # 작은 파일만 일반 전사
                return await self.faster_whisper.transcribe_file(file_path, language, progress_callback)
                    
        except Exception as e:
            print(f"Faster-Whisper STT Error: {str(e)}")
            raise e

    async def transcribe_realtime(self, audio_data: bytes, language: str = "ko", skip_duration_ms: int = 0) -> str:
        """
        실시간 전사: 로컬 Faster-Whisper 사용
        """
        try:
            return await self.faster_whisper.transcribe_realtime(audio_data, language, skip_duration_ms)
        except Exception as e:
            print(f"Faster-Whisper Realtime STT Error: {str(e)}")
            raise e

    def initialize_model(self):
        """모델 초기화 (Pre-warm)"""
        self.faster_whisper._initialize_model()

    def cleanup(self):
        """자원 정리"""
        self.faster_whisper.cleanup()


stt_service = STTService()
