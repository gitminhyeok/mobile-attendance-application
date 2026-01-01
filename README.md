# Project: Magnus Attendance App (PRD)

## 1. 프로젝트 개요 (Overview)
- **프로젝트명**: Magnus (매그너스)
- **목표**: 특정 장소(와이파이/IP 기준) 및 특정 시간(주말)에만 출석이 가능한 모바일 중심의 웹 어플리케이션 개발.
- **플랫폼**: 모바일 웹 (반응형 웹 어플리케이션).
- **주요 기능**: 카카오 로그인, 조건부 출석 체크, 월별 출석률 확인, 전체 순위 확인.

## 2. 기술 스택 (Tech Stack)
- **Language**: Python 3.10+
- **Backend Framework**: FastAPI
  - 비동기 처리 및 빠른 API 응답.
  - Jinja2Templates를 사용하여 프론트엔드 렌더링.
- **Database**: Google Firebase (Firestore)
  - NoSQL 기반.
- **Authentication**: Kakao OAuth 2.0
  - REST API 방식, 세션 또는 JWT 발급.
- **Frontend**: HTML5, CSS3 (Tailwind CSS)
  - Tailwind CDN 활용.
- **Deployment**: 로컬 개발 (추후 클라우드 배포).

## 3. 핵심 기능 명세 (Functional Requirements)

### 3.1. 인증 (Authentication)
- **카카오 로그인**: 원클릭 가입/로그인.
- **세션 유지**: 쿠키/세션.
- **사용자 정보 저장**: Firebase users 컬렉션 (UID, 닉네임, 프로필 사진).

### 3.2. 출석 체크 로직 (Business Logic)
- **위치 제한**: 공인 IP(Public IP) 대조 방식. 서버에서 클라이언트 요청 IP 확인.
- **시간 제한 (KST 기준)**:
  - **토요일**: 13:00 기준 (출석: 12:50~13:10, 지각: 13:10:01~13:30)
  - **일요일**: 16:00 기준 (출석: 15:50~16:10, 지각: 16:10:01~16:30)
  - 그 외: 출석 불가.

### 3.3. 데이터베이스 스키마 (Firestore)
- **Users**: `uid` (PK), `nickname`, `created_at`
- **Attendance**: `id` (Auto), `user_id` (FK), `date` (YYYY-MM-DD), `timestamp`, `status` (present/late), `point`

## 4. UI/UX 디자인 가이드 (Minimalist)
- **공통**: 세로형 레이아웃, 하단 네비게이션 바.
- **Tool**: Tailwind CSS.
- **메인 페이지**: 중앙 거대 버튼 (활성/비활성/완료 상태).
- **내 기록**: 이번 달 출석률, 달력/리스트.
- **순위**: 이번 달 기준 출석 횟수/점수 랭킹.

## 5. 개발 단계 (Development Roadmap)
- [ ] **Phase 1 (환경 설정)**: FastAPI 프로젝트 생성, Firebase 연동, 카카오 앱 등록.
- [ ] **Phase 2 (인증)**: 카카오 로그인, DB 저장.
- [ ] **Phase 3 (핵심 로직)**: IP 및 시간 체크 구현.
- [ ] **Phase 4 (UI 연동)**: Jinja2 + Tailwind 페이지 구현.
- [ ] **Phase 5 (테스트)**: 시나리오 테스트.
