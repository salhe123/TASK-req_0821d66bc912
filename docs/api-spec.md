# Model Governance & Evaluation Workbench — API Specification

Base URL: `/api`
Authentication: `Authorization: Bearer <session-token>` header OR `mgew_session` cookie (httpOnly, samesite=strict).
CSRF: all state-changing requests require `X-CSRF-Token: <value>` header matching the session's CSRF token. Missing/invalid → 403 `csrf_missing`.
Session tokens carry an embedded nonce bound to the session's CSRF token; skew > 60 s → 401 `token_skew_exceeded`; tokens past max age → 401 `token_expired`.

---

## 1. Authentication (`/api/auth`)

### POST `/auth/login`
Request: `{ "username": "...", "password": "..." }` (min 1 char each)
Response 200:
```json
{
  "user_id": "uuid", "username": "...", "roles": ["Administrator"],
  "csrf_token": "...", "session_token": "...", "expires_at": "ISO8601"
}
```
Sets `mgew_session` cookie. Errors: 401 `invalid_credentials`, 423 `account_locked`.

### POST `/auth/logout`
Revokes current session, deletes cookie. Returns `{ "ok": true }`.

### POST `/auth/change-password`
Request: `{ "current_password": "...", "new_password": "..." }` (new ≥ 12 chars)
Errors: 400 `invalid_current_password`.

### GET `/auth/me`
Returns session user profile including `csrf_token` (for page-reload rehydration):
```json
{
  "user_id": "uuid", "username": "...", "display_name": "...",
  "roles": ["..."], "permissions": [{"resource":"...","action":"..."}],
  "field_view_allowlist": ["*"], "timezone": "UTC", "csrf_token": "..."
}
```

### POST `/auth/me/timezone`
Request: `{ "timezone": "America/Los_Angeles" }` (IANA name)
Errors: 400 `invalid_timezone`. Audited as `USER_TIMEZONE_UPDATE`.

---

## 2. Evaluation Cycles (`/api/cycles`)

### GET `/cycles`
**Permission:** `cycle:participate`, `cycle:manage`, or `cycle:review` (others get empty list).
Response: `{ "items": [CycleSummary] }`

### POST `/cycles` — *cycle:manage*
Request:
```json
{
  "name": "Q2 2026", "starts_on": "2026-04-01", "ends_on": "2026-06-30",
  "deadline_at": "2026-06-30T17:00:00Z", "timezone": "UTC",
  "makeup_enabled": false, "makeup_business_days": 5,
  "holidays": [], "template_version_id": "uuid",
  "rule_set_version_id": "uuid|null"
}
```
Response 201: `CycleSummary`.

### GET `/cycles/{cycle_id}/assignments`
**Scoping:** `cycle:manage` or `cycle:review` sees all assignments; others see only own rows (evaluator or reviewer).
Response: `{ "items": [AssignmentSummary] }`

### POST `/cycles/{cycle_id}/assignments` — *cycle:manage*
Request: `{ "evaluator_user_id": "uuid", "reviewer_user_id": "uuid|null" }`
Response 201: `AssignmentSummary`.

### GET `/cycles/digest`
Per-user daily digest gated at 9:00 AM in user's timezone preference.
Response: `{ "show": true, "as_of_local": "ISO8601", "items": [DigestItem] }`

---

## 3. Assignments (`/api/assignments`)

### GET `/assignments/{id}` — *object-level: owner, assigned reviewer, or admin*
Response: `AssignmentSummary` (id, cycle_id, evaluator_user_id, reviewer_user_id, state, submitted_at, late_flag, returned_reason, archived_at).

### GET `/assignments/{id}/form` — *object-level: owner, assigned reviewer, or admin*
Response: `{ "assignment": AssignmentSummary, "cycle_name": "...", "deadline_at": "...", "template_version_id": "uuid", "items": [...], "draft_values": {...} }`

### POST `/assignments/{id}/save` — *evaluator owner only*
Request: `{ "values": { "q1": 8, "q2": 9 } }`
Transitions NOT_STARTED → IN_PROGRESS or RETURNED_FOR_REVISION → IN_PROGRESS.

