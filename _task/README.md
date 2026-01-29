# LiveMeeting (LM) 🎙️

AI 기반 실시간 회의록 자동 생성 시스템

## 📌 프로젝트 개요

LiveMeeting은 회의 중 실시간 녹음 또는 녹음 파일 업로드를 통해 자동으로 회의록을 작성해주는 웹 애플리케이션입니다.

### 주요 기능

✅ **실시간 녹음 & 화면 녹화**
- 마이크 및 화면 녹화 동시 진행
- 실시간 STT (Speech-to-Text) 처리
- 중간 요약본 자동 생성

✅ **녹음본 업로드**
- 기존 녹음 파일 업로드 (mp3, wav, m4a, mp4, webm)
- 자동 전사 및 회의록 생성

✅ **AI 회의록 생성**
- LLM 기반 구조화된 회의록 자동 작성
- 주요 안건, 논의사항, 결정사항, 액션 아이템 추출

✅ **다양한 내보내기 형식**
- CSV 형식
- XLSX (Excel) 형식
- CSV 형식
- XLSX (Excel) 형식
- 사용자 지정 저장 경로

✅ **완벽한 온프리미스 보안**
- 외부 클라우드 전송 없음
- 모든 데이터 로컬 서버 저장
- 인터넷 연결 없이 독립 망 운영 가능

## 🛠️ 기술 스택

### Backend
- **FastAPI**: 고성능 비동기 웹 프레임워크
- **PostgreSQL**: 관계형 데이터베이스
- **SQLAlchemy**: ORM
- **Alembic**: 데이터베이스 마이그레이션
- **Local Nova-2 / Whisper**: 온프리미스 STT 엔진 (Docker 내장)
- **Local LLM (Llama 3 / Mistral)**: 온프리미스 회의록 생성 (GPU 서버)

### Frontend
- **HTML/CSS/JavaScript**: 클라이언트 UI
- **WebSocket API**: 실시간 통신
- **MediaRecorder API**: 오디오/비디오 녹화

### DevOps
- **Docker & Docker Compose**: 컨테이너화 및 오케스트레이션

## 📁 프로젝트 구조

자세한 구조는 [`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md)를 참고하세요.

```
live_meeting/
├── backend/          # FastAPI 백엔드
├── frontend/         # HTML/CSS/JS 프론트엔드
├── media/            # 녹음 파일 저장소
├── exports/          # 내보내기 파일
└── docker-compose.yml
```

## 🚀 빠른 시작

### 1. 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 필요한 값을 입력하세요:

```bash
cp .env.example .env
```

필수 환경 변수:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (선택 사항: 클라우드 백업용)
- `OPENAI_API_KEY` (선택 사항: 하이브리드 모드 시)
- **Local AI 모델 경로는 `docker-compose.yml`에서 설정**
- `POSTGRES_USER`, `POSTGRES_PASSWORD`: DB 자격 증명

### 2. Docker Compose 실행

```bash
docker-compose up --build
```

### 3. 데이터베이스 마이그레이션

```bash
docker-compose exec backend alembic upgrade head
```

### 4. 애플리케이션 접속

브라우저에서 `http://localhost:8000` 접속

## 📖 사용 방법

### 실시간 녹음 방식

1. **로그인/회원가입** 후 대시보드 접속
2. **"실시간 녹음"** 버튼 클릭
3. 마이크 및 화면 녹화 권한 허용
4. **"녹음 시작"** 클릭
5. 회의 진행 중 실시간으로 전사 내용 확인
6. **"회의 종료"** 클릭 → AI 회의록 자동 생성
7. CSV 또는 XLSX 형식으로 내보내기

### 녹음본 업로드 방식

1. **로그인/회원가입** 후 대시보드 접속
2. **"녹음본 업로드"** 버튼 클릭
3. 파일 드래그 또는 "찾아보기"로 선택
4. 업로드 완료 후 자동으로 전사 및 회의록 생성
5. CSV 또는 XLSX 형식으로 내보내기

## 🔧 개발 가이드

### 로컬 개발 환경 구성

```bash
# 백엔드 의존성 설치
cd backend
pip install -r requirements.txt

# 데이터베이스 마이그레이션
alembic upgrade head

# 개발 서버 실행
uvicorn app.main:app --reload
```

### 테스트 실행

```bash
docker-compose exec backend pytest tests/
```

### 새로운 마이그레이션 생성

```bash
docker-compose exec backend alembic revision --autogenerate -m "마이그레이션 설명"
docker-compose exec backend alembic upgrade head
```

## 📝 API 문서

FastAPI 자동 생성 문서:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔒 보안

- JWT 토큰 기반 인증
- bcrypt 비밀번호 해싱
- CORS 설정
- 파일 업로드 크기 및 확장자 검증
- 환경 변수로 민감 정보 관리

## 📋 TODO

### 구현 예정 기능
- [ ] 실시간 녹음 기능
- [ ] 녹음본 업로드 기능
- [ ] Nova-2 STT 연동
- [ ] LLM 회의록 생성
- [ ] 중간 요약 기능
- [ ] CSV/XLSX 내보내기
- [ ] 회의 히스토리 관리
- [ ] 다중 언어 지원
- [ ] 화자 분리 (Diarization)
- [ ] 회의록 템플릿 커스터마이징

## 🤝 기여

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 📧 문의

프로젝트 관련 문의사항이 있으시면 Issue를 생성해주세요.

## 🙏 감사의 말

- AWS Transcribe (Nova-2) - STT 엔진
- OpenAI/Anthropic - LLM API
- FastAPI - 웹 프레임워크
