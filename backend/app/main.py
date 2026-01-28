from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from app.core.config import settings
import os

# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    description="AI 기반 실시간 회의록 자동 생성 시스템",
    version="1.0.0"
)

# Static Files & Templates 설정
import os
from pathlib import Path

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent  # app 디렉토리
BACKEND_ROOT = BASE_DIR.parent  # backend 디렉토리 (Docker에서는 /app)

# Frontend 디렉토리 찾기
# 1. Docker 환경 (/app/frontend) 우선 확인
frontend_dir = Path("/app/frontend")

# 2. Docker 경로에 없으면 로컬 개발 환경 경로 확인 (../../frontend)
if not (frontend_dir / "static").exists():
    # backend/app -> backend -> live_meeting -> frontend
    # BACKEND_ROOT가 backend일 경우 그 상위가 live_meeting
    project_root = BACKEND_ROOT.parent
    possible_local_frontend = project_root / "frontend"
    if (possible_local_frontend / "static").exists():
        frontend_dir = possible_local_frontend

static_dir = frontend_dir / "static"
templates_dir = frontend_dir / "templates"

@app.on_event("startup")
async def startup_event():
    print(f"DEBUG: DATABASE_URL={settings.DATABASE_URL}")
    
    # 템플릿 디렉토리 확인
    if not templates_dir.exists():
        print(f"WARNING: Templates directory not found at {templates_dir}")
    if not static_dir.exists():
        print(f"WARNING: Static directory not found at {static_dir}")

# 디렉토리가 없으면 생성 (Docker 마운트 이슈 방지용 안전장치)
if not static_dir.exists():
    print(f"WARNING: Static directory {static_dir} not found. Creating it.")
    static_dir.mkdir(parents=True, exist_ok=True)

if not templates_dir.exists():
    print(f"WARNING: Templates directory {templates_dir} not found. Creating it.")
    templates_dir.mkdir(parents=True, exist_ok=True)

# 디버깅을 위한 로그 출력
print(f"INFO: Base Directory: {BASE_DIR}")
print(f"INFO: Frontend Directory resolved to: {frontend_dir}")
print(f"INFO: Static Directory exists: {static_dir.exists()}")
print(f"INFO: Templates Directory exists: {templates_dir.exists()}")

if not static_dir.exists():
    print(f"WARNING: Static directory not found at {static_dir}")
    # 에러를 방지하기 위해 빈 디렉토리라도 생성하거나 예외 처리 필요할 수 있음
    # 여기서는 진행하지만 실행 시 에러 발생 가능성 있음

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/static/media", StaticFiles(directory="media"), name="media") # 미디어 파일 서빙
templates = Jinja2Templates(directory=str(templates_dir))

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 헬스 체크 엔드포인트
@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}


# --- Frontend Pages ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """메인 페이지 (대시보드)"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 페이지"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """회원가입 페이지"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/meeting/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail_page(request: Request, meeting_id: int):
    """회의 상세 페이지"""
    return templates.TemplateResponse("meeting_detail.html", {"request": request})



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


# API 라우터 등록
from app.api.endpoints import auth, recording, upload, meeting, export
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(recording.router, prefix="/api/recording", tags=["Recording"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(meeting.router, prefix="/api/meeting", tags=["Meeting"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])

# 나중에 추가될 라우터들
# from app.api.endpoints import recording, upload, meeting, export
# app.include_router(recording.router, prefix="/api/recording", tags=["Recording"])
# app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
# app.include_router(meeting.router, prefix="/api/meeting", tags=["Meeting"])
# app.include_router(export.router, prefix="/api/export", tags=["Export"])
