# UPGRADE_GUIDE.md — Auto-QC 자동 라우팅 + 알림 시스템

> **목적**: 이 문서는 Claude Code가 코드베이스를 수정할 때 참조하는 구현 지침서다.
> 단계별로 실행하며, 각 단계 완료 후 반드시 `pytest`를 돌려 기존 테스트가 깨지지 않는지 확인한다.

---

## 0. 현재 상태 요약 (AS-IS)

### 상태 흐름
```
TODO → (STARTED) → IN_PROGRESS → (SUBMITTED) → SUBMITTED
                                                    ├─ (ACCEPTED) → ACCEPTED
                                                    └─ (REWORK_REQUESTED) → REWORK → (STARTED) → IN_PROGRESS → ...
```

### 핵심 코드 위치
| 파일 | 역할 |
|------|------|
| `models.py` | CaseStatus enum, VALID_TRANSITIONS 없음 (services에 있음) |
| `services.py` | VALID_TRANSITIONS dict, process_event(), submit_case(), save_autoqc_summary() |
| `schemas.py` | Pydantic 스키마 |
| `routes.py` → `api/` | API 라우터 (re-export 구조) |
| `dashboard.py` | Streamlit UI |

### 현재 문제점
1. `save_autoqc_summary()`는 데이터만 저장하고 **아무 라우팅 로직이 없다**
2. SUBMITTED 후 검수자가 수동으로 확인 → 사람이 판단할 때까지 대기 상태
3. Auto-QC WARN/INCOMPLETE 케이스도 검수자에게 보임 → 검수자 시간 낭비
4. 알림 없음 → 상태 변경을 대시보드에서 직접 확인해야 함

---

## 1. 목표 상태 (TO-BE)

### 새로운 상태 흐름
```
TODO → IN_PROGRESS → SUBMITTED ──→ [Auto-QC 실행]
                                        │
                         ┌──────────────┼──────────────┐
                         │              │              │
                      PASS           WARN        INCOMPLETE
                         │              │              │
                         ▼              └──────┬───────┘
                     IN_REVIEW                 ▼
                         │              REWORK (작업자에게 반환)
                    ┌────┴────┐              │
                    │         │              ▼
                ACCEPTED   REWORK      IN_PROGRESS → SUBMITTED → [Auto-QC 재실행]
```

### 핵심 변경 사항
1. **CaseStatus에 `IN_REVIEW` 추가** — Auto-QC PASS 후 검수자 대기 상태
2. **Auto-QC 결과에 따른 자동 라우팅** — save_autoqc_summary()에서 상태 전이
3. **로컬 Flask 서버** — 웹 서버 → Auto-QC 트리거 (별도 프로젝트)
4. **Google Chat 알림** — 상태 변경 시 FastAPI에서 직접 webhook 호출
5. **EventType 추가** — AUTOQC_PASS, AUTOQC_FAIL (시스템 이벤트)

---

## 2. 구현 단계

### Phase 1: 모델 변경 (DB 스키마)

#### 1-1. CaseStatus enum에 IN_REVIEW 추가

**파일**: `models.py`

```python
class CaseStatus(str, PyEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"      # ← 추가
    REWORK = "REWORK"
    ACCEPTED = "ACCEPTED"
```

#### 1-2. EventType에 시스템 이벤트 추가

**파일**: `models.py`

```python
class EventType(str, PyEnum):
    # ... 기존 유지 ...

    # 시스템 이벤트 (Auto-QC 결과)
    AUTOQC_PASS = "AUTOQC_PASS"
    AUTOQC_FAIL = "AUTOQC_FAIL"
```

#### 1-3. Case 모델에 autoqc_triggered_at 필드 추가 (선택)

Auto-QC 트리거 시점 추적용. 폴링 백업에서 "아직 결과 안 온 케이스" 판별에 사용.

```python
class Case(Base):
    # ... 기존 필드 ...
    autoqc_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

#### 1-4. NotificationLog 모델 추가

알림 발송 기록 저장. 재발송 방지 + 감사 추적.

```python
class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # "google_chat"
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_url: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "SUCCESS", "FAILED"
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )
```

#### 1-5. DB 마이그레이션

SQLite라서 Alembic 없이 직접 처리. **기존 DB가 있는 환경에서는 ALTER TABLE 필요.**

```sql
-- 마이그레이션 스크립트 (migrate_v2.py로 제공)
ALTER TABLE cases ADD COLUMN autoqc_triggered_at DATETIME;

