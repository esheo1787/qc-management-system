# Step A 검증 방법

## 1. 서버 실행

```bash
cd c:\Users\Lenovo\Desktop\Projects\qc-management-system
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 2. Health Check 확인

```bash
# Root endpoint
curl http://localhost:8000/
# 예상 응답: {"status":"ok","service":"qc-management-system"}

# Health endpoint
curl http://localhost:8000/health
# 예상 응답: {"status":"healthy"}
```

## 3. Swagger UI 확인

브라우저에서 접속:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## 4. OpenAPI 스키마에서 endpoint 존재 확인

```bash
curl http://localhost:8000/openapi.json | python -m json.tool > openapi_snapshot.json
```

### 확인해야 할 주요 path:
- `/` (root)
- `/health`
- `/api/auth/me`
- `/api/admin/cases/bulk_register`
- `/api/admin/assign`
- `/api/admin/cases`
- `/api/admin/cases/{case_id}`
- `/api/admin/cases/{case_id}/metrics`
- `/api/admin/events`
- `/api/admin/users`
- `/api/admin/review_notes`
- `/api/me/tasks`
- `/api/events`
- `/api/worklogs`
- `/api/submit`
- `/api/timeoff`
- `/api/timeoff/{timeoff_id}`
- `/api/timeoff/me`
- `/api/admin/timeoff`
- `/api/admin/timeoff/{user_id}`
- `/api/holidays`
- `/api/admin/holidays`
- `/api/admin/holidays/{holiday_date}`
- `/api/admin/capacity`
- `/api/preqc_summary`
- `/api/preqc_summary/{case_id}`
- `/api/autoqc_summary`
- `/api/autoqc_summary/{case_id}`
- `/api/admin/qc_disagreements`
- `/api/admin/qc_disagreements/stats`
- `/api/admin/tags/apply`
- `/api/admin/tags/remove`
- `/api/admin/tags`
- `/api/admin/tags/{tag_text}/cases`
- `/api/admin/definitions`
- `/api/admin/definitions/{version_name}`
- `/api/admin/projects/definition`
- `/api/admin/projects/definitions`
- `/api/admin/projects/{project_id}/definitions`
- `/api/admin/cohort/summary`

## 5. 인증 테스트

```bash
# 인증 없이 접근 (401 예상)
curl http://localhost:8000/api/auth/me
# 예상 응답: {"detail":"Invalid or inactive API key"}

# 유효한 API Key로 접근 (seed 데이터 기준)
curl -H "X-API-Key: data_admin1" http://localhost:8000/api/auth/me
# 예상 응답: {"id":1,"username":"admin1","role":"ADMIN","is_active":true}

# Worker가 Admin endpoint 접근 (403 예상)
curl -H "X-API-Key: data_worker1" http://localhost:8000/api/admin/users
# 예상 응답: {"detail":"Admin access required"}
```

## 6. 주요 endpoint 스모크 테스트

```bash
# 케이스 목록 조회
curl -H "X-API-Key: data_admin1" "http://localhost:8000/api/admin/cases?limit=5"

# 사용자 목록 조회
curl -H "X-API-Key: data_admin1" http://localhost:8000/api/admin/users

# 공휴일 목록 조회
curl -H "X-API-Key: data_admin1" http://localhost:8000/api/holidays

# 태그 목록 조회
curl -H "X-API-Key: data_admin1" http://localhost:8000/api/admin/tags
```

## 7. Step A 완료 체크리스트

- [x] API Contract 문서 작성 완료 (`docs/API_CONTRACT.md`)
- [x] `/health` endpoint 존재 확인 (기존에 이미 있음)
- [x] 검증 방법 문서 작성 (`docs/VERIFICATION.md`)
- [ ] 서버 실행 및 health check 확인 (수동 검증 필요)
- [ ] Swagger UI에서 모든 endpoint 존재 확인 (수동 검증 필요)

## 8. 다음 단계 (Step B) 준비 사항

Step B에서는 다음을 수행합니다:
1. 모든 endpoint에 tags, summary, description 추가
2. response_model 명시 확인
3. Pydantic schema에 examples 추가
4. **기존 response JSON 구조는 절대 변경하지 않음**
