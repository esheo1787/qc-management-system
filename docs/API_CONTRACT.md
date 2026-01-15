# API Contract Document (v1.0.0)

> **목적**: 현재 운영 중인 API의 계약(Contract)을 문서화하여 리팩토링 시 기존 동작이 변경되지 않았음을 보장하기 위한 기준 문서

> **작성일**: 2026-01-15

> **주의사항**: 이 문서에 기재된 모든 항목(endpoint, request/response 구조, status code)은 리팩토링 후에도 동일하게 유지되어야 함

---

## 1. 공통 사항

### 1.1 Base URL
- 개발: `http://localhost:8000`

### 1.2 인증 방식
- **Header**: `X-API-Key`
- **인증 실패 시**: `401 Unauthorized`
- **권한 부족 시**: `403 Forbidden`

### 1.3 공통 에러 응답

| Status Code | 의미 | 사용 상황 |
|-------------|------|----------|
| 400 | Bad Request | ValidationError |
| 401 | Unauthorized | 잘못된 API Key |
| 403 | Forbidden | 권한 부족 (ADMIN 필요 등) |
| 404 | Not Found | 리소스 없음 |
| 409 | Conflict | 중복/충돌 |
| 422 | Unprocessable Entity | Pydantic 검증 실패 |
| 429 | Too Many Requests | WIP Limit 초과 |
| 500 | Internal Server Error | 서버 내부 오류 |

---

## 2. Health Check Endpoints

### 2.1 GET /
- **인증**: 불필요
- **설명**: Root health check
- **Response**: `200 OK`
```json
{
  "status": "ok",
  "service": "qc-management-system"
}
```

### 2.2 GET /health
- **인증**: 불필요
- **설명**: Health check endpoint
- **Response**: `200 OK`
```json
{
  "status": "healthy"
}
```

---

## 3. Auth Endpoints

### 3.1 GET /api/auth/me
- **인증**: 필요 (X-API-Key)
- **설명**: 현재 로그인된 사용자 정보 조회
- **Response Model**: `AuthMeResponse`
- **Response**: `200 OK`
```json
{
  "id": 1,
  "username": "admin1",
  "role": "ADMIN",
  "is_active": true
}
```

---

## 4. Admin: Case Management Endpoints

### 4.1 POST /api/admin/cases/bulk_register
- **인증**: ADMIN 필요
- **설명**: 다수 케이스 일괄 등록
- **Request Model**: `BulkRegisterRequest`
- **Request Body**:
```json
{
  "items": [
    {
      "case_uid": "CASE-001",
      "original_name": "폴더명",
      "display_name": "표시명",
      "nas_path": "/path/to/folder",
      "hospital": "병원명",
      "slice_thickness_mm": 1.0,
      "project_name": "프로젝트명",
      "part_name": "부위명",
      "difficulty": "NORMAL",
      "metadata_json": null,
      "preqc": null,
      "wwl": null,
      "memo": null,
      "tags": null
    }
  ]
}
```
- **Response Model**: `BulkRegisterResponse`
- **Response**: `200 OK`
```json
{
  "registered_count": 1,
  "skipped_uids": []
}
```

### 4.2 POST /api/admin/assign
- **인증**: ADMIN 필요
- **설명**: 케이스를 작업자에게 할당
- **Request Model**: `AssignRequest`
- **Request Body**:
```json
{
  "case_id": 1,
  "user_id": 2
}
```
- **Response Model**: `AssignResponse`
- **Response**: `200 OK`
```json
{
  "case_id": 1,
  "assigned_user_id": 2,
  "status": "TODO"
}
```

### 4.3 GET /api/admin/cases
- **인증**: ADMIN 필요
- **설명**: 케이스 목록 조회 (필터 지원)
- **Query Parameters**:
  - `status` (optional): CaseStatus enum
  - `project_id` (optional): int
  - `assigned_user_id` (optional): int
  - `limit` (default: 100, min: 1, max: 500): int
  - `offset` (default: 0, min: 0): int