CREATE TABLE IF NOT EXISTS notification_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id),
    channel VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    message_text TEXT NOT NULL,
    webhook_url VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_detail TEXT,
    created_at DATETIME NOT NULL
);
```

⚠️ **CaseStatus, EventType은 SQLAlchemy Enum이므로 SQLite에서는 문자열로 저장됨 → enum 값 추가는 코드 변경만으로 충분하고 DB 변경 불필요.**

**검증**: `pytest` 실행 → 모든 기존 테스트 통과 확인

---

### Phase 2: 상태 전이 로직 변경

#### 2-1. VALID_TRANSITIONS 수정

**파일**: `services.py`

```python
VALID_TRANSITIONS: dict[tuple[CaseStatus, EventType], CaseStatus] = {
    # 작업 시작
    (CaseStatus.TODO, EventType.STARTED): CaseStatus.IN_PROGRESS,
    (CaseStatus.REWORK, EventType.STARTED): CaseStatus.IN_PROGRESS,

    # 작업 제출
    (CaseStatus.IN_PROGRESS, EventType.SUBMITTED): CaseStatus.SUBMITTED,

    # Auto-QC 결과에 따른 자동 라우팅 (Phase 2 신규)
    (CaseStatus.SUBMITTED, EventType.AUTOQC_PASS): CaseStatus.IN_REVIEW,
    (CaseStatus.SUBMITTED, EventType.AUTOQC_FAIL): CaseStatus.REWORK,

    # 검수 판정 — SUBMITTED가 아닌 IN_REVIEW에서 발생 (변경!)
    (CaseStatus.IN_REVIEW, EventType.REWORK_REQUESTED): CaseStatus.REWORK,
    (CaseStatus.IN_REVIEW, EventType.ACCEPTED): CaseStatus.ACCEPTED,
}
```

⚠️ **기존 전이 삭제됨:**
- `(SUBMITTED, REWORK_REQUESTED)` → 삭제. 검수자는 IN_REVIEW 상태에서만 판정.
- `(SUBMITTED, ACCEPTED)` → 삭제. 마찬가지.

이 변경으로 **SUBMITTED 상태의 케이스는 Auto-QC 결과가 올 때까지 "잠긴" 상태**가 된다.

#### 2-2. save_autoqc_summary()에 라우팅 로직 추가

**파일**: `services.py`

현재 `save_autoqc_summary()`는 단순 저장만 한다. 여기에 라우팅 + 이벤트 생성 로직을 추가한다.

```python
def save_autoqc_summary(
    db: Session, request: AutoQcSummaryCreateRequest, current_user: User
) -> AutoQcSummaryResponse:
    """
    Save Auto-QC summary and route case based on result.

    PASS → IN_REVIEW (검수자 대기열)
    WARN/INCOMPLETE → REWORK (작업자 반환)
    """
    import uuid

    with safe_begin(db):
        case = db.query(Case).filter(Case.id == request.case_id).first()
        if not case:
            raise NotFoundError(f"Case {request.case_id} not found")

        # --- 기존 저장 로직 (현재 코드 유지) ---
        # ... (missing_segments_json, issues_json 등 변환)
        # ... (existing or new AutoQcSummary 생성/업데이트)
        # --- 저장 로직 끝 ---

        # ====== 신규: 자동 라우팅 ======
        # SUBMITTED 상태일 때만 라우팅 (이미 REWORK/IN_REVIEW면 무시)
        if case.status == CaseStatus.SUBMITTED and request.status:
            now = now_kst()

            if request.status == "PASS":
                # Auto-QC 통과 → IN_REVIEW
                event = Event(
                    case_id=case.id,
                    user_id=current_user.id,
                    event_type=EventType.AUTOQC_PASS,
                    idempotency_key=f"AUTOQC_PASS_{case.id}_rev{case.revision}_{uuid.uuid4().hex[:8]}",
                    event_code="Auto-QC PASS → 검수 대기",
                    created_at=now,
                )
                db.add(event)
                case.status = CaseStatus.IN_REVIEW

            elif request.status in ("WARN", "INCOMPLETE"):
                # Auto-QC 실패 → REWORK
                event = Event(
                    case_id=case.id,
                    user_id=current_user.id,
                    event_type=EventType.AUTOQC_FAIL,
                    idempotency_key=f"AUTOQC_FAIL_{case.id}_rev{case.revision}_{uuid.uuid4().hex[:8]}",
                    event_code=f"Auto-QC {request.status} → 재작업",
                    payload_json=json.dumps({
                        "autoqc_status": request.status,
                        "issue_count": request.issue_count,
                    }, ensure_ascii=False),
                    created_at=now,
                )
                db.add(event)
                case.status = CaseStatus.REWORK
                case.revision += 1

        db.flush()

        # ====== 신규: 알림 발송 ======
        # Phase 4에서 구현. 여기서는 호출만.
        # _send_autoqc_notification(db, case, request.status)

        return AutoQcSummaryResponse(...)  # 기존 반환 유지
```

#### 2-3. 검수자 대시보드 필터 변경

**파일**: `dashboard.py`

검수자 페이지에서 `SUBMITTED` 대신 `IN_REVIEW` 케이스만 보여줘야 한다.

```python
# AS-IS (검수 대기 목록)
cases = get_cases_by_status(db, CaseStatus.SUBMITTED)