### POST `/assignments/{id}/submit` — *evaluator owner only*
Request: `{ "values": { "q1": 8, "q2": 9 } }`
Transitions to SUBMITTED. Writes submission + calculation_trace. Errors: 409 `invalid_transition`, `deadline_passed_no_makeup`.

### POST `/assignments/{id}/return` — *assigned reviewer only (or admin)*
Request: `{ "reason": "..." }` (min 3 chars)
Transitions SUBMITTED → RETURNED_FOR_REVISION. Permission: `cycle:review`.

### POST `/assignments/{id}/approve` — *assigned reviewer only (or admin)*
Transitions SUBMITTED → ARCHIVED. Permission: `cycle:review`.

### GET `/assignments/mine/active`
Returns caller's non-archived assignments.

---

## 4. Submissions (`/api/submissions`)

### GET `/submissions/{id}` — *object-level authz*
Response (sensitive fields masked by allowlist):
```json
{
  "id": "uuid", "assignment_id": "uuid", "template_version_id": "uuid",
  "rule_set_version_id": "uuid", "actor_user_id": "uuid|***",
  "submitted_at": "ISO8601"
}
```

### GET `/submissions/{id}/trace` — *object-level authz*
Response:
```json
{
  "submission_id": "uuid", "template_version_id": "uuid",
  "rule_set_version_id": "uuid", "trace": { "engine_version": "...",
  "steps": [...], "totals": {...} }, "trace_hash": "sha256hex",
  "computed_at": "ISO8601"
}
```

### POST `/submissions/{id}/grades/{item_key}` — *cycle:review + assigned reviewer*
Request: `{ "value": "7" }`. Writes `GRADE_EDIT` audit with content_hash (not raw value).

---

## 5. Templates (`/api/templates`)

### GET `/templates` — *template:manage*
Response: `[TemplateSummary]` (id, name, description, latest_version_id, latest_version_no, items).

### POST `/templates` — *template:manage*
Request: `{ "name": "...", "description": "...", "items": [TemplateItem] }`
TemplateItem: `{ "key": "q1", "label": "Q1", "weight": 1.0, "required": true, "missing_strategy": "ZERO_FILL", "min_value": null, "max_value": null, "outlier_z": null }`

### POST `/templates/{id}/versions` — *template:manage*
Publishes a new template version with updated items.

---

## 6. Rule Sets (`/api/rule_sets`)

### GET `/rule_sets` — *rule_set:manage*
Response: `{ "items": [RuleSetSummary] }` with versions array.

### POST `/rule_sets` — *rule_set:manage*
Request: `{ "name": "...", "description": "...", "rules": { "outlier_z_default": "3.0" } }`

### POST `/rule_sets/{id}/versions` — *rule_set:manage*
Request: `{ "rules": { "outlier_z_default": "2.5" } }`

---

## 7. Build Plans (`/api/plans`)

### GET `/plans` — *build_plan:view*
Response: `{ "items": [PlanSummary] }` (id, name, description, head_version_id, head_version_no, versions[]).

### POST `/plans` — *build_plan:manage*
Request: `{ "name": "...", "description": "...", "note": "initial", "lines": [BomLineIn] }`
BomLineIn: `{ "line_identity_key": "K1", "part_number": "P-A", "description": "", "quantity": "10", "unit": "ea", "notes": "", "tags": [] }`

### POST `/plans/{id}/versions` — *build_plan:manage*
Request: `{ "parent_version_id": "uuid|null", "note": "...", "lines": [BomLineIn] }`

### GET `/plans/{id}/versions/{vid}` — *build_plan:view*
Validates `version.plan_id == plan_id`. Response: `PlanVersionDetail` with lines.

### GET `/plans/{id}/versions/{vid}/diff` — *build_plan:view*
Query: `?against=uuid` (defaults to parent). Response: `{ "base_version_id": "...", "target_version_id": "...", "entries": [DiffLineOut] }`

### GET `/plans/{id}/versions/{vid}/export` — *build_plan:view*
Returns signed `.zip` bundle (binary). Audited as `PLAN_EXPORT`.

### POST `/plans/{id}/versions/{vid}/rollback` — *build_plan:manage*
Request: `{ "note": "..." }`. Creates new version from target's BOM.

