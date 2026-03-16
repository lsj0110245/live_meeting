# 📚 API 명세서 및 DB 설계도

> LiveMeeting 프로젝트의 백엔드 설계 역량을 보여주는 문서입니다.
> Swagger UI: `http://localhost:8001/docs`

---

## 1. ERD (Entity Relationship Diagram)

### 1.1 전체 ERD

```
┌─────────────────────────────────────────────────────────┐
│                        Users                             │
│─────────────────────────────────────────────────────────│
│ PK │ id              │ SERIAL          │ 사용자 고유 ID  │
│    │ email           │ VARCHAR UNIQUE  │ 이메일         │
│    │ username        │ VARCHAR         │ 사용자 이름    │
│    │ hashed_password │ VARCHAR         │ bcrypt 해시    │
│    │ is_active       │ BOOLEAN         │ 활성 상태      │
│    │ age             │ VARCHAR         │ 나이           │
│    │ phone_number    │ VARCHAR         │ 전화번호       │
│    │ team_name       │ VARCHAR         │ 소속 팀        │
│    │ profile_image   │ VARCHAR         │ 프로필 이미지  │
│    │ created_at      │ TIMESTAMP       │ 생성일         │
│    │ updated_at      │ TIMESTAMP       │ 수정일         │
└───────────┬────────────────────┬────────────────────────┘
            │ 1:N                │ 1:N
            ▼                   ▼
┌──────────────────┐   ┌──────────────────────────────────┐
│     Folders      │   │            Meetings               │
│──────────────────│   │──────────────────────────────────│
│ PK │ id          │   │ PK │ id              │ SERIAL    │
│ FK │ owner_id    │◄──│ FK │ owner_id        │ → Users   │
│    │ name        │   │ FK │ folder_id       │ → Folders │
│    │ created_at  │   │    │ title           │ VARCHAR   │
└──────────────────┘   │    │ description     │ TEXT      │
        │ 1:N          │    │ status          │ ENUM      │
        └─────────────►│    │ audio_file_path │ VARCHAR   │
                       │    │ file_hash       │ SHA-256   │
                       │    │ duration        │ INTEGER   │
                       │    │ meeting_type    │ VARCHAR   │
                       │    │ meeting_date    │ DATETIME  │
                       │    │ attendees       │ TEXT      │
                       │    │ writer          │ VARCHAR   │
                       │    │ created_at      │ TIMESTAMP │
                       │    │ updated_at      │ TIMESTAMP │
                       └──┬──────────┬──────────┬─────────┘
                          │ 1:N      │ 1:1      │ 1:N
                          ▼          ▼          ▼
               ┌─────────────┐ ┌──────────┐ ┌────────────────────┐
               │ Transcripts │ │Summaries │ │IntermediateSummaries│
               │─────────────│ │──────────│ │────────────────────│
               │PK│ id       │ │PK│ id    │ │PK│ id              │
               │FK│meeting_id│ │FK│mtg_id │ │FK│ meeting_id      │
               │  │seg_index │ │  │content│ │  │ content         │
               │  │start_time│ │  │cr_at  │ │  │ created_at      │
               │  │end_time  │ │  │up_at  │ └────────────────────┘
               │  │text      │ └──────────┘
               │  │speaker   │
               └─────────────┘
```

### 1.2 관계 요약

```
[Users] 1 ─── N [Meetings]     사용자가 여러 회의를 소유
[Users] 1 ─── N [Folders]      사용자가 여러 폴더를 소유
[Folders] 1 ── N [Meetings]    폴더가 여러 회의를 포함
[Meetings] 1 ─ N [Transcripts] 회의가 여러 전사 세그먼트를 포함
[Meetings] 1 ─ 1 [Summaries]   회의와 최종 요약은 1:1
[Meetings] 1 ─ N [IntermediateSummaries]  실시간 녹음 중 중간 요약 N개
```

### 1.3 설계 포인트

