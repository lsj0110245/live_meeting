# 실시간 녹음 중단 이슈 분석 및 해결 보고서

**날짜**: 2026-02-19  
**작성자**: Antigravity AI  
**관련 이슈**: 실시간 녹음 도중 "서버 연결이 끊겨 녹음이 중단되었습니다" 메시지 발생 및 녹음 종료

---

## 1. 문제 증상 (Symptoms)
- 실시간 녹음 진행 중, 약 3~5분 경과 시점에서 **"서버 연결이 끊겨 녹음이 중단되었습니다."** 라는 알림창이 뜨며 녹음이 강제로 중단됨.
- 클라이언트(브라우저)와 서버 간의 WebSocket 연결이 끊어지는(Disconnect) 현상 발생.

## 2. 원인 분석 (Cause Analysis)
### 2.1. 서버 로그 분석
- 백엔드(`backend`) 로그 확인 결과, WebSocket 연결이 타임아웃(Timeout) 또는 응답 없음(Unresponsive)으로 인해 끊어지는 패턴 확인.
- 특히 오디오 데이터가 유입될 때 처리 시간이 지연되는 현상이 관찰됨.

### 2.2. 코드 레벨 분석
- **파일**: `backend/app/services/faster_whisper_stt_service.py`
- **함수**: `_preprocess_audio`
- **문제점**: 
  - 실시간 스트리밍 오디오 청크(약 0.5초~1초 단위)가 들어올 때마다 고비용의 **잡음 제거(Denoise) 연산(`noisereduce`)** 을 매번 수행함.
  - 이 `noisereduce` 라이브러리는 CPU 연산량이 매우 높아, 실시간 처리에 병목(Bottleneck)을 유발함.
  - 이로 인해 서버가 클라이언트의 `Ping/Pong` 신호에 제때 응답하지 못해 연결이 끊어짐.

## 3. 조치 내용 (Solution Implemented)

### 3.1. 오디오 전처리 로직 최적화 (Optimization)
- **수정 파일**: `backend/app/services/faster_whisper_stt_service.py`
- **수정 내용**: 
  - `_preprocess_audio` 함수 내에서 `quality` 파라미터에 따라 분기 처리 추가.
  - **파일 업로드 시 (`quality="high"`)**: 기존대로 꼼꼼한 잡음 제거(Denoise) 수행 (정확도 우선).
  - **실시간 녹음 시 (`quality="fast"`)**: **잡음 제거 과정을 생략(Skip)** 하고 원본 오디오를 그대로 사용하도록 변경 (속도 및 연결 유지 우선).

```python
# [변경 전]
# 무조건 잡음 제거 수행
reduced_noise_audio = nr.reduce_noise(y=samples, sr=16000, ...)

# [변경 후]
if quality == "high": # 파일 전사용
    reduced_noise_audio = nr.reduce_noise(y=samples, sr=16000, ...)
else: # 실시간용 (속도 우선)
    print("  Skipping Denoise for Realtime (Speed Priority)...")
    reduced_noise_audio = samples # Denoise 생략
```

### 3.2. 추가 개선: STT 환각(Hallucination) 필터링 강화
- **수정 내용**: 실시간 전사 시 무의미한 텍스트 반복이나 테스트용 문구가 출력되는 현상 수정.
  1.  **Initial Prompt 수정**: 
      - 기존: `"가나다라마바사, 아자차카타파하..."` (테스트 예시가 포함되어 모델이 이를 따라함)
      - 변경: `"회의 녹음입니다. 자연스러운 한국어 문장으로 기록해 주세요."`
  2.  **RegEx 필터링 추가**: `"아자차카"`, `"010-1234-5678"` 등 무의미한 패턴 감지 시 전사 결과에서 제외.

## 4. 결과 (Result)
- **CPU 부하 감소**: 실시간 처리 시 무거운 연산이 제거되어 서버 부하가 대폭 감소함.
- **연결 안정성 확보**: WebSocket 연결 끊김 없이 장시간 실시간 녹음이 가능해짐.
- **품질 유지**: 실시간 전사는 속도를 우선하되, 추후 "녹음 종료" 후 **파일 업로드 재분석(Finalize)** 과정에서 고품질 전사를 다시 수행하므로 최종 회의록 품질은 유지됨.

---
**비고**: 
- 녹음 종료 후 재생 시간(Duration)이 플레이어에서 짧게 표시되는 문제(WebM 헤더 이슈)에 대해서는, DB에 저장된 정확한 전사 시간을 우선 표시하도록 프론트엔드(`meeting.js`) 로직을 보완함.
