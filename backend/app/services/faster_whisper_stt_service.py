"""
Faster-Whisper 기반 STT 서비스

특징:
- 기존 Whisper 대비 4-5배 빠른 속도
- GPU 메모리 사용량 50% 감소
- 녹음 파일 처리 + 실시간 STT 모두 지원
"""

import os
import tempfile
from typing import Optional
from faster_whisper import WhisperModel


class FasterWhisperSTTService:
    """
    Faster-Whisper 기반 음성 인식 서비스
    
    - 녹음 파일 처리: 30초 청크, 정확도 우선
    - 실시간 STT: 5초 청크, 속도 우선
    """
    
    def __init__(self):
        from app.core.config import settings
        self.model_size = settings.STT_MODEL_SIZE
        self.model: Optional[WhisperModel] = None
        self.device = settings.STT_DEVICE
        self.compute_type = settings.STT_COMPUTE_TYPE
        
    def _initialize_model(self):
        """모델 초기화 (필요 시에만 로드)"""
        if self.model is None:
            print(f"Faster-Whisper 모델 초기화 중: {self.model_size}")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            print("Faster-Whisper 모델 로드 완료")
    
    async def transcribe_file(self, file_path: str, language: str = "ko", progress_callback=None) -> list:
        """
        녹음 파일 전사 (정확도 우선)
        """
        print(f"[파일 전사 시작] {file_path}")
        self._initialize_model()
        
        try:
            # Faster-Whisper는 beam_size로 정확도 조절
            segments, info = self.model.transcribe(
                file_path,
                language=language,
                beam_size=5,  # 정확도 우선
                vad_filter=True,  # 음성 구간 자동 감지
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400
                )
            )
            
            # 총 지속 시간 (진행률 계산용)
            total_duration = info.duration
            print(f"오디오 길이: {total_duration:.2f}초")
            
            # 전사 결과 반환 (세그먼트 리스트)
            result_segments = []
            for segment in segments:
                result_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                # 진행률 업데이트
                if total_duration > 0 and progress_callback:
                    percent = int((segment.end / total_duration) * 100)
                    progress_callback(percent)
                    
                print(f"  - [{segment.start:.2f}s ~ {segment.end:.2f}s] {segment.text.strip()[:20]}...")
            
            print(f"[파일 전사 완료] 세그먼트 개수: {len(result_segments)}")
            return result_segments
            
        except Exception as e:
            print(f"Faster-Whisper 전사 오류: {str(e)}")
            raise e
    
    async def transcribe_realtime(self, audio_bytes: bytes, language: str = "ko") -> str:
        """
        실시간 전사 (속도 우선)
        
        Args:
            audio_bytes: 오디오 데이터 (bytes)
            language: 언어 코드
            
        Returns:
            전사된 텍스트
        """
        self._initialize_model()
        
        # bytes를 임시 파일로 저장
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name
        
        try:
            # 실시간용: beam_size 낮춰서 속도 향상
            segments, info = self.model.transcribe(
                temp_path,
                language=language,
                beam_size=5,  # 정확도 향상 (기본 1 -> 5)
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500, # 노이즈 필터링 강화
                    speech_pad_ms=400
                )
            )
            
            transcript_text = ""
            for segment in segments:
                transcript_text += segment.text + " "
            
            return transcript_text.strip()
            
        finally:
            # 임시 파일 삭제
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def cleanup(self):
        """GPU 메모리 정리"""
        if self.model is not None:
            del self.model
            self.model = None
            
            # CUDA 캐시 정리
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    print("GPU 메모리 캐시 클리어 완료")
            except ImportError:
                pass


# 싱글톤 인스턴스
faster_whisper_stt_service = FasterWhisperSTTService()
