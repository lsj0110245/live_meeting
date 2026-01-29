# 개발 환경 설정 가이드 (On-Premise)

이 문서는 LiveMeeting 프로젝트의 로컬 개발 및 온프리미스 배포를 위한 환경 설정 방법을 안내합니다.

## 시스템 요구사항

- **OS**: Windows, Linux (Ubuntu 권장), or macOS
- **Hardware**:
  - **GPU**: NVIDIA GPU (VRAM 8GB 이상 권장) - *Local LLM 구동 시 필수*
  - **RAM**: 16GB 이상
  - **Disk**: 50GB 이상 (AI 모델 및 데이터 저장용)
- **Software**:
  - Docker & Docker Compose
  - **NVIDIA Container Toolkit** (GPU 가속을 위해 필수)

## 초기 설정 단계

1. **레포지토리 클론**
   ```bash
   git clone <repository-url>
   cd live_meeting
   ```

2. **환경 변수 설정**
   `.env.example`을 복사하여 `.env` 생성:
   ```bash
   cp .env.example .env
   ```
   *필요한 경우 `.env` 파일 내 `LOCAL_STT_URL`, `LOCAL_LLM_URL` 등을 수정하세요.*

3. **AI 모델 준비**
   모델 다운로드 스크립트를 실행하여 필요한 가중치 파일을 받습니다:
   ```bash
   # Linux/macOS
   chmod +x scripts/download_models.sh
   ./scripts/download_models.sh
   
   # Windows (Git Bash 권장)
   ./scripts/download_models.sh
   ```

4. **서비스 실행**
   ```bash
   docker-compose up -d
   ```
   *처음 실행 시 이미지를 다운로드하고 빌드하는 데 시간이 소요됩니다.*

## 실행 확인

- **Backend API**: http://localhost:8001/docs
- **Local STT**: http://localhost:9000/docs (Whisper)
- **Local LLM**: http://localhost:11434 (Ollama)

## 문제 해결

- **GPU가 인식되지 않을 때**:
  - `nvidia-smi` 커맨드가 호스트에서 작동하는지 확인하세요.
  - Docker Desktop의 경우 WSL2 backend 설정을 확인하세요.
  - `nvidia-container-toolkit`이 설치되어 있는지 확인하세요.

- **컨테이너 실행 실패 (OOM)**:
  - 모델 사이즈가 너무 큰 경우일 수 있습니다. `.env`에서 더 작은 모델(예: Whisper tiny, Llama 3 8GB quantized)을 사용하도록 설정을 변경하거나, `docker-compose.yml` 리소스 제한을 조정하세요.
