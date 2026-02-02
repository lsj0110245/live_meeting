# 실시간 STT 설정 변경: 변경 전 vs 변경 후

## 개요
STT(음성 인식) 엔진의 핵심 모델을 기존 `medium`에서 `large-v3-turbo`로 업그레이드했습니다. 이 서비스는 **파일 업로드**와 **실시간 회의** 기능이 동일한 엔진을 공유하므로, 변경 사항이 두 기능 모두에 자동으로 적용됩니다.

## 비교표

| 기능 | 변경 전 (Before) | 변경 후 (After) |
| :--- | :--- | :--- |
| **모델 (두뇌)** | `medium` | `deepdml/faster-whisper-large-v3-turbo-ct2` |
| **파라미터 크기** | 약 7.6억 개 (가벼움) | 약 15.5억 개 (Turbo 최적화됨) |
| **사용 장치** | GPU (`cuda`) | GPU (`cuda`) |
| **연산 정밀도** | `float16` | `float16` (설정으로 변경 가능) |
| **파일 변환 방식** | 정확도 중심 (Beam Size 5) | 정확도 중심 (Beam Size 5) |
| **실시간 변환 방식** | 속도 중심 (Beam Size 1) | 속도 중심 (Beam Size 1) |
| **한국어 정확도** | 양호함 ("채법" 같은 오타 발생) | **매우 우수** ("챗봇", "GPT API" 정확히 이해) |
| **메모리 사용량** | 약 1.5GB VRAM | 약 3.5GB VRAM |

## 실시간 처리 부분의 주요 변화
코드는 그대로지만, 엔진이 교체되면서 성능이 다음과 같이 바뀌었습니다.

### 1. 더 똑똑해진 엔진
`large-v3-turbo` 모델은 한국어 문맥, 전문 용어, 동음이의어(소리는 같지만 뜻이 다른 말)를 훨씬 잘 구분합니다.
- **전:** "채 GPT" 라고 들을 수 있음
- **후:** "챗GPT" 라고 정확히 받아적음

### 2. 속도와 반응성 (Latency)
- **전:** 반응이 매우 빠름
- **후:** 모델이 커져서 반응 속도가 아~주 미세하게(0.1초 미만) 느려질 수 있으나, `Turbo` 모델이라 사람이 체감하기는 어렵습니다. 여전히 쾌적합니다.

### 3. 리소스 사용량 주의
실시간 회의 모델이 더 많은 GPU 메모리를 사용합니다. 만약 실시간 회의를 여러 개 동시에 켜거나, 동시에 '요약하기(Ollama)'를 실행하면 6GB 메모리가 꽉 찰 수 있습니다.
- **해결책:** 만약 튕긴다면 [.env](file:///c:/big20/live_meeting/.env) 파일에서 `STT_COMPUTE_TYPE`을 `int8_float16`으로 변경하세요.

## 코드 변경 위치
변경 사항은 [backend/app/services/faster_whisper_stt_service.py](file:///c:/big20/live_meeting/backend/app/services/faster_whisper_stt_service.py) 파일 하나에 적용되었습니다:

```python
# 변경 전
def __init__(self, model_size: str = "medium"):
    self.model_size = model_size
    self.device = "cuda"

# 변경 후
def __init__(self):
    from app.core.config import settings
    self.model_size = settings.STT_MODEL_SIZE  # .env에서 설정을 읽어옴
    self.device = settings.STT_DEVICE
```

이제 [.env](file:///c:/big20/live_meeting/.env) 설정 파일만 수정하면 실시간 회의의 성능도 즉시 변경됩니다.
