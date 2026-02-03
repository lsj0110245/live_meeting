# STT 품질 개선 (추임새 제거 및 전문 용어 인식)

## Goal Description
현재 STT 코드는 기본적인 전사만 수행하며, 추임새("음", "어") 제거 및 전문 용어("LLM", "SaaS" 등) 인식에 대한 최적화가 되어 있지 않습니다. 이를 개선하기 위해 Whisper 모델의 `initial_prompt`를 튜닝하고, 필요한 경우 전사 후처리 로직을 추가합니다.

## User Review Required
> [!NOTE]
> 전문 용어 리스트를 하드코딩으로 추가할 예정입니다. 추후 사용자별 사전 기능을 추가할 수 있습니다.
> 현재 추가할 용어: [LLM](file:///c:/big20/live_meeting/backend/app/services/llm_service.py#7-152), `RAG`, `SaaS`, `API`, `Docker`, `Kubernetes`, `Python`, `Flutter`, `React`, `FastAPI`

## Proposed Changes

### Backend
#### [MODIFY] [faster_whisper_stt_service.py](file:///c:/big20/live_meeting/backend/app/services/faster_whisper_stt_service.py)
- [transcribe_file](file:///c:/big20/live_meeting/backend/app/services/faster_whisper_stt_service.py#42-88) 및 [transcribe_realtime](file:///c:/big20/live_meeting/backend/app/services/stt_service.py#42-52) 메서드의 `initial_prompt` 수정
    - **변경 전**: "이것은 비즈니스 회의 녹음입니다. 자연스러운 한국어로 전사해주세요."
    - **변경 후**: "이것은 비즈니스 회의 녹음입니다. 자연스러운 한국어로 전사해주세요. 추임새(음, 어, 아, 그, 저)는 제외하고, 전문 용어(LLM, SaaS, API, Docker 등)는 정확한 영문 표기를 유지해주세요."
- (옵션) 단순 문자열 치환을 통한 반복적인 추임새 제거 로직 추가

## Verification Plan
### Manual Verification
- 사용자가 추임새가 섞인 오디오나 전문 용어가 포함된 오디오를 "실시간 녹음" 또는 "파일 업로드"하여 전사 결과 확인.
- "음.. 그러니까 LLM이..." -> "그러니까 LLM이..." 로 전사되는지 확인.
