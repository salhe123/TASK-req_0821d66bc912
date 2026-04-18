# Model Governance & Evaluation Workbench — System Design Document

## 1. Overview

The Model Governance & Evaluation Workbench is an offline-first fullstack application for running regulated scoring cycles, governing build plans, and iterating ML models with a closed-loop feedback stream — entirely inside a corporate local network. A Vue.js single-page application drives a left-to-right operator workflow; a FastAPI backend exposes decoupled REST APIs; PostgreSQL persists all state including immutable calculation ledgers and append-only audit trails.

Primary roles: **Administrator**, **ML Engineer**, **Evaluator**, **Reviewer**, **Plan Owner**. The system runs on a single host with no outbound network dependencies and must sustain approved-model inference within a **150 ms p95 server budget**.

---

## 2. Architecture

### 2.1 Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend SPA | Vue.js 3, Pinia, Vue Router, Vite |
| Backend HTTP | FastAPI (ASGI, `uvicorn`) |
| DB driver / ORM | SQLAlchemy 2.x + `asyncpg` |
| Migrations | Alembic |
| Database | PostgreSQL (with `pgcrypto` for column encryption) |
| Password Hashing | Argon2id (salted), via `argon2-cffi` |
| Session Tokens | HMAC-signed opaque tokens with anti-replay timestamp (60 s skew) |
| Field Encryption at Rest | `pgcrypto` AES using an operator-mounted KEK |
| Backups | Nightly encrypted `pg_dump`, 30-day retention on local volume |
| Deployment | Docker Compose — SPA (nginx), API, PostgreSQL — single host, offline |
| Logging | Structured JSON, append-only audit table |

### 2.2 High-Level Architecture

```text
Vue.js SPA (served by nginx on local network)
        |
        | REST / JSON over HTTP (same-origin reverse proxy)
        v
FastAPI Router
        |
        v
Middleware: Session/Token → Anti-replay → CSRF → RBAC → Audit → Error envelope
        |
        v
Handler Layer (per resource group)
        |
        v
Service Layer
  ├─ Scoring engine (deterministic, Decimal math, ledger writer)
  ├─ Plan versioning & diff
  ├─ Model registry + routing
  ├─ Feedback ingestion + experiment gating
  └─ Crypto / masking / audit
        |
        v
SQLAlchemy (async) → PostgreSQL (pgcrypto) + local backup volume
```

### 2.3 Backend Module Structure

- `auth` — local login, session issuance, lockout, anti-replay token verification
- `cycles` — evaluation cycles, assignments, deadline + make-up logic, 9 AM digest builder
- `evaluations` — form templates, submissions, state machine, threshold flags
- `scoring` — deterministic engine, missing-value strategies, outlier flagging, calculation trace
- `plans` — plan versions, BOM lines, diff engine, export bundle signer, share-link tokens
- `models` — model registry, feature-schema hashing, routing rules, A/B, rollback
- `inference` — low-latency serving path with 150 ms p95 budget
- `feedback` — event ingest, per-arm signal store, experiment toggles
- `admin` — users, roles, facilities, audit read, backup/restore
- `common` — error envelope, pagination, validators, masking helpers, time utils

### 2.4 Frontend Module Structure

- `views/cycles` — cycle selector, participant list, assignment dashboard
- `views/evaluation` — evaluation form with template weights, real-time subtotal rollups, flag panel, timeline badge
- `views/plans` — plan list, compare-and-approve view, BOM diff, share-link issuance modal
- `views/models` — model registry, routing console, A/B toggle, rollback button
- `views/feedback` — embedded Like / Not Interested / Block controls (reusable component)
- `views/admin` — user/role management, audit log viewer, backup/restore console
- `stores/` — Pinia stores mirror backend resources; optimistic edits reconcile against server validation
- `lib/api.ts` — typed client bound to the OpenAPI schema FastAPI emits

---

## 3. Security Model

### 3.1 Authentication

- Local username + password only (no external IdP, no outbound calls)
- Password policy: minimum 12 characters, Argon2id salted hash
- Lockout after 5 failed attempts in a rolling 15-minute window (unlock via Administrator or automatic expiry)
- Session tokens: HMAC-signed opaque bearer with embedded `issued_at`; server rejects tokens whose `issued_at` skew exceeds 60 seconds vs server clock (anti-replay)
- Tokens bound to `user_id`, role set, and session row; server-side invalidation available

### 3.2 Roles & Permissions (RBAC) (addresses Q6)

Each role composes: (a) resource-action permissions, (b) data scope, (c) field-view allowlist (unlocks specific sensitive fields on response).