### POST `/plans/{id}/versions/{vid}/share` — *build_plan:manage*
Request: `{ "role": "Plan Owner", "expires_in_days": 7 }` (1–3650, clamped to 7)
Response: `{ "id": "uuid", "plan_version_id": "...", "role": "...", "token": "...", "expires_at": "..." }`

### GET `/plans/share-links/mine` — *build_plan:manage*
### DELETE `/plans/share-links/{id}` — *build_plan:manage, issuer only (or admin)*

---

## 8. Share Link Resolution (`/api/share`)

### GET `/share/{token}` — *build_plan:view_shared + role match*
Resolves a share token to the plan version content. Validates `link.role` is in caller's roles (admin wildcard bypasses). Errors: 403 `share_link_invalid`, `share_link_role_mismatch`.

---

## 9. Model Registry (`/api/models`)

### GET `/models`
**Gated:** empty list unless caller has any `model:*` permission or admin wildcard.

### POST `/models` — *model:register*
Request: `{ "name": "...", "description": "..." }`

### POST `/models/{id}/versions` — *model:register*
Request: `{ "feature_schema": [FeatureDescriptor], "artifact_uri": "...", "artifact_params": {} }`
FeatureDescriptor: `{ "name": "a", "dtype": "float", "transform": "identity", "source_query_hash": "q1" }`

### POST `/models/{id}/versions/{vid}/runs` — *model:run*
Request: `{ "kind": "TRAINING|EVALUATION", "dataset_ref": "...", "notes": "..." }`
Response 201: `ModelRunSummary`.

### POST `/models/{id}/versions/{vid}/runs/{rid}/complete` — *model:run*
Request: `{ "status": "SUCCEEDED|FAILED", "metrics": {}, "notes": "..." }`
Errors: 409 `run_already_completed`.

### GET `/models/{id}/versions/{vid}/runs` — *model:run*

### POST `/models/{id}/versions/{vid}/promote` — *model:promote*
Errors: 409 `evaluation_run_required` (no SUCCEEDED eval run), 409 `feature_schema_mismatch`.

---

## 10. Experiments (`/api/experiments`)

### GET `/experiments`
**Gated:** empty list unless caller has `experiment:manage`, `model:route/rollback`, `feedback:submit`, or admin wildcard.

### POST `/experiments` — *experiment:manage*
Request: `{ "name": "...", "description": "...", "model_a_version_id": "uuid", "model_b_version_id": "uuid|null", "weight_a": 90 }`

### POST `/experiments/{id}/toggle` — *experiment:manage*
Request: `{ "ingest_enabled": true, "apply_enabled": true }`

### POST `/experiments/{id}/routing` — *model:route*
Request: `{ "weight_a": 70 }` (weight_b = 100 - weight_a)

### POST `/experiments/{id}/rollback` — *model:rollback*
Request: `{ "trigger": "manual|metric", "reason": "..." }`
Sets weight_a=100, weight_b=0, disables both toggles.

---

## 11. Inference (`/api/inference`)

### POST `/inference/predict` — *feedback:submit*
Request: `{ "experiment_id": "uuid", "subject_key": "user-42", "features": { "a": 0.5 } }`
Response:
```json
{
  "subject_key": "user-42", "experiment_id": "uuid", "arm": "A",
  "model_version_id": "uuid", "score": 0.87, "latency_ms": 42.3
}
```
Errors: 409 `experiment_apply_disabled`.

---

## 12. Feedback (`/api/feedback`)

### POST `/feedback` — *feedback:submit*
Request: `{ "experiment_id": "uuid", "subject_key": "user-42", "target_id": "item-1", "kind": "LIKE|NOT_INTERESTED|BLOCK", "arm": "A", "model_version_id": "uuid" }`
**Subject binding:** `subject_key` must equal `auth.user_id` (admin wildcard can override; audited as `FEEDBACK_SUBJECT_OVERRIDE`).
Errors: 429 `rate_limited` (>60/min per subject), 403 `subject_impersonation_forbidden`.

### GET `/feedback/signals/{experiment_id}` — *experiment:manage*
Response: `{ "items": [SignalOut] }` (experiment_id, arm, target_id, like_count, not_interested_count, last_updated_at).

