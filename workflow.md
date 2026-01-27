# LiveMeeting 개발 로드맵 (On-Premise)

## 0️⃣ 온프리미스 AI 인프라 구축 (최우선)
**목표:** 로컬 환경에서 STT 및 LLM 모델 구동 준비

1.  **Local AI 서비스 구성**
    *   Docker Compose에 `stt-engine` (Whisper/Nova-2) 및 `llm-engine` (Llama 3/Mistral) 서비스 추가
    *   NVIDIA GPU 지원을 위한 `nvidia-container-toolkit` 설정 확인
2.  **모델 준비**
    *   Hugging Face 등에서 모델 가중치 파일 다운로드 스크립트 작성 (`scripts/download_models.sh`)
    *   Docker Volume을 통한 모델 파일 지속성 확보

---

## 1️⃣ DB 마이그레이션 (완료)
**목표:** 스키마 관리 체계 수립

*   ✅ `alembic init` 및 설정
*   ✅ Core 모델 (`User`, `Meeting`, `Transcript`, `Summary`) 정의
*   ✅ 마이그레이션 적용 (`alembic upgrade head`)

---

## 2️⃣ 인증 시스템 구축
**목표:** 안전한 사용자 관리

*   `core/security.py`: 비밀번호 해싱(bcrypt) 및 JWT 토큰 생성 로직 구현
*   `api/endpoints/auth.py`: 회원가입, 로그인 API 구현
*   `api/deps.py`: JWT 검증 및 `current_user` 의존성 주입 구현

---

## 3️⃣ 실시간 녹음 (Local STT 연동)
**목표:** WebSocket 스트리밍 및 실시간 전사

*   `services/stt_service.py`: **Local STT 컨테이너**로 오디오 청크를 전송하고 텍스트를 수신하는 로직 구현
*   `api/endpoints/recording.py`: WebSocket 엔드포인트 구현 (클라이언트 <-> 서버 <-> Local STT)
*   프론트엔드: `MediaRecorder API` 활용 오디오 캡처 및 전송 로직 작성

---

## 4️⃣ 파일 업로드 및 비동기 처리
**목표:** 녹음 파일 처리 파이프라인

*   `api/endpoints/upload.py`: 파일 업로드 처리 및 저장
*   `services/storage_service.py`: 로컬 디스크에 파일 안전 저장
*   비동기 작업(Background Tasks): 업로드 완료 후 `stt_service`를 통해 전체 전사 요청

---

## 5️⃣ 회의록 생성 (Local LLM 연동)
**목표:** AI 기반 회의 요약 및 구조화

*   `services/llm_service.py`: **Local LLM 컨테이너** API 호출 로직 구현 (OpenAI 호환 인터페이스 권장)
*   Prompt Engineering: 회의록 생성을 위한 최적의 프롬프트 템플릿 작성
*   `api/endpoints/meeting.py`: 요약 생성 트리거 및 결과 저장

---

## 6️⃣ 데이터 내보내기
**목표:** 결과물 활용 형만 제공

*   `services/export_service.py`: `pandas` 및 `openpyxl`을 사용한 데이터 변환
*   `api/endpoints/export.py`: CSV, XLSX 다운로드 엔드포인트

---

## 7️⃣ 프론트엔드 UI 개발
**목표:** 사용자 친화적 인터페이스

*   `templates/`: Jinja2 템플릿 (Login, Dashboard, Recording, Detail)
*   `static/js/`: 페이지별 비동기 로직 (Fetch API, WebSocket)
*   `static/css/`: 반응형 디자인 적용

---

## 8️⃣ 테스트 및 배포 준비
**목표:** 안정성 확보

*   단위 테스트 및 통합 테스트 작성 (`pytest`)
*   `docker-compose.prod.yml`: 상용 환경을 위한 최적화 설정
*   `README.md`: 최종 설치 및 실행 가이드 업데이트
