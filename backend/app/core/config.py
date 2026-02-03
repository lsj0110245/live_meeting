from pydantic_settings import BaseSettings
from typing import List


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
    
    # Local STT (Faster-Whisper)
    LOCAL_STT_URL: str = "http://localhost:9000"  # 레거시 호환용 (사용 안 함)
    
    # LLM 설정 (Ollama)
    LLM_MODEL: str = "llama3.1"  # Ollama 모델명
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.3  # LLM 온도 설정
    OLLAMA_BASE_URL: str = "http://llm:11434"  # Docker 내부 통신
    
    # LangSmith (Monitoring)
    LANGCHAIN_TRACING_V2: str = "false"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str = "LiveMeeting"
    
    # Local AI URLs (On-Premise)
    LOCAL_STT_URL: str = "http://stt:9000"
    LOCAL_LLM_URL: str = "http://llm:11434"
    
    # JWT 인증 설정
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    # CORS 설정
    CORS_ORIGINS: str = "http://localhost:8000,http://localhost:3000,http://localhost:8001"
    
    # 파일 업로드 설정
    MAX_FILE_SIZE_MB: int = 500
    ALLOWED_EXTENSIONS: str = "mp3,wav,m4a,mp4,webm,avi,mov"
    
    # STT 설정
    STT_LANGUAGE: str = "ko-KR"
    STT_MODEL_SIZE: str = "deepdml/faster-whisper-large-v3-turbo-ct2"  # openai/whisper-large-v3-turbo (CT2)
    STT_DEVICE: str = "cuda"
    STT_COMPUTE_TYPE: str = "float16"
    
    # 스토리지 설정
    STORAGE_TYPE: str = "local"  # or "s3"
    S3_BUCKET_NAME: str | None = None
    S3_REGION: str | None = None
    
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
