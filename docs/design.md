# Model Governance & Evaluation Workbench — System Design Document

## 1. Overview

The Model Governance & Evaluation Workbench (MGEW) is an offline-first fullstack application for running regulated scoring cycles, governing build plans, and iterating ML models with a closed-loop feedback stream — entirely inside a corporate local network. A Vue 3 single-page application drives a left-to-right operator workflow; a FastAPI backend exposes decoupled REST APIs; PostgreSQL 16 persists all state including immutable calculation ledgers and append-only audit trails.

Primary roles: **Administrator** (wildcard `*:*` permission), **ML Engineer**, **Evaluator**, **Reviewer**, **Plan Owner**. The system runs on a single host via Docker Compose with no outbound network dependencies, and must sustain approved-model inference within a **150 ms p95 server budget** on production hardware.

---

## 2. Architecture

### 2.1 Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend SPA | Vue 3.5, Pinia 2.3, Vue Router 4.5, Vite 6 |
| Backend HTTP | FastAPI 0.115 (ASGI, `uvicorn`) |
| DB driver / ORM | SQLAlchemy 2.0 (async) + `asyncpg` 0.30 |
| Migrations | Alembic 1.14 (11 revisions: 0001–0011) |
| Database | PostgreSQL 16 + `pgcrypto` extension |
| Password Hashing | Argon2id via `argon2-cffi` (memory=64 MB, time=3, parallelism=4) |
| Session Tokens | HMAC-SHA256 signed, nonce-bound to session CSRF token, bounded acceptance window (60 s future skew + session-max-age past bound) |
| Backup Encryption | AES-256-GCM via `cryptography` 44.0, key derived from KEK (SHA-256), KEK fingerprint as AEAD associated data |
| Backup Execution | Real `pg_dump -Fc` / `pg_restore --clean --if-exists` via subprocess (`postgresql-client` in API image) |
| Deployment | Docker Compose — `web` (nginx), `api` (uvicorn), `db` (postgres:16-alpine) — single host, offline |
| Testing | pytest + httpx (unit/API), vitest + @vue/test-utils (component), Playwright (E2E), asyncio load driver (p95) |

### 2.2 High-Level Architecture

```text
Vue 3 SPA (served by nginx, reverse-proxies /api → api:8000)
        |
        | REST / JSON over HTTP (same-origin)
        v
FastAPI Router (/api prefix)
        |
        v
Middleware Stack:
  RequestContext (request_id, inc_request) → MaintenanceMode (503) →
  ErrorEnvelope (ApiError → JSON, inc_error) → Auth (session cookie or
  Bearer token + CSRF on mutating methods)
        |
        v
18 Route Modules
        |
        v
Service Layer
  ├─ Scoring engine (Decimal math, ZERO_FILL / EXCLUDE_FROM_DENOMINATOR, z-score outlier)
  ├─ State machine (assignment transitions with actor enforcement)
  ├─ Plan versioning, BOM diff, export bundle, share tokens
  ├─ Model registry, feature-schema hash, promotion gate (requires SUCCEEDED eval run)
  ├─ Inference routing (sticky arm by subject_key hash)
  ├─ Feedback ingestion (rate limit 60/min, subject binding, BLOCK → subject_blocks)
  ├─ Backup archive (AES-GCM encrypt, pg_dump/pg_restore, nightly scheduler)
  ├─ Masking (field_view_allowlist gating)
  └─ Metrics (requestsTotal, errorsTotal, inferenceP95Ms, activeSessions, feedbackEventsPerMinute)
        |
        v
SQLAlchemy (async) → PostgreSQL 16 (pgcrypto) + local backup volume
```

### 2.3 Backend Route Modules (registered in `api/app/app.py`)

`health`, `auth`, `admin_users`, `admin_roles`, `admin_audit`, `admin_backups`, `templates`, `rule_sets`, `cycles`, `assignments`, `submissions`, `plans`, `share`, `models`, `experiments`, `inference`, `metrics`, `feedback` — all mounted at `/api`.

### 2.4 Frontend Module Structure

