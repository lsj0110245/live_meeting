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
        self._initialize_model()
        
        try:
            # [최적화] 파일 전사 정확도 극대화 설정
            # Blocking 방지를 위해 전체 전사 로직을 별도 스레드에서 실행
            # 중요: segments는 제너레이터이므로 순회(iteration)도 스레드 안에서 해야 함
            import asyncio
            
            def _transcribe_in_thread():
                """스레드 내부에서 실행될 전사 함수"""
                segments, info = self.model.transcribe(
                    file_path,
                    language=language,
                    beam_size=10,
                    best_of=10,
                    temperature=0,
                    repetition_penalty=1.2,
                    condition_on_previous_text=True,
                    initial_prompt="비즈니스 회의 전문 녹음입니다. IT 전문 용어와 고유 명사는 영문 표기를 유지하고, 문맥에 맞는 자연스러운 한국어로 전사하세요.",
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=1000, 
                        speech_pad_ms=400
                    )
                )
                
                # 제너레이터를 리스트로 변환 (이 작업도 스레드 안에서 수행)
                result_segments = []
                total_duration = info.duration
                
                for segment in segments:
                    result_segments.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text.strip()
                    })
                    print(f"  - [{segment.start:.2f}s ~ {segment.end:.2f}s] {segment.text.strip()[:20]}...")
                
                return result_segments, total_duration
            
            # 스레드에서 실행
            result_segments, total_duration = await asyncio.to_thread(_transcribe_in_thread)
            
            print(f"오디오 길이: {total_duration:.2f}초")
            print(f"[파일 전사 완료] 세그먼트 개수: {len(result_segments)}")
            
            # 진행률 콜백 처리 (이미 완료된 상태이므로 100%로 설정)
            if progress_callback:
                progress_callback(100)
            
            return result_segments
            
        except Exception as e:
            print(f"Faster-Whisper 전사 오류: {str(e)}")
            raise e
    
    async def transcribe_realtime(self, audio_bytes: bytes, language: str = "ko") -> str:
        """
        실시간 전사 (속도 우선)
        
        Args:
        실시간 오디오 스트림 전사
        """
        if not audio_bytes or len(audio_bytes) < 1024:
            # print(f"Skipping tiny audio chunk: {len(audio_bytes)} bytes")
            return ""

        self._initialize_model()
        
        # [공통 전처리] Denoise & Normalize 적용
        # 실시간 모드이므로 빠른 처리를 위해 quality="fast" 적용
        # Blocking 방지를 위해 별도 스레드에서 실행
        import asyncio
        import tempfile
        temp_path = None
        
        try:
            # [품질 개선] 전처리 활성화 (비동기로 안전하게 실행)
            # Denoise & Normalize를 통해 STT 정확도 향상
            # Blocking 방지를 위해 별도 스레드에서 실행
            print(f"[STT] Starting preprocessing for {len(audio_bytes)} bytes")
            temp_path = await asyncio.to_thread(
                self._preprocess_audio,
                audio_bytes,
                quality="fast"  # 실시간 모드는 fast 사용
            )
            print(f"[STT] Preprocessing completed: {temp_path}")

            # [최적화] 실시간 정확도 및 속도 극대화 설정
            # Blocking 방지를 위해 별도 스레드에서 실행
            segments, info = await asyncio.to_thread(
                self.model.transcribe,
                temp_path,
                language=language,
                beam_size=5,
                best_of=5,
                temperature=0,
                repetition_penalty=1.3,  # 반복 억제 강화
                no_repeat_ngram_size=3,
                condition_on_previous_text=False,
                initial_prompt="회의 녹음입니다. IT 기술 용어(LLM, GPT, API, Docker, FastAPI, SQL, JSON)는 정확히 영문으로 표기하고 자연스러운 한국어로 작성하세요.",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=500,          
                    min_speech_duration_ms=100, 
                    threshold=0.4  # 임계값 상향 (더 엄격한 음성 감지)
                )
            )

            transcript_text = ""
            for segment in segments:
                text = segment.text.strip()
                # print(f"Detected Segment: {text}") # 디버그용
                    
                # [필터링] 환각 패턴 제거
                if re.search(r"자막|박진희|vostfr|Subtitles|Thank you|시청해 주셔서", text, re.I):
                    continue
                
                if len(text) <= 1:
                    continue
                    
                transcript_text += text + " "

            if not segments:
                print(f"Realtime STT: No segments detected for audio chunk (length: {len(audio_bytes)} bytes)")
            # if transcript_text.strip():
            #      print(f"Final Transcript: {transcript_text}")
                 
            return transcript_text.strip()
 
        except Exception as e:
            if "Invalid data found" in str(e):
                # 잡음/무음 구간에서 발생하는 에러 무시
                return ""
            print(f"Realtime STT Internal Error: {e}")
            raise e
            
        finally:
            # 임시 파일 삭제
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    def _preprocess_audio(self, audio_data: bytes | str, quality: str = "fast") -> str:
        """
        오디오 전처리: 잡음 제거(Denoise) 및 증폭(Normalize)
        - audio_data: bytes(실시간) 또는 str(파일 경로)
        - quality: "fast"(실시간용) 또는 "high"(파일전사용)
        - Returns: 전처리된 WAV 임시 파일 경로
        """
        import tempfile
        import os
        try:
            import numpy as np
            import noisereduce as nr
            from pydub import AudioSegment, effects

            print(f"Preprocessing start... Quality: {quality}")

            # 1. 입력 데이터 로드 -> AudioSegment
            if isinstance(audio_data, str): # 파일 경로인 경우
                print(f"  Loading audio from file: {audio_data}")
                original_audio = AudioSegment.from_file(audio_data)
                raw_path = None
            else: # bytes인 경우 (실시간)
                print(f"  Loading audio from bytes (length: {len(audio_data)} bytes)")
                # WebM 등 포맷 헤더 문제 가능성 -> raw 저장 후 pydub 로드 시도
                with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                    f.write(audio_data)
                    raw_path = f.name
                
                # 매우 중요: WebM 스트림은 지속 시간이 없거나 헤더가 꼬일 수 있음.
                # format="webm" 명시 또는 ffmpeg 프로브 필요할 수 있음.
                original_audio = AudioSegment.from_file(raw_path)

            print(f"  Audio Loaded. Duration: {len(original_audio)}ms")

            # 2. AudioSegment -> Numpy Array 변환
            original_audio = original_audio.set_frame_rate(16000).set_channels(1)
            samples = np.array(original_audio.get_array_of_samples())
            
            # 3. [Denoise] 잡음 제거
            print("  Denoising audio...")
            if quality == "high": # 파일 전사용 (꼼꼼하게)
                reduced_noise_audio = nr.reduce_noise(
                    y=samples, sr=16000, 
                    stationary=True, 
                    prop_decrease=0.90, # 90% 제거
                    n_std_thresh_stationary=1.5
                )
            else: # 실시간용 (적당히)
                reduced_noise_audio = nr.reduce_noise(
                    y=samples, sr=16000, 
                    stationary=True, 
                    prop_decrease=0.75, # 75% 제거
                    n_std_thresh_stationary=1.5
                )

            # 4. Numpy -> AudioSegment 복원
            denoised_segment = AudioSegment(
                reduced_noise_audio.tobytes(), 
                frame_rate=16000,
                sample_width=original_audio.sample_width, 
                channels=1
            )

            # 5. [Normalize] 증폭 및 평준화
            print("  Normalizing audio...")
            denoised_segment = effects.normalize(denoised_segment)
            denoised_segment = denoised_segment + 5 # +5dB 추가 확보

            # 결과 저장
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                denoised_segment.export(temp_path, format="wav")
            
            print(f"Preprocessing Done. Saved to {temp_path}")

            # 임시 파일 정리
            if raw_path and os.path.exists(raw_path):
                os.remove(raw_path)
                
            return temp_path

        except Exception as e:
            print(f"!! Preprocessing Failed: {e}")
            # 실패 시 안전하게 원본 유지 (fallback)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                if isinstance(audio_data, bytes):
                    f.write(audio_data)
                    print(f"  Fallback: Saved raw bytes to {f.name}")
                    return f.name
                else: 
                    # 파일인 경우 그냥 원본 경로 복사하거나 그대로 사용해야 하는데
                    # 여기선 안전하게 pydub로 읽어서 wav 저장
                    # AudioSegment.from_file(audio_data).export(f.name, format="wav")
                    print(f"  Fallback: Using original file path {audio_data}")
                    return str(audio_data)
    
    async def transcribe_file_chunked(self, file_path: str, language: str = "ko", progress_callback=None) -> list:
        """
        녹음 파일 전사 (오버래핑 청킹 적용) - 긴 파일 처리용
        10초 청크, 2초 오버랩
        """
        print(f"[청킹 전사 시작] {file_path}")
        self._initialize_model()
        
        cleaned_path = None
        try:
            # [전처리] 파일 모드용 고품질 Denoise & Normalize 적용
            # CPU 연산량이 많으므로 별도 스레드에서 실행 (Non-blocking)
            import asyncio
            print(f"[전처리 중] 잡음 제거 및 오디오 증폭...")
            cleaned_path = await asyncio.to_thread(self._preprocess_audio, file_path, quality="high")
            
            from pydub import AudioSegment
            import tempfile
            import os
            
            # 오디오 파일 로드 (전처리된 파일 사용)
            if cleaned_path:
                 audio = AudioSegment.from_file(cleaned_path)
            else:
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