| 설계 결정 | 이유 |
|-----------|------|
| **Meetings.file_hash (SHA-256)** | 동일 파일 중복 업로드 방지 — 해시 비교로 기존 파일 재사용 |
| **Summaries 1:1 관계 (UNIQUE FK)** | 회의당 최종 요약은 반드시 하나 — 재생성 시 UPDATE |
| **IntermediateSummaries 1:N** | 실시간 녹음 중 3분마다 생성되는 중간 요약을 시계열로 누적 |
| **Cascade 삭제 (`all, delete-orphan`)** | 회의 삭제 시 관련 전사/요약/중간요약 자동 삭제 → 데이터 정합성 |
| **Transcripts.segment_index** | 전사 세그먼트의 순서 보장 — 이어서 녹음 시 index 연속성 유지 |
| **status ENUM** | `pending → recording → processing → completed / failed` 상태 머신 |

### 1.4 회의 상태 머신 (State Machine)

```
                    ┌───────────┐
                    │  pending  │  ← 회의 생성 직후
                    └─────┬─────┘
                          │ 녹음 시작 or 파일 업로드
                          ▼
                    ┌───────────┐
                    │ recording │  ← 실시간 녹음 진행 중
                    └─────┬─────┘
                          │ 녹음 종료 or 업로드 완료
                          ▼
                    ┌────────────┐
                    │ processing │  ← STT + LLM 처리 중
                    └──┬──────┬──┘
                       │      │
              성공 ─┘      └─ 실패
                   ▼              ▼
            ┌───────────┐  ┌────────┐
            │ completed │  │ failed │
            └───────────┘  └────────┘
```

---

## 2. API 명세서

### 2.1 인증 (Authentication)

> JWT 기반 인증. 토큰 만료: 300분 (5시간)

| Method | Endpoint | 설명 | 인증 | Request Body | Response |
|--------|----------|------|------|-------------|----------|
| `POST` | `/api/auth/register` | 회원가입 | ❌ | `{ email, username, password }` | `{ id, email, username }` |
| `POST` | `/api/auth/login` | 로그인 | ❌ | `{ email, password }` | `{ access_token, token_type }` |

**인증 흐름:**
```
POST /api/auth/login
  → { email: "user@test.com", password: "..." }
  ← { access_token: "eyJhbGciOi...", token_type: "bearer" }

이후 모든 API 요청:
  Authorization: Bearer eyJhbGciOi...
```

### 2.2 사용자 (Users)

| Method | Endpoint | 설명 | 인증 | 비고 |
|--------|----------|------|------|------|
| `GET` | `/api/users/me` | 내 정보 조회 | ✅ | JWT 디코딩으로 사용자 식별 |
| `PUT` | `/api/users/me` | 프로필 수정 | ✅ | 이름, 나이, 전화번호, 팀, 이미지 |

### 2.3 회의 (Meetings)

| Method | Endpoint | 설명 | 인증 | Request / Query |
|--------|----------|------|------|----------------|
| `GET` | `/api/meeting/` | 회의 목록 조회 | ✅ | `?folder_id=N` (폴더 필터링) |
| `GET` | `/api/meeting/{id}` | 회의 상세 조회 | ✅ | 전사 + 요약 + 중간요약 포함 |
| `PUT` | `/api/meeting/{id}` | 회의 정보 수정 | ✅ | `{ title, meeting_type, attendees, ... }` |
| `DELETE` | `/api/meeting/{id}` | 회의 삭제 | ✅ | Cascade로 관련 데이터 모두 삭제 |
| `DELETE` | `/api/meeting/` | 일괄 삭제 | ✅ | `{ meeting_ids: [1, 2, 3] }` |
| `POST` | `/api/meeting/{id}/summarize` | 회의록 재생성 | ✅ | LLM으로 요약 재생성 |
| `POST` | `/api/meeting/{id}/retry` | STT 재분석 | ✅ | 전사 텍스트 재처리 |

**회의 상세 응답 예시:**
```json
{
  "id": 1,
  "title": "Q1 마케팅 전략 회의",
  "status": "completed",
  "duration": 600,
  "meeting_type": "전략 회의",
  "meeting_date": "2026-03-01T14:00:00",
  "attendees": "김팀장, 이대리",
  "writer": "박사원",
  "audio_file_path": "/media/recordings/audio/meeting_1.webm",
  "transcripts": [
    {
      "id": 1,
      "segment_index": 0,
      "start_time": 0.0,
      "end_time": 5.2,
      "text": "오늘 회의는 1분기 마케팅 전략에 대해 논의하겠습니다.",
      "speaker": "Unknown"
    }
  ],
  "summary": {
    "content": "## 📅 요약\n- 1분기 마케팅 예산 배분 논의..."
  },
  "intermediate_summaries": [
    {
      "content": "마케팅 채널별 ROI 분석 결과를 공유하고...",
      "created_at": "2026-03-01T14:03:00"
    }
  ]
}
```