| Role | Scope |
|------|-------|
| Administrator | All resources; manages users, roles, audit read, backup/restore; field allowlist = full |
| ML Engineer | Datasets, models, routing rules, experiments; view model metrics in full |
| Evaluator | Own assigned evaluations (read/write until submitted) |
| Reviewer | Submitted evaluations (read full; transition return/approve); view grade values |
| Plan Owner | Build plans and BOMs; issue/revoke share links |

Sensitive fields default to **masked** on response; full values are returned only when the caller's `field_view_allowlist` grants the field.

### 3.3 Transport & Request Hardening

- CSRF: double-submit cookie token validated on all state-changing requests from the SPA
- XSS: SPA renders only via Vue template interpolation; server sets `Content-Security-Policy` and `X-Content-Type-Options: nosniff`
- SQL injection: all DB access parameterized via SQLAlchemy; no raw string concatenation
- Rate limits: per-user and per-IP caps on login and feedback endpoints

### 3.4 Data at Rest (addresses Q6)

- Sensitive columns (evaluator notes, raw grade values, subject identifiers in feedback events) encrypted with `pgcrypto` using a KEK loaded from an operator-mounted file at service start — the DB never holds the KEK
- Audit logs are append-only (no UPDATE/DELETE endpoints); grade-edit entries store ids, actor, timestamp, and a content hash rather than raw values
- Backups: nightly encrypted `pg_dump` to a mounted local volume, 30-day retention, verified by manifest hash
- Restore: Administrator-only two-phase workflow — maintenance mode → KEK-verified staging restore → atomic swap — recorded as `BACKUP_RESTORE` audit entry

---

## 4. Core Modules

### 4.1 Evaluation Cycles, Assignments, and Form Workflow (addresses Q1)

**States:** `NOT_STARTED → IN_PROGRESS → SUBMITTED → (RETURNED_FOR_REVISION → IN_PROGRESS)* → ARCHIVED`.

**Transition authority:**

| Transition | Actor | Gate |
|------------|-------|------|
| NOT_STARTED → IN_PROGRESS | Evaluator (assigned) | First save of any field |
| IN_PROGRESS → SUBMITTED | Evaluator | Required fields present, threshold flags acknowledged |
| SUBMITTED → RETURNED_FOR_REVISION | Reviewer | Required reason |
| SUBMITTED → ARCHIVED | Reviewer | Approval (no open flags without override) |
| RETURNED_FOR_REVISION → IN_PROGRESS | Evaluator | Automatic on next edit |

**Deadlines and make-up window:**
- Each cycle has a `deadline_at`. An assignment's *effective deadline* equals the cycle deadline unless the Administrator has enabled make-up for the cycle, in which case submissions are accepted for up to **5 business days** after `deadline_at` (Mon–Fri minus a configurable holiday list).
- Submissions inside the make-up window are accepted with `late=true` and flagged in the audit trail.

**UI surfaces:**
- Timeline badge on every evaluation shows current state and next actionable step
- Evaluation form renders template weights inline with each item, computes subtotals in real time on the client and verifies them server-side at submit
- Flag panel highlights missing values and items whose values exceed configured thresholds

**Daily digest (9:00 AM local):**
- Server computes a per-user digest: assignments within 48h of deadline, `RETURNED_FOR_REVISION` items, overdue items inside make-up window
- Delivered as in-app banner on first user action after 09:00 local; banner is dismissible but re-surfaces the next day

### 4.2 Scoring Engine & Calculation Ledger (addresses Q2)

The scoring engine is the **single source of truth** for a submission's numeric result. It is deterministic by construction: `Decimal` math, canonicalized JSON inputs, and an immutable reference to template and rule-set versions.

**Ledger row (`calculation_traces`):**

| Field | Meaning |
|-------|---------|
| `submission_id` | Parent submission |
| `template_version_id` | Immutable snapshot of form template |
| `rule_set_version_id` | Immutable snapshot of calculation rules |
| `inputs` (JSONB) | Canonicalized input payload |
| `trace_steps` (JSONB array) | One entry per scored item |
| `total_score` (NUMERIC) | Computed total |
| `created_at` | Timestamp |

Each `trace_step` records: item id, raw value, effective value after missing-value handling, weight, subtotal contribution, and flags.

**Missing-value strategies (per template item):**
- `ZERO_FILL` — treat missing as 0, full denominator
- `EXCLUDE_FROM_DENOMINATOR` — skip item, reduce denominator proportionally

