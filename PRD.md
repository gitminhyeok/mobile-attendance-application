# Project: Magnus Attendance App (PRD)

## 1. 프로젝트 개요 (Overview)
- **프로젝트명**: Magnus (매그너스)
- **목표**: 특정 장소(와이파이/IP 기준) 및 특정 시간(주말)에만 출석이 가능한 모바일 중심의 웹 어플리케이션.
- **플랫폼**: 모바일 웹 (반응형 웹 어플리케이션).
- **주요 기능**: 카카오 로그인, 조건부 출석 체크(IP/시간), 월별 출석률 확인, 전체 순위, 관리자 대시보드.

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
  - 모바일 퍼스트 디자인.

## 3. 핵심 기능 명세 (Functional Requirements)

### 3.1. 인증 (Authentication)
- **카카오 로그인**: REST API를 이용한 소셜 로그인.
- **사용자 관리**: Firebase `users` 컬렉션에 사용자 정보(UID, 닉네임, 프로필 사진, 가입일) 저장.
- **권한 관리**: `ADMIN_UID` 환경변수에 등록된 사용자만 관리자 페이지 접근 가능.

### 3.2. 출석 체크 로직 (Business Logic)
- **위치 제한**: 
  - 클라이언트의 공인 IP(Public IP)와 서버에 설정된 `ALLOWED_IP`를 대조.
  - `X-Forwarded-For` 헤더를 지원하여 프록시 환경 대응.
- **시간 제한 (KST 기준)**:
  - **토요일**: 13:00 훈련 기준
    - **출석**: 12:50:00 ~ 13:10:00
    - **지각**: 13:10:01 ~ 13:30:00
  - **일요일**: 16:00 훈련 기준
    - **출석**: 15:50:00 ~ 16:10:00
    - **지각**: 16:10:01 ~ 16:30:00
  - **그 외 시간**: 출석 불가.
- **중복 방지**: 1일 1회만 출석 가능.

### 3.3. 관리자 기능 (Admin)
- **대시보드**: 
  - 전체 사용자 중 장기 결석자 모니터링.
  - **경고(Warning)**: 마지막 출석일로부터 14일 이상 경과.
  - **제적(Dropout)**: 마지막 출석일로부터 21일 이상 경과.
- **접근 제어**: 관리자 권한이 없는 사용자가 접근 시 메인으로 리다이렉트.

### 3.4. 데이터베이스 스키마 (Firestore)
- **users**
  - `uid` (String): 카카오 고유 ID (PK)
  - `nickname` (String): 사용자 이름
  - `profile_image` (String): 프로필 이미지 URL
  - `created_at` (Timestamp): 가입일
- **attendance**
  - `user_id` (String): users 컬렉션의 uid (FK)
  - `date` (String): YYYY-MM-DD 형식의 날짜
  - `timestamp` (ServerTimestamp): 실제 기록 시간
  - `status` (String): "present" (출석) or "late" (지각)

## 4. UI/UX 디자인 가이드
- **디자인 컨셉**: Minimalist, Dark/Light Mode(시스템 설정 따름 또는 고정).
- **Framework**: Tailwind CSS.
- **메인 페이지**: 
  - 현재 상태(출석 가능/불가/완료)에 따라 동적으로 변하는 거대 버튼.
  - 직관적인 상태 메시지 표시.
- **내 기록**: 개인별 월간 출석 현황 시각화.
- **랭킹**: 출석 횟수 기반 사용자 랭킹 리스트.
- **관리자**: 결석자 명단을 붉은색(위험) 텍스트로 강조하여 리스트업.

## 5. 개발 진행 상황 (Development Roadmap)
- [x] **v0.3**: 기본 프레임워크 구축, 카카오 로그인, 출석 DB 연동.
- [x] **v0.5**: 디자인 리뉴얼, 로고 적용.
- [x] **v0.9**: 관리자 페이지(장기 결석자 확인), 권한 제어, 모바일 UI 최적화.
- [ ] **v1.0 (예정)**: 
  - WiFi IP 대역 재설정 (현장 테스트 필요).
  - Gym Map 정보 추가.
  - 프로덕션 배포 및 부하 테스트.