- **Response Model**: `CaseListResponse`
- **Response**: `200 OK`
```json
{
  "cases": [
    {
      "id": 1,
      "case_uid": "CASE-001",
      "display_name": "표시명",
      "original_name": "폴더명",
      "hospital": "병원명",
      "slice_thickness_mm": 1.0,
      "project_name": "프로젝트명",
      "part_name": "부위명",
      "difficulty": "NORMAL",
      "status": "TODO",
      "revision": 1,
      "assigned_user_id": null,
      "assigned_username": null,
      "created_at": "2026-01-15T10:00:00+09:00"
    }
  ],
  "total_count": 1
}
```

### 4.4 GET /api/admin/cases/{case_id}
- **인증**: ADMIN 필요
- **설명**: 케이스 상세 조회
- **Path Parameters**:
  - `case_id`: int
- **Response Model**: `CaseDetailResponse`
- **Response**: `200 OK`
```json
{
  "id": 1,
  "case_uid": "CASE-001",
  "display_name": "표시명",
  "original_name": "폴더명",
  "nas_path": "/path/to/folder",
  "hospital": "병원명",
  "slice_thickness_mm": 1.0,
  "project_id": 1,
  "project_name": "프로젝트명",
  "part_id": 1,
  "part_name": "부위명",
  "difficulty": "NORMAL",
  "status": "TODO",
  "revision": 1,
  "assigned_user_id": null,
  "assigned_username": null,
  "created_at": "2026-01-15T10:00:00+09:00",
  "started_at": null,
  "submitted_at": null,
  "accepted_at": null,
  "preqc_summary": null,
  "autoqc_summary": null,
  "events": [],
  "review_notes": [],
  "tags": []
}
```
- **Error**: `404 Not Found` (case not found)

### 4.5 GET /api/admin/cases/{case_id}/metrics
- **인증**: ADMIN 필요
- **설명**: 케이스 상세 + 작업 시간 메트릭 조회
- **Path Parameters**:
  - `case_id`: int
- **Response Model**: `CaseDetailWithMetricsResponse`
- **Response**: `200 OK`
```json
{
  "id": 1,
  "case_uid": "CASE-001",
  "display_name": "표시명",
  "original_name": "폴더명",
  "nas_path": "/path/to/folder",
  "hospital": "병원명",
  "slice_thickness_mm": 1.0,
  "project_id": 1,
  "project_name": "프로젝트명",
  "part_id": 1,
  "part_name": "부위명",
  "difficulty": "NORMAL",
  "status": "TODO",
  "revision": 1,
  "assigned_user_id": null,
  "assigned_username": null,
  "created_at": "2026-01-15T10:00:00+09:00",
  "started_at": null,
  "submitted_at": null,
  "accepted_at": null,
  "preqc_summary": null,
  "autoqc_summary": null,
  "events": [],
  "review_notes": [],
  "tags": [],
  "worklogs": [],
  "total_work_seconds": 0,
  "session_count": 0
}
```

### 4.6 GET /api/admin/events
- **인증**: ADMIN 필요
- **설명**: 최근 이벤트 목록 조회
- **Query Parameters**:
  - `limit` (default: 50, min: 1, max: 200): int
- **Response Model**: `list[EventListItem]`
- **Response**: `200 OK`
```json
[
  {
    "id": 1,
    "event_type": "CREATED",
    "user_id": 1,
    "username": "admin1",
    "case_id": 1,
    "case_uid": "CASE-001",
    "event_code": "케이스 등록",
    "created_at": "2026-01-15T10:00:00+09:00"
  }
]
```

### 4.7 GET /api/admin/users
- **인증**: ADMIN 필요
- **설명**: 전체 사용자 목록 조회
- **Response Model**: `UserListResponse`
- **Response**: `200 OK`
```json
{
  "users": [
    {
      "id": 1,
      "username": "admin1",
      "role": "ADMIN",
      "is_active": true,
      "created_at": "2026-01-15T10:00:00+09:00"
    }
  ]
}
```

### 4.8 POST /api/admin/review_notes
- **인증**: ADMIN 필요
- **설명**: 케이스에 검수 노트 추가
- **Request Model**: `ReviewNoteCreateRequest`
- **Request Body**:
```json
{
  "case_id": 1,
  "note_text": "검수 내용"
}
```
- **Response Model**: `ReviewNoteResponse`
- **Response**: `200 OK`
```json
{
  "id": 1,
  "case_id": 1,
  "reviewer_id": 1,
  "reviewer_username": "admin1",
  "note_text": "검수 내용",
  "created_at": "2026-01-15T10:00:00+09:00"
}
```