The chosen strategy is recorded on the step so Reviewers can see which path applied.

**Outlier flagging:**
- Default: flag if `|z-score| > 3.0` relative to prior submissions in the same cycle
- Per-item override: absolute range `[min, max]` or a different z threshold
- Raw values are **never altered** — flagging only

**Threshold warnings:**
- Template items may declare warning/error thresholds; exceedances are surfaced in the form UI and included in the ledger

### 4.3 Build Plan Governance (addresses Q3)

**Immutability:**
- `plan_versions` rows are immutable after save; edits produce a new version with `parent_version_id` set

**Compare-and-approve experience:**
- Plan Owners create/copy/compare versions via the SPA's side-by-side diff view
- Diff engine operates at the BOM-line level using `line_identity_key` (owner-chosen, stable across renames)
- Change classes: `ADDED`, `REMOVED`, `QUANTITY_CHANGED`, `PART_CHANGED`, `NOTE_TAG_CHANGED`

**Export bundle (offline sharing):**
- `.zip` containing `plan.json` (version metadata + full BOM), `diff.json` (vs parent), and a detached `signature` (HMAC over manifest hash using local KEK)
- Consumer of the bundle can verify integrity without network access

**Share links:**
- Time-limited bearer tokens scoped to `(plan_version_id, role, expires_at)` — max TTL 7 days
- Resolution of a share link still requires an active local login *and* the `build_plan:view_shared` permission
- Revocation is immediate; all share events append to audit

### 4.4 Model Registry, Routing, and A/B (addresses Q4)

**Registry:**
- Models registered by version with `feature_schema_hash` (hash of ordered feature names, dtypes, transformations, source-query hashes), metrics snapshot, and promotion status (`DRAFT → APPROVED → DEPRECATED`)

**Promotion gate — feature consistency:**
- Promotion to `APPROVED` is blocked with a 409 when `feature_schema_hash` differs from the inference service's current schema hash — response lists the differing features

**Routing rules (`inference_routing`):**
- `(model_a_id, model_b_id, weight_a, weight_b)` with defaults `(90, 10)`
- Routing is sticky by `subject_key` (user id, session id, or caller-supplied idempotency key): `hash(subject_key) mod 100 < weight_a` → arm A
- Guarantees that retries and repeat requests for the same subject hit the same arm

**One-click rollback:**
- Single atomic update sets `weight_a = 100, weight_b = 0`; records trigger (manual or metric-based) in `experiments.rollback_events`
- Auto-rollback defaults: error rate > 2%, p95 latency > 150 ms, or feedback-derived disengagement rate > baseline + 30% over 15 minutes
- All routing changes append a `MODEL_PROMOTION` / `ROUTING_CHANGE` audit row

**Inference SLO:**
- Approved-model inference requests must complete within a **150 ms p95** server budget; violations are counted per route and surface in metrics

### 4.5 Feedback Loop (addresses Q5)

- Feedback controls on result surfaces: `LIKE`, `NOT_INTERESTED`, `BLOCK`
- Events persist to `feedback_events` with `subject_key`, `target_id`, `event_type`, `model_version_id`, `experiment_id`
- `BLOCK` suppresses `(subject, target)` authoritatively and permanently within the experiment — independent of toggles
- `LIKE` / `NOT_INTERESTED` feed a per-arm rolling signal; propagation to inference cache ≤ 60 seconds
- Each experiment carries two independent toggles:
  - `ingest_enabled` — accepts new events into the arm's signal
  - `apply_enabled` — lets the arm's signal influence ranking
- Rollback flips both on the losing arm; events continue to be **recorded** (for audit) but are not ingested, so a future restore is not polluted
- Rate limit: 60 feedback events/min per subject (beyond → 409 `rate_limited`)

### 4.6 Administration (addresses Q6)

- Manage users, roles, permissions, facilities
- Audit log read with filters (actor, resource, date range); no mutation endpoints
- Backup & restore console — Administrator only:
  - Nightly backups listed with size, manifest hash, and age
  - Restore is two-phase: staging restore with KEK verification, then atomic swap; whole flow writes a `BACKUP_RESTORE` audit entry

---

## 5. Data Model

Primary keys are UUID v4. Timestamps are stored as `TIMESTAMPTZ` in UTC; the originating local-time + offset is preserved on display-oriented rows (evaluations, cycles).