| View / Component | Purpose |
|-----------------|---------|
| `LoginView` | Local username/password login with lockout feedback |
| `DashboardView` | Landing page after auth |
| `CyclesView` | Cycle selector, "my evaluations" table, cycle-participants table |
| `AssignmentFormView` | Uses `EvaluationForm` (subtotals, flags, threshold ack); reviewer panel (return/approve) |
| `PlansView` | Create-plan modal, list/select/diff/share/rollback |
| `ModelsView` | Create-model modal, register version, train/eval buttons, promote, create-experiment modal, `RoutingConsole` |
| `FeedbackView` | Predict panel + `FeedbackControl` (Like / Not Interested / Block) + blocks table |
| `AdminView` | Users, roles, audit logs, backup/restore console |
| `AppShell` | Nav gated by permission; session refresh rehydrates CSRF token on page reload |
| `EvaluationForm` | Weighted item table, real-time subtotal, per-item flags, threshold acknowledgement checkbox |
| `FeedbackControl` | Like / Not Interested / Block buttons with state + API binding |
| `RoutingConsole` | Weight slider, rollback dialog |

Stores: `session` (Pinia) — user, csrfToken, permissions, hasPermission helper. API client: `lib/api.ts` — typed fetch with CSRF header injection and 401 redirect.

---

## 3. Security Model

### 3.1 Authentication

