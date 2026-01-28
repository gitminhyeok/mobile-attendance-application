# Magnus Attendance Application

Magnus 팀을 위한 위치 및 시간 기반 모바일 출석 체크 어플리케이션입니다.  
FastAPI와 Firebase를 기반으로 구축되었으며, 특정 WiFi(IP)와 훈련 시간(주말)에만 출석이 가능하도록 설계되었습니다.

## ✨ 주요 기능 (Features)

- **📍 위치 기반 출석 체크**: 체육관의 특정 WiFi(공인 IP)에 접속해 있어야만 출석 버튼이 활성화됩니다.
- **⏰ 시간 제한 로직**: 정해진 훈련 시간(토요일 13시, 일요일 16시) 전후 20분 내에만 출석이 가능하며, 이후 20분간은 지각 처리됩니다.
- **💬 카카오 로그인**: 별도의 회원가입 절차 없이 카카오 계정으로 간편하게 시작할 수 있습니다.
- **🏆 랭킹 및 기록**: 자신의 출석 현황을 확인하고 팀원들과 출석 랭킹을 경쟁할 수 있습니다.
- **🛡️ 관리자 대시보드 (v1.0)**: 
  - **멤버 관리**: 이름, 기수, 전화번호, 병결(Sick), 미통보 불참(날짜) 등 상세 정보 수정 및 삭제.
  - **기수별 보기**: 기수별로 그룹화된 멤버 리스트 제공.
  - **수기 출석**: 관리자가 직접 날짜별 출석/지각 현황을 일괄 수정 가능.
  - **모니터링**: 장기 결석자 및 퇴출 예정자(경고 누적) 자동 분류.
  - **모바일 최적화**: 스마트폰에서도 손쉽게 관리할 수 있는 반응형 UI(카드 뷰, 모달) 제공.

## 🛠️ 기술 스택 (Tech Stack)

- **Backend**: Python (FastAPI), Uvicorn
- **Database**: Google Firestore (NoSQL)
- **Frontend**: HTML5, Jinja2 Templates, Tailwind CSS (Mobile First)
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
FIREBASE_CRED_PATH="serviceAccountKey.json"

# Kakao OAuth 설정
KAKAO_REST_API_KEY="your_kakao_rest_api_key"
KAKAO_REDIRECT_URI="http://localhost:8000/auth/kakao/callback"
KAKAO_JS_KEY="your_kakao_javascript_key" # 카카오 지도용

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
│   ├── auth.py          # 카카오 로그인 인증
│   ├── attendance.py    # 출석 체크 API
│   ├── views.py         # 화면 렌더링 (메인, 랭킹 등)
│   └── admin.py         # 관리자 페이지 로직 (멤버 관리, 수기 출석)
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

* **미통보 불참**: 2회 누적 시 제적 대상(경고)
* **병결**: 관리자 승인 시 출석 카운트 예외 처리

## 📝 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.