# 4. 서비스 계층 (Service Layer)

본 문서는 LiveMeeting의 핵심 비즈니스 로직을 담당하는 서비스 계층(`backend/app/services`)에 대한 상세 가이드입니다.
온프리미스 AI 모델(Whisper, Llama 3)과의 통신 및 데이터 처리 로직을 포함합니다.

---

## 4.1 STT 서비스 (`stt_service.py`)

음성 인식(Speech-to-Text)을 담당하는 서비스입니다.
Docker 컨테이너로 실행 중인 **Whisper Web Service** (`lm_stt`)와 통신하여 오디오 파일을 텍스트로 변환합니다.

### 주요 기능
*   **`transcribe_file_local`**: 오디오 파일을 로컬 Whisper 서비스에 전송하여 전사 작업을 수행합니다.
*   **Deepgram 연동 (구조만 잡힘)**: 실시간 스트리밍 처리를 위한 확장 포인트 (현재는 로컬 파일 처리 위주).

### 작동 흐름
1.  사용자가 오디오 파일 업로드.
2.  백엔드 API가 `STTService.transcribe_file_local(file_path)` 호출.
3.  `httpx` 비동기 클라이언트를 통해 `http://stt:9000/asr` (Docker 내부 네트워크)로 POST 요청 전송.
4.  Whisper 서비스가 오디오를 처리하고 JSON 결과 반환.
5.  서비스가 텍스트(`text` 필드)를 추출하여 반환.

```python
# 사용 예시 (pseudo code)
stt_service = STTService()
transcript_text = await stt_service.transcribe_file_local("path/to/audio.mp3")
```

---

## 4.2 LLM 서비스 (`llm_service.py`)

대규모 언어 모델(Large Language Model)을 이용한 텍스트 분석 및 생성을 담당합니다.
Docker 컨테이너로 실행 중인 **Ollama** (`lm_llm`)와 **LangChain**을 통해 통신합니다.

### 주요 기능
*   **`ChatOllama` 초기화**: LangChain을 사용하여 로컬 Ollama 인스턴스(`http://llm:11434`)와 연결합니다.
*   **프롬프트 템플릿 (`summary_prompt`)**: 회의록 요약을 위한 시스템 프롬프트가 정의되어 있습니다.
    *   요약, 주요 안건, 상세 논의 내용, 결정 사항, 향후 계획 등 구조화된 포맷을 유도합니다.
*   **`generate_summary`**: 전사된 텍스트를 입력받아 최종 회의록을 생성합니다.

### 작동 흐름
1.  회의 종료 또는 "요약 생성" 요청 발생.
2.  `LLMService.generate_summary(title, transcript_text)` 호출.
3.  LangChain이 프롬프트와 전사 텍스트를 조합하여 Ollama API 호출.
4.  Llama 3 모델이 회의록 생성.
5.  결과 텍스트 반환 및 DB 저장.

```python
# 사용 예시 (pseudo code)
llm_service = LLMService()
summary = await llm_service.generate_summary("주간 회의", "A: 안녕하세요... B: 네 알겠습니다...")
```

---

## 4.3 환경 설정 (`config.py` 참조)

서비스 계층은 `.env` 및 `config.py`의 설정을 따릅니다.

*   `LOCAL_STT_URL`: Whisper 서비스 주소 (기본: `http://stt:9000`)
*   `LOCAL_LLM_URL`: Ollama 서비스 주소 (기본: `http://llm:11434`)
*   `LLM_MODEL`: 사용할 모델명 (기본: `llama3`)
*   `LLM_MAX_TOKENS`: 생성 최대 토큰 수