### 2.4 녹음 (Recording) — WebSocket

| Type | Endpoint | 설명 | 인증 |
|------|----------|------|------|
| `WS` | `/api/recording/ws/{client_id}?token={jwt}` | 실시간 녹음 | ✅ (Query Token) |

#### WebSocket 프로토콜 상세

**Client → Server (JSON 메시지):**
```json
// 1. 메타데이터 전송 (연결 직후)
{
  "type": "metadata",
  "data": {
    "title": "주간 회의",
    "meeting_type": "정기 회의",
    "meeting_date": "2026-03-01",
    "attendees": "김팀장, 이대리",
    "writer": "박사원",
    "meeting_id": null           // 이어서 녹음 시 기존 ID 전달
  }
}

// 2. 녹음 중지
{ "type": "stop_recording" }
```

**Client → Server (Binary 메시지):**
```
[WebM 오디오 청크 바이너리 데이터]
  → MediaRecorder timeslice: 500ms
  → 서버에서 5초 분량 축적 후 STT 처리
```

**Server → Client (JSON 메시지):**
```json
// 연결 확인
{ "type": "connected", "message": "WebSocket 연결 성공" }

// 회의 ID 할당
{ "type": "meeting_created", "meeting_id": 42 }

// 실시간 전사 결과
{
  "type": "transcript",
  "transcript_id": 1,
  "text": "오늘 회의는 마케팅 전략에 대해...",
  "is_final": true,
  "start_time": 0.0,
  "end_time": 5.2
}

// 전사 텍스트 업데이트 (교정 후)
{
  "type": "transcript_update",
  "transcript_id": 1,
  "text": "오늘 회의는 마케팅 전략에 대해 논의하겠습니다."
}

// 중간 요약 (3분마다 자동)
{
  "type": "intermediate_summary",
  "content": "현재까지 1분기 마케팅 예산 배분에 대해 논의 중..."
}

// 에러
{ "type": "error", "message": "STT 처리 실패" }
```

#### WebSocket 연결 생명주기

```
1. Client: WS 연결 요청 (JWT 토큰 포함)
   └→ Server: JWT 검증 → 실패 시 WS_1008_POLICY_VIOLATION

2. Client: metadata JSON 전송
   └→ Server: Meeting 생성 (status: recording)
   └→ Server: meeting_created 응답
   └→ Server: STT 모델 Pre-warm (백그라운드)

3. Client: Binary 오디오 청크 전송 (0.5초마다)
   └→ Server: 5초 버퍼 축적 → STT 추론 → transcript 응답
   └→ Server: 3분마다 → intermediate_summary 응답

4. Client: stop_recording JSON 전송
   └→ Server: 잔여 버퍼 처리
   └→ Server: 최종 LLM 요약 생성 (BackgroundTask)
   └→ Server: status → processing → completed
```

### 2.5 파일 업로드 (Upload)

| Method | Endpoint | 설명 | 인증 | 비고 |
|--------|----------|------|------|------|
| `POST` | `/api/upload/file` | 오디오 파일 업로드 | ✅ | Multipart/form-data |
| `POST` | `/api/upload/recording/{id}/finalize` | 녹음 파일 최종 저장 | ✅ | WebM Duration 복구 |
| `POST` | `/api/upload/recording/{id}/concat-resume` | 이어서 녹음 합치기 | ✅ | FFmpeg concat |

**파일 업로드 요청:**
```http
POST /api/upload/file
Content-Type: multipart/form-data

file: [오디오 파일]
title: "마케팅 회의"
meeting_type: "전략 회의"
attendees: "김팀장, 이대리"
writer: "박사원"
```

**처리 흐름:**
```
파일 수신 → SHA-256 해시 계산 → 중복 체크
  → BackgroundTask 시작
    → 파일 저장 (media/recordings/audio/)
    → STT 처리 (30초 청킹, 고품질 Denoise)
    → 세그먼트별 LLM 전사 교정
    → DB 저장 (Transcripts)
    → LLM 요약 생성
    → DB 저장 (Summary)
    → status: completed
```

