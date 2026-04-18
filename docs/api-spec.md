# Model Governance & Evaluation Workbench — API Specification

Base URL: `/api`
All authenticated endpoints require `Authorization: Bearer <session-token>`.
All state-changing requests from the SPA require a CSRF double-submit header `X-CSRF-Token: <value>`.
Session tokens carry an embedded `issued_at`; the server rejects tokens whose skew exceeds 60 seconds.
All list endpoints support `page` and `size` query parameters.

---

## 1. Authentication & Session (`/api/auth`)

### POST `/login`
Request:
```json
{ "username": "evaluator1", "password": "MinimumTwelveCharsPass" }
```
Response:
```json
{
  "token": "opaque-signed-session-token",
  "expiresInSeconds": 28800,
  "roles": ["EVALUATOR"],
  "fieldViewAllowlist": []
}
```
Errors:
- 401 `unauthenticated` — invalid credentials
- 423 `account_locked` — 5 failed attempts within 15 minutes

### POST `/logout`
Invalidates the current session.

### POST `/change-password`
```json
{ "oldPassword": "...", "newPassword": "AtLeastTwelveChars" }
```
Errors:
- 400 `validation_failed` — new password < 12 chars

### GET `/session`
Returns current session metadata including remaining idle time and active roles.

---

## 2. Evaluation Cycles (`/api/cycles`)  *(addresses Q1)*

### GET `/`
Filters: `status` (`open` | `closed` | `all`), `keyword`.
Response item:
```json
{
  "id": "uuid",
  "name": "Q2 2026",
  "startsAt": "04/01/2026",
  "deadlineAt": "06/30/2026 05:11 PM",
  "makeupEnabled": true,
  "makeupBusinessDays": 5
}
```

### POST `/`  *(Administrator)*
```json
{
  "name": "Q2 2026",
  "startsAt": "04/01/2026",
  "deadlineAt": "06/30/2026 05:11 PM",
  "makeupEnabled": true,
  "makeupBusinessDays": 5,
  "holidays": ["05/26/2026"]
}
```

### GET `/{cycleId}`

### PUT `/{cycleId}`  *(Administrator — toggles `makeupEnabled` and holidays)*

### GET `/{cycleId}/assignments`
Filters: `evaluatorUserId`, `state`, `late`.
Response item:
```json
{
  "id": "uuid",
  "cycleId": "uuid",
  "evaluatorUserId": "uuid",
  "subjectId": "uuid",
  "state": "IN_PROGRESS",
  "effectiveDeadlineAt": "07/07/2026 05:11 PM",
  "late": false
}
```

### POST `/{cycleId}/assignments`  *(Administrator, ML Engineer)*
Add participants. Writes `PARTICIPANT_ADD_DROP` audit entry.
```json
{ "evaluatorUserId": "uuid", "subjectId": "uuid" }
```

### DELETE `/{cycleId}/assignments/{assignmentId}`
Remove participant. Writes `PARTICIPANT_ADD_DROP`.

### GET `/digest`  *(caller-scoped)*
Returns the 9:00 AM local-time in-app digest for the caller: assignments due within 48 h, returned-for-revision, overdue-within-makeup.

---

## 3. Evaluations & Submissions (`/api/evaluations`)  *(addresses Q1, Q2)*

### GET `/assignments/{assignmentId}`
Returns the evaluation form state, template version, weights, current values, and flags.

### PUT `/assignments/{assignmentId}/values`
Partial save of evaluator inputs. First save transitions `NOT_STARTED → IN_PROGRESS`.
```json
{
  "values": {
    "item_1": "85",
    "item_2": null,
    "item_3": "42"
  }
}
```

### POST `/assignments/{assignmentId}/submit`
Transition `IN_PROGRESS → SUBMITTED`. Server re-runs the scoring engine and writes a `calculation_trace`. Rejects if required items missing or threshold flags not acknowledged.
Errors:
- 400 `validation_failed` — list missing items
- 400 `threshold_flag_unacknowledged`
- 409 `invalid_transition`
- 409 `deadline_passed_no_makeup`

Response:
```json
{
  "state": "SUBMITTED",
  "late": false,
  "submissionId": "uuid",
  "totalScore": "87.25"
}
```

### POST `/assignments/{assignmentId}/return`  *(Reviewer)*
```json
{ "reason": "item_3 outside expected range, please verify" }
```
Transition `SUBMITTED → RETURNED_FOR_REVISION`.

### POST `/assignments/{assignmentId}/approve`  *(Reviewer)*
Transition `SUBMITTED → ARCHIVED`. Rejects if open flags without override.

