from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os


class Settings(BaseSettings):
    """
    애플리케이션 설정 관리
    환경 변수(.env)에서 설정을 로드합니다.
    """
    # 애플리케이션 설정
    APP_NAME: str = "LiveMeeting"
    DEBUG: bool = True
    
    # 데이터베이스 설정
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL: str
    
    # LLM 설정 (Ollama)
    LLM_MODEL: str = "llama3.1:latest"  # Ollama 모델명 (태그 명시)
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.3  # LLM 온도 설정
    OLLAMA_BASE_URL: str = "http://llm:11434"  # Docker 내부 통신

    # LangSmith (Monitoring)
    LANGCHAIN_TRACING_V2: str = "false"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str = "LiveMeeting"
    
    # JWT 인증 설정
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    # CORS 설정
    CORS_ORIGINS: str = "http://localhost:8000,http://localhost:3000,http://localhost:8001"
    
    # 파일 업로드 설정
    MAX_FILE_SIZE_MB: int = 500
    ALLOWED_EXTENSIONS: str = "mp3,wav,m4a,mp4,webm,avi,mov"
    
    # STT 설정 (인식 부하 및 VRAM 관리를 위해 medium 권장)
    STT_LANGUAGE: str = "ko-KR"
    STT_MODEL_SIZE: str = "deepdml/faster-whisper-large-v3-turbo-ct2"  # 고품질 인식을 위해 large-v3-turbo 사용
    STT_DEVICE: str = "cuda"
    STT_COMPUTE_TYPE: str = "float16"
    
    # 스토리지 설정
    STORAGE_TYPE: str = "local"  # or "s3"
    S3_BUCKET_NAME: str | None = None
    S3_REGION: str | None = None

    @property
    def MEDIA_ROOT(self) -> Path:
        """
        프로젝트 루트의 media 디렉토리에 대한 절대 경로 반환
        app/core/config.py -> core -> app -> backend -> project_root/media
        """
        # Docker 환경 (/app/media) 우선 확인
        if os.path.exists("/app/media"):
            return Path("/app/media")
        
        # 로컬 환경: backend/app/core/config.py 기준 상위 3단계 (backend) -> 그 상위 (project_root)
        backend_root = Path(__file__).resolve().parent.parent.parent
        project_root = backend_root.parent
        return project_root / "media"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]


settings = Settings()
