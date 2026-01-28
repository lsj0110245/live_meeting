# Pydantic 스키마 가이드

이 문서는 LiveMeeting 프로젝트에서 사용하는 Pydantic 스키마(`schemas/`)의 구조와 역할을 설명합니다.
API 요청(Request)과 응답(Response)의 데이터 검증 및 직렬화를 담당합니다.

## 1. User 스키마 (`schemas/user.py`)

사용자 인증 및 정보 관리를 위한 스키마입니다.

| 클래스 | 역할 | 주요 필드 | 비고 |
|---|---|---|---|
| `UserBase` | 공통 필드 정의 | `email`, `username`, `is_active` | |
| `UserCreate` | **회원가입 요청** | `password` (필수) | 비밀번호 평문 입력 |
| `UserUpdate` | 정보 수정 요청 | 모든 필드 Optional | |
| `User` | **API 응답** (조회) | `id`, `created_at` | **비밀번호 제외** (보안) |

## 2. Meeting 스키마 (`schemas/meeting.py`)

회의 메타데이터 관리를 위한 스키마입니다.

| 클래스 | 역할 | 주요 필드 | 비고 |
|---|---|---|---|
| `MeetingBase` | 공통 필드 정의 | `title`, `description` | |
| `MeetingCreate` | **회의 생성 요청** | `title` (필수) | |
| `Meeting` | **API 응답** (조회) | `id`, `owner_id`, `created_at` | |

## 3. Transcript 스키마 (`schemas/transcript.py`)

STT 전사 데이터를 위한 스키마입니다.

| 클래스 | 역할 | 주요 필드 | 비고 |
|---|---|---|---|
| `TranscriptBase` | 공통 필드 정의 | `start_time`, `end_time`, `text` | |
| `TranscriptCreate` | **전사 저장 요청** | `meeting_id` | STT 서비스 내부용 |
| `Transcript` | **API 응답** (조회) | `id` | |

## 📌 주요 특징
1. **유효성 검사**: `EmailStr` 등을 사용하여 이메일 형식을 자동 검증합니다.
2. **보안**: `User` 응답 스키마에는 `password` 필드가 없어, 비밀번호 해시가 실수로 클라이언트에 노출되는 것을 방지합니다.
3. **ORM 호환**: `class Config: from_attributes = True` 설정을 통해 SQLAlchemy 모델 객체를 Pydantic 모델로 쉽게 변환합니다.
