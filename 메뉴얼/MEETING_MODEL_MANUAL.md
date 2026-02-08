# 회의록 생성 모델 매뉴얼 (LiveMeeting AI Model Manual)

본 문서는 LiveMeeting 프로젝트의 핵심 기능인 **AI 자동 회의록 생성 모델**의 구조, 작동 원리, 설정 및 데이터 스키마를 상세히 기술합니다.

---

## 1. 개요 (Overview)

LiveMeeting의 회의록 생성 모델은 음성 데이터를 텍스트로 변환(STT)한 후, 대규모 언어 모델(LLM)을 활용하여 핵심 내용을 요약, 분류, 구조화하는 파이프라인으로 구성됩니다.

### 1.1 핵심 기술 스택
- **STT (Speech-to-Text)**: Faster-Whisper (모델: `large-v3-turbo`)
- **LLM (Large Language Model)**: Ollama (모델: `exaone3.5:7.8b`)
- **Framework**: LangChain, FastAPI
- **Database**: PostgreSQL (SQLAlchemy)

---

## 2. 시스템 아키텍처 (System Architecture)

데이터의 흐름은 다음과 같습니다.

1.  **Audio Upload**: 클라이언트가 오디오 파일을 업로드합니다.
2.  **STT Processing**: `faster_whisper_stt_service.py`가 오디오를 텍스트(Transcript)로 변환합니다.
3.  **Text Aggregation**: `meeting_tasks.py`가 분절된 텍스트를 하나의 문맥으로 합칩니다.
4.  **LLM Generation**:
    *   텍스트 길이에 따라 **Standard Mode** 또는 **Map-Reduce Mode**로 분기하여 LLM에 요청을 보냅니다.
    *   LLM은 사전에 정의된 프롬프트에 따라 JSON 형식의 구조화된 요약을 생성합니다.
5.  **Post-Processing**:
    *   JSON 파싱 및 검증.
    *   Markdown 포맷팅.
    *   메타데이터(제목, 참석자, 회의 유형) 자동 추출 및 DB 업데이트.
6.  **Storage**: 최종 결과는 `summaries` 테이블에 저장됩니다.

---

## 3. 상세 프로세스 (Process Details)

### 3.1 텍스트 전처리 및 분기 (Validation & Strategy)
- **입력**: 회의 ID (`meeting_id`).
- **로직**:
    - 해당 회의의 모든 전사(Transcript) 데이터를 시간순으로 정렬하여 로드.
    - 화자(`speaker`)와 내용(`text`)을 결합하여 전체 텍스트 생성.
    - **안전장치 (Safety Limit)**: 텍스트 길이가 **10,000자**를 초과할 경우 `Map-Reduce` 전략을 사용하고, 그렇지 않으면 `Standard` 전략을 사용.

### 3.2 요약 생성 전략 (Generation Strategies)

#### A. Standard Mode (단일 패스)
- 전체 텍스트를 한 번에 LLM 프롬프트에 포함하여 전송.
- 문맥 파악이 가장 정확하며, 회의의 전체적인 흐름을 잘 반영함.

#### B. Map-Reduce Mode (대용량 처리)
- **Chunking**: 전체 텍스트를 **3,000자** 단위로 분할 (Overlap: 500자).
- **Map (개별 요약)**: 각 청크별로 간단한 요약문(3줄 이내) 생성.
- **Reduce (통합 요약)**: 각 청크의 요약문을 합쳐서 다시 LLM에 최종 구조화 요약을 요청.

### 3.3 프롬프트 엔지니어링 (Prompt Engineering)
- **페르소나**: 유능한 비즈니스 전문 비서.
- **원칙**:
    - 완벽한 한국어 사용.
    - 명확하고 간결한 비즈니스 어조 ("~함", "~했음").
    - JSON 포맷 준수.
- **출력 구조 (JSON)**:
    - `metadata`: `title_suggestion`, `meeting_type`, `attendees`
    - `summary`: `purpose`, `content`, `conclusion`, `action_items`

---

## 4. 데이터 스키마 (Data Schema)