---

## 5. Worker Endpoints

### 5.1 GET /api/me/tasks
- **인증**: WORKER 필요
- **설명**: 현재 작업자에게 할당된 작업 목록
- **Response Model**: `CaseListResponse`
- **Response**: `200 OK`
```json
{
  "cases": [...],
  "total_count": 0
}
```
- **Error**: `403 Forbidden` (ADMIN이 접근 시)

---

## 6. Event Endpoints

### 6.1 POST /api/events
- **인증**: 필요
- **설명**: 상태 전이 이벤트 생성
- **Request Model**: `EventCreateRequest`
- **Request Body**:
```json
{
  "case_id": 1,
  "event_type": "STARTED",
  "idempotency_key": "unique-key-123"
}
```
- **Response Model**: `EventResponse`
- **Response**: `200 OK`
```json
{
  "id": 1,
  "case_id": 1,
  "event_type": "STARTED",
  "user_id": 1,
  "status_before": "TODO",
  "status_after": "IN_PROGRESS",
  "created_at": "2026-01-15T10:00:00+09:00"
}
```

---

## 7. WorkLog Endpoints

### 7.1 POST /api/worklogs
- **인증**: 필요
- **설명**: 작업 로그 생성 (START/PAUSE/RESUME)
- **Request Model**: `WorkLogCreateRequest`
- **Request Body**:
```json
{
  "case_id": 1,
  "action": "START"
}
```
- **Response Model**: `WorkLogResponse`
- **Response**: `200 OK`
```json
{
  "id": 1,
  "case_id": 1,
  "user_id": 1,
  "action": "START",
  "work_seconds": 0,
  "started_at": "2026-01-15T10:00:00+09:00",
  "ended_at": null
}
```

### 7.2 POST /api/submit
- **인증**: 필요
- **설명**: 케이스 제출 (WorkLog SUBMIT + Event SUBMITTED 원자적 처리)
- **Request Model**: `SubmitRequest`
- **Request Body**:
```json
{
  "case_id": 1,
  "idempotency_key": "submit-unique-key"
}
```
- **Response Model**: `SubmitResponse`
- **Response**: `200 OK`
```json
{
  "case_id": 1,
  "status": "SUBMITTED",
  "total_work_seconds": 3600,
  "session_count": 1,
  "submitted_at": "2026-01-15T11:00:00+09:00"
}
```

---

## 8. TimeOff Endpoints

### 8.1 POST /api/timeoff
- **인증**: 필요
- **설명**: 휴가/휴무 등록
- **Request Model**: `TimeOffCreateRequest`
- **Request Body**:
```json
{
  "user_id": 1,
  "date": "2026-01-20",
  "hours": 8.0,
  "reason": "연차"
}
```
- **Response Model**: `TimeOffResponse`
- **Response**: `200 OK`

### 8.2 DELETE /api/timeoff/{timeoff_id}
- **인증**: 필요 (본인 것만 삭제 가능)
- **Path Parameters**:
  - `timeoff_id`: int
- **Response**: `200 OK`
```json
{
  "message": "Time-off deleted"
}
```

### 8.3 GET /api/timeoff/me
- **인증**: 필요
- **설명**: 내 휴무 목록 조회
- **Query Parameters**:
  - `start_date` (optional): date
  - `end_date` (optional): date
- **Response Model**: `TimeOffListResponse`
- **Response**: `200 OK`

### 8.4 GET /api/admin/timeoff
- **인증**: ADMIN 필요
- **설명**: 전체 휴무 목록 조회
- **Query Parameters**:
  - `start_date` (optional): date
  - `end_date` (optional): date
- **Response Model**: `TimeOffListResponse`
- **Response**: `200 OK`

### 8.5 GET /api/admin/timeoff/{user_id}
- **인증**: ADMIN 필요
- **설명**: 특정 사용자 휴무 목록 조회
- **Path Parameters**:
  - `user_id`: int
- **Query Parameters**:
  - `start_date` (optional): date
  - `end_date` (optional): date
- **Response Model**: `TimeOffListResponse`
- **Response**: `200 OK`

---

## 9. Holiday Endpoints

