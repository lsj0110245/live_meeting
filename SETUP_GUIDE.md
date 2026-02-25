# LiveMeeting 프로젝트 설치 및 실행 가이드

이 문서는 다른 컴퓨터에서 프로젝트를 처음 실행할 때 필요한 절차를 설명합니다.

## 1. 사전 준비 (Prerequisites)

새 컴퓨터에 다음 소프트웨어가 설치되어 있어야 합니다.
*   **Git**: 소스 코드 다운로드용
*   **Docker Desktop**: 컨테이너 실행용 (WSL2 백엔드 권장)
*   **NVIDIA GPU Driver** (선택): 로컬 AI 모델 가속을 위해 권장 (없으면 CPU 모드로 동작하여 매우 느릴 수 있음)

## 2. 프로젝트 가져오기

터미널(PowerShell 또는 CMD)을 열고 프로젝트를 다운로드합니다. (GitHub 등에 올렸을 경우)

```bash
git clone <레포지토리_주소> live_meeting
cd live_meeting
```

## 3. 환경 설정 (`.env` 파일 생성)

`.env` 파일은 보안상 GitHub에 올라가지 않으므로 **수동으로 생성**해야 합니다.
프로젝트 루트 폴더(`live_meeting/`)에 `.env` 파일을 만들고, 아래 내용을 참고하여 채워주세요.
(기존 컴퓨터의 `.env` 내용을 그대로 복사해오는 것이 가장 좋습니다.)

**.env.example** 파일을 복사해서 사용해도 됩니다:
```bash
cp .env.example .env
```

**주요 설정 항목 확인:**
*   `HUGGING_FACE_TOKEN`: HuggingFace 모델 다운로드를 위해 필요합니다.
*   `LANGCHAIN_API_KEY`: LangChain 모니터링 키 (없으면 `LANGCHAIN_TRACING_V2=false`로 변경).
*   `POSTGRES_PASSWORD` 및 `SECRET_KEY`: 보안을 위해 변경 권장.
*   `OLLAMA_BASE_URL`: Docker 내부 통신용 (`http://llm:11434`).

## 4. Docker 실행

도커를 이용해 DB, 백엔드, AI 모델 서버(Ollama)를 한 번에 실행합니다.

```bash
docker-compose up -d --build
```
*   처음 실행 시 AI 모델(Ollama, Faster-Whisper 등)을 다운로드하느라 시간이 꽤 걸릴 수 있습니다 (수 기가바이트).
*   `docker-compose logs -f` 명령어로 로그를 확인하며 에러가 없는지 체크하세요.

## 5. 초기 모델 설정 (Ollama)

컨테이너 실행 시 `scripts/ollama_entrypoint.sh`에 의해 설정된 `LLM_MODEL`을 자동으로 다운로드(pull)합니다.
만약 수동으로 모델을 추가하거나 확인하고 싶다면 아래 명령어를 사용하세요.

```bash
docker exec -it lm_llm ollama list
docker exec -it lm_llm ollama pull exaone3.5:7.8b
```

## 6. 접속

브라우저에서 다음 주소로 접속하여 확인합니다.
*   **Web Application (Frontend + Backend)**: http://localhost:8001
*   **Backend API Docs**: http://localhost:8001/docs
*   **Database**: localhost 포트 `15432`로 접속 가능

## 7. 문제 해결

*   **GPU 오류**: `nvidia-smi` 명령어로 GPU가 인식되는지 확인하세요. Docker Desktop 설정에서 GPU 지원이 켜져 있어야 합니다.
*   **DB 연결 오류**: 잠시 기다렸다가 다시 시도하거나 `docker-compose restart backend`를 해보세요.
