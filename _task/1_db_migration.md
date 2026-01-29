# DB Migration 완료 가이드

## 개요
Alembic을 사용하여 PostgreSQL 데이터베이스 스키마를 버전 관리합니다.

## 완료된 작업
- ✅ Alembic 초기화 및 설정 완료
- ✅ `alembic.ini` DB URL 설정 및 `env.py` Docker 호환 수정 완료
- ✅ **모델 생성 및 마이그레이션 적용**
  - **`User` (사용자)**: `users` 테이블
  - **`Meeting` (회의)**: `meetings` 테이블 (User와 1:N 관계)
  - **`Transcript` (스크립트)**: `transcripts` 테이블 (Meeting과 1:N 관계)
  - **`Summary` (요약)**: `summaries` 테이블 (Meeting과 1:1 관계)
- ✅ 마이그레이션 적용 (`alembic upgrade head`)

## 생성된 테이블 스키마
### 1. `users`
| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer | PK |
| `email` | String | 사용자 이메일 (Unique) |
| `hashed_password` | String | 비밀번호 해시 |
| `is_active` | Boolean | 활성 상태 |

### 2. `meetings`
| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer | PK |
| `title` | String | 회의 제목 |
| `description` | Text | 회의 설명 |
| `owner_id` | Integer | FK (`users.id`) |
| `created_at` | DateTime | 생성 일시 |

### 3. `transcripts`
| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer | PK |
| `meeting_id` | Integer | FK (`meetings.id`) |
| `segment_index` | Integer | 세그먼트 순서 |
| `start_time` | Float | 시작 시간 (초) |
| `end_time` | Float | 종료 시간 (초) |
| `text` | Text | 텍스트 내용 |
| `speaker` | String | 화자 정보 |

### 4. `summaries`
| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer | PK |
| `meeting_id` | Integer | FK (`meetings.id`, Unique) |
| `content` | Text | 요약 내용 |
| `created_at` | DateTime | 생성 일시 |
| `updated_at` | DateTime | 수정 일시 |

## 주요 명령어

```bash
# 현재 마이그레이션 버전 확인
docker-compose exec backend alembic current

# 새 마이그레이션 생성 (모델 수정 후)
docker-compose exec backend alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
docker-compose exec backend alembic upgrade head

# 마이그레이션 롤백 (1단계)
docker-compose exec backend alembic downgrade -1
```

## 파일 구조 참고
```
backend/
├── alembic/
│   ├── env.py          # 설정 파일 (Docker 경로 수정됨)
│   └── versions/       # 마이그레이션 파일들
└── app/
    └── models/
        ├── user.py
        ├── meeting.py
        ├── transcript.py
        └── summary.py
```
