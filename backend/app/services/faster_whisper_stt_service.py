"""
Faster-Whisper 기반 STT 서비스

특징:
- 기존 Whisper 대비 4-5배 빠른 속도
- GPU 메모리 사용량 50% 감소
- 녹음 파일 처리 + 실시간 STT 모두 지원
"""

import os
import tempfile
import re
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
            # [최적화] 파일 전사 정확도 극대화 설정
            segments, info = self.model.transcribe(
                file_path,
                language=language,
                beam_size=10,         # 오프라인 처리는 더 깊게 탐색 (5 -> 10)
                best_of=10,           # 최상의 결과 선별
                temperature=0,        # 일관성 최우선
                repetition_penalty=1.2, # 중복 방지
                condition_on_previous_text=True, # [중요] 오프라인 전사는 이전 문맥을 참조하여 전체 일관성 향상
                initial_prompt="비즈니스 회의 전문 녹음입니다. IT 전문 용어와 고유 명사는 영문 표기를 유지하고, 문맥에 맞는 자연스러운 한국어로 전사하세요.",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=1000, 
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
        # 데이터 유효성 검사 (너무 작으면 스킵)
        if not audio_bytes or len(audio_bytes) < 1024:  # 1KB 미만은 무시
            print(f"Skipping tiny audio chunk: {len(audio_bytes)} bytes")
            return ""

        self._initialize_model()
        
        # bytes를 임시 파일로 저장
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name
        
            try:
                # [최적화] 실시간 정확도 및 속도 극대화 설정
                segments, info = self.model.transcribe(
                    temp_path,
                    language=language,
                    beam_size=5,          # 정확도 극대화 (최상위 품질)
                    best_of=5,            # 최고 결과 선택
                    temperature=0,        # 결정론적 결과로 속도 및 안정성 확보
                    repetition_penalty=1.2, # 반복 문구 억제
                    no_repeat_ngram_size=3, # 반복되는 단어 조합 억제
                    condition_on_previous_text=False, # 이전 문맥 참조에 의한 환각 전파 방지
                    initial_prompt="회의 녹음입니다. IT 기술 용어(LLM, GPT, API, Docker, FastAPI, SQL, JSON)는 정확히 영문으로 표기하고 자연스러운 한국어로 작성하세요.",
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=500, # 반응성 상향 (빨리 인식 완료)
                        speech_pad_ms=400,
                        min_speech_duration_ms=250   # 짧은 말도 인식
                    )
                )

                transcript_text = ""
                for segment in segments:
                    text = segment.text.strip()
                    
                    # [필터링] 환각 패턴 제거
                    if re.search(r"자막|박진희|vostfr|Subtitles|Thank you|시청해 주셔서", text, re.I):
                        continue
                    
                    if len(text) <= 1:
                        continue
                        
                    transcript_text += text + " "

                return transcript_text.strip()

            except Exception as e:
                if "Invalid data found" in str(e):
                    # 잡음/무음 구간에서 발생하는 에러 무시
                    return ""
                print(f"Realtime STT Internal Error: {e}")
                raise e
            
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
            
            # 청킹 설정 (문맥 유지를 위해 30초 단위로 상향)
            CHUNK_LENGTH_MS = 30000  # 30초
            OVERLAP_MS = 5000        # 5초 오버랩
            STEP_MS = CHUNK_LENGTH_MS - OVERLAP_MS
            
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
                    # [최적화] 청킹 전사 정확도 극대화
                    segments, info = self.model.transcribe(
                        temp_path,
                        language=language,
                        beam_size=10,
                        best_of=5,
                        temperature=0,
                        repetition_penalty=1.2,
                        condition_on_previous_text=True, # 청크 간 문맥 유지
                        initial_prompt="회의 녹음입니다. 전문 용어 표기를 정확히 하고 자연스러운 문장으로 기록하세요.",
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
