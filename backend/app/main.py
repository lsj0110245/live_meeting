from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    description="AI 기반 실시간 회의록 자동 생성 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 헬스 체크 엔드포인트
@app.get("/")
async def root():
    """기본 엔드포인트 - 헬스 체크"""
    return {
        "message": "LiveMeeting API is running!",
        "app": settings.APP_NAME,
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}


# 데이터베이스 연결 테스트 엔드포인트
@app.get("/db-test")
async def test_database():
    """데이터베이스 연결 테스트"""
    from app.db.session import engine
    from sqlalchemy import text
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            return {
                "status": "success",
                "message": "Database connection successful!",
                "result": result.scalar()
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        }


# API 라우터 등록 (나중에 추가)
# from app.api.endpoints import auth, recording, upload, meeting, export
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
# app.include_router(recording.router, prefix="/api/recording", tags=["Recording"])
# app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
# app.include_router(meeting.router, prefix="/api/meeting", tags=["Meeting"])
# app.include_router(export.router, prefix="/api/export", tags=["Export"])
