# QC Management System

**의료 영상 세그멘테이션 작업의 품질 관리를 위한 웹 기반 관리 시스템**

| 항목 | 내용 |
|------|------|
| 프로젝트명 | QC Management System (의료 영상 QC 관리 시스템) |
| 개발 기간 | 2026.01 ~ |
| 개발 인원 | 1인 |
| 테스트 | 77 tests passed |

---

## 1. 프로젝트 소개

### 배경

의료 영상 AI 모델 학습을 위해서는 고품질의 세그멘테이션 데이터가 필수적입니다.
그러나 수작업으로 진행되는 세그멘테이션 작업은 다음과 같은 문제가 있습니다:

- 작업자별 품질 편차 발생
- 검수 과정에서의 누락 및 오류
- 작업 진행 상황 파악의 어려움
- 품질 이슈 추적 및 분석의 부재

### 목적

- **작업자-검수자 워크플로우 자동화**: 작업 배정부터 검수 완료까지 체계적 관리
- **QC 불일치 분석**: Auto-QC 결과와 검수자 판단 간의 불일치를 기록하고 분석
- **성과 추적**: 작업자별 생산성, 품질 지표를 실시간으로 모니터링

---

## 2. 주요 기능

### 케이스 관리
- 케이스 등록/조회/수정
- 작업자 배정 및 재배정
- 상태 추적 (TODO → IN_PROGRESS → SUBMITTED → ACCEPTED/REWORK)
- CSV 일괄 등록

### Pre-QC (작업 전 품질 분석)
- 원본 데이터 품질 사전 분석
- 혈관 가시성, 노이즈 레벨, 아티팩트 여부 기록
- 작업 난이도 예측에 활용

### Auto-QC (자동 품질 검증)
- 작업 결과 자동 검증
- 상태: PASS / WARN / INCOMPLETE
- 이슈별 상세 내역 기록 (세그먼트 누락, 경계 오류 등)

### 작업자 워크플로우
- 작업 시작/일시중지/재개/제출
- 순수 작업 시간 자동 계산
- QC 피드백 기록 (수정 내역)
- 추가 수정 사항 기록 (놓친 문제/오탐 수정)

### 검수자 워크플로우
- 제출된 케이스 검수
- 승인 / 재작업 요청
- Auto-QC 이슈 확인 체크
- 작업자 추가 수정 확인 체크
- QC 불일치 기록 (놓친 문제/잘못된 경고)

### QC 불일치 분석
- 기간별 불일치 통계 (놓친 문제 / 잘못된 경고)
- 상세 목록 및 세그먼트별 통계
- Auto-QC 정확도 분석에 활용

### 작업 통계 대시보드
| 탭 | 내용 |
|-----|------|
| 성과 | 작업자별 완료 건수, 평균 작업 시간, 재작업률 |
| 분포 | 상태별/난이도별/프로젝트별 케이스 분포 |
| 가동률 | 팀 가용 시간 대비 실제 작업 시간 비율 |

---

## 3. 기술 스택

| 분류 | 기술 | 선택 이유 |
|------|------|-----------|
| **Backend** | FastAPI | 빠른 개발, 자동 API 문서화 (Swagger) |
| **ORM** | SQLAlchemy 2.0 | Type-safe 쿼리, 마이그레이션 용이 |
| **Database** | SQLite (WAL mode) | 무설치, 이식성, 동시성 지원 |
| **Validation** | Pydantic v2 | 스키마 검증, 직렬화 |
| **Frontend** | Streamlit | 빠른 프로토타이핑, 데이터 시각화 |
| **Testing** | pytest | 픽스처 기반 테스트, 격리된 트랜잭션 |

---

## 4. 아키텍처

### 폴더 구조

```
qc-management-system/
├── main.py              # FastAPI 앱 진입점
├── routes.py            # 라우터 등록
├── models.py            # SQLAlchemy 모델
├── schemas.py           # Pydantic 스키마
├── services.py          # 비즈니스 로직
├── database.py          # DB 연결 설정
├── metrics.py           # 지표 계산 함수
├── dashboard.py         # Streamlit 대시보드
│
├── api/                 # API 엔드포인트 모듈
│   ├── auth.py          # 인증/인가
│   ├── cases.py         # 케이스 CRUD
│   ├── events.py        # 이벤트/워크로그
│   ├── qc_summary.py    # Pre-QC/Auto-QC
│   ├── qc_disagreements.py  # QC 불일치
│   └── ...
│
├── tests/               # 테스트 코드 (77 tests)
│   ├── conftest.py      # pytest 픽스처
│   ├── test_cases.py
│   ├── test_events.py
│   └── ...
│
└── docs/                # 문서
    ├── API_CONTRACT.md
    └── VERIFICATION.md
```

### 레이어별 역할

