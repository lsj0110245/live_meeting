# LiveMeeting 환경 설정 가이드

## 📋 시스템 요구사항

### 필수 설치 항목
- **Docker Desktop** 4.0 이상
- **Git** (선택사항, 버전 관리용)
- **curl** 또는 **Postman** (API 테스트용)

### 권장 사양
- OS: Windows 10/11, macOS, Linux
- RAM: 최소 4GB (권장 8GB)
- 디스크 공간: 최소 5GB

---

## 🔧 현재 환경 설정

### Python 버전
- **Python 3.10** (Docker 컨테이너 내부)

### PostgreSQL 버전
- **PostgreSQL 18.1** (pgvector 지원)
- **pgvector 확장**: 0.8.1
  - 벡터 임베딩 저장 및 검색 지원
  - 의미 기반 회의록 검색 가능
  - RAG (Retrieval-Augmented Generation) 기능 구현 준비

#### 📌 중요: PostgreSQL 18 볼륨 마운트 경로
PostgreSQL 18부터 데이터 디렉토리 구조가 변경되었습니다:

| 버전 | 볼륨 마운트 경로 | 설명 |
|------|----------------|------|
| PostgreSQL 17 이하 | `/var/lib/postgresql/data` | 기존 방식 |
| PostgreSQL 18 이상 | `/var/lib/postgresql` | 새로운 구조 (pg_ctlcluster 호환) |

**현재 설정 (`docker-compose.yml`)**:
```yaml
volumes:
  - postgres_data:/var/lib/postgresql  # ✅ PostgreSQL 18 올바른 경로
```

잘못된 경로를 사용하면 다음 에러가 발생합니다:
```
Error: in 18+, these Docker images are configured to store database data in a 
format which is compatible with "pg_ctlcluster"
```

### 포트 설정
기존 서비스와 충돌을 피하기 위해 비표준 포트 사용:

| 서비스 | 호스트 포트 | 컨테이너 포트 | 용도 |
|--------|------------|--------------|------|
| Backend API | 8001 | 8000 | FastAPI 서버 |
| PostgreSQL | 15432 | 5432 | 데이터베이스 |

**접속 방법:**
- API: `http://localhost:8001`
- DB: `localhost:15432` (외부 클라이언트)
- DB 내부: `db:5432` (컨테이너 간 통신)

---

## 🌍 환경 변수 설정

### 1. `.env` 파일 생성

`.env.example`을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

### 2. 필수 환경 변수

#### 데이터베이스 (PostgreSQL)
```env
POSTGRES_USER=lm_user
POSTGRES_PASSWORD=secure_password123
POSTGRES_DB=live_meeting
DATABASE_URL=postgresql://lm_user:secure_password123@db:5432/live_meeting
```

#### API 키
```env
# OpenAI (LLM 회의록 생성)
OPENAI_API_KEY=sk-proj-your-key-here

# Deepgram (STT - 선택사항)
DEEPGRAM_API_KEY=your-deepgram-key

# AWS (Nova-2 STT - 나중에 설정 가능)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION=us-east-1
```

#### JWT 인증
```env
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**JWT Secret Key 생성 방법:**
```bash
# Python으로 생성
python -c "import secrets; print(secrets.token_hex(32))"

# 또는 OpenSSL로 생성
openssl rand -hex 32
```

#### 애플리케이션 설정
```env
APP_NAME=LiveMeeting
DEBUG=true
CORS_ORIGINS=http://localhost:8001,http://localhost:8000,http://localhost:3000
```

---

## 🚀 Docker 실행 가이드

### 1단계: 초기 빌드 및 실행
```bash
# 프로젝트 디렉토리로 이동
cd c:\big20\live_meeting

# Docker 컨테이너 빌드 및 실행 (백그라운드)
docker-compose up -d --build
```

### 2단계: 상태 확인
```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f backend
docker-compose logs -f db

# 특정 컨테이너 로그만 보기
docker-compose logs -f backend
```

### 3단계: API 테스트
```bash
# 기본 엔드포인트
curl http://localhost:8001/

# 헬스 체크
curl http://localhost:8001/health

# 데이터베이스 연결 테스트
curl http://localhost:8001/db-test
```

**예상 응답:**
```json
{
  "status": "success",
  "message": "Database connection successful!",
  "result": 1
}
```

---

## 🛠️ Docker 관리 명령어

### 컨테이너 제어
```bash
# 시작
docker-compose start

# 중지
docker-compose stop

# 재시작
docker-compose restart

# 중지 및 삭제
docker-compose down

# 볼륨 포함 전체 삭제 (주의!)
docker-compose down -v
```

### 컨테이너 내부 접속
```bash
# Backend 컨테이너 접속
docker-compose exec backend bash

# PostgreSQL 접속
docker-compose exec db psql -U lm_user -d live_meeting
```

### 빌드 관련
```bash
# 캐시 없이 완전 재빌드
docker-compose build --no-cache

# 특정 서비스만 재빌드
docker-compose build backend
```

---

## 🗄️ 데이터베이스 관리

### PostgreSQL 직접 접속
```bash
# Docker 컨테이너를 통해 접속
docker-compose exec db psql -U lm_user -d live_meeting

# 외부 클라이언트로 접속 (DBeaver, pgAdmin 등)
Host: localhost
Port: 15432
Database: live_meeting
Username: lm_user
Password: secure_password123
```

### 데이터베이스 명령어
```sql
-- 테이블 목록 확인
\dt