# TO-BE
cases = get_cases_by_status(db, CaseStatus.IN_REVIEW)
```

검색 범위:
- `dashboard.py`에서 `CaseStatus.SUBMITTED`를 참조하는 **검수자 관련** 코드를 찾아 `CaseStatus.IN_REVIEW`로 변경
- 작업자 관련 코드에서 `SUBMITTED`는 그대로 유지 (작업자 입장에서는 제출 후 대기 상태)

#### 2-4. get_worker_tasks() 수정

**파일**: `services.py`

작업자 작업 목록에 SUBMITTED도 포함 (Auto-QC 결과 대기 중 표시).

```python
def get_worker_tasks(db: Session, worker: User) -> CaseListResponse:
    cases = (
        db.query(Case)
        .filter(
            Case.assigned_user_id == worker.id,
            Case.status.in_([
                CaseStatus.TODO,
                CaseStatus.IN_PROGRESS,
                CaseStatus.SUBMITTED,    # ← 추가: Auto-QC 대기 중 표시
                CaseStatus.REWORK,
            ]),
        )
        .order_by(Case.created_at.desc())
        .all()
    )
    # ...
```

**검증**: `pytest` 실행. **기존 테스트 중 SUBMITTED→ACCEPTED, SUBMITTED→REWORK 전이 테스트는 실패할 것.** 이 테스트들을 Phase 2-5에서 수정한다.

#### 2-5. 기존 테스트 수정

IN_REVIEW 추가로 인해 깨지는 테스트 패턴:

```python
# AS-IS: SUBMITTED에서 바로 ACCEPTED
event = process_event(db, EventCreateRequest(
    case_id=case.id,
    event_type=EventType.ACCEPTED,
    idempotency_key="...",
), admin)

# TO-BE: SUBMITTED → (Auto-QC PASS) → IN_REVIEW → ACCEPTED
# 1) Auto-QC 결과 저장 (상태가 IN_REVIEW로 전이)
save_autoqc_summary(db, AutoQcSummaryCreateRequest(
    case_id=case.id,
    status="PASS",
), admin)
# 2) 그 후 ACCEPTED
event = process_event(db, EventCreateRequest(
    case_id=case.id,
    event_type=EventType.ACCEPTED,
    idempotency_key="...",
), admin)
```

**검증**: `pytest` 실행 → 전체 통과 확인

---

### Phase 3: 로컬 Flask Auto-QC 트리거 서버

> 이것은 **별도 프로젝트 폴더**로 생성한다. 웹 시스템 코드베이스와 분리.

#### 3-1. 프로젝트 구조

```
autoqc-trigger/
├── app.py              # Flask + APScheduler
├── config.py           # 설정 (API URL, NAS 경로, 폴링 주기)
├── autoqc_runner.py    # Auto-QC 실행 로직 (기존 Slicer 연동)
├── requirements.txt    # flask, apscheduler, requests
└── README.md
```

#### 3-2. app.py 핵심 구조

```python
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import requests

app = Flask(__name__)

# === Webhook 수신 (FastAPI → Flask) ===
@app.route("/trigger", methods=["POST"])
def trigger_autoqc():
    """
    FastAPI가 케이스 제출 시 호출.
    요청 본문: {"case_id": 123, "case_uid": "CASE_001", "nas_path": "/path/to/case"}
    """
    data = request.json
    case_id = data["case_id"]
    nas_path = data["nas_path"]

    # 비동기로 Auto-QC 실행 (별도 스레드)
    from threading import Thread
    thread = Thread(target=run_and_upload, args=(case_id, nas_path))
    thread.start()

    return jsonify({"status": "triggered", "case_id": case_id}), 202


