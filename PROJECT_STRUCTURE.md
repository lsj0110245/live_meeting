# LiveMeeting (LM) 프로젝트 구조

## 📁 디렉토리 구조

```
live_meeting/
├── backend/                          # FastAPI 백엔드
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI 앱 진입점
│   │   │
│   │   ├── api/                      # API 엔드포인트
│   │   │   ├── __init__.py
│   │   │   ├── deps.py               # 의존성 (JWT 인증 등)
│   │   │   └── endpoints/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py           # 인증 (회원가입/로그인)
│   │   │       ├── recording.py      # 실시간 녹음 WebSocket
│   │   │       ├── upload.py         # 녹음본 파일 업로드
│   │   │       ├── meeting.py        # 회의 CRUD
│   │   │       └── export.py         # CSV/XLSX 내보내기
│   │   │
│   │   ├── core/                     # 핵심 설정
│   │   │   ├── __init__.py
│   │   │   ├── config.py             # 환경 변수 설정
│   │   │   └── security.py           # JWT, 비밀번호 해싱
│   │   │
│   │   ├── db/                       # 데이터베이스
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Base 모델
│   │   │   └── session.py            # DB 세션
│   │   │
│   │   ├── models/                   # SQLAlchemy 모델
│   │   │   ├── __init__.py
│   │   │   ├── user.py               # 사용자 모델
│   │   │   ├── meeting.py            # 회의 모델
│   │   │   └── transcript.py         # 전사 텍스트 모델
│   │   │
│   │   ├── schemas/                  # Pydantic 스키마
│   │   │   ├── __init__.py
│   │   │   ├── user.py               # 사용자 요청/응답
│   │   │   ├── meeting.py            # 회의 요청/응답
│   │   │   └── transcript.py         # 전사 요청/응답
│   │   │
│   │   ├── services/                 # 비즈니스 로직
│   │   │   ├── __init__.py
│   │   │   ├── stt_service.py        # Local Nova-2 / Whisper STT 서비스
│   │   │   ├── llm_service.py        # Local LLM (Llama 3) 요약 서비스
│   │   │   ├── export_service.py     # CSV/XLSX 생성
│   │   │   └── storage_service.py    # 파일 저장 (S3/로컬)
│   │   │
│   │   └── utils/                    # 유틸리티
│   │       ├── __init__.py
│   │       └── helpers.py            # 헬퍼 함수
│   │
│   ├── alembic/                      # DB 마이그레이션
│   │   ├── versions/
│   │   └── env.py
│   │
│   ├── tests/                        # 테스트
│   │   ├── __init__.py
│   │   ├── test_auth.py
│   │   ├── test_recording.py
│   │   └── test_export.py
│   │
│   ├── Dockerfile                    # Backend 도커 이미지
│   ├── requirements.txt              # Python 의존성
│   └── alembic.ini                   # Alembic 설정
│
├── frontend/                         # 프론트엔드
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css             # 메인 스타일
│   │   ├── js/
│   │   │   ├── auth.js               # 로그인/회원가입
│   │   │   ├── recorder.js           # 실시간 녹음/화면녹화
│   │   │   ├── upload.js             # 파일 업로드
│   │   │   ├── meeting.js            # 회의 관리
│   │   │   └── export.js             # 내보내기
│   │   └── assets/
│   │       └── logo.png
│   │
│   └── templates/
│       ├── index.html                # 메인 페이지
│       ├── login.html                # 로그인
│       ├── register.html             # 회원가입
│       ├── dashboard.html            # 대시보드
│       ├── recording.html            # 녹음 페이지
│       └── meeting_detail.html       # 회의록 상세
│
├── media/                            # 미디어 파일 (Docker 볼륨)
│   ├── recordings/                   # 오디오/비디오 녹음본
│   │   ├── audio/
│   │   └── video/
│   └── transcripts/                  # 전사 텍스트 (백업)
│
├── exports/                          # 내보내기 파일 (임시)
│   ├── csv/
│   └── xlsx/
│
├── .agent/                           # 에이전트 설정
│   └── workflows/
│       └── setup-project.md          # 프로젝트 워크플로우
│
├── docker-compose.yml                # Docker Compose 설정
├── docker-compose.prod.yml           # 프로덕션 설정
├── .env                              # 환경 변수 (gitignore)
├── .env.example                      # 환경 변수 예시
├── .gitignore
├── README.md
└── PROJECT_STRUCTURE.md              # 이 파일
```

## 🗄️ 데이터베이스 스키마

