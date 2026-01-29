# API Endpoints Documentation

LiveMeeting 프로젝트의 주요 API 엔드포인트 명세입니다.

## 1. 🔐 인증 (Authentication)
**Base URL:** `/api/auth`

| Method | Endpoint | Description | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/register` | 회원가입 | `UserCreate` (email, password, username) | `UserSchema` |
| `POST` | `/login` | 로그인 (JWT 발급) | `OAuth2PasswordRequestForm` (username, password) | `Token` (access_token) |
| `POST` | `/test-token` | 토큰 테스트 | `Header: Authorization` | `UserSchema` |

---

## 2. 🎤 실시간 녹음 (Real-time Recording)
**Base URL:** `/api/recording`

| Method | Endpoint | Description | Parameters | Note |
|---|---|---|---|---|
| `WS` | `/ws/{client_id}` | WebSocket 연결 | `token` (Query Param) | 오디오 청크 스트리밍 전송 |

---

## 3. 📤 파일 업로드 (Upload)
**Base URL:** `/api/upload`

| Method | Endpoint | Description | Request Body | Note |
|---|---|---|---|---|
| `POST` | `/file` | 오디오 파일 업로드 | `multipart/form-data` (file) | 업로드 후 자동 STT 백그라운드 작업 시작 |

---

## 4. 📝 회의 관리 (Meeting Management)
**Base URL:** `/api/meeting`

| Method | Endpoint | Description | Params | Response |
|---|---|---|---|---|
| `GET` | `/` | 내 회의 목록 조회 | `skip`, `limit` | `List[MeetingSchema]` |
| `GET` | `/{id}` | 회의 상세 조회 | - | `MeetingSchema` |
| `POST` | `/` | 회의 수동 생성 | `MeetingCreate` | `MeetingSchema` |
| `POST` | `/{id}/summarize` | **회의록(요약) 생성 요청** | - | 백그라운드 LLM 작업 트리거 |

---

## 5. 💾 내보내기 (Export)
**Base URL:** `/api/export`

| Method | Endpoint | Description | Params | Response |
|---|---|---|---|---|
| `GET` | `/{id}` | 회의록 다운로드 | `format` (csv, xlsx) | File Stream (Download) |
