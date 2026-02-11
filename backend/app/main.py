from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import mimetypes
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

# 2. Docker 경로에 없으면 로컬 개발 환경 경로 확인
if not (frontend_dir / "static").exists():
    # 현재 backend 디렉토리의 부모(프로젝트 루트)에서 frontend 찾기
    project_root = BACKEND_ROOT.parent
    local_frontend = project_root / "frontend"
    
    if (local_frontend / "static").exists():
        frontend_dir = local_frontend
    else:
        # Fallback: backend 내부에 frontend가 있는 구조인 경우 (혹시 모를 경우대비)
        frontend_dir = BACKEND_ROOT / "frontend"

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

    # [STT 사전 로드] 서버 구동 시 모델 미리 불러오기 (백그라운드)
    # 첫 전사 시 지연 시간을 제거하기 위함
    try:
        from app.services.stt_service import stt_service
        import asyncio
        print("INFO: Pre-loading STT model in background...")
        asyncio.create_task(asyncio.to_thread(stt_service.initialize_model))
    except Exception as e:
        print(f"WARNING: Failed to pre-load STT model: {e}")

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

# 미디어 파일 디렉토리 설정 (settings.MEDIA_ROOT 사용)
media_dir = settings.MEDIA_ROOT
if not media_dir.exists():
    media_dir.mkdir(parents=True, exist_ok=True)

print(f"INFO: Media Directory (MEDIA_ROOT) resolved to: {media_dir}")
# MIME 타입 보강 (음성 재생 호환성)
mimetypes.add_type('audio/webm', '.webm')  # 다시 audio/webm으로 복구 (오디오 전용)
mimetypes.add_type('audio/wav', '.wav')
mimetypes.add_type('audio/mpeg', '.mp3')

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/media/{file_path:path}")
async def get_media(file_path: str):
    """
    미디어 파일 서빙 엔드포인트
    - FileResponse를 사용하여 브라우저의 Range 요청(Seeking) 및 캐싱 자동 처리
    """
    abs_path = settings.MEDIA_ROOT / file_path
    if not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(status_code=403, detail=f"Permission denied or file not found: {file_path}") # 403인 경우도 고려 (권한)
    
    # MIME 타입 유추 (이미 위에서 .webm 등 보강됨)
    return FileResponse(
        abs_path,
        filename=os.path.basename(abs_path),
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

# --------------------------------------------------
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

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    from fastapi import Response
    return Response(status_code=204)


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

@app.get("/folders/{folder_name}", response_class=HTMLResponse)
async def folder_page(request: Request, folder_name: str):
    """폴더별 페이지 (SPA 라우팅 지원)"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/meeting/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail_page(request: Request, meeting_id: int):
    """회의 상세 페이지"""
    return templates.TemplateResponse("meeting_detail.html", {"request": request})

@app.get("/recording", response_class=HTMLResponse)
async def recording_page(request: Request):
    """실시간 녹음 페이지"""
    return templates.TemplateResponse("recording.html", {"request": request})

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """프로필 페이지"""
    return templates.TemplateResponse("profile.html", {"request": request})



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
from app.api.endpoints import auth, recording, upload, meeting, export, users, folders, progress
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(folders.router, prefix="/api/folders", tags=["Folders"])
app.include_router(recording.router, prefix="/api/recording", tags=["Recording"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(meeting.router, prefix="/api/meeting", tags=["Meeting"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(progress.router, prefix="/api/progress", tags=["Progress"])

# 나중에 추가될 라우터들
# from app.api.endpoints import recording, upload, meeting, export
# app.include_router(recording.router, prefix="/api/recording", tags=["Recording"])
# app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
# app.include_router(meeting.router, prefix="/api/meeting", tags=["Meeting"])
# app.include_router(export.router, prefix="/api/export", tags=["Export"])
