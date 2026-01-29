# 5. 프론트엔드 가이드 (Frontend Guide)

본 문서는 LiveMeeting의 사용자 인터페이스(UI)를 구성하는 프론트엔드 구조와 동작 방식에 대한 가이드입니다.
Backend-driven 방식(Jinja2 Templates)과 Vanilla JavaScript를 혼합하여 가볍고 빠른 SPA(Single Page Application)와 유사한 경험을 제공합니다.

---

## 5.1 디렉토리 구조

```
frontend/
├── static/
│   ├── css/
│   │   └── style.css       # 전역 스타일시트 (다크 테마, 반응형)
│   └── js/
│       ├── auth.js         # 로그인, 회원가입 처리
│       ├── common.js       # 공통 유틸리티 (Auth 체크, 로그아웃)
│       ├── dashboard.js    # 메인 대시보드 (회의 목록, 파일 업로드)
│       └── meeting.js      # 회의 상세 화면 (녹음, 요약 보기)
└── templates/
    ├── base.html           # 기본 레이아웃 (헤더, 네비게이션)
    ├── index.html          # 랜딩 페이지 & 대시보드
    ├── login.html          # 로그인 페이지
    ├── register.html       # 회원가입 페이지
    └── meeting_detail.html # 회의 상세 페이지
```

---

## 5.2 템플릿 (Templates)

Jinja2 템플릿 엔진을 사용하여 HTML을 렌더링합니다.

### [base.html](file:///c:/big20/live_meeting/frontend/templates/base.html)
*   모든 페이지의 기본 골격입니다.
*   공통 `<head>` (폰트, 아이콘, CSS), 네비게이션 바(로고, 로그아웃 버튼)를 포함합니다.
*   `{% block content %}`와 `{% block scripts %}`를 통해 하위 페이지에서 내용을 주입합니다.

### [index.html](file:///c:/big20/live_meeting/frontend/templates/index.html) (메인)
*   **이중 뷰(Dual View)** 구조를 가집니다.
    1.  **Landing View**: 비로그인 사용자에게 보이는 환영 메시지 및 로그인/가입 버튼.
    2.  **Dashboard View**: 로그인 사용자에게 보이는 "내 회의 목록" 및 "새 회의 시작" 버튼.
*   [dashboard.js](file:///c:/big20/live_meeting/frontend/static/js/dashboard.js)가 토큰 유무를 판단하여 뷰를 전환합니다.

### [login.html](file:///c:/big20/live_meeting/frontend/templates/login.html) / [register.html](file:///c:/big20/live_meeting/frontend/templates/register.html)
*   사용자 인증을 위한 폼 페이지입니다.
*   [auth.js](file:///c:/big20/live_meeting/frontend/static/js/auth.js)를 통해 백엔드 API와 통신합니다.

### [meeting_detail.html](file:///c:/big20/live_meeting/frontend/templates/meeting_detail.html)
*   특정 회의의 상세 정보를 보여줍니다.
*   오디오 플레이어, 전사 텍스트(Transcript), AI 요약 결과(Summary) 탭으로 구성됩니다.

---

## 5.3 자바스크립트 모듈 (JavaScript Modules)

Vanilla JS를 사용하여 API 통신 및 DOM 조작을 수행합니다.

### [common.js](file:///c:/big20/live_meeting/frontend/static/js/common.js)
*   **[checkLoginStatus()](file:///c:/big20/live_meeting/frontend/static/js/common.js#7-24)**: 페이지 로드 시 로컬 스토리지의 [access_token](file:///c:/big20/live_meeting/backend/app/api/endpoints/auth.py#46-74)을 확인하여 로그아웃/로그인 버튼 상태를 변경합니다.
*   **[logout()](file:///c:/big20/live_meeting/frontend/static/js/common.js#25-30)**: 토큰을 삭제하고 메인으로 리다이렉트합니다.
*   **[authFetch()](file:///c:/big20/live_meeting/frontend/static/js/common.js#31-46)**: `fetch` API의 래퍼(Wrapper)로, 요청 헤더에 자동으로 JWT 토큰을 포함시킵니다.

### [auth.js](file:///c:/big20/live_meeting/frontend/static/js/auth.js)
*   **[handleLogin](file:///c:/big20/live_meeting/frontend/static/js/auth.js#16-44)**: 로그인 API 호출 (`/api/auth/login`). 성공 시 토큰을 `localStorage`에 저장 및 리다이렉트.
*   **[handleRegister](file:///c:/big20/live_meeting/frontend/static/js/auth.js#45-105)**: 회원가입 API 호출 (`/api/auth/register`). 유효성 검사(이메일 형식, 비밀번호 길이 등) 포함.

### [dashboard.js](file:///c:/big20/live_meeting/frontend/static/js/dashboard.js)
*   **[loadMeetings](file:///c:/big20/live_meeting/frontend/static/js/dashboard.js#70-94)**: `/api/meetings/` API를 호출하여 회의 목록을 가져와 렌더링합니다.
*   **[setupUpload](file:///c:/big20/live_meeting/frontend/static/js/dashboard.js#23-69)**: 파일 업로드 UI 이벤트를 처리하고 `/api/upload/` API를 호출합니다.

### [meeting.js](file:///c:/big20/live_meeting/frontend/static/js/meeting.js)
*   회의 상세 데이터를 로드하고 화면에 표시합니다.
*   "요약 생성하기" 버튼 클릭 시 `/api/meetings/{id}/summarize` API를 호출하여 백그라운드 작업을 트리거합니다.

---

## 5.4 주요 UX/UI 특징

*   **반응형 디자인**: 모바일 및 데스크탑 환경 모두 지원.
*   **다크 테마**: 눈의 피로를 최소화하는 어두운 배경과 눈에 띄는 포인트 컬러 사용.
*   **실시간 피드백**: 로딩 인디케이터(Loading Spinners), Toast 알림 등을 통한 사용자 피드백 제공.
