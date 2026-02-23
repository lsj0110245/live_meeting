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
            # [Fix] 전역 락을 사용하여 레이스 컨디션 방지
            from app.api.endpoints.recording import _model_lock
            with _model_lock:
                if self.model is None: # 이중 체크
                    print(f"Faster-Whisper 모델 초기화 중: {self.model_size}")
                    hf_token = os.environ.get("HUGGING_FACE_TOKEN")
                    if hf_token and not os.environ.get("HF_TOKEN"):
                        os.environ["HF_TOKEN"] = hf_token
                        print("HF_TOKEN 환경 변수가 설정되었습니다.")
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
        try:
            # [최적화] 파일 전사 정확도 극대화 설정
            # Blocking 방지를 위해 전체 전사 로직을 별도 스레드에서 실행
            # 중요: segments는 제너레이터이므로 순회(iteration)도 스레드 안에서 해야 함
            import asyncio

            def _transcribe_in_thread():
                """스레드 내부에서 실행될 전사 함수"""
                # [수정] 모델 초기화도 스레드 내부에서 수행
                self._initialize_model()

                segments, info = self.model.transcribe(
                    file_path,
                    language=language,
                    beam_size=10,
                    best_of=10,
                    temperature=0,
                    repetition_penalty=1.2,
                    condition_on_previous_text=True,
                    initial_prompt="회의 녹음입니다. 자연스러운 한국어 문장으로 기록해 주세요.",
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=1000,
                        speech_pad_ms=400,
                        threshold=0.5, # VAD 임계값 추가
                        min_speech_duration_ms=250 # 너무 짧은 소리는 무시
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

    async def transcribe_realtime(self, audio_bytes: bytes, language: str = "ko", skip_duration_ms: int = 0) -> str:
        """
        실시간 전사 (속도 우선)

        Args:
            audio_bytes: 실시간 오디오 스트림 데이터
            language: 언어 코드
            skip_duration_ms: 오디오 시작 부분에서 건너뛸 시간 (ms) - 헤더 중복 방지용
        """
        if not audio_bytes or len(audio_bytes) < 1024:
            # print(f"Skipping tiny audio chunk: {len(audio_bytes)} bytes")
            return ""

        # [공통 전처리] Denoise & Normalize 적용 (CPU 작업 - 별도 스레드 무방)
        import asyncio
        import tempfile
        import os
        temp_path = None

        try:
            # [품질 개선] 전처리
            print(f"[STT] Starting preprocessing for {len(audio_bytes)} bytes")
            temp_path = await asyncio.to_thread(
                self._preprocess_audio,
                audio_bytes,
                quality="fast",
                skip_duration_ms=skip_duration_ms
            )
            print(f"[STT] Preprocessing completed: {temp_path}")

            # [수정] 모델 초기화와 전사를 동일 스레드에서 실행하여 CUDA 컨텍스트 충돌/Deadlock 방지
            def _realtime_transcribe_task():
                self._initialize_model()
                return self.model.transcribe(
                    temp_path,
                    language=language,
                    beam_size=5,
                    best_of=5,
                    temperature=0,
                    repetition_penalty=1.3,
                    no_repeat_ngram_size=3,
                    condition_on_previous_text=False,
                    initial_prompt="회의 녹음입니다. 자연스러운 한국어 문장으로 기록해 주세요.",
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=800,
                        speech_pad_ms=400,
                        min_speech_duration_ms=300,
                        threshold=0.5
                    ),
                    no_speech_threshold=0.6,
                    log_prob_threshold=-1.0
                )

            # 단일 스레드에서 실행
            segments, info = await asyncio.to_thread(_realtime_transcribe_task)

            transcript_text = ""
            for segment in segments:
                text = segment.text.strip()
                # print(f"Detected Segment: {text}, Prob: {segment.no_speech_prob:.4f}") # 디버그용

                # [필터링] 환각 및 침묵 패턴 제거
                if segment.no_speech_prob > 0.8: # 확실한 침묵인 경우
                    continue

                # [강화된 필터링] 테스트 패턴, 반복적인 숫자, 환각 텍스트 제거
                # 예: "아자차카타파하", "010-1234-5678" 같은 무의미한 예시 문구
                if re.search(r"자막|박진희|vostfr|Subtitles|Thank you|시청해 주셔서|무단 전재|배포 금지|감사합니다|가나다라|아자차카|마바사|010-1234-5678|123-456-7890", text, re.I):
                    # 환각 패턴이 포함된 경우 스킵
                    continue

                # [추가 필터링] 의미 없는 반복 문자열 (예: ".......")
                if re.match(r'^[\.\,\?\!\s]*$', text):
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

    def _bytes_to_wav_via_ffmpeg(self, audio_bytes: bytes, skip_duration_ms: int = 0) -> str | None:
        """
        ffmpeg stdin pipe를 통해 bytes -> WAV 변환 (포맷 자동 감지).
        WebM 스트리밍 청크처럼 헤더가 불완전해도 최대한 처리.
        Returns: 성공 시 WAV 임시 파일 경로, 실패 시 None
        """
        import tempfile
        import subprocess
        import os

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_f:
            out_path = out_f.name

        try:
            cmd = [
                "ffmpeg",
                "-y",                        # 덮어쓰기 허용
                "-loglevel", "warning",      # 경고 이상만 출력
                "-f", "webm",                # 입력 포맷 힌트 (EBML 헤더 없어도 관대하게 처리)
                "-i", "pipe:0",              # stdin에서 읽기
                "-ar", "16000",              # 16kHz 리샘플
                "-ac", "1",                  # 모노
                "-f", "wav",                 # 출력 포맷
                "-acodec", "pcm_s16le",      # PCM 16-bit LE
            ]

            # skip_duration_ms가 있으면 시작부터 해당 시간 제거
            if skip_duration_ms > 0:
                skip_sec = skip_duration_ms / 1000.0
                cmd += ["-ss", str(skip_sec)]

            cmd.append(out_path)

            result = subprocess.run(
                cmd,
                input=audio_bytes,
                capture_output=True,
                timeout=15
            )

            if result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 44:
                return out_path
            else:
                stderr_msg = result.stderr.decode("utf-8", errors="replace")
                print(f"  [ffmpeg pipe] Failed (code={result.returncode}): {stderr_msg[:200]}")
                if os.path.exists(out_path):
                    os.remove(out_path)
                return None

        except Exception as e:
            print(f"  [ffmpeg pipe] Exception: {e}")
            if os.path.exists(out_path):
                os.remove(out_path)
            return None

    def _preprocess_audio(self, audio_data: bytes | str, quality: str = "fast", skip_duration_ms: int = 0) -> str:
        """
        오디오 전처리: WAV 변환 + 잡음 제거(Denoise) + 증폭(Normalize)
        - audio_data: bytes(실시간) 또는 str(파일 경로)
        - quality: "fast"(실시간용) 또는 "high"(파일전사용)
        - skip_duration_ms: 오디오 시작 부분에서 스킵할 시간 (실시간 헤더 중복 방지)
        - Returns: 전처리된 WAV 임시 파일 경로
        """
        import tempfile
        import os
        try:
            import numpy as np
            import noisereduce as nr
            from pydub import AudioSegment, effects

            print(f"Preprocessing start... Quality: {quality}")

            # ── 1. 입력 데이터 로드 ──────────────────────────────────────────
            if isinstance(audio_data, str):
                # 파일 경로인 경우: pydub로 직접 로드
                print(f"  Loading audio from file: {audio_data}")
                original_audio = AudioSegment.from_file(audio_data)

            else:
                # bytes인 경우 (실시간 WebM 스트림):
                # [핵심 수정] pydub(파일 경유)가 아닌 ffmpeg stdin pipe로 직접 변환
                # → 불완전한 EBML 헤더를 가진 WebM 청크도 안정적으로 처리
                print(f"  Loading audio from bytes via ffmpeg pipe (length: {len(audio_data)} bytes)")
                wav_path = self._bytes_to_wav_via_ffmpeg(audio_bytes=audio_data, skip_duration_ms=skip_duration_ms)

                if wav_path is None:
                    # ffmpeg도 실패한 경우: 무음 500ms 반환 (Whisper가 조용히 무시)
                    print("  [Fallback] ffmpeg pipe failed → returning silent WAV")
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as sf:
                        silent = AudioSegment.silent(duration=500, frame_rate=16000)
                        silent.export(sf.name, format="wav")
                        return sf.name

                # ffmpeg가 이미 skip_duration_ms를 처리했으므로 이후 단계에서는 0으로 설정
                skip_duration_ms = 0
                original_audio = AudioSegment.from_wav(wav_path)
                os.remove(wav_path)  # 임시 파일 즉시 정리

            print(f"  Audio Loaded. Duration: {len(original_audio)}ms, Loudness: {original_audio.dBFS:.2f}dBFS")

            # ── 2. [헤더 중복 방지] skip_duration_ms 만큼 잘라내기 ─────────
            if skip_duration_ms > 0 and len(original_audio) > skip_duration_ms:
                print(f"  Skipping initial {skip_duration_ms}ms of audio (header redundancy).")
                original_audio = original_audio[skip_duration_ms:]

            # ── 3. [침묵 감지] ────────────────────────────────────────────
            # realtime(fast) 모드: Whisper vad_filter가 이미 침묵을 걸러주므로 여기서는 패스
            # high 품질 모드(파일 전사): 완전 무음(-55dBFS) 수준만 조기 차단
            SILENCE_THRESHOLD_DBFS = -55  # -55dBFS 이하는 거의 디지털 무음
            if quality == "high" and original_audio.dBFS < SILENCE_THRESHOLD_DBFS:
                print(f"  Audio is completely silent ({original_audio.dBFS:.1f}dBFS). Returning silent WAV.")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    temp_path = f.name
                    AudioSegment.silent(duration=500, frame_rate=16000).export(temp_path, format="wav")
                return temp_path
            elif quality == "fast":
                # realtime 모드: 음량 정보만 로그로 남기고 Whisper VAD에 위임
                print(f"  Audio loudness: {original_audio.dBFS:.1f}dBFS (Whisper VAD will handle silence)")

            # ── 4. AudioSegment → Numpy Array ────────────────────────────────
            original_audio = original_audio.set_frame_rate(16000).set_channels(1)
            samples = np.array(original_audio.get_array_of_samples())

            # ── 5. [Denoise] 잡음 제거 ───────────────────────────────────────
            if quality == "high":
                print("  Denoising audio (High Quality)...")
                reduced_noise_audio = nr.reduce_noise(
                    y=samples, sr=16000,
                    stationary=True,
                    prop_decrease=0.90,
                    n_std_thresh_stationary=1.5
                )
            else:
                print("  Skipping Denoise for Realtime (Speed Priority)...")
                reduced_noise_audio = samples

            # ── 6. Numpy → AudioSegment 복원 ─────────────────────────────────
            denoised_segment = AudioSegment(
                reduced_noise_audio.tobytes(),
                frame_rate=16000,
                sample_width=original_audio.sample_width,
                channels=1
            )

            # ── 7. [Normalize] 증폭 및 평준화 ────────────────────────────────
            print("  Normalizing audio...")
            denoised_segment = effects.normalize(denoised_segment)
            denoised_segment = denoised_segment + 5  # +5dB 추가 확보

            # ── 8. 결과 WAV 저장 ─────────────────────────────────────────────
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                denoised_segment.export(temp_path, format="wav")

            print(f"Preprocessing Done. Saved to {temp_path}")
            return temp_path

        except Exception as e:
            print(f"!! Preprocessing Failed: {e}")
            # [Fallback] ffmpeg pipe로 최소한의 WAV 변환만 시도
            if isinstance(audio_data, bytes):
                wav_path = self._bytes_to_wav_via_ffmpeg(audio_bytes=audio_data, skip_duration_ms=0)
                if wav_path:
                    print(f"  Fallback: ffmpeg pipe WAV saved to {wav_path}")
                    return wav_path
                # ffmpeg도 실패 → 무음 반환
                import tempfile as _tf
                from pydub import AudioSegment as _AS
                with _tf.NamedTemporaryFile(suffix=".wav", delete=False) as sf:
                    _AS.silent(duration=500, frame_rate=16000).export(sf.name, format="wav")
                    print(f"  Fallback: returning silent WAV {sf.name}")
                    return sf.name
            else:
                # 파일 경로인 경우 원본 그대로 반환
                print(f"  Fallback: Using original file path {audio_data}")
                return str(audio_data)

    async def transcribe_file_chunked(self, file_path: str, language: str = "ko", progress_callback=None) -> list:
        """
        녹음 파일 전사 (오버래핑 청킹 적용) - 긴 파일 처리용
        10초 청크, 2초 오버랩
        """
        print(f"[청킹 전사 시작] {file_path}")
        print(f"[청킹 전사 시작] {file_path}")

        cleaned_path = None
        try:
            # [전처리] 파일 모드용 고품질 Denoise & Normalize 적용
            # CPU 연산량이 많으므로 별도 스레드에서 실행 (Non-blocking)
            import asyncio
            print(f"[전처리 중] 잡음 제거 및 오디오 증폭...")
            cleaned_path = await asyncio.to_thread(self._preprocess_audio, file_path, quality="high")

            # [수정] 전체 청킹 전사 로직을 별도 스레드로 격리하여 Blocking 방지
            def _transcribe_chunked_in_thread():
                self._initialize_model()

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
                            initial_prompt="회의 녹음입니다. 자연스러운 한국어 문장으로 기록해 주세요.",
                            vad_filter=True,
                            vad_parameters=dict(
                                min_silence_duration_ms=1000,
                                speech_pad_ms=400,
                                threshold=0.5,
                                min_speech_duration_ms=250
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

                    # 진행률 업데이트 (주의: 스레드 내부에서 호출되므로 thread-safe해야 함. 보통 간단한 print/callback은 OK)
                    if progress_callback:
                        percent = int((end_ms / total_duration_ms) * 100)
                        progress_callback(percent)

                    print(f"  청크 {chunk_count} 처리 완료 ({start_ms/1000:.1f}s ~ {end_ms/1000:.1f}s)")

                # 중복 제거 (오버랩 구간)
                result_segments = self._merge_overlapping_segments(all_segments)
                return result_segments

            # 메인 로직 스레드에서 실행
            result_segments = await asyncio.to_thread(_transcribe_chunked_in_thread)

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