### GET `/submissions/{submissionId}/trace`
Returns the full calculation ledger:
```json
{
  "submissionId": "uuid",
  "templateVersionId": "uuid",
  "ruleSetVersionId": "uuid",
  "inputs": { "item_1": "85", "item_2": null, "item_3": "42" },
  "steps": [
    {
      "itemId": "item_1",
      "rawValue": "85",
      "effectiveValue": "85",
      "weight": "0.50",
      "subtotal": "42.50",
      "missingStrategy": null,
      "flags": []
    },
    {
      "itemId": "item_2",
      "rawValue": null,
      "effectiveValue": null,
      "weight": "0.30",
      "subtotal": "0",
      "missingStrategy": "EXCLUDE_FROM_DENOMINATOR",
      "flags": ["missing"]
    },
    {
      "itemId": "item_3",
      "rawValue": "42",
      "effectiveValue": "42",
      "weight": "0.20",
      "subtotal": "8.40",
      "missingStrategy": null,
      "flags": ["outlier"]
    }
  ],
  "totalScore": "72.71",
  "createdAt": "04/18/2026 11:42 AM"
}
```

### GET `/submissions/{submissionId}/history`
Immutable transition history for the underlying assignment.

---

## 4. Build Plans (`/api/plans`)  *(addresses Q3)*

### POST `/`  *(Plan Owner)*
```json
{ "name": "Chassis Revision 2026-A", "initialLines": [] }
```

### GET `/`
Filters: `ownerUserId`, `keyword`.

### GET `/{planId}`

### POST `/{planId}/versions`
Create a new version from a parent (or from scratch). Version rows are immutable after save.
```json
{ "parentVersionId": "uuid", "lines": [ { "lineIdentityKey": "LN-001", "partNo": "PT-100", "quantity": "2.00", "notes": "keep", "tags": ["critical"] } ] }
```

### POST `/{planId}/versions/copy`
```json
{ "fromVersionId": "uuid" }
```

### GET `/{planId}/versions/{versionId}`

### GET `/{planId}/versions/{versionId}/diff`
Query: `?against={otherVersionId}` (defaults to parent).
Response:
```json
{
  "fromVersionId": "uuid",
  "toVersionId": "uuid",
  "changes": [
    { "lineIdentityKey": "LN-001", "change": "QUANTITY_CHANGED", "before": "2.00", "after": "3.00", "notes": "scale up" },
    { "lineIdentityKey": "LN-010", "change": "ADDED", "after": { "partNo": "PT-205", "quantity": "1.00" } },
    { "lineIdentityKey": "LN-007", "change": "REMOVED", "before": { "partNo": "PT-099", "quantity": "1.00" } }
  ]
}
```

### POST `/{planId}/versions/{versionId}/export`
Returns a signed `.zip` bundle (binary) containing `plan.json`, `diff.json`, and `signature`.

### POST `/{planId}/versions/{versionId}/share-links`  *(Plan Owner)*
Issue a time-limited share token.
```json
{ "roleId": "uuid", "expiresAt": "04/25/2026 05:00 PM" }
```
Response:
```json
{ "shareLinkId": "uuid", "token": "opaque", "expiresAt": "04/25/2026 05:00 PM" }
```

### POST `/share-links/{shareLinkId}:revoke`  *(Plan Owner, Administrator)*

### GET `/share-links/{token}:resolve`
Requires an active session *and* `build_plan:view_shared` permission. 403 otherwise.

### POST `/{planId}/versions/{versionId}:rollback`
Creates a new version whose content copies an earlier version's BOM, with `parent_version_id` set to current head. Writes `PLAN_ROLLBACK` audit.

---

## 5. Model Registry & Inference (`/api/models`, `/api/inference`)  *(addresses Q4)*

### Registry — `/api/models`

#### POST `/`  *(ML Engineer)*
```json
{ "name": "ranker" }
```

#### POST `/{modelId}/versions`
Register a new model version with its feature schema snapshot.
```json
{
  "versionNo": "2026.04.18-1",
  "featureSchema": [
    { "name": "user_tenure_days", "dtype": "int", "transform": "none", "sourceHash": "abc123" }
  ],
  "metrics": { "auc": "0.891", "p95Ms": "118" }
}
```
Response includes the server-computed `featureSchemaHash`.

#### POST `/{modelId}/versions/{versionId}:promote`
Transition to `APPROVED`. Blocks with 409 `feature_schema_mismatch` if the inference service's current schema hash differs.
```json
{ "error": "feature_schema_mismatch", "details": { "missing": ["recency_score"], "extra": ["legacy_flag"] } }
```

#### POST `/{modelId}/versions/{versionId}:deprecate`

#### GET `/{modelId}/versions`

### Routing — `/api/models/routing`

#### GET `/`
Returns the active routing rule set.

#### PUT `/`
Update routing weights. Writes `ROUTING_CHANGE` audit.
```json
{ "modelAId": "uuid", "modelBId": "uuid", "weightA": 90, "weightB": 10 }
```

#### POST `/:rollback`
One-click rollback: sets `weightA=100, weightB=0`. Body records trigger metadata.
```json
{ "trigger": "manual", "reason": "guardrail breach" }
```

### Experiments — `/api/experiments`

#### POST `/`  *(ML Engineer)*
```json
{ "name": "ranker-2026.04", "modelAId": "uuid", "modelBId": "uuid", "ingestEnabled": true, "applyEnabled": true }
```

#### PUT `/{experimentId}/toggles`
```json
{ "ingestEnabled": false, "applyEnabled": false }
```