- Local username + password only (no external IdP, no outbound calls)
- Password policy: minimum 12 characters, Argon2id salted hash (rehash on login if algorithm version outdated)
- Lockout after 5 failed attempts in a rolling 15-minute window; unlock via `POST /api/admin/users/{id}/unlock` or automatic expiry
- Session tokens: HMAC-SHA256 signed opaque bearer with `iat`, `sid`, `uid`, and `nonce` (bound to session's `csrf_token`)
- Anti-replay: bounded acceptance window — reject tokens where `iat > now + 60s` (future) OR `now - iat > session_max_age + 60s` (stale replay)
- Nonce mismatch: `token.nonce != session.csrf_token` → 401 `token_nonce_mismatch`
- Cookie: `mgew_session` httpOnly, samesite=strict, secure flag env-sensitive (true in production)
- `/api/auth/me` returns `csrf_token` so the SPA can rehydrate after page reload

### 3.2 Roles & Permissions (RBAC)

Each role composes: (a) resource:action permission tuples, (b) `field_view_allowlist` (JSONB list of sensitive field names the role may see unmasked).

| Role | Key Permissions | Field Allowlist |
|------|----------------|-----------------|
| Administrator | `*:*` (wildcard — all resources/actions) | `["*"]` (all fields) |
| ML Engineer | model:register/promote/route/rollback/run, experiment:manage, audit:read | model.feature_schema, model.metrics |
| Evaluator | cycle:participate | evaluator_notes |
| Reviewer | cycle:review, cycle:participate | evaluator_notes |
| Plan Owner | build_plan:manage/view/view_shared | plan.bom.notes |

Additional seeded permissions: `template:manage`, `rule_set:manage`, `feedback:submit`, `backup:manage`, `user:manage`, `role:manage`, `audit:read`.

### 3.3 Object-Level Authorization

- **Assignment read** (`get_assignment`, `get_assignment_form`): evaluator owner, assigned reviewer (with `cycle:review`), or admin wildcard
- **Reviewer actions** (return, approve, grade edit): assigned reviewer only (or admin wildcard)
- **Submission detail/trace**: submission actor, assignment evaluator, assigned reviewer, or admin wildcard
- **Cycle participant listing**: privileged (cycle:manage/review) sees all; others see only own rows
- **Feedback submit**: `subject_key` must equal `auth.user_id`; admin wildcard can override (audited as `FEEDBACK_SUBJECT_OVERRIDE`)
- **Share-link resolution**: `link.role` must be in caller's roles (or admin wildcard)
- **Share-link revocation**: issuer only (or admin wildcard)
- **Inference predict**: requires `feedback:submit` permission

### 3.4 Transport & Request Hardening

- CSRF: `X-CSRF-Token` header validated on all mutating requests; `csrf_missing` → 403
- XSS: Vue template interpolation; server sets `Content-Security-Policy` and `X-Content-Type-Options: nosniff`
- SQL injection: all DB access parameterized via SQLAlchemy; no raw string concatenation
- Rate limits: feedback endpoint capped at 60 events/min per subject_key
- Sensitive-field masking: `apply_mask` / `mask_list` on submissions (`actor_user_id`) and admin audit (`payload`, `actor_user_id`) gated by `field_view_allowlist`

### 3.5 Data at Rest

- Sensitive columns (grade_values.raw_value_encrypted) encrypted with `pgcrypto` (`pgp_sym_encrypt`) using KEK loaded from operator-mounted file
- Backup archives: AES-256-GCM with random 12-byte nonce, KEK fingerprint as AEAD associated data; framing: `MGEW | 0x01 | nonce(12) | ciphertext+tag(16)`
- Audit logs are append-only (no UPDATE/DELETE endpoints); grade-edit entries store content_hash not raw values
- Backup retention: 30-day window; `prune_old` deletes both metadata rows and on-disk archive files

---

## 4. Core Modules

### 4.1 Evaluation Cycles, Assignments, and Form Workflow

**States:** `NOT_STARTED → IN_PROGRESS → SUBMITTED → (RETURNED_FOR_REVISION → IN_PROGRESS)* → ARCHIVED`

| Transition | Actor | Gate |
|------------|-------|------|
| NOT_STARTED → IN_PROGRESS | Evaluator (assigned) | First save |
| IN_PROGRESS → SUBMITTED | Evaluator | Via `/submit` with values |
| SUBMITTED → RETURNED_FOR_REVISION | Assigned Reviewer | Required reason (min 3 chars) |
| SUBMITTED → ARCHIVED | Assigned Reviewer | Via `/approve` |
| RETURNED_FOR_REVISION → IN_PROGRESS | Evaluator | Automatic on next `/save` |

**Deadlines:** each cycle has `deadline_at`. Effective deadline = `deadline_at` + makeup business days (Mon–Fri minus holiday list) when `makeup_enabled=true`. Submissions past deadline but within makeup window are accepted with `late_flag=true`.

**Daily digest** (`GET /api/cycles/digest`): uses per-user timezone preference (`users.timezone` column, updatable via `POST /api/auth/me/timezone`); falls back to first cycle timezone, then UTC. Shows at 9:00 AM local time; once-per-day gating via `digest_last_shown_date`.

**UI:** CyclesView provides a cycle selector, "my evaluations" table with Open buttons, and a cycle-participants table (visibility scoped by role). AssignmentFormView integrates the `EvaluationForm` component (weighted items, real-time subtotals, per-item flags, threshold acknowledgement) plus a reviewer panel with return/approve controls.

### 4.2 Scoring Engine & Calculation Ledger

Deterministic by construction: `Decimal` math, canonical JSON inputs (sorted keys via `canonical_json`), immutable reference to template_version and rule_set_version.

**Ledger row (`calculation_traces`):** `submission_id` (UNIQUE), `template_version_id`, `rule_set_version_id`, `trace_json` (JSONB with engine_version, steps, totals), `trace_hash` (SHA-256 of canonical trace), `computed_at`.

**Missing-value strategies** (per template item): `ZERO_FILL` (treat missing as 0, full denominator) or `EXCLUDE_FROM_DENOMINATOR` (skip item, reduce denominator).

**Outlier flagging:** default z-score > 3.0; per-item override via `min_value`/`max_value` on template items. Raw values are never altered.

**Grade values** (`grade_values`): `raw_value_encrypted` (pgcrypto AES), `raw_present` (bool), `content_hash` (SHA-256 of canonical value).

### 4.3 Rule-Set Management

Rule sets parameterize outlier/threshold behaviour. Endpoints: `GET /api/rule_sets`, `POST /api/rule_sets`, `POST /api/rule_sets/{id}/versions`. Requires `rule_set:manage` permission (Administrator). Versions are immutable once published; referenced by evaluation cycles via `rule_set_version_id`.

### 4.4 Build Plan Governance

**Immutability:** `plan_versions` rows are immutable; edits produce a new version with `parent_version_id`.

**BOM diff:** operates at `bom_lines` level using `line_identity_key`. Change classes: `ADDED`, `REMOVED`, `QUANTITY_CHANGED`, `PART_CHANGED`, `NOTE_TAG_CHANGED`.

**Export bundle:** `.zip` containing `plan.json` + `diff.json` + detached `signature` (HMAC over manifest hash).

**Share links:** time-limited bearer tokens scoped to `(plan_version_id, role, expires_at)` — max TTL clamped to 7 days. Resolution requires active login + `build_plan:view_shared` permission + role match. Revocation scoped to issuer (or admin wildcard).

**Plan creation:** UI provides a create-plan modal; API is `POST /api/plans` with initial BOM lines.

### 4.5 Model Registry, Runs, Routing, and A/B

**Registry:** models registered by version with `feature_schema` (JSONB), `feature_schema_hash` (SHA-256 of sorted feature names), `artifact_uri`, `artifact_params`. Status: `DRAFT → APPROVED → DEPRECATED`.

**Training/evaluation runs** (`model_runs` table): `POST /api/models/{id}/versions/{vid}/runs` starts a run (TRAINING or EVALUATION); `POST .../runs/{rid}/complete` finishes it. **Promotion gate:** `DRAFT → APPROVED` requires at least one `SUCCEEDED` `EVALUATION` run on the version.

**Feature consistency:** promotion blocked with 409 `feature_schema_mismatch` when the version's `feature_schema_hash` differs from the model's `live_schema_hash`.

**Routing** (`inference_routing`): `(model_a_id, model_b_id, weight_a, weight_b)` default `(90, 10)`. Sticky by `subject_key`: `hash(subject_key) mod 100 < weight_a` → arm A.

**Rollback:** `POST /api/experiments/{id}/rollback` sets `weight_a=100, weight_b=0`, disables `ingest_enabled` + `apply_enabled`, records trigger (`manual` | `metric`) in `rollback_events`.

**UI:** ModelsView provides create-model modal, register-version flow, Train/Evaluate buttons, Promote button, create-experiment modal, and `RoutingConsole` with weight slider + rollback dialog.

### 4.6 Feedback Loop

- Controls: `LIKE`, `NOT_INTERESTED`, `BLOCK` via `POST /api/feedback`
- Subject binding: `subject_key` must equal authenticated user ID (admin override → audited)
- `BLOCK` persists to `subject_blocks` table, independent of experiment toggles
- `LIKE` / `NOT_INTERESTED` update `feedback_signals` (per-arm rolling counters) when `ingest_enabled=true`
- Rollback flips both toggles on the losing arm; events continue to be recorded for audit
- Rate limit: 60 events/min per subject (→ 429 `rate_limited`)
- UI: FeedbackView provides a predict panel (calls `/api/inference/predict`), renders results with `FeedbackControl`, and displays a blocks table

### 4.7 Backup & Restore

- **Create:** `POST /api/admin/backups` runs `pg_dump -Fc --no-owner --no-acl` via subprocess, AES-GCM encrypts the output, writes to `BACKUP_VOLUME`, records `backup_archives` row
- **Nightly scheduler:** in-process asyncio loop (`backup_scheduler.py`) triggers at `BACKUP_SCHEDULER_HOUR` (default 02:00 UTC); configurable via env vars; once-per-day guard prevents duplicates
- **Restore:** two-phase — `POST .../stage` (enters maintenance mode, verifies KEK fingerprint + manifest hash) → `POST .../commit` (runs `pg_restore --clean --if-exists --single-transaction` when `BACKUP_RESTORE_EXECUTE=true`) → `POST .../abort` (exits maintenance without swap)
- **Retention:** `POST /api/admin/backups/prune` deletes metadata rows AND on-disk files older than 30 days

### 4.8 Administration

- User CRUD: `POST/GET/PATCH /api/admin/users`, `POST /api/admin/users/{id}/unlock`
- Role CRUD: `GET/POST/PATCH /api/admin/roles`, `GET /api/admin/permissions`
- Audit read: `GET /api/admin/audit/logs` with filters (actor, resource, action, date range); sensitive fields masked by role allowlist
- Health: `GET /api/health` (liveness), `GET /api/health/ready` (DB + KEK checks)
- Metrics: `GET /api/metrics` — requestsTotal, errorsTotal, inferenceP95Ms, inferenceP95ViolationsTotal, activeSessions, feedbackEventsPerMinute

---

## 5. Data Model

Primary keys: UUID v4 (server-generated via `gen_random_uuid()`). Timestamps: `TIMESTAMPTZ` in UTC. Numeric precision: `NUMERIC` / `Decimal` (no binary floats).

### Migrations (11 revisions)

| # | Revision | Scope |
|---|----------|-------|
| 0 | `0001_phase0_bootstrap` | pgcrypto extension, schema_meta |
| 1 | `0002_phase1_identity` | users, roles, permissions, user_roles, role_permissions, sessions, failed_logins, audit_logs; 5 default roles + default permission grants |
| 2 | `0003_phase2_cycles` | templates, template_versions, evaluation_cycles, assignments; digest_last_shown_date on users |
| 3 | `0004_phase3_scoring` | rule_sets, rule_set_versions, submissions, grade_values, calculation_traces; default rule set seed |
| 4 | `0005_phase4_plans` | plans, plan_versions, bom_lines, plan_share_links |
| 5 | `0006_phase5_models` | models (registered_models), model_versions, experiments, inference_routing, rollback_events |
| 6 | `0007_phase6_feedback` | feedback_events, feedback_signals, subject_blocks |
| 7 | `0008_phase7_backups` | backup_archives, restore_events |
| 8 | `0009_phase8_model_runs` | model_runs + model:run permission seed |
| 9 | `0010_phase9_ruleset_tz` | rule_set:manage permission + users.timezone column |
| 10 | `0011_admin_wildcard` | Grant (*,*) wildcard permission to Administrator role |

### Key Tables

**Identity:** `users` (id, username, password_hash, is_active, locked_until, timezone, digest_last_shown_date), `roles` (id, name, field_view_allowlist JSONB), `permissions` (id, resource, action), `sessions` (id, user_id, csrf_token, issued_at, expires_at, revoked_at, last_seen_at), `failed_logins`, `audit_logs` (append-only)

**Cycles:** `evaluation_cycles` (id, name, starts_on, ends_on, deadline_at, timezone, makeup_enabled, makeup_business_days, holidays JSONB, template_version_id, rule_set_version_id), `assignments` (id, cycle_id, evaluator_user_id, reviewer_user_id, state, draft_values JSONB, submitted_at, late_flag, returned_reason, archived_at), `templates`, `template_versions` (items JSONB)

**Scoring:** `rule_sets`, `rule_set_versions` (rules JSONB), `submissions`, `grade_values` (raw_value_encrypted bytes, content_hash), `calculation_traces` (trace_json JSONB, trace_hash)

**Plans:** `plans` (name, owner_user_id), `plan_versions` (version_no, parent_version_id, note), `bom_lines` (line_identity_key, part_number, quantity NUMERIC, unit, notes, tags JSONB), `plan_share_links` (role, token_hash, expires_at, created_by, revoked_at)

**Models:** `models` (name, live_schema_hash), `model_versions` (version_no, status, feature_schema JSONB, feature_schema_hash, artifact_uri, artifact_params JSONB, approved_at), `model_runs` (kind TRAINING|EVALUATION, status QUEUED|RUNNING|SUCCEEDED|FAILED, metrics JSONB, dataset_ref), `experiments` (ingest_enabled, apply_enabled), `inference_routing` (model_a_id, model_b_id, weight_a, weight_b), `rollback_events` (trigger, reason, metrics_snapshot JSONB)

**Feedback:** `feedback_events` (experiment_id, arm, subject_key, target_id, kind, model_version_id), `feedback_signals` (experiment_id, arm, target_id, like_count, not_interested_count), `subject_blocks` (subject_key, target_id)

**Backups:** `backup_archives` (filename, size_bytes, manifest_hash, kek_fingerprint), `restore_events` (archive_id, state staged|committed|aborted, started_by, kek_fingerprint, notes JSONB)

---

## 6. Cross-Cutting Concerns

### 6.1 Deterministic Scoring
All arithmetic uses `Decimal`; inputs are canonicalized (sorted keys, normalized whitespace) before hashing; replaying the same inputs against the same template + rule-set versions produces a byte-identical `trace_hash`.

### 6.2 Feature Consistency
Promotion of a `model_version` checks `feature_schema_hash` against the model's `live_schema_hash`; mismatch → 409 `feature_schema_mismatch` with the diff (missing/extra features).

### 6.3 Inference Latency Budget
Approved-model inference tracked per-route with a **150 ms p95** SLO on production hardware. Violations counted to `metrics.inference_p95_violations_total`. CI test overlay defaults to 400 ms budget to absorb VM jitter.

### 6.4 Audit Trail
Append-only `audit_logs`; actions recorded: `USER_LOGIN`, `USER_LOGOUT`, `USER_PASSWORD_CHANGE`, `USER_TIMEZONE_UPDATE`, `CYCLE_CREATE`, `ASSIGNMENT_ADD`, `SUBMISSION`, `SUBMISSION_RETURNED`, `SUBMISSION_ARCHIVED`, `GRADE_EDIT`, `TEMPLATE_CREATE`, `TEMPLATE_VERSION_PUBLISH`, `RULE_SET_CREATE`, `RULE_SET_VERSION_PUBLISH`, `PLAN_CREATE`, `PLAN_VERSION_CREATE`, `PLAN_EXPORT`, `PLAN_ROLLBACK`, `SHARE_LINK_ISSUE`, `SHARE_LINK_OPEN`, `SHARE_LINK_REVOKE`, `MODEL_CREATE`, `MODEL_VERSION_REGISTER`, `MODEL_PROMOTION`, `MODEL_RUN_START`, `MODEL_RUN_COMPLETE`, `ROUTING_UPDATE`, `ROLLBACK`, `FEEDBACK_SUBJECT_OVERRIDE`, `BACKUP_CREATE`, `BACKUP_PRUNE`, `BACKUP_RESTORE`.

### 6.5 Observability
- Structured JSON logs: `request_id`, method, path, status, `duration_ms`
- `inc_request()` on every request (RequestContext middleware)
- `inc_error()` on ApiError, HTTPException, and ValidationError exception handlers
- `set_active_sessions()` refreshed on login/logout
- `/api/health` (liveness), `/api/health/ready` (DB + KEK), `/api/metrics` (all counters + gauges)

---

## 7. Error Envelope

All error responses:
```json
{ "error": "<code>", "message": "<human>", "details": { ... } }
```

| HTTP | Code examples |
|------|---------------|
| 400 | `validation_error`, `invalid_current_password`, `invalid_timezone` |
| 401 | `missing_session`, `session_expired`, `session_revoked`, `token_skew_exceeded`, `token_expired`, `token_nonce_mismatch` |
| 403 | `permission_denied`, `csrf_missing`, `not_your_assignment`, `not_assigned_reviewer`, `not_your_submission`, `subject_impersonation_forbidden`, `subject_scope_denied`, `share_link_role_mismatch`, `share_link_not_yours` |
| 404 | `not_found` |
| 409 | `invalid_transition`, `feature_schema_mismatch`, `evaluation_run_required`, `deadline_passed_no_makeup`, `plan_name_taken`, `model_name_taken`, `run_already_completed`, `already_assigned`, `experiment_apply_disabled` |
| 422 | `validation_error` (Pydantic) |
| 423 | `account_locked` |
| 429 | `rate_limited` |
| 500 | `internal_error`, `restore_failed` |
| 503 | `maintenance` |

---

## 8. Deployment

- Docker Compose on one host: `web` (nginx serving SPA + reverse proxy `/api` → `api:8000`), `api` (FastAPI/uvicorn + postgresql-client), `db` (postgres:16-alpine + pgcrypto)
- Volumes: `db_data` (Postgres data), `backup_data` (encrypted archives)
- Secrets: `infra/secrets/kek` (32-byte KEK), `infra/secrets/session_signing_key` (32-byte HMAC key) — operator-mounted, dev-generated via `scripts/generate_dev_secrets.sh`
- Config via environment: `DATABASE_URL`, `DATABASE_URL_SYNC`, `KEK_PATH`, `SESSION_SIGNING_KEY_PATH`, `BACKUP_VOLUME`, `ENVIRONMENT`, `LOG_LEVEL`, `COOKIE_SECURE`, `BACKUP_SCHEDULER_ENABLED/HOUR/TIMEZONE`, `BACKUP_RESTORE_EXECUTE`, `P95_BUDGET_MS`
- Alembic migrations applied at API startup via lifespan hook (`RUN_MIGRATIONS_ON_STARTUP=true`)
- Nightly backup scheduler started in lifespan when `BACKUP_SCHEDULER_ENABLED=true`

---

## 9. Testing Strategy

All tests run inside Docker via `run_tests.sh` — no host-installed Python, Node, or PostgreSQL needed. Five tiers:

| Tier | Runner | Scope | Target |
|------|--------|-------|--------|
| 1 | pytest | Backend unit (services, scoring, RBAC, masking, lockout math, diff, tokens, retention, guardrail) | ≥90% service-layer line coverage |
| 2 | pytest + httpx | API integration against live api container — every endpoint with success + failure assertions, authz regression suites | Full endpoint coverage |
| 3 | vitest + @vue/test-utils | Frontend component tests (EvaluationForm, FeedbackControl, RoutingConsole, AppShell, etc.) | ≥80% component line coverage |
| 4 | Playwright (Chromium) | Browser E2E: UI journeys (login, cycles, admin, plans, models) + full-stack API flows (lifecycle, feedback, model, plan, security) | All primary workflows |
| 5 | asyncio httpx driver | Approved-route inference p95 ≤ budget (150 ms contract / 400 ms CI default) | Latency SLO |

Coverage artifacts: `coverage/api-coverage.xml` (Cobertura), `coverage/web-lcov/` (lcov + HTML), `e2e/playwright-report/` (HTML traces).
