# DB Migration 완료 가이드

## 개요
Alembic을 사용하여 PostgreSQL 데이터베이스 스키마를 버전 관리합니다.

## 완료된 작업
- ✅ Alembic 초기화 (`alembic init alembic`)
- ✅ `alembic.ini` DB URL 설정 (`postgresql://lm_postgres:0000@db:5432/live_meeting`)
- ✅ `env.py` 수정 (`sys.path` 및 import 경로 Docker 호환)
- ✅ `User` 모델 생성 (`backend/app/models/user.py`)
- ✅ 마이그레이션 파일 생성 (`f55db5cb4819_create_user_model.py`)
- ✅ 마이그레이션 적용 (`alembic upgrade head`)

## 생성된 테이블
| 테이블 | 컬럼 | 설명 |
|--------|------|------|
| `users` | `id`, `email`, `hashed_password`, `is_active` | 사용자 정보 저장 |

## 주요 명령어

```bash
# 현재 마이그레이션 버전 확인
docker-compose exec backend alembic current

# 새 마이그레이션 생성
docker-compose exec backend alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
docker-compose exec backend alembic upgrade head

# 마이그레이션 롤백 (1단계)
docker-compose exec backend alembic downgrade -1
```

## 새 모델 추가 시

1. `backend/app/models/` 에 새 모델 파일 생성
2. `env.py`에서 import 추가
3. 마이그레이션 생성 및 적용

## 파일 구조
```
backend/
├── alembic/
│   ├── env.py          # Alembic 환경 설정
│   ├── versions/       # 마이그레이션 파일들
│   └── script.py.mako
├── alembic.ini         # Alembic 설정
└── app/
    ├── db/
    │   └── base.py     # SQLAlchemy Base
    └── models/
        └── user.py     # User 모델
```