### Inference — `/api/inference`

#### POST `/predict`
Caller provides `subjectKey` for sticky routing.
```json
{ "subjectKey": "user-42", "features": { "user_tenure_days": 120 } }
```
Response:
```json
{
  "modelVersionId": "uuid",
  "arm": "A",
  "prediction": { "score": "0.87" },
  "latencyMs": 42
}
```
SLO: p95 ≤ 150 ms for approved models.

---

## 6. Feedback (`/api/feedback`)  *(addresses Q5)*

### POST `/events`
```json
{
  "subjectKey": "user-42",
  "targetId": "item-9991",
  "eventType": "LIKE",
  "modelVersionId": "uuid",
  "experimentId": "uuid"
}
```
Errors:
- 429 `rate_limited` — > 60 events/min per subject
- 400 `validation_failed` — unknown `eventType`

Behavior:
- `BLOCK` is persistent across toggles
- `LIKE` / `NOT_INTERESTED` update the per-arm signal within 60 seconds when `ingestEnabled=true`

### GET `/events`  *(ML Engineer, Administrator)*
Filters: `experimentId`, `modelVersionId`, `eventType`, `createdFrom`, `createdTo`.

---

## 7. Administration (`/api/admin`)  *(addresses Q6)*

### Users — `/admin/users`

#### POST `/`
```json
{ "username": "reviewer1", "password": "AtLeastTwelveChars", "roleIds": ["uuid"] }
```

#### GET `/`
Filters: `role`, `status`, `keyword`.

#### PUT `/{id}`

#### PUT `/{id}/unlock`
Clears failed-attempt lockout.

#### POST `/{id}/reset-password`
Admin-assisted reset; new password must meet policy.

### Roles — `/admin/roles`

#### POST `/`
```json
{
  "name": "REVIEWER",
  "fieldViewAllowlist": ["grade_values.raw_value", "evaluator_notes"],
  "permissions": [
    { "resource": "assignment", "action": "approve" },
    { "resource": "assignment", "action": "return" }
  ]
}
```

#### GET `/`

#### PUT `/{id}`

#### DELETE `/{id}`

### Permissions — `/admin/permissions`

#### GET `/`
Returns the resource/action catalog.

### Audit Logs — `/admin/audit`

#### GET `/logs`
Append-only — no mutation endpoints.
Filters: `actorUserId`, `resourceType`, `resourceId`, `action`, `dateFrom`, `dateTo`.
Covered actions: `PARTICIPANT_ADD_DROP`, `RULE_CHANGE`, `GRADE_EDIT`, `PLAN_ROLLBACK`, `MODEL_PROMOTION`, `ROUTING_CHANGE`, `SHARE_LINK_ISSUE`, `SHARE_LINK_OPEN`, `SHARE_LINK_REVOKE`, `BACKUP_RESTORE`.

### Backups & Restore — `/admin/backups`

#### GET `/`
List nightly backup archives with size, manifest hash, and age (30-day retention).

#### POST `/{archiveId}/restore:stage`
Phase 1: enter maintenance mode, verify KEK against archive header, restore into staging schema. Administrator only.

#### POST `/{archiveId}/restore:commit`
Phase 2: atomic swap to live schema. Writes `BACKUP_RESTORE` audit.

#### POST `/{archiveId}/restore:abort`
Exits maintenance mode without swap.

---

## 8. Health & Diagnostics

### GET `/health`
Process liveness. `200 { "status": "ok" }`.

### GET `/health/ready`
Checks DB connectivity, migrations applied, and KEK loaded.

### GET `/metrics`
```json
{
  "requestsTotal": 18423,
  "errorsTotal": 12,
  "inferenceP95Ms": 118,
  "inferenceP95ViolationsTotal": 0,
  "activeSessions": 17,
  "feedbackEventsPerMinute": 42
}
```

---

## 9. Conventions

- **CSRF:** state-changing SPA requests include `X-CSRF-Token`; missing/invalid → 403.
- **Token anti-replay (Q6):** sessions carry `issued_at`; skew > 60 s → 401 `token_skew_exceeded`.
- **RBAC field masking (Q6):** sensitive fields return masked unless the caller's `fieldViewAllowlist` grants the field.
- **Timestamps:** dates render MM/DD/YYYY and times 12-hour AM/PM on API responses; stored internally as UTC `TIMESTAMPTZ`.
- **Money & scores:** NUMERIC values serialized as two-decimal strings to avoid float drift.
- **Errors:** always envelope `{ "error": "<code>", "message": "...", "details": { ... } }`.

| HTTP | Common codes |
|------|--------------|
| 400 | `validation_failed`, `threshold_flag_unacknowledged` |
| 401 | `unauthenticated`, `session_expired`, `token_skew_exceeded` |
| 403 | `forbidden`, `out_of_scope`, `share_link_permission_missing` |
| 404 | `not_found` |
| 409 | `invalid_transition`, `feature_schema_mismatch`, `deadline_passed_no_makeup`, `version_conflict` |
| 423 | `account_locked` |
| 429 | `rate_limited` |
| 500 | `internal_error` |
