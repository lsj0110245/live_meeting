# 회의 메타데이터 입력 기능 구현 계획

## 목표

실시간 녹음 및 파일 업로드를 시작하기 전에 사용자가 회의 메타데이터를 입력하도록 하여, 회의록 관리의 완성도를 높입니다.

## 사용자 요구사항 확인 완료

✅ **모든 필드 필수 입력**
- 회의명, 회의유형, 회의일시, 참석자, 작성자 모두 필수

✅ **회의유형 입력 방식**
- 드롭다운이 아닌 텍스트 입력 필드로 구현

✅ **메타데이터 수정 기능**
- 녹음/업로드 종료 후 내보내기 전에 "수정하시겠습니까?" 확인
- 수정 가능한 모달 제공

## Proposed Changes

### Frontend - 공통 모달 컴포넌트

#### [NEW] [meeting-metadata-modal.html](file:///c:/big20/live_meeting/frontend/templates/components/meeting-metadata-modal.html)

재사용 가능한 메타데이터 입력 모달 컴포넌트를 생성합니다. 이 모달은 [recording.html](file:///c:/big20/live_meeting/frontend/templates/recording.html)과 [index.html](file:///c:/big20/live_meeting/frontend/templates/index.html)에서 include하여 사용합니다.

**주요 기능:**
- 회의명 (필수 입력)
- 회의유형 (드롭다운 선택)
- 회의일시 (datetime-local input)
- 참석자 (텍스트 입력, 쉼표로 구분)
- 작성자 (텍스트 입력)
- 취소/확인 버튼

---

### Frontend - 실시간 녹음

#### [MODIFY] [recording.html](file:///c:/big20/live_meeting/frontend/templates/recording.html)

메타데이터 입력 모달을 include하고, 녹음 시작 전 모달을 표시하도록 수정합니다.

**변경 사항:**
- 모달 컴포넌트 include 추가
- 녹음 시작 버튼 클릭 시 바로 녹음하지 않고 모달 표시

#### [MODIFY] [recording.js](file:///c:/big20/live_meeting/frontend/static/js/recording.js)

녹음 시작 플로우를 수정하여 메타데이터를 먼저 수집합니다.

**변경 사항:**
- [startRecording()](file:///c:/big20/live_meeting/frontend/static/js/recording.js#107-164) 함수를 `showMetadataModal()`로 변경
- 모달에서 확인 버튼 클릭 시 메타데이터를 수집하고 실제 녹음 시작
- WebSocket 연결 후 메타데이터를 서버로 전송

---

### Frontend - 파일 업로드

#### [MODIFY] [dashboard.js](file:///c:/big20/live_meeting/frontend/static/js/dashboard.js)

파일 업로드 플로우를 수정하여 메타데이터를 먼저 수집합니다.

**변경 사항:**
- 파일 선택 후 바로 업로드하지 않고 모달 표시
- 모달에서 확인 버튼 클릭 시 메타데이터와 함께 파일 업로드
- FormData에 메타데이터 필드 추가

---

### Frontend - 회의 상세 페이지 (내보내기 전 수정)

#### [MODIFY] [meeting_detail.html](file:///c:/big20/live_meeting/frontend/templates/meeting_detail.html)

내보내기 버튼 클릭 시 메타데이터 수정 확인 모달을 표시합니다.

**변경 사항:**
- 메타데이터 수정 모달 추가
- 내보내기 버튼 클릭 시 수정 확인 플로우 추가

#### [MODIFY] [meeting.js](file:///c:/big20/live_meeting/frontend/static/js/meeting.js)

내보내기 전 "메타데이터를 수정하시겠습니까?" 확인 후 수정 가능하도록 합니다.

**변경 사항:**
- [exportMeeting()](file:///c:/big20/live_meeting/frontend/static/js/meeting.js#126-130) 함수 수정: 바로 내보내기 대신 확인 모달 표시
- 모달에서 "수정" 선택 시 메타데이터 편집 모달 표시
- "그대로 내보내기" 선택 시 바로 내보내기 진행
- 메타데이터 수정 후 저장 API 호출

#### [MODIFY] [recording.js](file:///c:/big20/live_meeting/frontend/static/js/recording.js)

녹음 종료 시 메타데이터 수정 확인 플로우를 추가합니다.

**변경 사항:**
- [stopRecording()](file:///c:/big20/live_meeting/frontend/static/js/recording.js#165-194) 함수 수정: 녹음 종료 후 수정 확인 모달 표시
- "수정" 선택 시 메타데이터 편집 모달 표시
- "저장" 선택 시 서버에 최종 저장 및 대시보드로 이동

---

### Backend - API 수정


#### [MODIFY] [recording.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/recording.py)

WebSocket 연결 시 메타데이터를 수신하고 Meeting 레코드를 생성합니다.

**변경 사항:**
- WebSocket 메시지 타입에 `metadata` 추가
- 메타데이터 수신 시 Meeting 레코드 생성
- 이후 전사 데이터는 해당 Meeting에 연결

#### [MODIFY] [upload.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/upload.py)

파일 업로드 API에서 메타데이터를 함께 수신합니다.

**변경 사항:**
- Form 데이터로 메타데이터 필드 추가 수신
- Meeting 생성 시 메타데이터 저장

---

## Verification Plan

### Automated Tests

```bash
# 백엔드 API 테스트
pytest backend/tests/test_recording.py
pytest backend/tests/test_upload.py
```

### Manual Verification

1. **실시간 녹음 플로우**
   - 녹음 시작 버튼 클릭 → 모달 표시 확인
   - 메타데이터 입력 → 녹음 시작 확인
   - DB에 메타데이터 저장 확인

2. **파일 업로드 플로우**
   - 파일 선택 → 모달 표시 확인
   - 메타데이터 입력 → 업로드 진행 확인
   - DB에 메타데이터 저장 확인

3. **회의 상세 페이지**
   - 메타데이터가 올바르게 표시되는지 확인
