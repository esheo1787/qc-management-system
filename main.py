"""
FastAPI Main Application.
Sync mode for simplicity and SQLite compatibility.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes import router, TAGS_METADATA

app = FastAPI(
    title="QC Management System",
    description="""
## 내부 QC/작업 관리 시스템 API

의료 영상 품질 관리(QC) 및 작업 관리를 위한 내부 운영 도구입니다.

### 주요 기능

* **케이스 관리**: 케이스 등록, 할당, 상태 추적
* **작업 로그**: 작업 시간 기록 (시작/일시중지/재개/제출)
* **QC 요약 저장**: Pre-QC, Auto-QC 결과 요약 저장 (QC는 로컬에서 실행)
* **휴가/공휴일 관리**: 용량 계산을 위한 휴가 및 공휴일 관리
* **코호트 분석**: 태그 기반 코호트 그룹핑 및 메트릭스

### 인증

모든 API는 `X-API-Key` 헤더를 통한 API Key 인증이 필요합니다.

```
X-API-Key: your_api_key_here
```

### 권한

* **ADMIN**: 모든 기능 접근 가능
* **WORKER**: 본인 작업 관련 기능만 접근 가능

### 설계 원칙

* 서버는 QC를 실행하지 않음 (요약만 저장)
* 상태 변경은 Event를 통해서만 수행
* 작업 시간 기록은 WorkLog를 통해서만 수행
* 모든 시간은 Asia/Seoul 타임존 기준
""",
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "QC Management System",
    },
    license_info={
        "name": "Internal Use Only",
    },
)

# CORS (allow Streamlit dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    init_db()


@app.get(
    "/",
    tags=["Health"],
    summary="서비스 상태 확인",
    description="서비스가 정상 동작 중인지 확인합니다. 인증 불필요.",
)
def root():
    """Health check."""
    return {"status": "ok", "service": "qc-management-system"}


@app.get(
    "/health",
    tags=["Health"],
    summary="헬스 체크",
    description="서비스 헬스 체크 엔드포인트. 인증 불필요.",
)
def health():
    """Health check endpoint."""
    return {"status": "healthy"}