```
┌─────────────────────────────────────────────────────┐
│                    Streamlit UI                      │
│                   (dashboard.py)                     │
└─────────────────────────┬───────────────────────────┘
                          │ HTTP
┌─────────────────────────▼───────────────────────────┐
│                   FastAPI Router                     │
│                     (api/*.py)                       │
│              - 요청 검증, 응답 직렬화                  │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│                   Service Layer                      │
│                   (services.py)                      │
│              - 비즈니스 로직, 트랜잭션                 │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│                   SQLAlchemy ORM                     │
│                    (models.py)                       │
│              - 데이터 접근, 관계 매핑                  │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│                  SQLite Database                     │
│                   (data/app.db)                      │
└─────────────────────────────────────────────────────┘
```

---

## 5. 주요 구현 사항

### API 계약 기반 개발
- OpenAPI (Swagger) 자동 문서화
- Pydantic 스키마를 통한 요청/응답 검증
- 명확한 에러 응답 (HTTPException)

```python
# 예시: 케이스 생성 API
@router.post("/cases/", response_model=CaseResponse)
def create_case(case: CaseCreate, db: Session = Depends(get_db)):
    return case_service.create(db, case)
```

### 트랜잭션 격리를 통한 테스트 안정성
- 각 테스트는 독립적인 트랜잭션에서 실행
- 테스트 종료 시 자동 롤백으로 DB 격리 보장

```python
# conftest.py
@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()  # 자동 롤백
    connection.close()
```

### 공통 UI 컴포넌트
- 테이블 자동 높이 조절 (행 수에 맞춤)
- AgGrid: `domLayout='autoHeight'` 조건부 적용
- st.dataframe: `calculate_dataframe_height()` 함수

```python
def calculate_table_height(row_count, page_size=25, min_rows=5):
    """행 수가 적으면 자동 축소, 많으면 고정 높이"""
    display_rows = min(row_count, page_size)
    display_rows = max(display_rows, min_rows)
    return HEADER_HEIGHT + (display_rows * ROW_HEIGHT) + FOOTER_HEIGHT
```

### 집계 함수 단일화 (SSOT)
- 불일치 통계는 `_get_reviewer_disagreement_stats()` 단일 함수로 계산
- 여러 화면에서 동일한 수치 보장

```python
def _get_reviewer_disagreement_stats(db, start_date, end_date):
    """QC 불일치 통계 집계 (Single Source of Truth)"""
    # 놓친 문제, 잘못된 경고, 세그먼트별 통계 계산
    return {
        "total_count": ...,
        "missed_count": ...,
        "false_alarm_count": ...,
        "missed_records": [...],
        "segment_stats": {...}
    }
```

### 상태 머신 기반 워크플로우
- Case 상태 변경은 Event를 통해서만 수행
- 멱등성 보장 (idempotency_key)
- 낙관적 락 (revision 기반)

```
TODO ──[ASSIGN]──▶ TODO (assigned)
  │                    │
  │               [STARTED]
  │                    ▼
  │              IN_PROGRESS ◀──[RESUME]──┐
  │                    │                   │
  │               [SUBMITTED]          [REWORK]
  │                    ▼                   │
  │               SUBMITTED ──────────────┘
  │                    │
  │               [ACCEPTED]
  │                    ▼
  └──────────────▶ ACCEPTED
```

---

## 6. 실행 방법

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/esheo1787/qc-management-system.git
cd qc-management-system

# 2. 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate  # Windows

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 데이터베이스 초기화
python seed.py
```

### 서버 실행

```bash
# API 서버 (FastAPI)
uvicorn main:app --reload
# → http://127.0.0.1:8000
# → http://127.0.0.1:8000/docs (Swagger UI)

# 대시보드 (Streamlit)
streamlit run dashboard.py
# → http://localhost:8501
```

### 테스트 실행

```bash
# 전체 테스트
python -m pytest tests/ -v

# 간단한 결과
python -m pytest tests/ -q
# 결과: 77 passed
```

---

## 7. 스크린샷

> 스크린샷은 추후 추가 예정입니다.

| 화면 | 설명 |
|------|------|
| 대시보드 메인 | 케이스 목록 및 필터 |
| 작업자 화면 | 작업 시작/제출, QC 피드백 |
| 검수자 화면 | 검수/승인/재작업 요청 |
| QC 불일치 분석 | 통계 및 상세 목록 |
| 성과 대시보드 | 작업자별 성과 지표 |

---

## 8. 향후 계획

### Phase 1: QC 도구 연동
- [ ] Pre-QC 자동 분석 도구 개발
- [ ] Auto-QC 자동 검증 도구 개발
- [ ] 결과 자동 업로드 API

### Phase 2: 3D Slicer 연동
- [ ] 3D Slicer Extension 개발
- [ ] 케이스 불러오기 / 제출 연동
- [ ] 작업 시간 자동 기록

### Phase 3: 고도화
- [ ] 다중 검수자 지원
- [ ] 작업자 교육 모드
- [ ] AI 기반 QC 예측

---

## 연락처

- GitHub: [esheo1787](https://github.com/esheo1787)
