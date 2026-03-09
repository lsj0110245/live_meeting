# 📋 LiveMeeting — AI 회의록 자동 생성 시스템

**실시간 녹음 & 파일 업로드 → AI 음성 인식(STT) → LLM 회의록 자동 생성**

[![Python](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18%20+%20pgvector-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![Ollama](https://img.shields.io/badge/Ollama-EXAONE%203.5-orange.svg)](https://ollama.com/)

---

## 📋 목차

1. [프로젝트 개요](#-프로젝트-개요)
2. [주요 기능](#-주요-기능)
3. [시스템 아키텍처](#-시스템-아키텍처)
4. [프로젝트 구조](#-프로젝트-구조)
5. [빠른 시작](#-빠른-시작)
6. [기술 스택](#-기술-스택)
7. [API 문서](#-api-문서)
8. [DB 스키마](#-db-스키마)
9. [개발 가이드](#-개발-가이드)

---

## 🎯 프로젝트 개요

LiveMeeting은 **AI 기술을 활용한 회의록 자동 생성 시스템**입니다.

사용자가 브라우저에서 **실시간 녹음**을 하거나 **녹음 파일을 업로드**하면, AI가 음성을 텍스트로 변환(STT)한 뒤 LLM이 구조화된 회의록을 자동 생성합니다.

### 핵심 가치

- ✅ **실시간 녹음**: 브라우저에서 마이크를 통해 실시간 녹음 및 WebSocket 스트리밍
- ✅ **녹음 파일 업로드**: MP3, WAV, M4A, MP4, WebM 등 다양한 포맷 지원
- ✅ **AI 음성 인식 (STT)**: Faster-Whisper (large-v3-turbo) 기반 고속·고정밀 한국어 음성 인식
- ✅ **AI 회의록 생성**: EXAONE 3.5 (Ollama) LLM 기반 구조화된 회의록 자동 생성
- ✅ **중간 요약**: 실시간 녹음 중 일정 간격으로 중간 요약 자동 생성
- ✅ **LLM 전사 보정**: STT 전사 텍스트의 오타 및 문맥 오류 자동 보정
- ✅ **내보내기**: CSV / XLSX 형식으로 회의록 내보내기
- ✅ **폴더 관리**: 회의를 폴더별로 분류·관리
- ✅ **사용자 인증**: JWT 기반 회원가입·로그인·프로필 관리

---

## 🚀 주요 기능

### 1. **실시간 녹음 & STT**

- 브라우저 `MediaRecorder API`를 통한 마이크 녹음
- WebSocket 기반 오디오 청크 스트리밍 → 서버 실시간 전사
- Faster-Whisper (GPU/CUDA) 기반 고속 음성 인식
- 오디오 전처리: FFmpeg 변환 + NoisReduce 잡음 제거 + 증폭(Normalize)
- 실시간 녹음 중 중간 요약 자동 생성

### 2. **녹음 파일 업로드 & 처리**

- 드래그 앤 드롭 파일 업로드 지원
- MP3, WAV, M4A, MP4, WebM, AVI, MOV 포맷 지원
- 파일 중복 방지 (SHA-256 해시 기반)
- 오버래핑 청킹 (10초 청크, 2초 오버랩) 방식으로 긴 파일 정확하게 처리
- 비동기 백그라운드 작업으로 처리 진행률 실시간 확인

### 3. **AI 회의록 생성**

- EXAONE 3.5 (7.8B, Ollama 로컬 구동) LLM 기반 회의록 생성
- 구조화된 출력: 주요 안건, 논의 사항, 결정 사항, 액션 아이템
- 긴 텍스트 Map-Reduce 방식 청킹 요약
- STT 전사 텍스트 오타 및 문맥 보정 (하이브리드 전략)

### 4. **회의 관리**

- 회의 목록 조회 · 상세 보기 · 삭제
- 회의 메타데이터 입력 (제목, 설명, 회의 유형, 일시, 참석자, 작성자)
- 폴더별 회의 분류 (폴더 생성 · 이동 · 삭제)
- CSV / XLSX 내보내기

### 5. **사용자 관리**

- 이메일 기반 회원가입 · JWT 로그인
- 프로필 관리 (이름, 나이, 전화번호, 소속 팀, 프로필 이미지)

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  대시보드     │  │  실시간 녹음  │  │  회의록 상세  │       │
│  │  (index.html)│  │(recording.html)│ │(meeting_detail)│    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │ Fetch API       │ WebSocket       │ Fetch API     │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                           │
│                  Port: 8000 (Docker: 8001)                   │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  REST API    │  │  WebSocket   │  │  Jinja2 SSR  │       │
│  │  (endpoints) │  │  (recording) │  │  (templates) │       │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘       │
│         │                 │                                  │
│  ┌──────┴─────────────────┴──────────────────────────┐      │
│  │              Services Layer                        │      │
│  │  ┌──────────────┐  ┌──────────────┐               │      │
│  │  │ Faster-Whisper│  │  LLM Service │               │      │
│  │  │  STT Service  │  │  (Ollama)    │               │      │
│  │  │  (GPU/CUDA)   │  │  EXAONE 3.5  │               │      │
│  │  └──────────────┘  └──────────────┘               │      │
│  └───────────────────────────────────────────────────┘      │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────┐           ┌──────────────────┐
│   PostgreSQL 18  │           │   Ollama (LLM)   │
│   + pgvector     │           │   EXAONE 3.5:7.8b│
│   Port: 15432    │           │   Port: 11434    │
└──────────────────┘           └──────────────────┘
```

### Docker 컨테이너 구성

| 컨테이너 | 이미지 | 역할 | 포트 |
|----------|--------|------|------|
| **lm_backend** | python:3.10-slim (커스텀) | FastAPI 백엔드 + 프론트엔드 서빙 + STT | 8001 → 8000 |
| **lm_postgres** | pgvector/pgvector:pg18 | 데이터베이스 | 15432 → 5432 |
| **lm_llm** | ollama/ollama:latest | LLM 서버 (EXAONE 3.5) | 11434 → 11434 |

---

## 📁 프로젝트 구조

```
live_meeting/
├── backend/                          # FastAPI 백엔드
│   ├── Dockerfile                    # Docker 이미지 빌드
│   ├── start.sh                      # 컨테이너 시작 스크립트 (DB 대기 → Alembic → uvicorn)
│   ├── requirements.txt              # Python 의존성
│   ├── download_model.py             # STT 모델 빌드 시 다운로드
│   ├── alembic.ini                   # Alembic 설정
│   ├── alembic/                      # DB 마이그레이션
│   │   └── versions/                 # 마이그레이션 파일들
│   │
│   ├── app/                          # 애플리케이션 코드
│   │   ├── main.py                   # FastAPI 앱 진입점 (라우터, 미들웨어, 페이지 렌더링)
│   │   │
│   │   ├── api/                      # API 레이어
│   │   │   ├── deps.py               # 의존성 (JWT 인증, DB 세션)
│   │   │   └── endpoints/            # REST API 엔드포인트
│   │   │       ├── auth.py           # 인증 (회원가입 / 로그인)
│   │   │       ├── users.py          # 사용자 정보 · 프로필
│   │   │       ├── recording.py      # 실시간 녹음 WebSocket
│   │   │       ├── upload.py         # 녹음 파일 업로드 · STT 처리
│   │   │       ├── meeting.py        # 회의 CRUD · 요약 생성
│   │   │       ├── folders.py        # 폴더 관리
│   │   │       ├── export.py         # CSV / XLSX 내보내기
│   │   │       └── progress.py       # 처리 진행률 조회
│   │   │
│   │   ├── core/                     # 핵심 설정
│   │   │   ├── config.py             # 환경 변수 (Pydantic Settings)
│   │   │   └── security.py           # JWT 토큰 · bcrypt 해싱
│   │   │
│   │   ├── db/                       # 데이터베이스
│   │   │   ├── base.py               # SQLAlchemy Base
│   │   │   └── session.py            # DB 세션 관리
│   │   │
│   │   ├── models/                   # SQLAlchemy ORM 모델
│   │   │   ├── user.py               # 사용자
│   │   │   ├── meeting.py            # 회의
│   │   │   ├── transcript.py         # 전사 텍스트(세그먼트)
│   │   │   ├── summary.py            # 최종 요약 (1:1)
│   │   │   ├── intermediate_summary.py # 중간 요약 (1:N)
│   │   │   ├── folder.py             # 폴더
│   │   │   └── enums.py              # 상태 Enum (pending/recording/processing/completed/failed)
│   │   │
│   │   ├── schemas/                  # Pydantic 요청/응답 스키마
│   │   │   ├── user.py               # 사용자 스키마
│   │   │   ├── meeting.py            # 회의 스키마
│   │   │   ├── transcript.py         # 전사 스키마
│   │   │   └── folder.py             # 폴더 스키마
│   │   │
│   │   ├── services/                 # 비즈니스 로직 (서비스 레이어)
│   │   │   ├── faster_whisper_stt_service.py  # Faster-Whisper STT (녹음 파일 + 실시간)
│   │   │   ├── stt_service.py                 # STT 라우팅 (엔진 선택)
│   │   │   ├── llm_service.py                 # LLM 서비스 (Ollama EXAONE 3.5)
│   │   │   ├── meeting_tasks.py               # 백그라운드 요약 생성 Task
│   │   │   └── progress_service.py            # 진행률 관리
│   │   │
│   │   └── utils.py                  # 유틸리티 함수
│   │
│   └── scripts/                      # 유틸리티 스크립트
│       ├── check_status.py           # 상태 확인
│       ├── test_llm.py               # LLM 테스트
│       ├── verify_table.py           # 테이블 확인
│       ├── clean_stalled_tasks.py    # 중단 작업 정리
│       └── add_metadata_columns.py   # 메타데이터 컬럼 추가
│
├── frontend/                         # 프론트엔드 (Jinja2 SSR + Vanilla JS)
│   ├── templates/                    # HTML 템플릿
│   │   ├── base.html                 # 공통 레이아웃 (베이스 템플릿)
│   │   ├── index.html                # 메인 대시보드
│   │   ├── login.html                # 로그인 페이지
│   │   ├── register.html             # 회원가입 페이지
│   │   ├── recording.html            # 실시간 녹음 페이지
│   │   ├── meeting_detail.html       # 회의록 상세 페이지
│   │   ├── profile.html              # 프로필 페이지
│   │   └── components/               # 재사용 컴포넌트
│   │
│   └── static/                       # 정적 파일
│       ├── css/
│       │   └── style.css             # 메인 스타일시트
│       ├── js/
│       │   ├── common.js             # 공통 유틸리티
│       │   ├── auth.js               # 인증 (로그인/회원가입)
│       │   ├── dashboard.js          # 대시보드 로직
│       │   ├── recording.js          # 실시간 녹음 로직 (WebSocket)
│       │   ├── meeting.js            # 회의 상세 로직
│       │   └── profile.js            # 프로필 로직
│       └── images/                   # 이미지 에셋
│
├── media/                            # 미디어 파일 (Docker 볼륨)
│   ├── recordings/                   # 녹음 파일
│   │   ├── audio/                    # 오디오 녹음
│   │   └── video/                    # 비디오 녹음
│   └── transcripts/                  # 전사 텍스트 백업
│
├── exports/                          # 내보내기 파일 (임시)
│   ├── csv/
│   └── xlsx/
│
├── ai_models/                        # Ollama 모델 저장소 (Docker 볼륨)
├── scripts/                          # 인프라 스크립트
│   ├── ollama_entrypoint.sh          # Ollama 모델 자동 pull 스크립트
│   └── download_models.sh            # AI 모델 일괄 다운로드
│
├── 메뉴얼/                            # 사용자 매뉴얼
│   └── MEETING_MODEL_MANUAL.md       # 회의 모델 매뉴얼
│
├── docker-compose.yml                # Docker Compose 설정
├── .env                              # 환경 변수 (Git 제외)
├── .env.example                      # 환경 변수 예시
├── SETUP_GUIDE.md                    # 설치 및 실행 가이드
└── README.md                         # 이 파일
```

---

## 🚀 빠른 시작

### 1️⃣ 사전 요구사항

- **Docker** 및 **Docker Compose** 설치
- **Git** 설치
- **최소 시스템 사양**:
  - RAM: 16GB 이상
  - GPU: NVIDIA GPU (VRAM 8GB+) 권장 — GPU 없이도 CPU 모드 동작 가능 (속도 저하)
  - 디스크: 20GB 이상 여유 공간 (AI 모델 포함)

### 2️⃣ 환경 설정

```bash
# 1. 저장소 클론
git clone <레포지토리_주소> live_meeting
cd live_meeting

# 2. 환경 변수 파일 생성
cp .env.example .env
```

`.env` 파일을 열어 아래 값을 실제 값으로 설정합니다:

```env
# Database
POSTGRES_USER=lm_postgres
POSTGRES_PASSWORD=change_this_to_secure_password
POSTGRES_DB=live_meeting
DATABASE_URL=postgresql://lm_postgres:change_this_to_secure_password@db:5432/live_meeting

# JWT (openssl rand -hex 32 로 생성)
SECRET_KEY=change_this_to_generated_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=300

# LLM (Ollama)
LLM_MODEL=exaone3.5:7.8b
OLLAMA_BASE_URL=http://llm:11434

# STT (Faster-Whisper)
STT_ENGINE=faster-whisper
STT_MODEL_SIZE=deepdml/faster-whisper-large-v3-turbo-ct2
STT_DEVICE=cuda
STT_COMPUTE_TYPE=float16

# HuggingFace (STT 모델 다운로드용)
HUGGING_FACE_TOKEN=your_huggingface_token

# LangSmith (선택, 모니터링)
LANGCHAIN_TRACING_V2=false
```

> ⚠️ **보안 주의**: `.env` 파일은 Git에 절대 커밋하지 마세요. `.gitignore`에 이미 포함되어 있습니다.

### 3️⃣ 서비스 실행

```bash
# 전체 서비스 빌드 & 시작 (최초 실행 시 AI 모델 다운로드로 수 분 소요)
docker-compose up --build -d

# 로그 확인
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f backend    # 백엔드
docker-compose logs -f llm        # LLM (Ollama)
docker-compose logs -f db         # 데이터베이스
```

### 4️⃣ 서비스 접속

| 서비스 | URL | 설명 |
|--------|-----|------|
| **웹 애플리케이션** | http://localhost:8001 | 프론트엔드 + 백엔드 통합 |
| **API 문서 (Swagger)** | http://localhost:8001/docs | 자동 생성 API 문서 |
| **PostgreSQL** | localhost:15432 | DB 직접 접속 (DBeaver 등) |
| **Ollama API** | http://localhost:11434 | LLM 서버 |

### 5️⃣ Ollama 모델 확인

컨테이너 실행 시 `scripts/ollama_entrypoint.sh`에 의해 자동으로 모델이 다운로드됩니다.
수동 확인이 필요한 경우:

```bash
# 설치된 모델 확인
docker exec -it lm_llm ollama list

# 모델 수동 다운로드
docker exec -it lm_llm ollama pull exaone3.5:7.8b
```

---

## 🛠️ 기술 스택

### Backend

| 구성요소 | 기술 | 버전 |
|---------|------|------|
| Framework | FastAPI | 0.109 |
| ORM | SQLAlchemy | 2.0.25 |
| DB Migration | Alembic | 1.13.1 |
| Database | PostgreSQL + pgvector | 18 |
| Authentication | JWT (python-jose) | 3.3 |
| Password | bcrypt / passlib | 3.2.2 |
| Template Engine | Jinja2 | 3.1+ |
| Validation | Pydantic + Pydantic Settings | 2.5.3 |
| WebSocket | websockets | 12.0 |
| HTTP Client | httpx | 0.26.0 |

### AI / ML

| 구성요소 | 기술 | 용도 |
|---------|------|------|
| LLM | EXAONE 3.5 (7.8B) via Ollama | 회의록 생성 · 텍스트 보정 |
| LLM Framework | LangChain + ChatOllama | 프롬프트 체인 구성 |
| STT | Faster-Whisper (large-v3-turbo) | 한국어 음성 인식 (GPU/CUDA) |
| 오디오 처리 | pydub + noisereduce + scipy | 잡음 제거 · 청킹 · 전처리 |
| 오디오 변환 | FFmpeg | 포맷 변환 (WebM→WAV 등) |

### Frontend

| 구성요소 | 기술 | 설명 |
|---------|------|------|
| Rendering | Jinja2 (SSR) | 서버 사이드 렌더링 |
| JavaScript | Vanilla JS (ES6+) | 클라이언트 로직 |
| 실시간 녹음 | MediaRecorder API | 브라우저 음성 녹음 |
| 실시간 통신 | WebSocket API | 오디오 스트리밍 |
| HTTP 요청 | Fetch API | REST API 호출 |
| Styling | Vanilla CSS | 커스텀 스타일 |

### Infrastructure

| 구성요소 | 기술 |
|---------|------|
| 컨테이너 | Docker, Docker Compose |
| LLM 서버 | Ollama (로컬 GPU/CPU) |
| 데이터베이스 | PostgreSQL 18 + pgvector |
| OS 의존성 | FFmpeg, postgresql-client |

---

## 📚 API 문서

### 주요 엔드포인트

#### 인증 (Authentication)

```http
POST /api/auth/register          # 회원가입
POST /api/auth/login             # 로그인 (JWT 발급)
```

#### 사용자 (Users)

```http
GET  /api/users/me               # 현재 사용자 정보
PUT  /api/users/me               # 프로필 수정
```

#### 회의 (Meetings)

```http
GET  /api/meetings               # 회의 목록 조회
POST /api/meetings               # 회의 생성
GET  /api/meetings/{id}          # 회의 상세 조회
PUT  /api/meetings/{id}          # 회의 수정
DELETE /api/meetings/{id}        # 회의 삭제
POST /api/meetings/{id}/summarize        # 회의록 생성 (LLM)
POST /api/meetings/{id}/interim-summary  # 중간 요약 생성
```

#### 녹음 (Recording)

```http
WS   /ws/recording               # 실시간 녹음 WebSocket
```

#### 파일 업로드 (Upload)

```http
POST /api/upload/file            # 녹음 파일 업로드 (STT 자동 처리)
```

#### 폴더 (Folders)

```http
GET  /api/folders                # 폴더 목록
POST /api/folders                # 폴더 생성
PUT  /api/folders/{id}           # 폴더 수정
DELETE /api/folders/{id}         # 폴더 삭제
```

#### 내보내기 (Export)

```http
GET  /api/export/{meeting_id}/csv    # CSV 내보내기
GET  /api/export/{meeting_id}/xlsx   # XLSX 내보내기
```

#### 진행률 (Progress)

```http
GET  /api/progress/{meeting_id}  # 처리 진행률 조회
```

> 전체 API 명세: http://localhost:8001/docs (Swagger UI)

---

## 📊 DB 스키마

### 주요 테이블

| 테이블 | 설명 |
|--------|------|
| `users` | 사용자 계정 (이메일, JWT 인증, 프로필) |
| `meetings` | 회의 세션 (제목, 상태, 녹음 파일, 메타데이터) |
| `transcripts` | 전사 텍스트 세그먼트 (시작/종료 시간, 화자) |
| `summaries` | 최종 요약 (Meeting과 1:1) |
| `intermediate_summaries` | 중간 요약 (Meeting과 1:N, 실시간 녹음 중 생성) |
| `folders` | 폴더 (회의 분류·그룹화) |

### 회의 상태 (Status)

```
pending → recording → processing → completed
                                  → failed
```

| 상태 | 설명 |
|------|------|
| `pending` | 회의 생성됨 (아직 녹음/업로드 전) |
| `recording` | 실시간 녹음 진행 중 |
| `processing` | STT 처리 또는 회의록 생성 중 |
| `completed` | 회의록 생성 완료 |
| `failed` | 처리 실패 |

---

## 👨‍💻 개발 가이드

### 로컬 개발 환경

#### Backend 개발 (Docker 없이)

```bash
cd backend

# 가상환경 생성
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 의존성 설치
pip install -r requirements.txt

# DB, LLM은 Docker로 실행 필요
docker-compose up -d db llm

# 백엔드 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Docker 전체 실행

```bash
# 전체 서비스 빌드 & 시작
docker-compose up --build -d

# 특정 서비스만 재빌드
docker-compose up --build backend

# 서비스 재시작
docker-compose restart backend

# 서비스 중지
docker-compose down
```

### DB 마이그레이션 (Alembic)

```bash
# 컨테이너 내부에서 실행
docker-compose exec backend alembic upgrade head

# 새 마이그레이션 생성
docker-compose exec backend alembic revision --autogenerate -m "설명"
```

### 유틸리티 스크립트

```bash
# LLM 테스트
docker-compose exec backend python scripts/test_llm.py

# DB 테이블 확인
docker-compose exec backend python scripts/verify_table.py

# 중단된 작업 정리
docker-compose exec backend python scripts/clean_stalled_tasks.py
```

---

## 🔒 보안

### 핵심 보안 사항

- ✅ `.env` 파일은 Git에 커밋하지 않기 (`.gitignore` 설정 확인)
- ✅ API 키를 코드에 하드코딩하지 않기 — 환경 변수만 사용
- ✅ JWT Secret Key는 강력한 랜덤 문자열 사용 (`openssl rand -hex 32`)
- ✅ 비밀번호는 bcrypt로 해싱
- ✅ CORS 설정으로 허용된 도메인만 접근 가능
- ✅ 파일 업로드 크기 및 확장자 검증
- ✅ SQL Injection 방지 (SQLAlchemy ORM 사용)
- ✅ STT 모델 다운로드 시 Docker Secrets 사용 (HuggingFace Token)

---

## 📖 추가 문서

| 문서 | 내용 |
|------|------|
| [설치 및 실행 가이드](SETUP_GUIDE.md) | 새 환경에서의 프로젝트 설정 |
| [회의 모델 매뉴얼](메뉴얼/MEETING_MODEL_MANUAL.md) | 회의 모델 사용법 |

---

## 🔧 문제 해결

| 문제 | 해결 방법 |
|------|----------|
| GPU 오류 | `nvidia-smi` 명령어로 GPU 인식 확인, Docker Desktop GPU 지원 활성화 |
| DB 연결 오류 | `docker-compose restart backend` 실행, DB 헬스체크 대기 |
| STT 모델 다운로드 실패 | `.env`에 `HUGGING_FACE_TOKEN` 설정 확인 |
| Ollama 모델 없음 | `docker exec -it lm_llm ollama pull exaone3.5:7.8b` |
| 포트 충돌 | `docker-compose.yml`에서 포트 매핑 변경 (기본: 8001, 15432, 11434) |

---

## 📝 라이선스

This project is licensed under the MIT License

---

## 👥 팀

**Big20 Team** — LiveMeeting Development

---

**Last Updated**: 2026-03-09