**Identity & access:**
- `users` — id, username, password_hash (Argon2id), failed_attempts, locked_until, last_activity_at, is_active
- `roles` — id, name, field_view_allowlist (JSONB)
- `permissions` — id, resource, action
- `role_permissions` — role_id, permission_id
- `user_roles` — user_id, role_id
- `sessions` — id, user_id, issued_at, expires_at, revoked_at
- `audit_logs` — id, actor_user_id, action, resource_type, resource_id, content_hash, created_at (append-only)

**Cycles, templates, and evaluations:**
- `evaluation_cycles` — id, name, starts_at, deadline_at, makeup_enabled, makeup_business_days (default 5)
- `assignments` — id, cycle_id, evaluator_user_id, subject_id, state, late, effective_deadline_at
- `templates` — id, name
- `template_versions` — id, template_id, version_no, schema (JSONB), thresholds (JSONB), is_active
- `rule_sets` — id, name
- `rule_set_versions` — id, rule_set_id, version_no, rules (JSONB), is_active
- `submissions` — id, assignment_id, template_version_id, rule_set_version_id, submitted_at, submitted_by
- `calculation_traces` — id, submission_id, inputs (JSONB), trace_steps (JSONB), total_score NUMERIC, created_at
- `grade_values` — id, submission_id, item_id, raw_value_encrypted (pgcrypto), effective_value NUMERIC, flags (JSONB)

**Plans & BOM:**
- `plans` — id, name, owner_user_id
- `plan_versions` — id, plan_id, parent_version_id, version_no, created_at, created_by (immutable)
- `bom_lines` — id, plan_version_id, line_identity_key, part_no, quantity NUMERIC, notes, tags (TEXT[])
- `plan_share_links` — id, plan_version_id, role_id, token_hash, expires_at, revoked_at

**Models & experiments:**
- `models` — id, name
- `model_versions` — id, model_id, version_no, feature_schema_hash, metrics (JSONB), status
- `inference_routing` — id, model_a_id, model_b_id, weight_a, weight_b, updated_at
- `experiments` — id, name, model_a_id, model_b_id, ingest_enabled, apply_enabled, created_at
- `rollback_events` — id, experiment_id, trigger (`manual` | `metric`), metrics_snapshot (JSONB), created_at

**Feedback:**
- `feedback_events` — id, subject_key, target_id, event_type, model_version_id, experiment_id, created_at
- `feedback_signals` — experiment_id, arm_id, target_id, score, updated_at (rolling store)

**Backups:**
- `backup_archives` — id, created_at, path, size_bytes, manifest_hash, kek_fingerprint
- `restore_events` — id, archive_id, administrator_user_id, started_at, finished_at, outcome

**High-selectivity indexes:**
- `(cycle_id, evaluator_user_id)` on `assignments`
- `(submission_id)` UNIQUE on `calculation_traces`
- `(plan_id, version_no)` UNIQUE on `plan_versions`
- `(plan_version_id, line_identity_key)` UNIQUE on `bom_lines`
- `(model_id, version_no)` UNIQUE on `model_versions`
- `(experiment_id, target_id)` on `feedback_signals`
- `(actor_user_id, created_at)` on `audit_logs`
- `(subject_key, created_at)` on `feedback_events`

---

## 6. Cross-Cutting Concerns

### 6.1 Deterministic Scoring (addresses Q2)

- All arithmetic uses `Decimal` with fixed precision; no binary floats in ledger math
- Inputs are canonicalized (sorted keys, normalized whitespace) before hashing
- Replaying the same inputs against the same template and rule-set versions produces a byte-identical `calculation_trace`

### 6.2 Feature Consistency (addresses Q4)

- Training pipeline and inference service both publish their `feature_schema_hash` to the registry at startup
- Promotion of a `model_version` checks the stored hash against the live inference hash; mismatch → 409 `feature_schema_mismatch` with the diff

### 6.3 Inference Latency Budget

- Approved-model inference handlers tracked per-route with a **150 ms p95** SLO
- Budget enforced by (a) prepared-statement caching, (b) pre-warmed model artifacts in memory, (c) feature store served from in-process cache
- SLO violations counted to `metrics.inference_p95_violations_total`

### 6.4 Audit Trail (addresses Q6)

- Append-only `audit_logs`; actions recorded: `PARTICIPANT_ADD_DROP`, `RULE_CHANGE`, `GRADE_EDIT`, `PLAN_ROLLBACK`, `MODEL_PROMOTION`, `ROUTING_CHANGE`, `BACKUP_RESTORE`, `SHARE_LINK_*`
- Grade edits store ids + content hash (not raw values) since raw values are encrypted

### 6.5 Observability

