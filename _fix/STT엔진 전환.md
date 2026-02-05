### 4) STT 엔진 전환 (Deepgram Nova-2 도입)
* **현황**: Faster-Whisper(Large-v3-Turbo) 사용 중. 정확도는 높으나 서버 자원(VRAM) 소모가 큼.
* **해결**: 업계 최고 수준의 속도와 정확도를 가진 Deepgram Nova-2 모델을 선택적으로 사용할 수 있도록 엔진 전환 로직을 구현합니다.
* **장점**: 서버 부하 감소, 한국어 인식률 향상, 실시간 응답성 개선.

## 2. Proposed Changes

### [Component] Backend Core & API

#### [MODIFY] [config.py](file:///c:/big20/live_meeting/backend/app/core/config.py)
* `STT_ENGINE` (faster-whisper | deepgram) 설정 추가.
* `DEEPGRAM_API_KEY`, `DEEPGRAM_MODEL` (nova-2) 설정 추가.

#### [NEW] [deepgram_stt_service.py](file:///c:/big20/live_meeting/backend/app/services/deepgram_stt_service.py)
* Deepgram SDK를 사용한 파일 및 실시간 전사 로직 구현.

#### [MODIFY] [stt_service.py](file:///c:/big20/live_meeting/backend/app/services/stt_service.py)
* 설정값(`STT_ENGINE`)에 따라 Faster-Whisper 또는 Deepgram 서비스를 동적으로 선택하도록 수정.

#### [MODIFY] [requirements.txt](file:///c:/big20/live_meeting/backend/requirements.txt)
* `deepgram-sdk>=3.0.0` 추가.

#### [MODIFY] [config.py](file:///c:/big20/live_meeting/backend/app/core/config.py)
* (이미 완료) [MEDIA_ROOT](file:///c:/big20/live_meeting/backend/app/core/config.py#57-71) 설정 유지.

#### [MODIFY] [recording.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/recording.py)
* (이미 완료) [MEDIA_ROOT](file:///c:/big20/live_meeting/backend/app/core/config.py#57-71) 기반 저장 로직 유지.

## 3. Verification Plan

### Manual Verification
* 실시간 녹음 종료 후 브라우저 개발자 도구 Network 탭을 확인.
* `/media/realtime_86.webm` 요청 시 응답 코드가 `206 Partial Content`로 나오는지 확인.
* 오디오 재생바를 조절(Seeking)했을 때 소리가 끊김 없이 나오는지 확인.

### Manual Verification
* 모델 변경 후 실시간 인식 시 CPU/GPU 점유율이 안정화되는지 확인.
* 끊김 현상이 줄어들고 전체적인 문장 연결성이 개선되는지 테스트.