### 4.1 Meeting 모델 (`meetings` 테이블)
회의의 기본 정보를 저장합니다.

| 필드명 | 타입 | 설명 |
|---|---|---|
| `id` | Integer | Primary Key |
| `title` | String | 회의 제목 (LLM이 제안한 제목으로 업데이트됨) |
| `meeting_type` | String | 회의 유형 (예: 아이디어 회의, 주간 보고) |
| `attendees` | Text | 참석자 명단 |
| `audio_file_path` | String | 원본 오디오 파일 경로 |
| `status` | String | 처리 상태 (`pending`, `processing`, `completed` 등) |

### 4.2 Summary 모델 (`summaries` 테이블)
생성된 요약본을 저장합니다.

| 필드명 | 타입 | 설명 |
|---|---|---|
| `id` | Integer | Primary Key |
| `meeting_id` | Integer | Foreign Key (Meeting) |
| `content` | Text | 최종 포맷팅된 Markdown 회의록 본문 |
| `created_at` | DateTime | 생성 일시 |

---

## 5. 설정 및 환경 변수 (Configuration)

`.env` 파일 및 `app/core/config.py`에서 다음 설정을 관리합니다.

### 5.1 LLM 설정
- `LLM_MODEL`: `exaone3.5:7.8b` (기본값)
- `LLM_TEMPERATURE`: `0.3` (창의성보다 정확성 중시)
- `OLLAMA_BASE_URL`: `http://llm:11434`

### 5.2 STT 설정
- `STT_ENGINE`: `faster-whisper`
- `STT_MODEL_SIZE`: `deepdml/faster-whisper-large-v3-turbo-ct2`
- `STT_DEVICE`: `cuda` (GPU 사용 시)

---

## 6. 온프레미스(On-Premise) 구축 및 보안

LiveMeeting은 데이터 보안을 최우선으로 고려하여 **완전한 온프레미스(로컬) 환경**에서 동작하도록 설계되었습니다.

### 6.1 데이터 주권 (Data Sovereignty)
- **외부 유출 없음**: 모든 음성 데이터와 텍스트는 내부 서버에서만 처리되며, 외부 클라우드 API(ChatGPT, Claude 등)로 전송되지 않습니다.
- **로컬 LLM 구동**: Ollama를 통해 오픈소스 모델(EXAONE 3.5 등)을 서버 내부(Docker Container)에서 직접 구동합니다.

### 6.2 보안 아키텍처
- **네트워크 격리**: Docker Network 내부에서만 서비스 간 통신(Backend <-> DB <-> LLM)이 이루어집니다.
- **인터넷 차단 환경 지원**: 모델 가중치 파일만 사전에 다운로드하면, 인터넷 연결이 없는 폐쇄망 환경에서도 완벽하게 동작합니다.

---

## 7. 트러블슈팅 (Troubleshooting)

### 7.1 LLM 응답 없음 (Timeout)
- **증상**: 로그에 "LLM 응답 없음" 출력.
- **원인**: 텍스트가 너무 길거나 Ollama 서버 부하.
- **해결**: `Safety Limit` 조절 또는 Docker 자원 할당량 증설.

### 7.2 JSON 파싱 에러
- **증상**: 요약 내용이 깨지거나 "해석할 수 없습니다" 메시지 표시.
- **원인**: LLM이 JSON 형식을 지키지 않고 잡담을 포함하거나 Markdown 코드를 섞음.
- **해결**: `llm_service.py` 내의 `regex` 및 `ast` 파싱 로직이 자동으로 보정 시도. (3단계 Fallback 적용됨)

---

## 8. 커스터마이징 가이드

### 프롬프트 수정
`backend/app/services/llm_service.py` 파일의 `self.summary_prompt` 변수를 수정하여 AI의 어조나 출력 형식을 변경할 수 있습니다.

### 청킹 사이즈 조절
`backend/app/services/meeting_tasks.py` 파일의 `_generate_summary_with_chunking` 함수 내 `CHUNK_SIZE` 값을 변경하여 처리 속도와 정밀도를 조절할 수 있습니다.
