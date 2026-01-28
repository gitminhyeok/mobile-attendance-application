# Project: Magnus Attendance App (PRD)

## 1. 프로젝트 개요 (Overview)
- **프로젝트명**: Magnus (매그너스)
- **목표**: 특정 장소(와이파이/IP 기준) 및 특정 시간(주말)에만 출석이 가능한 모바일 중심의 웹 어플리케이션.
- **플랫폼**: 모바일 웹 (반응형 웹 어플리케이션).
- **주요 기능**: 카카오 로그인(승인제), 조건부 출석 체크(IP/시간), 월별 출석률/랭킹 조회, 관리자 대시보드(수기 관리 포함).

## 2. 기술 스택 (Tech Stack)
- **Language**: Python 3.10+
- **Backend Framework**: FastAPI
  - 비동기 처리 및 빠른 API 응답.
  - Jinja2Templates를 사용하여 SSR(Server Side Rendering) 구현.
- **Database**: Google Firebase (Firestore)
  - NoSQL 기반 클라우드 데이터베이스.
- **Authentication**: Kakao OAuth 2.0
  - REST API 방식, 쿠키를 이용한 세션 관리.
- **Frontend**: HTML5, CSS3 (Tailwind CSS)
  - Tailwind CDN 활용.
  - 모바일 퍼스트 디자인 & 반응형 관리자 페이지.

## 3. 핵심 기능 명세 (Functional Requirements)

### 3.1. 인증 및 보안 (Authentication & Security)
- **카카오 로그인**: REST API를 이용한 소셜 로그인.
- **승인 시스템 (Approval System)**:
  - 신규 가입 시 `pending` 상태로 시작.
  - 관리자가 승인(`approved`)하기 전까지 출석, 랭킹, 기록 조회 등 주요 기능 접근 제한.
- **사용자 관리**: 
  - Firebase `users` 컬렉션에 사용자 정보 저장.
  - **초기 이름 보존**: 가입 시점의 닉네임을 `initial_nickname`으로 저장하여 관리용 참조.
- **권한 관리**: `ADMIN_UID` 환경변수에 등록된 사용자만 관리자 페이지 접근 가능.

### 3.2. 출석 체크 로직 (Business Logic)
- **위치 제한**: 
  - 클라이언트의 공인 IP(Public IP)와 서버에 설정된 `ALLOWED_IP`를 대조.
  - `X-Forwarded-For` 헤더를 지원하여 프록시 환경 대응.
- **시간 제한 (KST 기준)**:
  - **토요일**: 13:00 훈련 기준 (12:50~13:10 출석 / 13:30까지 지각)
  - **일요일**: 16:00 훈련 기준 (15:50~16:10 출석 / 16:30까지 지각)
  - **그 외 시간**: 출석 불가.
- **중복 방지**: 1일 1회만 출석 가능.

### 3.3. 관리자 기능 (Admin)
- **대시보드**: 
  - **가입 승인 대기**: 신규 가입자 목록 확인 및 승인 처리 (보라색 테마).
  - **장기 결석자 모니터링**: 
    - **경고**: 결석 14일 이상 (미통보 불참 제외).
    - **퇴출 대상**: 결석 21일 이상 또는 미통보 불참 2회 누적.
  - **병결자 관리**: 병결 상태인 회원은 카운트에서 제외하고 별도 관리.
- **전체 멤버 관리**:
  - **정보 수정**: 이름, 기수, 전화번호, 미통보 불참일(날짜), 병결 여부 수정.
  - **회원 삭제**: 회원 정보 및 연관된 모든 출석 기록 영구 삭제 (2중 확인).
  - **기수별 보기**: 기수별로 그룹화된 아코디언 리스트 제공 (최신순 정렬).
  - **편의 기능**: 경고 대상자 명단 복사(HTTP 호환), 모바일 카드 뷰/수정 모달 지원.
- **수기 출석 관리 (Manual Attendance)**:
  - 달력을 통해 지난 훈련일 조회 가능.
  - 특정 날짜를 클릭하여 회원들의 출석 상태(출석/지각/결석)를 일괄 수정 및 적용.

### 3.4. 데이터베이스 스키마 (Firestore)
- **users**
  - `uid` (String): 카카오 고유 ID (PK)
  - `nickname` (String): 현재 표시 이름 (수정 가능)
  - `initial_nickname` (String): 가입 시 원본 닉네임 (보존용)
  - `is_auth` (String): 승인 상태 ("pending" / "approved")
  - `profile_image` (String): 프로필 이미지 URL
  - `created_at` (Timestamp): 가입일
  - `phone` (String): 전화번호 (010-XXXX-XXXX)
  - `batch` (String): 가입 기수 (YY-MM)
  - `unnotified_date1`, `unnotified_date2` (String): 미통보 불참 날짜 (YY-MM-DD)
  - `is_sick_leave` (Boolean): 병결 상태 여부
- **attendance**
  - `user_id` (String): users 컬렉션의 uid (FK)
  - `date` (String): YYYY-MM-DD 형식의 날짜
  - `timestamp` (ServerTimestamp): 실제 기록 시간
  - `status` (String): "present" (출석) or "late" (지각)

## 4. UI/UX 디자인 가이드
- **디자인 컨셉**: Minimalist, Black & White with Red/Blue/Yellow/Purple Accents.
- **Framework**: Tailwind CSS.
- **메인 페이지**: 
  - 동적 출석 버튼, 상태별 메시지 (승인 대기/병결/경고/제적).
  - **월별 조회**: 출석률 카드와 랭킹 섹션에서 좌우 화살표로 월별 데이터 탐색 가능.
- **내 기록**: 캘린더 히트맵, 최장 연속 기록(날짜 포함).
- **관리자**: 
  - 모바일 터치 친화적인 인터페이스 (카드 뷰, 콤팩트 모달).
  - 직관적인 상태 색상 및 아이콘 활용.

## 5. 개발 진행 상황 (Development Roadmap)
- [x] **v0.3**: 기본 프레임워크 구축, 카카오 로그인, 출석 DB 연동.
- [x] **v0.5**: 디자인 리뉴얼, 로고 적용.
- [x] **v0.9**: 관리자 페이지(장기 결석자 확인), 권한 제어.
- [x] **v1.0**: 
  - **멤버 정보 확장**: 이름 수정, 전화번호, 기수, 미통보 불참, 병결 관리.
  - **수기 출석 시스템**: 관리자용 달력 및 일괄 출석 수정 기능.
  - **모바일 최적화**: 관리자 페이지 반응형 UI (카드 리스트, 수정 모달).
  - **보안 강화**: 승인제(Approval System) 도입 및 회원 삭제 기능.
  - **UX 개선**: 월별 데이터 조회 기능, 캘린더/랭킹 디자인 고도화.
- [ ] **v1.1 (예정)**: 
  - WiFi IP 대역 정밀 재설정.
  - Gym Map 정보 (카카오 지도 API) 연동.
  - 프로덕션 배포 및 부하 테스트.