### 9.1 GET /api/holidays
- **인증**: 필요
- **설명**: 공휴일 목록 조회
- **Response Model**: `HolidayListResponse`
- **Response**: `200 OK`
```json
{
  "holidays": ["2026-01-01", "2026-02-16", ...],
  "timezone": "Asia/Seoul"
}
```

### 9.2 PUT /api/admin/holidays
- **인증**: ADMIN 필요
- **설명**: 공휴일 목록 전체 업데이트
- **Request Model**: `HolidayUpdateRequest`
- **Request Body**:
```json
{
  "holidays": ["2026-01-01", "2026-02-16"]
}
```
- **Response Model**: `HolidayListResponse`
- **Response**: `200 OK`

### 9.3 POST /api/admin/holidays/{holiday_date}
- **인증**: ADMIN 필요
- **설명**: 단일 공휴일 추가
- **Path Parameters**:
  - `holiday_date`: date (YYYY-MM-DD)
- **Response Model**: `HolidayListResponse`
- **Response**: `200 OK`

### 9.4 DELETE /api/admin/holidays/{holiday_date}
- **인증**: ADMIN 필요
- **설명**: 단일 공휴일 삭제
- **Path Parameters**:
  - `holiday_date`: date (YYYY-MM-DD)
- **Response Model**: `HolidayListResponse`
- **Response**: `200 OK`

---

## 10. Capacity Metrics Endpoints

### 10.1 GET /api/admin/capacity
- **인증**: ADMIN 필요
- **설명**: 팀 가용량 메트릭 조회
- **Query Parameters**:
  - `start_date` (required): date
  - `end_date` (required): date
