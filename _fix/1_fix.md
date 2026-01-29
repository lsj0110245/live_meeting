# 1. 트러블슈팅 및 버그 수정 로그 (Fix Log)

본 문서는 LiveMeeting 프로젝트 개발 중 발생한 주요 오류와 해결 방법을 기록합니다.

---

## 1.1 초기 백엔드 실행 오류
**증상**: `uvicorn` 실행 시 `NameError: name 'List' is not defined` 에러 발생하며 컨테이너 시작 실패.
**원인**: [backend/app/api/endpoints/meeting.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/meeting.py) 등에서 `typing.List`, `typing.Any`를 사용했으나 import 문이 누락됨.
**해결**: 
```python
from typing import Any, List  # 누락된 모듈 추가
```

## 1.2 사용자 등록(회원가입) 실패 - 500 Error
**증상**: 회원가입 요청 시 `ValueError: password cannot be hashed` 오류 발생.
**원인**: `passlib 1.7.4`와 `bcrypt 4.1.2` 버전 간의 호환성 문제.
**해결**: [requirements.txt](file:///c:/big20/live_meeting/backend/requirements.txt)에서 `bcrypt` 버전을 다운그레이드.
```text
bcrypt==4.0.1
```

## 1.3 사용자 등록 실패 - DB 스키마 불일치
**증상**: `TypeError: 'username' is an invalid keyword argument for User`.
**원인**: SQLAlchemy [User](file:///c:/big20/live_meeting/backend/app/models/user.py#5-20) 모델에 `username` 컬럼이 정의되지 않았으나, 회원가입 로직에서는 `username`을 저장하려고 함.
**해결**:
1. [backend/app/models/user.py](file:///c:/big20/live_meeting/backend/app/models/user.py)에 `username = Column(String, index=True)` 추가.
2. Alembic 마이그레이션 실행 (`alembic revision --autogenerate`, `upgrade head`).

## 1.4 데이터베이스 연결 실패 (Healthcheck)
**증상**: `docker-compose` 로그에 `FATAL: database "lm_postgres" does not exist` 반복.
**원인**: [docker-compose.yml](file:///c:/big20/live_meeting/docker-compose.yml)의 Healthcheck 명령어가 기본 유저명(`lm_postgres`)을 DB 이름으로 착각하여 접속 시도.
**해결**: DB 이름을 명시적으로 지정.
```yaml
test: ["CMD-SHELL", "pg_isready -U lm_postgres -d live_meeting"]
```

## 1.5 파일 업로드 실패 - 500 Error
**증상**: 오디오 파일 업로드 시 `TypeError: 'audio_file_path' is an invalid keyword argument for Meeting`.
**원인**: [upload.py](file:///c:/big20/live_meeting/backend/app/api/endpoints/upload.py)에서 [Meeting](file:///c:/big20/live_meeting/backend/app/models/meeting.py#6-26) 객체 생성 시 `audio_file_path`와 `status` 필드를 입력했으나, DB 모델([models/meeting.py](file:///c:/big20/live_meeting/backend/app/models/meeting.py))에 해당 컬럼들이 없음.
**해결**:
1. [models/meeting.py](file:///c:/big20/live_meeting/backend/app/models/meeting.py)에 컬럼 추가:
   ```python
   audio_file_path = Column(String, nullable=True)
   status = Column(String, default="pending")
   ```
2. DB 마이그레이션 적용.

## 1.6 프론트엔드 UI 불균형
**증상**: 상단 네비게이션 바의 '로그인' 링크와 '무료 시작하기' 버튼의 크기/위치가 맞지 않음.
**원인**: '로그인'은 단순 텍스트(`<a>`), '시작하기'는 버튼 클래스(`.btn`) 적용으로 인한 스타일 차이.
**해결**: [base.html](file:///c:/big20/live_meeting/frontend/templates/base.html)에서 로그인 링크에도 버튼 스타일 적용 (`btn btn-outline`).

## 1.7 AI 모델 설정 오류 (Ollama)
**증상**: 온프리미스 환경임에도 [.env](file:///c:/big20/live_meeting/.env)에 `LLM_MODEL=gpt-4`로 설정되어 잠재적 오류 위험.
**원인**: 초기 설정 파일의 값 잔재.
**해결**: [.env](file:///c:/big20/live_meeting/.env)를 수정하여 로컬 GPU 모델로 변경.
```ini
LLM_MODEL=llama3
LLM_MAX_TOKENS=4096
```