### Users 테이블
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Meetings 테이블
```sql
CREATE TABLE meetings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    status VARCHAR(50) DEFAULT 'recording',  -- recording, processing, completed
    recording_type VARCHAR(50),              -- realtime, upload
    audio_file_path VARCHAR(500),
    video_file_path VARCHAR(500),
    duration INTEGER,                        -- 초 단위
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Transcripts 테이블
```sql
CREATE TABLE transcripts (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    timestamp_start FLOAT,                   -- 초 단위
    timestamp_end FLOAT,
    speaker VARCHAR(100),                    -- 선택사항
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Summaries 테이블
```sql
CREATE TABLE summaries (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
    summary_type VARCHAR(50),                -- interim, final
    content TEXT NOT NULL,
    key_points JSONB,                        -- 주요 포인트 리스트
    action_items JSONB,                      -- 액션 아이템 리스트
    decisions JSONB,                         -- 결정 사항 리스트
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 주요 기술 스택

### Backend
- **FastAPI**: 고성능 비동기 웹 프레임워크
- **SQLAlchemy**: ORM
- **Alembic**: DB 마이그레이션
- **PostgreSQL**: 데이터베이스
- **Local AI Engine**: Nova-2 / Whisper (STT) 및 Llama 3 (LLM) 직접 구동
- **websockets**: 실시간 통신
- **python-jose**: JWT 인증
- **passlib**: 비밀번호 해싱
- **transformers / vllm**: 로컬 LLM 추론
- **openpyxl**: XLSX 생성
- **pandas**: CSV 생성

### Frontend
- **Vanilla JavaScript**: 클라이언트 로직
- **MediaRecorder API**: 오디오/비디오 녹화
- **WebSocket API**: 실시간 통신
- **Fetch API**: HTTP 요청

### DevOps
- **Docker**: 컨테이너화
- **Docker Compose**: 멀티 컨테이너 오케스트레이션
- **Nginx** (선택): 리버스 프록시

## 🚀 핵심 기능 플로우

### 1️⃣ 실시간 녹음 플로우
```
사용자 → [녹음 시작] 
    ↓
마이크 권한 확인 (getUserMedia)
    ↓
화면 녹화 권한 확인 (getDisplayMedia)
    ↓
WebSocket 연결 (/ws/recording)
    ↓
오디오 스트림 → 서버 전송 (청크 단위)
    ↓
Local STT 엔진 변환 (Docker 내부 처리)
    ↓
텍스트 축적 (DB 저장)
    ↓
[5분마다] 중간 요약 생성 (선택)
    ↓
[회의 종료] → 최종 회의록 생성 (LLM)
    ↓
회의록 표시 → 내보내기 옵션
```

### 2️⃣ 녹음본 업로드 플로우
```
사용자 → [파일 선택/드래그]
    ↓
파일 업로드 (POST /api/upload/file)
    ↓
서버에 파일 저장
    ↓
Local STT 처리 (비동기 큐)
    ↓
전사 텍스트 생성
    ↓
LLM 회의록 생성
    ↓
회의록 표시 → 내보내기 옵션
```

### 3️⃣ 회의록 생성 프롬프트 예시
```
당신은 전문 회의록 작성자입니다. 다음 회의 전사 내용을 바탕으로 구조화된 회의록을 작성해주세요.

[전사 내용]
{transcript_text}

[요구사항]
1. 날짜 및 시간
2. 주요 안건 (3-5개)
3. 논의 사항 (주제별 요약)
4. 결정 사항 (구체적으로)
5. 액션 아이템 (담당자, 기한 포함 - 가능한 경우)
6. 다음 회의 일정 (언급된 경우)

[형식]
마크다운 형식으로 작성해주세요.
```

## 📝 주요 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/auth/register` | 회원가입 |
| POST | `/api/auth/login` | 로그인 (JWT 토큰 발급) |
| WS | `/ws/recording` | 실시간 녹음 WebSocket |
| POST | `/api/upload/file` | 녹음본 파일 업로드 |
| GET | `/api/meetings` | 회의 목록 조회 |
| GET | `/api/meetings/{id}` | 회의 상세 조회 |
| POST | `/api/meetings/{id}/summarize` | 회의록 생성 |
| POST | `/api/meetings/{id}/interim-summary` | 중간 요약 생성 |
| GET | `/api/meetings/{id}/export` | CSV/XLSX 내보내기 |
| DELETE | `/api/meetings/{id}` | 회의 삭제 |

## 🔒 보안 고려사항

1. **JWT 인증**: 모든 API 요청에 토큰 필요
2. **비밀번호 해싱**: bcrypt 사용
3. **CORS 설정**: 프론트엔드 도메인만 허용
4. **파일 업로드 제한**: 크기, 확장자 검증
5. **환경 변수**: 민감 정보는 .env에 저장
6. **SQL Injection 방지**: SQLAlchemy ORM 사용
7. **XSS 방지**: 사용자 입력 sanitize

## 🧪 테스트 전략

1. **단위 테스트**: 각 서비스 함수 테스트
2. **API 테스트**: FastAPI TestClient 사용
3. **통합 테스트**: 전체 플로우 검증
4. **부하 테스트**: Locust/JMeter (선택)
