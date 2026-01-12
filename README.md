# QC Management System

의료 영상 작업 관리 및 품질 관리(QC) 운영 도구

## 시스템 요구사항

- Python 3.9 이상
- Windows 10/11 (개발 및 운영 환경)

## 빠른 시작 (Windows)

### 1. 초기 설정 (최초 1회)

`setup.bat`을 더블클릭하여 실행합니다.

이 스크립트는 다음을 자동으로 수행합니다:
- 가상환경(venv) 생성
- 의존성 패키지 설치
- 데이터베이스 초기화 및 시드 데이터 생성

**중요**: 설정 완료 후 표시되는 API 키를 반드시 저장하세요!

### 2. 서버 실행

#### API 서버 (FastAPI)
```
run_server.bat 더블클릭
```
- URL: http://127.0.0.1:8000
- API 문서: http://127.0.0.1:8000/docs

#### 대시보드 (Streamlit)
```
run_dashboard.bat 더블클릭
```
- URL: http://localhost:8501

**참고**: API 서버와 대시보드를 모두 실행해야 정상 동작합니다.

## 수동 설치 (선택사항)

### 1. 가상환경 생성 및 활성화

```bash
python -m venv venv
venv\Scripts\activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 데이터베이스 초기화

```bash
python seed.py
```

### 4. 서버 실행

API 서버:
```bash
python -m uvicorn main:app --reload
```

대시보드:
```bash
python -m streamlit run dashboard.py
```

## 프로젝트 구조

```
qc-management-system/
├── main.py              # FastAPI 애플리케이션
├── models.py            # SQLAlchemy 모델 정의
├── schemas.py           # Pydantic 스키마
├── database.py          # 데이터베이스 연결 설정
├── metrics.py           # 지표 계산 함수
├── dashboard.py         # Streamlit 대시보드
├── seed.py              # 초기 데이터 생성
├── requirements.txt     # Python 의존성
├── setup.bat            # 초기 설정 스크립트
├── run_server.bat       # API 서버 실행 스크립트
├── run_dashboard.bat    # 대시보드 실행 스크립트
└── data/
    └── app.db           # SQLite 데이터베이스
```

## 사용자 역할

- **Admin**: 전체 시스템 관리, 케이스 할당, 검수, 설정 변경
- **Worker**: 할당된 케이스 작업, 시간 기록, 제출

## 주요 기능

### 케이스 관리
- 케이스 등록/조회
- 작업자 할당
- 상태 추적 (TODO → IN_PROGRESS → SUBMITTED → ACCEPTED/REWORK)

### 작업 시간 추적
- START/PAUSE/RESUME/SUBMIT 워크로그
- 순수 작업 시간(work_seconds) 계산
- Man-Days(MD) 환산

### 품질 관리
- Pre-QC / Auto-QC 요약 저장
- QC 불일치 분석
- 작업자 QC 피드백

### 휴무/캘린더
- 공휴일 관리
- 개인 휴가 관리
- 팀 가용시간 계산

### 코호트 태깅
- 케이스 태그 관리
- 정의 스냅샷 버전 관리
- 프로젝트-정의 연결

## 기술 스택

- **Backend**: FastAPI (sync mode)
- **Database**: SQLAlchemy 2.0 + SQLite (WAL mode)
- **Validation**: Pydantic v2
- **Dashboard**: Streamlit
- **Timezone**: Asia/Seoul

## 설계 원칙

1. **상태 변경**: Event를 통해서만 Case.status 변경
2. **시간 기록**: WorkLog로만 작업 시간 기록
3. **지표 계산**: 실시간 계산 (DB 저장 안함)
4. **권한 검증**: 서버에서 강제
5. **동시성**: revision 기반 낙관적 락

## 환경 설정

환경별 설정은 `.env` 파일로 관리할 수 있습니다 (선택사항).

```env
# 예시
DATABASE_URL=sqlite:///./data/app.db
TIMEZONE=Asia/Seoul
```

## 라이선스

Internal Use Only - 내부 운영 전용
