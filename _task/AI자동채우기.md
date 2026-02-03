# 메타데이터 선택 입력 및 AI 자동 채우기

## 목표

1. **필수 입력 완화**: '회의명'과 '작성자'만 필수로 변경, 나머지는 선택 입력 허용
2. **AI 자동 채우기**: 회의록 생성 시 AI가 전사 내용을 분석하여 비어있는 메타데이터(회의 유형, 참석자, 목적, 주요 내용, 결론 등)를 자동으로 채움

## 구현 계획

### 1. 필드 제약 조건 완화

#### Backend ([upload.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/upload.py), [recording.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/recording.py), [meeting.py](file:///c:/big20/live_meeting/backend/app/schemas/meeting.py))
- `Form(...)` 필수 검증을 `Optional`로 변경
- 유효성 검사 로직에서 `title`, `writer` 외 필드 제외

#### Frontend ([metadata_modal.html](file:///c:/big20/live_meeting/frontend/templates/components/metadata_modal.html), [recording.js](file:///c:/big20/live_meeting/frontend/static/js/recording.js), [dashboard.js](file:///c:/big20/live_meeting/frontend/static/js/dashboard.js))
- input 태그의 `required` 속성 제거 (회의유형, 회의일시, 참석자)
- 유효성 검사 JS 로직 수정

### 2. AI 자동 채우기 기능 구현 (LLM 서비스)

#### [MODIFY] [llm_service.py](file:///c:/big20/live_meeting/backend/app/services/llm_service.py)
- Llama 3 프롬프트 수정: 요약뿐만 아니라 메타데이터(JSON 형식)도 추출하도록 개선
  - **추출 항목**: 회의 유형, 주요 참석자(추론 가능 시), 회의 목적, 주요 내용, 결론
- 반환 형식을 구조화된 JSON으로 변경하거나 파싱 로직 추가

#### [MODIFY] [meeting_tasks.py](file:///c:/big20/live_meeting/backend/app/services/meeting_tasks.py)
- LLM 결과 파싱 후 [Meeting](file:///c:/big20/live_meeting/backend/app/schemas/meeting.py#39-53) 모델 업데이트
- 비어있는 필드(`meeting_type`, `attendees`)가 있다면 AI 결과로 채움
- [Summary](file:///c:/big20/live_meeting/backend/app/models/summary.py#6-22) 모델 업데이트 (구조화된 요약 내용 저장)

### 3. UI 변경 사항

#### [MODIFY] [meeting_detail.html](file:///c:/big20/live_meeting/frontend/templates/meeting_detail.html) / [meeting.js](file:///c:/big20/live_meeting/frontend/static/js/meeting.js)
- 메타데이터 모달에 "✨ AI로 자동 채우기" 버튼 추가 (선택 사항)
- 회의록 생성 완료 후 페이지 새로고침 시 메타데이터 필드가 채워져 있는지 확인

## 실행 순서

1. **필수 검증 완화 (Backend & Frontend)**
   - [metadata_modal.html](file:///c:/big20/live_meeting/frontend/templates/components/metadata_modal.html)의 `required` 속성 제거
   - [upload.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/upload.py), [recording.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/recording.py) API 필수 인자 수정
   - [recording.js](file:///c:/big20/live_meeting/frontend/static/js/recording.js)의 [submitMetadata](file:///c:/big20/live_meeting/frontend/static/js/dashboard.js#696-723) 유효성 검사 수정

2. **LLM 서비스 고도화 (Backend)**
   - [LLMService](file:///c:/big20/live_meeting/backend/app/services/llm_service.py#6-82) 프롬프트 수정 (메타데이터 추출 포함)
   - [process_meeting_summary](file:///c:/big20/live_meeting/backend/app/services/meeting_tasks.py#7-52)에서 메타데이터 업데이트 로직 추가

3. **테스트 및 검증**
   - 회의명/작성자만 입력하고 녹음/업로드 테스트
   - 회의록 생성 후 비어있던 회의유형/참석자 필드가 채워지는지 확인
