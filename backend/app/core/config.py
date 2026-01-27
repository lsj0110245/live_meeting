from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "LiveMeeting"
    DEBUG: bool = True
    
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL: str
    
    # AWS (Nova-2 STT)
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    
    # LLM API
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-4"
    LLM_MAX_TOKENS: int = 2000
    LLM_TEMPERATURE: float = 0.3
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:8000,http://localhost:3000"
    
    # File Upload
    MAX_FILE_SIZE_MB: int = 500
    ALLOWED_EXTENSIONS: str = "mp3,wav,m4a,mp4,webm,avi,mov"
    
    # STT
    STT_LANGUAGE: str = "ko-KR"
    
    # Storage
    STORAGE_TYPE: str = "local"  # or "s3"
    S3_BUCKET_NAME: str | None = None
    S3_REGION: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]


settings = Settings()
