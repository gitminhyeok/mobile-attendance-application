# Magnus Attendance Application

Magnus 팀을 위한 위치 및 시간 기반 모바일 출석 체크 어플리케이션입니다.  
FastAPI와 Firebase를 기반으로 구축되었으며, 특정 WiFi(IP)와 훈련 시간(주말)에만 출석이 가능하도록 설계되었습니다.

## 🌟 Key Features
- **Smart Attendance**: One-click attendance check based on WiFi IP and Time validation.
- **Dynamic UI**: 
    - Interactive 'Fingerprint' attendance button with pulse animations.
    - Smoothly animated attendance rate charts.
    - Visual feedback for 'Present' (Blue) vs 'Late' (Amber) status.
- **Stats & Ranking**: Monthly attendance rates (including late arrivals), streak tracking, and member rankings.
- **Admin Dashboard**: Manage approvals, edit user info, and monitor long-term absences.
- **Kakao Integration**: Easy login via Kakao OAuth.

## 🛠 Tech Stack
- **Frontend**: HTML5, Tailwind CSS (Play CDN), Jinja2 Templates, Lucide Icons
- **Backend**: Python FastAPI
- **Database**: Google Firebase Firestore
- **Deployment**: AWS EC2 (Recommended)

## 🎨 UI Updates (v1.1)
- **Attendance Button**: Redesigned as a large, interactive circular button with a fingerprint icon and breathing animation.
- **Status Indicators**: Distinct visual styles for on-time (Blue Check) and late (Amber Check) attendance.
- **Chart Animations**: Donut charts now animate smoothly from 0% to the target value on load.
- **Footer**: Added a minimalist developer credit footer.

## 🚀 Installation

### 1. 사전 요구사항 (Prerequisites)
- Python 3.10 이상
- Google Firebase 프로젝트 및 인증 키 (`serviceAccountKey.json`)
- Kakao Developers 앱 키 (REST API Key)

### 2. 설치 (Installation)

레포지토리를 클론하고 필요한 패키지를 설치합니다.

```bash
git clone <repository-url>
cd magnus-attendance-application
pip install -r requirements.txt
```

### 3. 환경 변수 설정 (Configuration)

프로젝트 루트에 `.env` 파일을 생성하고 다음 정보를 입력합니다.

```ini
# .env 파일 예시

# Firebase 설정
FIREBASE_CRED_PATH="serviceAccountKey.json"

# Kakao OAuth 설정
KAKAO_REST_API_KEY="your_kakao_rest_api_key"
KAKAO_REDIRECT_URI="http://localhost:8000/auth/kakao/callback"
KAKAO_JS_KEY="your_kakao_javascript_key" # 카카오 지도용

# 세션 보안 (프로덕션 필수)
SECRET_KEY="your_random_secret_key_here"

# 출석 설정
ALLOWED_IP="127.0.0.1, 211.xxx.xxx.xxx"

# 관리자 설정
ADMIN_UID="1234567890, 0987654321"  # 쉼표로 구분하여 여러 명 등록 가능
```

### 4. 실행 (Run)

모바일 접속을 위해 호스트를 `0.0.0.0`으로 설정하여 실행합니다.

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- **PC 접속**: `http://localhost:8000`
- **모바일 접속**: `http://[PC_IP_ADDRESS]:8000` (예: `http://192.168.0.10:8000`)
- **관리자 페이지**: `/admin` 경로로 접속 (권한 필요)

## 📂 프로젝트 구조 (Structure)

```
magnus-attendance-application/
├── main.py              # 앱 진입점 (Entry point)
├── database.py          # Firebase DB 초기화 및 연결
├── logic.py             # 출석 시간 및 IP 체크 핵심 로직
├── routers/             # API 라우터
│   ├── auth.py          # 카카오 로그인 및 승인 대기 처리
│   ├── attendance.py    # 출석 체크 API
│   ├── views.py         # 화면 렌더링 (메인, 랭킹 등)
│   └── admin.py         # 관리자 페이지 로직 (승인, 멤버 관리, 수기 출석)
├── templates/           # HTML 템플릿 (Jinja2)
│   ├── admin/           # 관리자용 템플릿
│   └── ...
├── static/              # 정적 파일 (CSS, JS, Images)
└── requirements.txt     # 의존성 패키지 목록
```

## 📅 출석 규칙 (Attendance Rules)

| 요일 | 훈련 시간 | 출석 인정 시간 | 지각 인정 시간 |
|:---:|:---:|:---:|:---:|
| **토요일** | 13:00 | 12:50 ~ 13:10 | 13:10 ~ 13:30 |
| **일요일** | 16:00 | 15:50 ~ 16:10 | 16:10 ~ 16:30 |

* **미통보 불참**: 2회 누적 시 퇴출 대상
* **병결**: 관리자 승인 시 출석 카운트 예외 처리

## 📝 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.