-- 데이터베이스 목록
\l

-- 종료
\q
```

### 백업 및 복원
```bash
# 백업
docker-compose exec db pg_dump -U lm_user live_meeting > backup.sql

# 복원
docker-compose exec -T db psql -U lm_user live_meeting < backup.sql
```

### DBeaver로 데이터베이스 연결하기

DBeaver는 강력한 데이터베이스 관리 도구입니다. PostgreSQL with pgvector 연결 방법:

#### 1. 새 연결 생성
1. DBeaver 실행
2. **Database** → **새 데이터베이스 연결** 클릭 (또는 `Ctrl+Shift+N`)
3. **PostgreSQL** 선택 → **다음**

#### 2. 연결 정보 입력
다음 정보를 입력하세요:

| 항목 | 값 | 설명 |
|------|-----|------|
| **Host** | `localhost` | 로컬 호스트 |
| **Port** | `15432` | ⚠️ 표준 포트 5432가 아닌 **15432** 사용 |
| **Database** | `live_meeting` | 데이터베이스 이름 |
| **Username** | `lm_user` | PostgreSQL 사용자명 |
| **Password** | `secure_password123` | `.env` 파일에 설정한 비밀번호 |
| **Show all databases** | ☑️ 체크 | (선택사항) 모든 DB 보기 |

#### 3. 드라이버 설정
- 처음 연결 시 PostgreSQL 드라이버 자동 다운로드
- **Test Connection** 버튼 클릭하여 연결 테스트
- **성공** 메시지 확인 후 **Finish**

#### 4. pgvector 확장 확인
연결 후 다음 SQL로 pgvector 설치 확인:

```sql
-- pgvector extension 확인
SELECT extname, extversion 
FROM pg_extension 
WHERE extname = 'vector';

-- 결과:
--  extname | extversion
-- ---------+------------
--  vector  | 0.8.1
```

#### 5. 벡터 타입 테스트
pgvector가 정상 작동하는지 테스트:

```sql
-- 벡터 컬럼을 가진 테스트 테이블 생성
CREATE TABLE vector_test (
    id SERIAL PRIMARY KEY,
    embedding vector(3)
);

-- 샘플 데이터 삽입
INSERT INTO vector_test (embedding) VALUES 
    ('[1, 2, 3]'),
    ('[4, 5, 6]');

-- 조회
SELECT * FROM vector_test;

-- 테이블 삭제
DROP TABLE vector_test;
```

#### 6. DBeaver 유용한 기능
- **SQL 에디터**: `Ctrl+]` 또는 우클릭 → **SQL Editor**
- **테이블 뷰어**: 테이블 더블 클릭
- **ER 다이어그램**: 데이터베이스 우클릭 → **ER 다이어그램**
- **데이터 내보내기**: 테이블 우클릭 → **Export Data**

#### 📌 연결 문제 해결
- **Connection refused**: Docker 컨테이너가 실행 중인지 확인 (`docker-compose ps`)
- **Authentication failed**: `.env` 파일의 비밀번호 확인
- **Port already in use**: 포트 15432가 올바른지 확인

---

## 📚 API 문서 접속

Docker 실행 후 브라우저에서 접속:

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

---

## ⚠️ 트러블슈팅

### 1. 포트 충돌 에러
```
Error: port is already allocated
```

**해결 방법:**
- `docker-compose.yml`에서 포트 번호 변경
- 기존 서비스 중지 후 재시도

### 2. 데이터베이스 연결 실패
```
Database connection failed
```

**해결 방법:**
```bash
# PostgreSQL 컨테이너 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs db

# 재시작
docker-compose restart db
```

### 3. 모듈 import 에러
```
ModuleNotFoundError: No module named 'xxx'
```

**해결 방법:**
```bash
# 컨테이너 재빌드
docker-compose down
docker-compose up -d --build
```

### 4. 환경 변수 적용 안 됨
**해결 방법:**
```bash
# .env 파일 수정 후 반드시 재시작
docker-compose restart backend
```

### 5. Docker Desktop 실행 안 됨
**Windows에서 WSL2 에러:**
- Docker Desktop 설정에서 WSL2 활성화
- Windows 기능에서 "Linux용 Windows 하위 시스템" 활성화

---

## 🔍 개발 환경 체크리스트

시작 전 확인:

- [ ] Docker Desktop 실행 중
- [ ] `.env` 파일 생성 및 API 키 설정 완료
- [ ] 포트 8001, 15432가 사용 가능한지 확인
- [ ] `docker-compose up -d --build` 성공
- [ ] `curl http://localhost:8001/health` 정상 응답
- [ ] `curl http://localhost:8001/db-test` 정상 응답

---

## 📞 다음 단계

환경 설정이 완료되었다면:

1. **데이터베이스 마이그레이션**
   ```bash
   docker-compose exec backend alembic init alembic
   docker-compose exec backend alembic revision --autogenerate -m "Initial"
   docker-compose exec backend alembic upgrade head
   ```

2. **개발 시작**
   - User 모델 생성
   - 인증 API 구현
   - 실시간 녹음 기능 개발

---

## 📖 참고 문서

- [Docker 공식 문서](https://docs.docker.com/)
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [PostgreSQL 공식 문서](https://www.postgresql.org/docs/)
- [프로젝트 워크플로우](.agent/workflows/setup-project.md)
- [프로젝트 구조](PROJECT_STRUCTURE.md)
