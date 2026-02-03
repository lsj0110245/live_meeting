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
                initial_prompt="이것은 비즈니스 회의 녹음입니다. 자연스러운 한국어로 전사해주세요. 추임새(음, 어, 아, 그, 저)는 제외하고, 전문 용어(LLM, SaaS, API, Docker 등)는 정확한 영문 표기를 유지해주세요.", # 문맥 가이드 추가
                vad_filter=True,  # 음성 구간 자동 감지
                vad_parameters=dict(
                    min_silence_duration_ms=1000, # 침묵 감지 기준 상향 (500 -> 1000)
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
                initial_prompt="이것은 비즈니스 회의 녹음입니다. 자연스러운 한국어로 전사해주세요. 추임새(음, 어, 아, 그, 저)는 제외하고, 전문 용어(LLM, SaaS, API, Docker 등)는 정확한 영문 표기를 유지해주세요.",
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
    
    async def transcribe_file_chunked(self, file_path: str, language: str = "ko", progress_callback=None) -> list:
        """
        녹음 파일 전사 (오버래핑 청킹 적용) - 긴 파일 처리용
        10초 청크, 2초 오버랩
        """
        print(f"[청킹 전사 시작] {file_path}")
        self._initialize_model()
        
        try:
            from pydub import AudioSegment
            import tempfile
            import os
            
            # 오디오 파일 로드
            audio = AudioSegment.from_file(file_path)
            total_duration_ms = len(audio)
            total_duration_sec = total_duration_ms / 1000.0
            print(f"오디오 길이: {total_duration_sec:.2f}초")
            
            # 청킹 설정
            CHUNK_LENGTH_MS = 10000  # 10초
            OVERLAP_MS = 2000        # 2초 오버랩
            STEP_MS = CHUNK_LENGTH_MS - OVERLAP_MS  # 8초씩 이동
            
            all_segments = []
            chunk_count = 0
            
            # 청크별 처리
            for start_ms in range(0, total_duration_ms, STEP_MS):
                end_ms = min(start_ms + CHUNK_LENGTH_MS, total_duration_ms)
                chunk = audio[start_ms:end_ms]
                chunk_count += 1
                
                # 임시 파일로 저장
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_path = temp_file.name
                    chunk.export(temp_path, format="wav")
                
                try:
                    # Whisper 전사
                    segments, info = self.model.transcribe(
                        temp_path,
                        language=language,
                        beam_size=5,
                        initial_prompt="이것은 비즈니스 회의 녹음입니다. 자연스러운 한국어로 전사해주세요. 추임새(음, 어, 아, 그, 저)는 제외하고, 전문 용어(LLM, SaaS, API, Docker 등)는 정확한 영문 표기를 유지해주세요.",
                        vad_filter=True,
                        vad_parameters=dict(
                            min_silence_duration_ms=1000,
                            speech_pad_ms=400
                        )
                    )
                    
                    # 세그먼트 수집 (시간 오프셋 보정)
                    offset_sec = start_ms / 1000.0
                    for segment in segments:
                        adjusted_segment = {
                            "start": segment.start + offset_sec,
                            "end": segment.end + offset_sec,
                            "text": segment.text.strip()
                        }
                        all_segments.append(adjusted_segment)
                        
                finally:
                    # 임시 파일 삭제
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                
                # 진행률 업데이트
                if progress_callback:
                    percent = int((end_ms / total_duration_ms) * 100)
                    progress_callback(percent)
                
                print(f"  청크 {chunk_count} 처리 완료 ({start_ms/1000:.1f}s ~ {end_ms/1000:.1f}s)")
            
            # 중복 제거 (오버랩 구간)
            result_segments = self._merge_overlapping_segments(all_segments)
            
            print(f"청킹 전사 완료: 총 {len(result_segments)}개 세그먼트")
            return result_segments
            
        except Exception as e:
            print(f"청킹 전사 오류: {str(e)}")
            raise e
    
    def _merge_overlapping_segments(self, segments: list) -> list:
        """
        오버랩 구간의 중복 세그먼트 병합
        """
        if not segments:
            return []
        
        # 시작 시간 기준 정렬
        sorted_segments = sorted(segments, key=lambda x: x["start"])
        
        merged = []
        current = sorted_segments[0].copy()
        
        for next_seg in sorted_segments[1:]:
            # 오버랩 체크 (현재 세그먼트 끝 시간 > 다음 세그먼트 시작 시간)
            if current["end"] > next_seg["start"]:
                # 중복 구간: 텍스트가 비슷하면 스킵, 다르면 병합
                if next_seg["text"] not in current["text"]:
                    current["text"] += " " + next_seg["text"]
                current["end"] = max(current["end"], next_seg["end"])
            else:
                # 겹치지 않음: 현재 세그먼트 저장하고 다음으로 이동
                merged.append(current)
                current = next_seg.copy()
        
        # 마지막 세그먼트 추가
        merged.append(current)
        
        return merged

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