def run_and_upload(case_id: int, nas_path: str):
    """Auto-QC 실행 후 결과를 웹 서버에 업로드."""
    try:
        result = run_autoqc(nas_path)  # autoqc_runner.py 호출

        # 결과를 웹 서버 API로 전송
        response = requests.post(
            f"{WEB_API_URL}/api/autoqc-summary",
            json={
                "case_id": case_id,
                "status": result["status"],  # "PASS" / "WARN" / "INCOMPLETE"
                "missing_segments": result.get("missing_segments"),
                "issues": result.get("issues"),
                "issue_count": result.get("issue_count"),
                # ... 기타 필드
            },
            headers={"X-API-Key": API_KEY},
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Auto-QC failed for case {case_id}: {e}")
        # TODO: 실패 알림


# === 폴링 백업 (Webhook 실패 대비) ===
def poll_submitted_cases():
    """
    주기적으로 SUBMITTED 상태인데 Auto-QC 결과가 없는 케이스 확인.
    Webhook이 실패했을 때의 안전망.
    """
    try:
        response = requests.get(
            f"{WEB_API_URL}/api/cases",
            params={"status": "SUBMITTED"},
            headers={"X-API-Key": API_KEY},
        )
        cases = response.json()["cases"]

        for case in cases:
            # Auto-QC 결과가 이미 있으면 스킵
            autoqc_resp = requests.get(
                f"{WEB_API_URL}/api/autoqc-summary/{case['id']}",
                headers={"X-API-Key": API_KEY},
            )
            if autoqc_resp.status_code == 200 and autoqc_resp.json():
                continue  # 이미 결과 있음

            # Auto-QC 실행
            if case.get("nas_path"):
                run_and_upload(case["id"], case["nas_path"])

    except Exception as e:
        print(f"Polling error: {e}")


# === 스케줄러 설정 ===
scheduler = BackgroundScheduler()
scheduler.add_job(poll_submitted_cases, "interval", minutes=10)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
```

#### 3-3. FastAPI에 webhook 호출 추가

**파일**: `services.py`의 `submit_case()`

제출 시 로컬 Flask 서버에 webhook을 보낸다. **실패해도 제출 자체는 성공**해야 한다 (fire-and-forget).

```python
def submit_case(db, request, current_user):
    # ... 기존 제출 로직 ...

    # ====== 신규: Auto-QC 트리거 ======
    _trigger_autoqc(case)  # fire-and-forget

    return SubmitResponse(...)


def _trigger_autoqc(case: Case) -> None:
    """로컬 Flask 서버에 Auto-QC 트리거 webhook 전송. 실패해도 무시."""
    import requests as req
    from config import AUTOQC_TRIGGER_URL  # "http://localhost:5050/trigger"

    if not AUTOQC_TRIGGER_URL:
        return  # 설정 안 되어 있으면 스킵 (개발 환경)

    try:
        req.post(
            AUTOQC_TRIGGER_URL,
            json={
                "case_id": case.id,
                "case_uid": case.case_uid,
                "nas_path": case.nas_path,
            },
            timeout=5,
        )
    except Exception:
        pass  # 실패해도 폴링이 잡아줌
```

#### 3-4. config.py에 설정 추가

**파일**: `config.py`

```python
# Auto-QC 트리거 설정
AUTOQC_TRIGGER_URL = os.getenv("AUTOQC_TRIGGER_URL", "")  # "http://localhost:5050/trigger"
```

**검증**: 
- Flask 서버 없이도 웹 서버 정상 동작 확인 (AUTOQC_TRIGGER_URL 비어있으면 스킵)
- `pytest` 실행 → 전체 통과

---

### Phase 4: Google Chat 알림 서비스

#### 4-1. 알림 서비스 모듈 생성

**파일**: `notification.py` (신규)

```python
"""
Google Chat Webhook 알림 서비스.
FastAPI 내부에서 직접 호출. 외부 오케스트레이터(n8n 등) 불필요.
"""
import json
import requests as req
from typing import Optional
from sqlalchemy.orm import Session
from models import Case, NotificationLog, now_kst
from config import (
    GCHAT_WEBHOOK_REVIEWER,   # 검수자 채팅방 webhook URL
    GCHAT_WEBHOOK_WORKER,     # 작업자 채팅방 webhook URL
    NOTIFICATIONS_ENABLED,    # True/False
)


def send_google_chat(
    db: Session,
    webhook_url: str,
    message: str,
    case_id: Optional[int] = None,
    event_type: str = "UNKNOWN",
) -> bool:
    """Google Chat webhook 호출 + 로그 저장."""
    if not NOTIFICATIONS_ENABLED or not webhook_url:
        return False

    status = "SUCCESS"
    error_detail = None

    try:
        resp = req.post(
            webhook_url,
            json={"text": message},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        status = "FAILED"
        error_detail = str(e)

    # 로그 저장
    log = NotificationLog(
        case_id=case_id,
        channel="google_chat",
        event_type=event_type,
        message_text=message,
        webhook_url=webhook_url,
        status=status,
        error_detail=error_detail,
    )
    db.add(log)
    db.commit()

    return status == "SUCCESS"


# === 알림 템플릿 함수 ===

def notify_autoqc_pass(db: Session, case: Case) -> None:
    """Auto-QC PASS → 검수자에게 알림."""
    worker_name = case.assigned_user.username if case.assigned_user else "?"
    msg = (
        f"✅ *Auto-QC 통과*\n"
        f"케이스: `{case.case_uid}` ({case.display_name})\n"
        f"작업자: {worker_name}\n"
        f"검수 대기열에 추가되었습니다."
    )
    send_google_chat(db, GCHAT_WEBHOOK_REVIEWER, msg, case.id, "AUTOQC_PASS")


def notify_autoqc_fail(db: Session, case: Case, autoqc_status: str, issue_summary: str = "") -> None:
    """Auto-QC WARN/INCOMPLETE → 작업자에게 알림."""
    emoji = "⚠️" if autoqc_status == "WARN" else "🚨"
    label = "경미한 문제" if autoqc_status == "WARN" else "심각한 문제"
    msg = (
        f"{emoji} *Auto-QC: {label} 발견*\n"
        f"케이스: `{case.case_uid}` ({case.display_name})\n"
        f"상태: {autoqc_status}\n"
    )
    if issue_summary:
        msg += f"내용: {issue_summary}\n"
    msg += "수정 후 재제출해 주세요."
    send_google_chat(db, GCHAT_WEBHOOK_WORKER, msg, case.id, "AUTOQC_FAIL")


def notify_rework_requested(db: Session, case: Case, note_text: str = "") -> None:
    """검수자 재작업 요청 → 작업자에게 알림."""
    msg = (
        f"🔄 *재작업 요청*\n"
        f"케이스: `{case.case_uid}` ({case.display_name})\n"
    )
    if note_text:
        msg += f"사유: {note_text}\n"
    msg += "확인 후 수정해 주세요."
    send_google_chat(db, GCHAT_WEBHOOK_WORKER, msg, case.id, "REWORK_REQUESTED")


def notify_accepted(db: Session, case: Case) -> None:
    """검수 완료 → 작업자에게 알림."""
    msg = (
        f"🎉 *검수 완료*\n"
        f"케이스: `{case.case_uid}` ({case.display_name})\n"
        f"검수가 승인되었습니다."
    )
    send_google_chat(db, GCHAT_WEBHOOK_WORKER, msg, case.id, "ACCEPTED")
```

#### 4-2. config.py에 알림 설정 추가

```python
# Google Chat Webhook URLs
GCHAT_WEBHOOK_REVIEWER = os.getenv("GCHAT_WEBHOOK_REVIEWER", "")
GCHAT_WEBHOOK_WORKER = os.getenv("GCHAT_WEBHOOK_WORKER", "")
NOTIFICATIONS_ENABLED = os.getenv("NOTIFICATIONS_ENABLED", "false").lower() == "true"
```

#### 4-3. .env.example 업데이트

```env
# Auto-QC Trigger
AUTOQC_TRIGGER_URL=http://localhost:5050/trigger

# Google Chat Notifications
GCHAT_WEBHOOK_REVIEWER=https://chat.googleapis.com/v1/spaces/XXXXX/messages?key=...
GCHAT_WEBHOOK_WORKER=https://chat.googleapis.com/v1/spaces/YYYYY/messages?key=...
NOTIFICATIONS_ENABLED=false
```

#### 4-4. 알림 호출 지점 연결

**services.py**에서 상태 전이 발생 시 알림 함수 호출:

```python
# save_autoqc_summary() 내부, 라우팅 로직 직후:
if request.status == "PASS":
    # ... 상태 전이 ...
    from notification import notify_autoqc_pass
    notify_autoqc_pass(db, case)

elif request.status in ("WARN", "INCOMPLETE"):
    # ... 상태 전이 ...
    from notification import notify_autoqc_fail
    issue_summary = _build_issue_summary(request)  # 헬퍼 함수
    notify_autoqc_fail(db, case, request.status, issue_summary)


# process_event() 내부:
if request.event_type == EventType.REWORK_REQUESTED:
    # ... 상태 전이 ...
    from notification import notify_rework_requested
    notify_rework_requested(db, case, request.event_code or "")

elif request.event_type == EventType.ACCEPTED:
    # ... 상태 전이 ...
    from notification import notify_accepted
    notify_accepted(db, case)
```

**검증**: 
- `NOTIFICATIONS_ENABLED=false`일 때 알림 미발송 확인
- `pytest` 실행 → 전체 통과

---

### Phase 5: Worker False Positive 처리 (검수자 최종 확인)

작업자가 Auto-QC WARN 항목 중 "잘못된 경고"를 표시할 수 있다.
단, **Auto-QC는 예외 처리 없이 항상 동일 기준으로 검사**한다.
작업자의 피드백은 **검수자에게 전달되는 맥락 정보**로만 기능한다.

#### 핵심 원칙

```
Auto-QC = 기계적 검사. 작업자 피드백으로 기준이 바뀌지 않음.
검수자 = 최종 판단권. "잘못된 경고" 주장의 타당성을 검수자가 결정.
```

#### 흐름

```
작업자: WARN 항목에 "잘못된 경고" 피드백 제출
    │
    ▼
작업자: 실제 이슈만 수정 후 재제출
    │
    ▼
Auto-QC 재실행 (동일 기준, 예외 없음)
    │
    ├─ 남은 WARN이 "잘못된 경고" 표시 항목뿐 → PASS → IN_REVIEW
    │       검수자가 케이스 열면:
    │         - Auto-QC 결과 (WARN 항목 목록)
    │         - 작업자 피드백 ("이 항목은 잘못된 경고")
    │         → 검수자가 동의하면 ACCEPTED
    │         → 검수자가 거부하면 REWORK + 사유 기재
    │
    └─ 실제 이슈 남아있음 → WARN → REWORK (작업자에게 반환)
```

#### 5-1. Auto-QC에서 "잘못된 경고" 항목 처리

**중요: Auto-QC 로직 자체는 변경하지 않는다.**

대신 로컬 Flask 서버(autoqc-trigger)에서 결과 판정 시, 작업자가 "잘못된 경고"로 표시한 항목만 남은 경우 최종 status를 `PASS`로 올려보낸다.

```python
# autoqc-trigger/autoqc_runner.py

def determine_final_status(raw_issues: list, worker_false_alarms: list) -> str:
    """
    Auto-QC 원본 결과에서, 작업자가 FALSE_ALARM으로 표시한 항목을 제외하고
    남은 이슈가 있는지 판단.

    - raw_issues: Auto-QC가 검출한 전체 이슈 (기준 불변)
    - worker_false_alarms: 작업자가 "잘못된 경고"로 표시한 항목
    - 반환: "PASS" / "WARN" / "INCOMPLETE"

    ⚠️ Auto-QC 검사 기준 자체는 바꾸지 않는다.
       전체 이슈 목록은 그대로 웹에 업로드한다 (검수자가 볼 수 있도록).
       이 함수는 "라우팅 판정"만 조정한다.
    """
    # INCOMPLETE 이슈는 절대 예외 처리 불가
    incomplete_issues = [i for i in raw_issues if i.get("level") == "INCOMPLETE"]
    if incomplete_issues:
        return "INCOMPLETE"

    # WARN 이슈 중 작업자 FALSE_ALARM 표시 제외
    warn_issues = [i for i in raw_issues if i.get("level") == "WARN"]
    false_alarm_keys = {(fa["segment"], fa["code"]) for fa in worker_false_alarms}

    remaining_warns = [
        i for i in warn_issues
        if (i.get("segment"), i.get("code")) not in false_alarm_keys
    ]

    if remaining_warns:
        return "WARN"

    return "PASS"  # WARN이 전부 FALSE_ALARM으로 상쇄됨
```

#### 5-2. 작업자 FALSE_ALARM 피드백 조회 API

**파일**: `api/` (해당 라우터)

로컬 Flask 서버가 Auto-QC 재실행 전에 호출하여 작업자 피드백을 가져간다.

```python
@router.get("/api/cases/{case_id}/worker-false-alarms")
def get_worker_false_alarms(case_id: int, ...):
    """
    작업자가 "잘못된 경고"로 표시한 항목 목록.
    Auto-QC 클라이언트가 라우팅 판정 시 참조 (QC 기준 변경 아님).
    """
    feedbacks = get_case_feedbacks(db, case_id)
    false_alarms = []
    for fb in feedbacks:
        if fb.additional_fixes_json:
            fixes = json.loads(fb.additional_fixes_json)
            for fix in fixes:
                if fix.get("type") == "FALSE_ALARM":
                    false_alarms.append({
                        "segment": fix.get("segment"),
                        "code": fix.get("code"),
                        "worker_reason": fix.get("description", ""),
                    })
    return {"case_id": case_id, "false_alarms": false_alarms}
```

#### 5-3. 검수자 UI에 작업자 피드백 표시

**파일**: `dashboard.py` (검수자 페이지)

IN_REVIEW 케이스 상세 화면에서 Auto-QC 결과와 함께 작업자 피드백을 나란히 표시한다.

```
┌─────────────────────────────────────┐
│ Auto-QC 결과                         │
│  ⚠️ WARN: IVC 세그먼트 이름 불일치    │
│                                     │
│ 작업자 피드백                         │
│  🏷️ "잘못된 경고" — IVC: 이름 규칙   │
│     사유: "프로젝트 정의서 v2에서      │
│           IVC_trunk로 변경됨"         │
│                                     │
│ [✅ 동의 (ACCEPTED)]  [↩️ 거부 (REWORK)] │
└─────────────────────────────────────┘
```

검수자가 "동의"하면 ACCEPTED, "거부"하면 REWORK + 사유를 기재한다.
검수자의 판단은 `ReviewerQcFeedback`에 기록되어 불일치 분석에 반영된다.

#### 5-4. 불일치 분석 연동

기존 `ReviewerQcFeedback`의 `disagreement_type` 필드를 활용:

| 상황 | disagreement_type | 의미 |
|------|------------------|------|
| Auto-QC WARN → 작업자 "잘못된 경고" → 검수자 동의 | `FALSE_ALARM` | Auto-QC 기준이 과민함 |
| Auto-QC WARN → 작업자 "잘못된 경고" → 검수자 거부 | `MISSED` | 작업자가 실제 이슈를 무시함 |
| Auto-QC PASS → 검수자가 문제 발견 | `MISSED` | Auto-QC가 놓침 |

이 데이터가 축적되면 Auto-QC 기준 자체를 조정할 근거가 된다.

---

## 3. 구현 순서 (체크리스트)

```
Phase 1: 모델 변경
  □ 1-1. CaseStatus에 IN_REVIEW 추가
  □ 1-2. EventType에 AUTOQC_PASS, AUTOQC_FAIL 추가
  □ 1-3. Case.autoqc_triggered_at 필드 추가
  □ 1-4. NotificationLog 모델 추가
  □ 1-5. 마이그레이션 스크립트 작성 (migrate_v2.py)
  □ pytest 실행 → 통과 확인

Phase 2: 상태 전이 로직
  □ 2-1. VALID_TRANSITIONS 수정
  □ 2-2. save_autoqc_summary()에 라우팅 로직 추가
  □ 2-3. dashboard.py 검수자 필터 변경 (SUBMITTED → IN_REVIEW)
  □ 2-4. get_worker_tasks()에 SUBMITTED 추가
  □ 2-5. 기존 테스트 수정
  □ pytest 실행 → 전체 통과

Phase 3: 로컬 Flask 서버
  □ 3-1. autoqc-trigger/ 프로젝트 폴더 생성
  □ 3-2. app.py (Flask + APScheduler)
  □ 3-3. submit_case()에 webhook 호출 추가
  □ 3-4. config.py에 AUTOQC_TRIGGER_URL 추가
  □ pytest 실행 → 통과 (Flask 없이도 동작)

Phase 4: Google Chat 알림
  □ 4-1. notification.py 생성
  □ 4-2. config.py에 알림 설정 추가
  □ 4-3. .env.example 업데이트
  □ 4-4. services.py에 알림 호출 연결
  □ pytest 실행 → 통과 (NOTIFICATIONS_ENABLED=false)

Phase 5: False Positive 처리 (검수자 최종 확인)
  □ 5-1. autoqc-trigger에 determine_final_status() 구현 (QC 기준 불변, 라우팅만 조정)
  □ 5-2. /api/cases/{id}/worker-false-alarms 엔드포인트 추가
  □ 5-3. dashboard.py 검수자 IN_REVIEW 상세 화면에 작업자 피드백 표시
  □ 5-4. ReviewerQcFeedback에 FALSE_ALARM disagreement_type 연동
  □ pytest 실행 → 통과
```

---

## 4. 아키텍처 원칙 (위반 금지)

1. **웹 DB = 단일 진실 원천.** 모든 상태, 로그, 통계는 웹 DB에 있다. 외부 서비스는 복사본만 보관.
2. **Streamlit → FastAPI → 외부.** Streamlit이 직접 Google Chat이나 Flask를 호출하면 안 된다.
3. **Fire-and-forget.** Auto-QC 트리거와 알림 발송 실패가 제출 자체를 막으면 안 된다.
4. **Webhook + Polling 이중 구조.** Webhook 실패 시 폴링이 잡아준다.
5. **기존 테스트 보존.** 모든 Phase 후 `pytest` 통과 필수. 테스트가 깨지면 테스트를 새 로직에 맞게 수정하되, 테스트의 의도(검증 대상)는 유지.
6. **환경 변수 기반 on/off.** 알림, Auto-QC 트리거 모두 환경 변수로 비활성화 가능해야 한다.

---

## 5. 영향받는 파일 목록

| 파일 | 변경 유형 | Phase |
|------|-----------|-------|
| `models.py` | 수정 (enum + 모델 추가) | 1 |
| `services.py` | 수정 (전이 로직, save_autoqc, submit_case) | 2, 3 |
| `schemas.py` | 수정 (IN_REVIEW 반영, 필요시 스키마 추가) | 2 |
| `config.py` | 수정 (환경 변수 추가) | 3, 4 |
| `notification.py` | 신규 | 4 |
| `dashboard.py` | 수정 (검수자 필터, 상태 표시) | 2 |
| `.env.example` | 수정 | 3, 4 |
| `migrate_v2.py` | 신규 | 1 |
| `tests/` | 수정 (상태 전이 테스트 업데이트) | 2 |
| `autoqc-trigger/` | 신규 (별도 프로젝트) | 3 |
| `api/` 내 라우터 | 수정 (worker-false-alarms 엔드포인트) | 5 |
| `dashboard.py` | 수정 (검수자 IN_REVIEW 상세에 작업자 피드백 표시) | 5 |
| `autoqc-trigger/autoqc_runner.py` | 수정 (determine_final_status 추가) | 5 |

---

## 6. 테스트 작성 가이드

### Phase 2 신규 테스트

```python
def test_autoqc_pass_routes_to_in_review(db, admin, worker, case_in_submitted):
    """Auto-QC PASS 결과 저장 시 IN_REVIEW로 전이되는지 확인."""
    save_autoqc_summary(db, AutoQcSummaryCreateRequest(
        case_id=case_in_submitted.id,
        status="PASS",
    ), admin)
    db.refresh(case_in_submitted)
    assert case_in_submitted.status == CaseStatus.IN_REVIEW


def test_autoqc_warn_routes_to_rework(db, admin, worker, case_in_submitted):
    """Auto-QC WARN 결과 저장 시 REWORK로 전이되는지 확인."""
    save_autoqc_summary(db, AutoQcSummaryCreateRequest(
        case_id=case_in_submitted.id,
        status="WARN",
        issues=[{"code": "SEGMENT_NAME_MISMATCH", "segment": "IVC"}],
    ), admin)
    db.refresh(case_in_submitted)
    assert case_in_submitted.status == CaseStatus.REWORK


def test_submitted_cannot_be_directly_accepted(db, admin, case_in_submitted):
    """SUBMITTED에서 바로 ACCEPTED 전이 불가 (Auto-QC 거쳐야 함)."""
    with pytest.raises(ValidationError):
        process_event(db, EventCreateRequest(
            case_id=case_in_submitted.id,
            event_type=EventType.ACCEPTED,
            idempotency_key="...",
        ), admin)


def test_in_review_can_be_accepted(db, admin, case_in_review):
    """IN_REVIEW에서 ACCEPTED 전이 가능."""
    result = process_event(db, EventCreateRequest(
        case_id=case_in_review.id,
        event_type=EventType.ACCEPTED,
        idempotency_key="...",
    ), admin)
    assert result.case_status == CaseStatus.ACCEPTED


def test_autoqc_on_non_submitted_case_no_routing(db, admin, case_in_progress):
    """IN_PROGRESS 상태에서 Auto-QC 결과 저장 시 상태 변경 없음."""
    save_autoqc_summary(db, AutoQcSummaryCreateRequest(
        case_id=case_in_progress.id,
        status="PASS",
    ), admin)
    db.refresh(case_in_progress)
    assert case_in_progress.status == CaseStatus.IN_PROGRESS  # 변경 없음
```

### Phase 4 알림 테스트

```python
def test_notification_disabled_no_call(db, monkeypatch):
    """NOTIFICATIONS_ENABLED=false면 HTTP 호출 안 함."""
    monkeypatch.setattr("notification.NOTIFICATIONS_ENABLED", False)
    result = send_google_chat(db, "https://...", "test", event_type="TEST")
    assert result is False
    assert db.query(NotificationLog).count() == 0
```

---

## 7. n8n 주간 리포트 (향후)

이 업그레이드와 별개로, n8n은 **주간 리포트에만** 사용한다.

```
금요일 17:00 (n8n Schedule trigger)
  → GET /api/weekly-report (FastAPI)
  → 집계 (재작업 사유, 작업자별 실패율, 1차 통과율)
  → Google Sheets (읽기 전용 복사본)
  → Google Chat 팀 요약
  → Gmail 매니저 보고
```

이 엔드포인트(`/api/weekly-report`)는 이번 업그레이드 범위에 포함하지 않는다. Phase 1~5 완료 후 별도 작업.

---

## 8. 외부 작업자 지원 (향후)

Phase 1~5는 사무실 내부 환경(NAS + Flask 서버) 기준이다. 외부 프리랜서 작업자가 합류하면 아래를 추가 구현한다.

### 사무실 vs 외부 작업자 비교

| | 사무실 작업자 | 외부 작업자 |
|---|---|---|
| 데이터 위치 | NAS (공유 네트워크) | 로컬 PC (USB/VPN으로 전달받음) |
| Auto-QC 실행 | Flask 서버가 NAS에서 자동 | 작업자 PC에서 CLI로 직접 |
| 트리거 방식 | 웹 제출 → webhook → Flask | 작업자가 CLI 실행 → API 업로드 |
| QC 결과 업로드 | Flask → `POST /api/autoqc-summary` | CLI → `POST /api/autoqc-summary` |
| 알림 수신 | Google Chat (사내) | Google Chat / 이메일 |

### 핵심: 서버 코드 변경 없음

서버 입장에서는 어디서 실행했든 같은 `POST /api/autoqc-summary` API로 동일한 JSON이 들어온다. 사무실/외부를 구분할 필요가 없다.

### 외부 작업자 흐름

```
외부 작업자: 로컬 PC에서 작업 완료
    │
    ▼
로컬 Auto-QC CLI 실행 → 결과를 웹 서버 API로 업로드
    │
    ├─ PASS → IN_REVIEW → 검수자에게 알림
    │
    └─ WARN/INCOMPLETE → REWORK → 작업자에게 Google Chat/이메일 알림
                                      │
                                작업자가 수정
                                      │
                                로컬 Auto-QC CLI 재실행 → 결과 API 업로드
                                      │
                                      ├─ PASS → IN_REVIEW → 검수자에게 알림
                                      └─ WARN → REWORK → 반복
```

### 추가 구현 항목

1. **Auto-QC CLI 배포 패키지**: `autoqc_cli.py` + 의존성을 zip/installer로 제공
   ```bash
   # 외부 작업자 PC에서
   python autoqc_cli.py --case-id 123 --data-path ./CASE_123 --server https://qc.example.com
   ```
2. **외부 접속 인프라**: Cloudflare Tunnel 또는 Tailscale (비용 0원)
3. **이메일 알림 추가**: Google Chat 외에 이메일 채널 (외부 작업자용)
4. **데이터 전달 프로세스**: 보안 규정에 따라 USB/VPN/암호화 클라우드 중 결정

이 항목들은 Phase 1~5 완료 후, 외부 작업자 합류 시점에 별도 Phase로 진행한다.