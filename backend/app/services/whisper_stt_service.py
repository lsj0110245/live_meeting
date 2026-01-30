import torch
import os
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from app.core.config import settings

class WhisperSTTService:
    """
    Whisper 모델을 직접 로드하여 GPU 메모리를 세밀하게 제어하는 STT 서비스
    """
    def __init__(self):
        self.model = None
        self.processor = None
        self.pipe = None
        self.device = None
        self.torch_dtype = None
        
    def _initialize_model(self):
        """
        Whisper 모델 초기화 (필요할 때만 로드)
        """
        if self.pipe is not None:
            return  # 이미 초기화됨
            
        print("Whisper 모델 초기화 중...")
        
        # GPU 사용 가능 여부 확인
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
        
        # Whisper 모델 ID (medium 모델 사용 - Docker STT와 동일)
        model_id = "openai/whisper-medium"
        
        # 모델 다운로드 및 로드
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id,
            torch_dtype=self.torch_dtype,
            low_cpu_mem_usage=True,  # CPU 메모리 절약
            use_safetensors=True     # 안전하고 빠른 모델 로딩
        )
        self.model.to(self.device)
        
        # Processor 로드
        self.processor = AutoProcessor.from_pretrained(model_id)
        
        # Pipeline 생성 (핵심!)
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            torch_dtype=self.torch_dtype,
            device=self.device,
            return_timestamps=True,     # 타임스탬프 반환
            chunk_length_s=30,          # 30초씩 청크 분할 (회의 발화 단위)
            stride_length_s=5,          # 5초 겹침 (약 17% 오버랩, 화자 전환 시 끊김 방지)
        )
        
        print(f"Whisper 모델 초기화 완료 (Device: {self.device})")
    
    def _cleanup_gpu(self):
        """
        GPU 메모리 정리
        """
        if self.device == "cuda":
            torch.cuda.empty_cache()
            print("GPU 메모리 캐시 클리어 완료")
    
    async def transcribe_file(self, file_path: str, language: str = "ko") -> str:
        """
        오디오 파일을 전사하여 텍스트 반환
        
        Args:
            file_path: 오디오 파일 경로
            language: 언어 코드 (기본값: "ko")
            
        Returns:
            전사된 텍스트
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        try:
            # 모델 초기화 (처음 호출 시에만)
            self._initialize_model()
            
            print(f"STT 전사 시작: {file_path}")
            
            # Whisper 전사 실행
            result = self.pipe(
                file_path,
                generate_kwargs={
                    "language": language,
                    "task": "transcribe"
                }
            )
            
            # 결과에서 텍스트 추출
            transcript_text = result.get("text", "")
            
            print(f"STT 전사 완료: {len(transcript_text)} 글자")
            
            # GPU 메모리 정리
            self._cleanup_gpu()
            
            return transcript_text
            
        except Exception as e:
            print(f"Whisper STT Error: {str(e)}")
            # 에러 발생 시에도 GPU 메모리 정리
            self._cleanup_gpu()
            raise e
    
    def unload_model(self):
        """
        모델을 메모리에서 완전히 제거 (선택적 사용)
        """
        if self.model is not None:
            del self.model
            del self.processor
            del self.pipe
            self.model = None
            self.processor = None
            self.pipe = None
            self._cleanup_gpu()
            print("Whisper 모델 언로드 완료")

# 싱글톤 인스턴스
whisper_stt_service = WhisperSTTService()