- Structured JSON logs: `request_id`, `user_id`, `method`, `path`, `status`, `duration_ms`, `route_slo`
- `/health` — process liveness
- `/health/ready` — DB connectivity + migrations applied + KEK loaded
- `/metrics` — request counters, inference p95 violations, outbox / experiment depth

---

## 7. Error Envelope

All error responses share a common JSON shape:
```json
{ "error": "<code>", "message": "<human>", "details": { ... } }
```

| HTTP | Code examples |
|------|---------------|
| 400 | `validation_failed`, `threshold_flag_unacknowledged` |
| 401 | `unauthenticated`, `session_expired`, `token_skew_exceeded` |
| 403 | `forbidden`, `out_of_scope`, `share_link_permission_missing` |
| 404 | `not_found` |
| 409 | `invalid_transition`, `feature_schema_mismatch`, `version_conflict`, `rate_limited` |
| 423 | `account_locked` |
| 429 | `rate_limited` |
| 500 | `internal_error` |

---

## 8. Deployment

- Docker Compose on one host: `web` (nginx serving the SPA build), `api` (FastAPI/uvicorn), `db` (PostgreSQL with `pgcrypto`)
- Reverse proxy routes `/api/*` → FastAPI, everything else → SPA
- No outbound network dependencies
- Config via environment variables: `DATABASE_URL`, `KEK_PATH`, `SESSION_SIGNING_KEY`, `BIND_ADDR`, `BACKUP_VOLUME`
- Alembic migrations applied at API startup
- Nightly backup job inside the `db` container writes encrypted `pg_dump` to `BACKUP_VOLUME`

---

## 9. Testing Strategy

All tests run inside Docker via `run_tests.sh` — no reliance on host-installed Python, Node, or PostgreSQL. The script builds the API + SPA + DB images, applies migrations, runs the suites, and tears the stack down.

This is a **fullstack** project, so the suite has three tiers — unit, component (frontend), and API — with an `API_tests` folder retained.

**Backend unit tests (`pytest`)** — target ≥90% line coverage measured with `coverage.py`.
- Scoring engine: determinism (replay → byte-identical ledger), `ZERO_FILL` vs `EXCLUDE_FROM_DENOMINATOR`, outlier flagging at z > 3.0 and custom bounds, threshold flag emission
- State machine for assignments (all transitions in §4.1 table) and make-up business-day math against configurable holidays
- Feature-schema hash computation and promotion-gate behavior on mismatch
- Plan diff engine: ADDED / REMOVED / QUANTITY_CHANGED / PART_CHANGED / NOTE_TAG_CHANGED with `line_identity_key` stability
- Share-link token issuance, expiry, and revocation
- Argon2id verify, lockout window math (5 in 15 min), anti-replay token skew (60 s)
- Field masking vs `field_view_allowlist`; audit row construction for grade edits (hash, no raw)

**Frontend component tests (Vitest + Vue Test Utils)** — target ≥80% line coverage.
- Evaluation form: weight rendering, real-time subtotal rollups match server ground truth, flag panel behavior for missing/threshold values
- Timeline badge renders correct next action per state
- Plan compare view: diff colorization, note/tag surfacing
- A/B routing console: weight slider, one-click rollback disabled states
- Feedback control emits the expected event payload

**API tests (`pytest` + `httpx` against the running FastAPI container)** — call real HTTP endpoints and assert on full JSON payload shape, not just status codes.
- Auth: login → session → logout; lockout after 5 failed attempts; token skew > 60 s rejected
- Cycles: select cycle → assignments list → evaluation workflow (`NOT_STARTED → … → ARCHIVED`); make-up enabled admits submissions inside 5-business-day window, flags `late=true`; disabled rejects with 409
- Scoring: submit with missing and outlier values; assert `calculation_trace` payload shape, strategy recorded per step, raw values preserved
- Plans: create/copy/compare; diff payload shape; export bundle signature verifies; share-link open succeeds only with login + `build_plan:view_shared`
- Models: register → feature hash mismatch → 409; promote → route → A/B split sticky by subject; rollback flips weights atomically
- Feedback: LIKE/NOT_INTERESTED/BLOCK events; BLOCK persistent across toggles; 61st event in 60 s → 429
- Admin: audit logs append-only, grade-edit rows store hash not raw; backup/restore flow records `BACKUP_RESTORE`
- Health & metrics: `/health/ready` fails cleanly when KEK absent; inference p95 violation counter increments past budget

**Load check** — a `k6` run inside the Docker network verifies the approved-model inference route holds p95 ≤ 150 ms under sustained concurrent load.
