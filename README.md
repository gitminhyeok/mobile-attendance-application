# Magnus Attendance Application

Magnus 팀을 위한 위치 및 시간 기반 모바일 출석 체크 어플리케이션입니다.  
FastAPI와 Firebase를 기반으로 구축되었으며, 특정 WiFi(IP)와 훈련 시간(주말)에만 출석이 가능하도록 설계되었습니다.

## ✨ 주요 기능 (Features)

- **📍 위치 기반 출석 체크**: 체육관의 특정 WiFi(공인 IP)에 접속해 있어야만 출석 버튼이 활성화됩니다.
- **⏰ 시간 제한 로직**: 정해진 훈련 시간(토요일 13시, 일요일 16시) 전후 20분 내에만 출석이 가능하며, 이후 20분간은 지각 처리됩니다.
- **💬 카카오 로그인**: 별도의 회원가입 절차 없이 카카오 계정으로 간편하게 시작할 수 있습니다.
- **🏆 랭킹 및 기록**: 자신의 출석 현황을 확인하고 팀원들과 출석 랭킹을 경쟁할 수 있습니다.
- **🛡️ 관리자 대시보드**: 운영진은 장기 결석자(경고/제적 대상)를 실시간으로 파악할 수 있습니다.

## 🛠️ 기술 스택 (Tech Stack)

- **Backend**: Python (FastAPI), Uvicorn
- **Database**: Google Firestore (NoSQL)
- **Frontend**: HTML5, Jinja2 Templates, Tailwind CSS
- **Auth**: Kakao OAuth 2.0
- **Deployment**: Local / Cloud capable

## 🚀 시작하기 (Getting Started)

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
FIREBASE_CRED_PATH="serviceAccountKey.json"  # Firebase 서비스 계정 키 파일 경로

# Kakao OAuth 설정
KAKAO_REST_API_KEY="your_kakao_rest_api_key"
KAKAO_REDIRECT_URI="http://localhost:8000/auth/kakao/callback"

# 출석 설정
ALLOWED_IP="127.0.0.1, 211.xxx.xxx.xxx"  # 허용할 공인 IP 목록 (콤마로 구분)

# 관리자 설정
ADMIN_UID="1234567890, 0987654321"  # 관리자 권한을 부여할 카카오 UID 목록
```

### 4. 실행 (Run)

로컬 개발 서버를 실행합니다.

```bash
uvicorn main:app --reload
```

브라우저에서 `http://localhost:8000` 으로 접속합니다.

## 📂 프로젝트 구조 (Structure)

```
magnus-attendance-application/
├── main.py              # 앱 진입점 (Entry point)
├── database.py          # Firebase DB 초기화 및 연결
├── logic.py             # 출석 시간 및 IP 체크 핵심 로직
├── routers/             # API 라우터
│   ├── auth.py          # 카카오 로그인 인증
│   ├── attendance.py    # 출석 체크 API
│   ├── views.py         # 화면 렌더링 (메인, 랭킹 등)
│   └── admin.py         # 관리자 페이지 로직
├── templates/           # HTML 템플릿 (Jinja2)
├── static/              # 정적 파일 (CSS, JS, Images)
└── requirements.txt     # 의존성 패키지 목록
```

## 📅 출석 규칙 (Attendance Rules)

| 요일 | 훈련 시간 | 출석 인정 시간 | 지각 인정 시간 |
|:---:|:---:|:---:|:---:|
| **토요일** | 13:00 | 12:50 ~ 13:10 | 13:10 ~ 13:30 |
| **일요일** | 16:00 | 15:50 ~ 16:10 | 16:10 ~ 16:30 |

* 위 시간 외에는 출석 버튼이 비활성화되거나 "출석 시간이 아닙니다"라는 메시지가 표시됩니다.

## 📝 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.