### 2.6 폴더 (Folders)

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| `GET` | `/api/folders/` | 폴더 목록 조회 | ✅ |
| `POST` | `/api/folders/` | 폴더 생성 | ✅ |
| `PUT` | `/api/folders/{id}` | 폴더 이름 수정 | ✅ |
| `DELETE` | `/api/folders/{id}` | 폴더 삭제 | ✅ |

### 2.7 내보내기 (Export)

| Method | Endpoint | 설명 | 인증 | 비고 |
|--------|----------|------|------|------|
| `GET` | `/api/export/{id}?format=csv` | CSV 내보내기 | ✅ | utf-8-sig BOM |
| `GET` | `/api/export/{id}?format=xlsx` | XLSX 내보내기 | ✅ | source.xlsx 템플릿 기반 |

### 2.8 진행률 (Progress)

| Method | Endpoint | 설명 | 인증 | 응답 |
|--------|----------|------|------|------|
| `GET` | `/api/progress/{meeting_id}` | 처리 진행률 조회 | ✅ | `{ progress: 75, status: "processing" }` |

### 2.9 미디어 서빙 (Static Files)

| Method | Endpoint | 설명 | 비고 |
|--------|----------|------|------|
| `GET` | `/media/{file_path}` | 오디오/비디오 파일 서빙 | HTTP 206 Range Request 지원 |

**Range Request 지원:**
```http
GET /media/recordings/audio/meeting_1.webm
Range: bytes=0-1048575

HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1048575/5242880
Accept-Ranges: bytes
ETag: "abc123"
```

---

## 3. 인증/보안 설계

### 3.1 JWT 인증 체계

```
┌──────────┐    POST /auth/login     ┌──────────────┐
│  Client  │ ──────────────────────► │   Backend    │
│          │ ◄────────────────────── │              │
│          │   { access_token }      │  JWT 생성    │
│          │                         │  (HS256)     │
│          │    GET /api/meeting/    │              │
│          │ ──────────────────────►│              │
│          │  Authorization: Bearer  │  deps.py     │
│          │                         │  get_current │
│          │ ◄────────────────────── │  _user()     │
│          │   { meetings: [...] }   │              │
└──────────┘                         └──────────────┘
```

### 3.2 보안 기능 요약

| 보안 계층 | 구현 방식 |
|-----------|----------|
| 비밀번호 | `passlib[bcrypt]` — 단방향 해싱 |
| 토큰 | JWT HS256, 300분 만료 |
| API 보호 | `deps.get_current_user()` 의존성 주입 |
| 소유권 검증 | `meeting.owner_id == current_user.id` |
| WebSocket 인증 | Query Parameter JWT → 연결 전 검증 |
| CORS | 허용 도메인 명시적 관리 |
| 파일 업로드 | 확장자 제한 + 500MB 크기 제한 |
| SQL Injection | SQLAlchemy ORM (Raw SQL 미사용) |
| 데이터 주권 | 완전 온프레미스 — 외부 전송 없음 |

---

## 4. Alembic 마이그레이션 이력

> 총 **11개 버전**의 스키마 진화 과정이 추적됩니다.

| # | 버전 해시 | 내용 | 설계 의도 |
|---|-----------|------|----------|
| 1 | `f55db5cb4819` | User 모델 생성 | 인증 시스템 기초 |
| 2 | `a8981f3b4ff3` | Meeting, Transcript, Summary 생성 | 핵심 도메인 모델 |
| 3 | `375f9b500b8c` | username 컬럼 추가 | 사용자 식별 개선 |
| 4 | `7c7550e2d45b` | username 재시도 | 마이그레이션 충돌 해결 |
| 5 | `1bf0a1ef0b85` | audio_file_path 추가 | 녹음 파일 관리 |
| 6 | `7c78715da1d6` | status 컬럼 추가 | 상태 머신 도입 |
| 7 | `90f4345f2a1a` | file_hash 추가 | 중복 업로드 방지 |
| 8 | `a0ff3c623e1e` | 메타데이터 컬럼 일괄 추가 | LLM 자동 추출 지원 |
| 9 | `aead48c7fdac` | Folder 모델 추가 | 회의 분류 체계 |
| 10 | `b79f55bcff7d` | IntermediateSummaries 추가 | 실시간 중간 요약 |
| 11 | `d66a257e837e` | User 프로필 필드 확장 | UX 개선 |

---

**Last Updated**: 2026-03-11
