# QC Management System

의료 영상 세그멘테이션 작업 관리 및 품질 관리(QC) 운영 도구

## 프로젝트 설명

내부 운영용 **작업 관리 / 품질 관리(QC) 운영 도구**입니다.
- 운영 안정성, 비용 0원, 개인 PC ↔ 회사 PC 이식성을 목표로 설계
- 원본 의료 데이터(NRRD/DICOM)는 서버로 업로드하지 않음
- 케이스 메타/상태/이력/시간 로그/QC 요약만 관리

## 주요 기능

### 케이스 관리
- 케이스 등록/조회/수정
- 작업자 배정 및 재배정
- 상태 추적 (TODO → IN_PROGRESS → SUBMITTED → ACCEPTED/REWORK)
- 일괄 등록 (CSV 업로드)

### Pre-QC / Auto-QC
- Pre-QC 요약 저장 (혈관 가시성, 노이즈, 아티팩트 등)
- Auto-QC 결과 저장 (PASS/WARN/INCOMPLETE)
- CSV 일괄 업로드 지원

### 작업자 워크플로우
- 작업 시작/일시중지/재개/제출
- 순수 작업 시간(work_seconds) 자동 계산
- QC 피드백 기록 (수정 내역)
- 추가 수정 사항 기록

### 검수자 워크플로우
- 제출된 케이스 검수 (승인/재작업 요청)
- Auto-QC 이슈 확인 체크박스
- 작업자 추가 수정 확인 체크박스
- QC 불일치 기록 (놓친 문제/잘못된 경고)

### QC 불일치 분석
- 기간별 불일치 통계
- 놓친 문제 / 잘못된 경고 상세 목록
- 세그먼트별 불일치 통계

### 작업 통계
- **성과 탭**: 작업자별 완료 건수, 평균 작업 시간, 재작업률
- **분포 탭**: 상태별/난이도별/프로젝트별 분포
- **가동률 탭**: 팀 가용 시간 대비 실제 작업 시간

### 기타
- 공휴일/개인 휴가 관리
- 코호트 태깅 (연구용 케이스 분류)
- 프로젝트/부위 정의 관리

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | FastAPI (sync mode) |
| Frontend | Streamlit |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (WAL mode) |
| Validation | Pydantic v2 |
| Testing | pytest |
| Timezone | Asia/Seoul |

## 설치 방법

### 1. 저장소 클론
```bash
git clone <repository-url>
cd qc-management-system
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 데이터베이스 초기화
```bash
python seed.py
```

## 실행 방법

### API 서버 (FastAPI)
```bash
uvicorn main:app --reload
```
- URL: http://127.0.0.1:8000
- API 문서: http://127.0.0.1:8000/docs

### 대시보드 (Streamlit)
```bash
streamlit run dashboard.py
```
- URL: http://localhost:8501

> **참고**: API 서버와 대시보드를 모두 실행해야 정상 동작합니다.

### Windows 배치 파일 사용
```
run_server.bat     # API 서버 실행
run_dashboard.bat  # 대시보드 실행
```

## 테스트 실행

```bash
# 전체 테스트
python -m pytest tests/ -v

# 간단한 결과만
python -m pytest tests/ -q

# 특정 파일 테스트
python -m pytest tests/test_cases.py -v
```

현재 테스트 현황: **77 tests passed**

## 폴더 구조

```
qc-management-system/
├── main.py              # FastAPI 애플리케이션 진입점
├── models.py            # SQLAlchemy 모델 정의
├── schemas.py           # Pydantic 스키마
├── services.py          # 비즈니스 로직
├── routes.py            # API 라우터 등록
├── database.py          # 데이터베이스 연결 설정
├── config.py            # 설정 (타임존 등)
├── metrics.py           # 지표 계산 함수
├── dashboard.py         # Streamlit 대시보드
├── seed.py              # 초기 데이터 생성
├── seed_demo.py         # 데모 데이터 생성 (50건)
├── requirements.txt     # Python 의존성
├── pytest.ini           # pytest 설정
│
├── api/                 # API 엔드포인트 모듈
│   ├── auth.py          # 인증
│   ├── cases.py         # 케이스 관리
│   ├── events.py        # 이벤트/워크로그
│   ├── definitions.py   # 프로젝트/부위 정의
│   ├── qc_summary.py    # Pre-QC/Auto-QC
│   ├── qc_disagreements.py  # QC 불일치
│   ├── timeoff.py       # 휴무 관리
│   └── ...
│
├── tests/               # 테스트 코드
│   ├── conftest.py      # pytest 설정/픽스처
│   ├── test_auth.py
│   ├── test_cases.py
│   ├── test_events.py
│   ├── test_qc.py
│   └── ...
│
├── docs/                # 문서
│   ├── API_CONTRACT.md  # API 명세
│   └── VERIFICATION.md  # 검증 체크리스트
│
├── data/
│   └── app.db           # SQLite 데이터베이스
│
└── .claude/             # Claude 설정 (gitignore)
```

## 사용자 역할

| 역할 | 권한 |
|------|------|
| **Admin** | 전체 시스템 관리, 케이스 할당, 검수, 설정 변경 |
| **Worker** | 할당된 케이스 작업, 시간 기록, 제출 |

## 데모 데이터 생성

테스트용 50건의 케이스를 생성하려면:
```bash
python seed_demo.py
```

생성되는 데이터:
- 사용자 6명 (admin 2, worker 4)
- 케이스 50건 (다양한 상태 분포)
- Pre-QC / Auto-QC 데이터
- 작업자/검수자 피드백

## 설계 원칙

1. **상태 변경**: Event를 통해서만 Case.status 변경
2. **시간 기록**: WorkLog로만 작업 시간 기록
3. **지표 계산**: 실시간 계산 (DB 저장 안함)
4. **권한 검증**: 서버에서 강제
5. **동시성**: revision 기반 낙관적 락
6. **멱등성**: idempotency_key로 중복 요청 방지

## 라이선스

Internal Use Only - 내부 운영 전용