### GET `/feedback/blocks/{subject_key}` — *own-subject: feedback:submit; cross-subject: experiment:manage*
Errors: 403 `subject_scope_denied`.

---

## 13. Administration

### Users (`/api/admin/users`) — *user:manage*
- `GET /admin/users` — list
- `POST /admin/users` — create: `{ "username": "...", "password": "...", "roles": ["Evaluator"], "display_name": "..." }`
- `GET /admin/users/{id}`
- `PATCH /admin/users/{id}` — update (is_active, roles, display_name)
- `POST /admin/users/{id}/unlock` — clear lockout

### Roles (`/api/admin/roles`) — *role:manage*
- `GET /admin/roles`
- `POST /admin/roles` — create with field_view_allowlist + permissions
- `PATCH /admin/roles/{id}`
- `GET /admin/permissions` — catalog of all resource:action pairs

### Audit (`/api/admin/audit`) — *audit:read*
- `GET /admin/audit/logs` — filters: actor_user_id, resource_type, resource_id, action, since, until, limit (1–500)
  Response: `{ "items": [AuditLogEntry] }` (sensitive fields masked by role allowlist)

### Backups (`/api/admin/backups`) — *backup:manage*
- `GET /admin/backups` — list archives
- `POST /admin/backups` — create (runs pg_dump + AES-GCM encrypt)
- `POST /admin/backups/{id}/stage` — enter maintenance mode, verify KEK + manifest hash
- `POST /admin/backups/{id}/commit` — run pg_restore (when BACKUP_RESTORE_EXECUTE=true) or state-machine only
- `POST /admin/backups/{id}/abort` — exit maintenance without restore
- `POST /admin/backups/prune` — remove archives + files older than 30 days

---

## 14. Health & Metrics

### GET `/health`
`200 { "status": "ok" }`

### GET `/health/ready`
Checks DB connectivity + KEK loaded. Response: `{ "status": "ok"|"degraded", "checks": {...} }`

### GET `/metrics` — *audit:read*
```json
{
  "requestsTotal": 18423, "errorsTotal": 12,
  "inferenceP95Ms": 118.5, "inferenceP95ViolationsTotal": 0,
  "activeSessions": 17, "feedbackEventsPerMinute": 42,
  "p95BudgetMs": 150.0
}
```

---

## 15. Conventions

- **Error envelope:** all errors return `{ "error": "<code>", "message": "...", "details": {...} }`
- **CSRF:** mutating SPA requests include `X-CSRF-Token`; server returns csrf_token in both login response and `/auth/me` for page-reload rehydration
- **Token anti-replay:** bounded acceptance window (60 s future skew + session max-age past bound) + nonce binding to session csrf_token
- **RBAC field masking:** sensitive fields return `"***"` unless the caller's `field_view_allowlist` grants the field name (or `"*"` wildcard)
- **Timestamps:** ISO 8601 strings; stored internally as UTC TIMESTAMPTZ
- **Numeric precision:** `Decimal` / `NUMERIC`; no binary floats in scoring or pricing math
- **IDs:** UUID v4 (server-generated)

| HTTP | Common error codes |
|------|--------------------|
| 400 | `validation_error`, `invalid_current_password`, `invalid_timezone` |
| 401 | `missing_session`, `session_expired`, `session_revoked`, `token_skew_exceeded`, `token_expired`, `token_nonce_mismatch`, `invalid_credentials` |
| 403 | `permission_denied`, `csrf_missing`, `not_your_assignment`, `not_assigned_reviewer`, `not_your_submission`, `subject_impersonation_forbidden`, `subject_scope_denied`, `share_link_role_mismatch`, `share_link_not_yours`, `share_link_invalid` |
| 404 | `not_found` |
| 409 | `invalid_transition`, `feature_schema_mismatch`, `evaluation_run_required`, `deadline_passed_no_makeup`, `plan_name_taken`, `model_name_taken`, `rule_set_name_taken`, `run_already_completed`, `already_assigned`, `experiment_apply_disabled`, `restore_already_staged`, `kek_fingerprint_mismatch` |
| 422 | `validation_error` (Pydantic field-level) |
| 423 | `account_locked` |
| 429 | `rate_limited` |
| 500 | `internal_error`, `restore_failed` |
| 503 | `maintenance` |