- **Response Model**: `TeamCapacityResponse`
- **Response**: `200 OK`
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "total_workdays": 22,
  "total_available_hours": 176.0,
  "total_actual_hours": 100.0,
  "utilization_rate": 0.57,
  "by_user": [...]
}
```

---

## 11. Pre-QC Summary Endpoints

### 11.1 POST /api/preqc_summary
- **인증**: 필요
- **설명**: Pre-QC 요약 저장 (로컬 클라이언트에서 업로드)
- **Request Model**: `PreQcSummaryCreateRequest`
- **Response Model**: `PreQcSummaryResponse`
- **Response**: `200 OK`

### 11.2 GET /api/preqc_summary/{case_id}
- **인증**: 필요
- **설명**: Pre-QC 요약 조회
- **Path Parameters**:
  - `case_id`: int
- **Response Model**: `PreQcSummaryResponse`
- **Response**: `200 OK`
- **Error**: `404 Not Found`

---

## 12. Auto-QC Summary Endpoints

### 12.1 POST /api/autoqc_summary
- **인증**: 필요
- **설명**: Auto-QC 요약 저장 (로컬 클라이언트에서 업로드)
- **Request Model**: `AutoQcSummaryCreateRequest`
- **Response Model**: `AutoQcSummaryResponse`
- **Response**: `200 OK`

### 12.2 GET /api/autoqc_summary/{case_id}
- **인증**: 필요
- **설명**: Auto-QC 요약 조회
- **Path Parameters**:
  - `case_id`: int
- **Response Model**: `AutoQcSummaryResponse`
- **Response**: `200 OK`
- **Error**: `404 Not Found`

---

## 13. QC Disagreement Endpoints

### 13.1 GET /api/admin/qc_disagreements
- **인증**: ADMIN 필요
- **설명**: QC 불일치 목록 조회
- **Query Parameters**:
  - `part_name` (optional): str
  - `hospital` (optional): str
  - `difficulty` (optional): str
  - `start_date` (optional): date
  - `end_date` (optional): date
- **Response Model**: `QcDisagreementListResponse`
- **Response**: `200 OK`

### 13.2 GET /api/admin/qc_disagreements/stats
- **인증**: ADMIN 필요
- **설명**: QC 불일치 통계 조회
- **Query Parameters**:
  - `start_date` (optional): date
  - `end_date` (optional): date
- **Response Model**: `QcDisagreementStats`
- **Response**: `200 OK`

---

## 14. Tag Endpoints

### 14.1 POST /api/admin/tags/apply
- **인증**: ADMIN 필요
- **설명**: 케이스들에 태그 적용
- **Request Model**: `ApplyTagsRequest`
- **Request Body**:
```json
{
  "case_uids": ["CASE-001", "CASE-002"],
  "tag_text": "연구용"
}
```
- **Response Model**: `ApplyTagsResponse`
- **Response**: `200 OK`
```json
{
  "applied_count": 2,
  "skipped_uids": []
}
```

### 14.2 POST /api/admin/tags/remove
- **인증**: ADMIN 필요
- **설명**: 케이스들에서 태그 제거
- **Request Model**: `RemoveTagRequest`
- **Response Model**: `RemoveTagResponse`
- **Response**: `200 OK`

### 14.3 GET /api/admin/tags
- **인증**: ADMIN 필요
- **설명**: 전체 태그 목록 조회
- **Response Model**: `TagListResponse`
- **Response**: `200 OK`
```json
{
  "tags": [
    {
      "tag_text": "연구용",
      "case_count": 10
    }
  ]
}
```

### 14.4 GET /api/admin/tags/{tag_text}/cases
- **인증**: ADMIN 필요
- **설명**: 특정 태그가 적용된 케이스 목록
- **Path Parameters**:
  - `tag_text`: str
- **Response Model**: `CasesByTagResponse`
- **Response**: `200 OK`

---

## 15. Definition Snapshot Endpoints

### 15.1 POST /api/admin/definitions
- **인증**: ADMIN 필요
- **설명**: 정의 스냅샷 생성 (버전 고정)
- **Request Model**: `DefinitionSnapshotCreateRequest`
- **Response Model**: `DefinitionSnapshotResponse`
- **Response**: `200 OK`

### 15.2 GET /api/admin/definitions
- **인증**: ADMIN 필요
- **설명**: 정의 스냅샷 목록 조회
- **Response Model**: `DefinitionSnapshotListResponse`
- **Response**: `200 OK`

### 15.3 GET /api/admin/definitions/{version_name}
- **인증**: ADMIN 필요
- **설명**: 특정 버전 정의 스냅샷 조회
- **Path Parameters**:
  - `version_name`: str
- **Response Model**: `DefinitionSnapshotResponse`
- **Response**: `200 OK`
- **Error**: `404 Not Found`

---

## 16. Project-Definition Link Endpoints

### 16.1 POST /api/admin/projects/definition
- **인증**: ADMIN 필요
- **설명**: 프로젝트-정의 연결
- **Request Model**: `ProjectDefinitionLinkRequest`
- **Response Model**: `ProjectDefinitionLinkResponse`
- **Response**: `200 OK`

### 16.2 GET /api/admin/projects/definitions
- **인증**: ADMIN 필요
- **설명**: 전체 프로젝트-정의 연결 목록
- **Response Model**: `ProjectDefinitionListResponse`
- **Response**: `200 OK`

### 16.3 GET /api/admin/projects/{project_id}/definitions
- **인증**: ADMIN 필요
- **설명**: 특정 프로젝트의 정의 연결 목록
- **Path Parameters**:
  - `project_id`: int
- **Response Model**: `ProjectDefinitionListResponse`
- **Response**: `200 OK`

---

## 17. Cohort Summary Endpoint

### 17.1 POST /api/admin/cohort/summary
- **인증**: ADMIN 필요
- **설명**: 코호트 필터 기반 요약 메트릭 조회
- **Request Model**: `CohortFilter`
- **Request Body**:
```json
{
  "tag_text": "연구용",
  "project_id": null,
  "definition_version": null,
  "status": null,
  "start_date": null,
  "end_date": null
}
```
- **Response Model**: `CohortSummary`
- **Response**: `200 OK`

---

## 18. API Endpoint 요약 테이블

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | / | - | Root health check |
| GET | /health | - | Health check |
| GET | /api/auth/me | User | 현재 사용자 정보 |
| POST | /api/admin/cases/bulk_register | Admin | 케이스 일괄 등록 |
| POST | /api/admin/assign | Admin | 케이스 할당 |
| GET | /api/admin/cases | Admin | 케이스 목록 |
| GET | /api/admin/cases/{case_id} | Admin | 케이스 상세 |
| GET | /api/admin/cases/{case_id}/metrics | Admin | 케이스 상세 + 메트릭 |
| GET | /api/admin/events | Admin | 최근 이벤트 |
| GET | /api/admin/users | Admin | 사용자 목록 |
| POST | /api/admin/review_notes | Admin | 검수 노트 추가 |
| GET | /api/me/tasks | Worker | 내 작업 목록 |
| POST | /api/events | User | 이벤트 생성 |
| POST | /api/worklogs | User | 작업 로그 생성 |
| POST | /api/submit | User | 케이스 제출 |
| POST | /api/timeoff | User | 휴무 등록 |
| DELETE | /api/timeoff/{timeoff_id} | User | 휴무 삭제 |
| GET | /api/timeoff/me | User | 내 휴무 목록 |
| GET | /api/admin/timeoff | Admin | 전체 휴무 목록 |
| GET | /api/admin/timeoff/{user_id} | Admin | 특정 사용자 휴무 |
| GET | /api/holidays | User | 공휴일 목록 |
| PUT | /api/admin/holidays | Admin | 공휴일 업데이트 |
| POST | /api/admin/holidays/{holiday_date} | Admin | 공휴일 추가 |
| DELETE | /api/admin/holidays/{holiday_date} | Admin | 공휴일 삭제 |
| GET | /api/admin/capacity | Admin | 팀 가용량 메트릭 |
| POST | /api/preqc_summary | User | Pre-QC 요약 저장 |
| GET | /api/preqc_summary/{case_id} | User | Pre-QC 요약 조회 |
| POST | /api/autoqc_summary | User | Auto-QC 요약 저장 |
| GET | /api/autoqc_summary/{case_id} | User | Auto-QC 요약 조회 |
| GET | /api/admin/qc_disagreements | Admin | QC 불일치 목록 |
| GET | /api/admin/qc_disagreements/stats | Admin | QC 불일치 통계 |
| POST | /api/admin/tags/apply | Admin | 태그 적용 |
| POST | /api/admin/tags/remove | Admin | 태그 제거 |
| GET | /api/admin/tags | Admin | 태그 목록 |
| GET | /api/admin/tags/{tag_text}/cases | Admin | 태그별 케이스 |
| POST | /api/admin/definitions | Admin | 정의 스냅샷 생성 |
| GET | /api/admin/definitions | Admin | 정의 스냅샷 목록 |
| GET | /api/admin/definitions/{version_name} | Admin | 정의 스냅샷 조회 |
| POST | /api/admin/projects/definition | Admin | 프로젝트-정의 연결 |
| GET | /api/admin/projects/definitions | Admin | 프로젝트-정의 목록 |
| GET | /api/admin/projects/{project_id}/definitions | Admin | 프로젝트별 정의 |
| POST | /api/admin/cohort/summary | Admin | 코호트 요약 |

---

## 19. Enum 값 목록

### 19.1 UserRole
- `ADMIN`
- `WORKER`

### 19.2 CaseStatus
- `TODO`
- `IN_PROGRESS`
- `PAUSED`
- `SUBMITTED`
- `ACCEPTED`
- `REWORK`

### 19.3 EventType
- `CREATED`
- `ASSIGNED`
- `STARTED`
- `PAUSED`
- `RESUMED`
- `SUBMITTED`
- `ACCEPTED`
- `REWORK`
- `REWORK_STARTED`
- `EDIT`
- `CANCEL`
- `FEEDBACK_CREATED`
- `FEEDBACK_UPDATED`
- `FEEDBACK_DELETED`
- `FEEDBACK_SUBMIT`

### 19.4 ActionType (WorkLog)
- `START`
- `PAUSE`
- `RESUME`
- `SUBMIT`
- `REWORK_START`

### 19.5 Difficulty
- `EASY`
- `NORMAL`
- `HARD`
- `VERY_HARD`

---

## 20. 검증 체크리스트

리팩토링 후 아래 항목이 모두 동일해야 함:

- [ ] 모든 endpoint path가 동일
- [ ] 모든 HTTP method가 동일
- [ ] 모든 query/path parameter 이름과 타입이 동일
- [ ] 모든 request body JSON key가 동일
- [ ] 모든 response body JSON key가 동일
- [ ] 모든 status code가 동일
- [ ] 인증 방식 (X-API-Key header)이 동일
- [ ] 에러 응답 형식이 동일 (`{"detail": "..."}"`)
