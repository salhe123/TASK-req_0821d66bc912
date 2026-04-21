# Tests Coverage And Sufficiency Review

- Audit Date: 2026-04-21
- Method: static inspection only. No tests, containers, scripts, or package managers were executed.
- Project shape: **fullstack** — Vue 3 SPA + FastAPI backend + PostgreSQL, orchestrated via Docker Compose. Materially relevant test categories for this shape: backend unit, API integration, frontend component, end-to-end, and a load-SLO gate.

---

## Tests Check

### Categories present and whether they materially matter

| Category | Location | Framework | Materially matters? | Meaningful? |
|----------|----------|-----------|---------------------|-------------|
| Backend unit | `repo/api/tests/unit/` (21 suites) | `pytest` | Yes — deterministic scoring, token/lockout math, diff engine, masking, RBAC, state machine | Yes, non-trivial assertions |
| API integration | `repo/api/tests/api/` (25 suites) | `pytest` + `httpx` against the live `api` container | Yes — every mutating endpoint, authz, lifecycle, audit trail | Yes, real HTTP + real DB |
| Frontend component | `repo/web/tests/component/` (17 suites) | `vitest` + `@vue/test-utils` | Yes — per-view behavior, permission-gated UI, form state machines | Yes, view- and component-level |
| End-to-end | `repo/e2e/tests/` (13 spec files: `ui_*_journey`, `*_flow`, `smoke`, `security`) | `playwright` | Yes — real DOM through `nginx → api → db`; the only cross-boundary proof | Yes, mix of UI journeys + API journeys |
| Load SLO gate | `repo/api/tests/load/test_inference_p95.py` | asyncio `httpx` driver | Yes — prompt stipulates a 150 ms p95 inference budget | Yes, asserts against an env-configurable budget |

### Are API tests sending real requests (not mocked transport)?

**Yes.** `repo/api/tests/api/conftest.py:7-10` imports `httpx` and `psycopg` and issues real HTTP calls; authentication in `conftest.py:75,107` goes through the real `/api/auth/login` endpoint to obtain session tokens; mutating tests then call the live api service under the Compose test overlay (`repo/docker-compose.test.yml`). No test mocks the transport layer or the FastAPI router. Assertions check full payload shapes — e.g. `repo/api/tests/api/test_submissions.py:102,195` asserts the `calculation_traces` JSON structure; `repo/api/tests/api/test_plans.py:68` asserts diff entry fields; `repo/api/tests/api/test_feedback.py:162` asserts the blocks-list payload — not just status codes.

### End-to-end coverage across the real frontend/backend boundary?

**Yes, present.** `repo/e2e/tests/` contains 13 spec files. `ui_*_journey.spec.ts` drives the real DOM (login → navigate → interact → assert), while `*_flow.spec.ts` (cycle_lifecycle, plan_flow, model_flow, feedback_flow, full_flow) drive real HTTP journeys through `nginx → api → db`. `repo/e2e/tests/security.spec.ts` exercises CSRF / token-skew failure modes end-to-end. The browser tier therefore does not rely on backend tests alone to cover the frontend/backend boundary.

### `run_tests.sh` Docker-only contract

- `repo/run_tests.sh:1-94` is a thin orchestrator: `set -euo pipefail` at `:4`, Docker Compose detection at `:14-22`, stack up at `:44`, readiness gates at `:47-74`, test tiers at `:77, 80, 88, 91`, teardown trap at `:25-29`.
- Each tier is executed **inside a container**: `$COMPOSE run --rm api_tests`, `web_tests`, `e2e`, `load_tests`. The host only needs Docker + Compose.
- The script does not invoke host `python`, `pip`, `node`, `npm`, `yarn`, `pytest`, `vitest`, `playwright`, `jdk`, or any language runtime directly. The only host Bash it touches is `scripts/generate_dev_secrets.sh` at `:32`, which generates two 32-byte random files and has no language dependency.
- Pass/fail is delegated to the native runners (`pytest` / `vitest` / `playwright`); no Bash-level assertions substitute for application tests.
- Exit code propagation: `set -e` + native runner exit codes; the teardown trap does not mask failures.

### Prompt-requirement → test traceability (high-risk surfaces only)

| Prompt requirement / clarified behavior | Covered by |
|----------------------------------------|------------|
| Local login + Argon2 + 5-in-15 lockout + 60 s anti-replay | `repo/api/tests/unit/test_passwords.py`, `test_lockout_math.py`, `test_session_tokens.py`; `repo/api/tests/api/test_auth.py:36-157` |
| CSRF on state-changing endpoints | `repo/api/tests/api/test_security_headers.py:17-35` (matrix across mutating routes) |
| 5-state evaluation lifecycle incl. RETURNED_FOR_REVISION + make-up window | `repo/api/tests/api/test_cycles_lifecycle.py`; `repo/e2e/tests/cycle_lifecycle.spec.ts`, `ui_cycles_journey.spec.ts` |
| Deterministic scoring ledger + `ZERO_FILL` / `EXCLUDE_FROM_DENOMINATOR` + z-outlier flagging | `repo/api/tests/unit/test_scoring.py`; `repo/api/tests/api/test_submissions.py:102,195` (trace payload shape) |
| Plan version immutability + BOM diff classes + export bundle + signed share links | `repo/api/tests/unit/test_bom_diff.py`, `test_plan_export.py`, `test_share_tokens.py`; `repo/api/tests/api/test_plans.py`; `repo/e2e/tests/plan_flow.spec.ts` |
| Feature-schema-hash promotion gate + sticky A/B routing + rollback | `repo/api/tests/unit/test_routing.py`, `test_guardrail.py`; `repo/api/tests/api/test_models.py:47-191`, `test_model_runs.py`, `test_experiment_routing_update.py` |
| Feedback LIKE / NOT_INTERESTED / BLOCK + 60/min rate limit + toggle-gated ingest | `repo/api/tests/unit/test_feedback_rate_limit.py`; `repo/api/tests/api/test_feedback.py:56-227` |
| KEK-verified backup stage/commit/abort + 30-day retention prune | `repo/api/tests/unit/test_backup_archive.py`, `test_retention.py`; `repo/api/tests/api/test_admin.py`, `test_admin_backups_extended.py` |
| Audit-log append-only + masked sensitive fields | `repo/api/tests/unit/test_masking.py`; `repo/api/tests/api/test_audit_r3.py`, `test_audit_r4.py` |
| Object-level authz (submissions, plans, cycles) | `repo/api/tests/api/test_authz_post_audit.py`, `test_authz_post_audit_2.py` |
| 150 ms p95 inference budget | `repo/api/tests/load/test_inference_p95.py:88` (asserts against `P95_BUDGET_MS`) |

### Quantitative endpoint coverage (context for the score)

FastAPI surface: **69 endpoints** across 18 route modules under `repo/api/app/routes/`, all mounted with `/api` prefix at `repo/api/app/app.py:75-92`.

- Endpoints with at least one direct API test (success and/or failure payload asserted): **68 / 69 ≈ 98.5 %**.
- Endpoints with both success **and** failure payload-shape assertions: **60 / 69 ≈ 87 %**.
- Endpoints with no direct test: **1** — `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` at `repo/api/app/routes/cycles.py:277`.
- Endpoints with only happy-path / smoke reads: **7** — `GET /api/admin/roles`, `GET /api/admin/permissions`, `GET /api/cycles`, `GET /api/rule_sets`, `POST /api/rule_sets/{id}/versions`, `GET /api/plans`, `GET /api/experiments`.

### Overall sufficiency

The suite is **broad and genuinely confidence-building** for the core surfaces (auth, lifecycle, scoring, plans, models, feedback, backups, audit). It goes beyond happy-path snapshots: API tests assert payload shapes, E2E drives the real DOM, unit tests pin deterministic scoring and guardrail math. The boundary weakness is not depth — it's that a couple of narrow behaviors specified in the prompt have **no regression test** (see Key Gaps).

---

## Test Coverage Score

**82 / 100**

---

## Score Rationale

Starting from a baseline of 100, the score was reduced as follows:

- **−6** for the feedback event integrity gap. The prompt requires the feedback loop to be arm- and model-version-bound, but `repo/api/app/services/feedback.py:107-116` accepts a caller-supplied `model_version_id` whose consistency with `inference_routing` is not checked, and there is **no API test** that posts `arm="A"` with a model version that belongs to arm B. A severe regression here could pass CI. (Matches the open finding in `.tmp/audit_report-2.md:151`.)
- **−4** for the unenforced make-up window contract. `repo/api/app/schemas/cycles.py:49` permits `makeup_business_days` up to 30, violating the prompt's explicit "up to 5 business days," and lifecycle tests do not assert a rejection when `> 5` is posted.
- **−3** for the missing `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` test. The endpoint is a participant-drop action that writes a `PARTICIPANT_ADD_DROP` audit row — removing a participant without coverage means authz regressions here could ship silently.
- **−2** for the client-side subtotal divergence from server semantics. `repo/web/src/components/EvaluationForm.vue:34-41` uses `continue` for missing values and ignores the per-item `missing_strategy`, so the on-screen number can differ from the server's deterministic score for `ZERO_FILL` items. No component test asserts parity with server math.
- **−2** for thin reads on `/api/plans`, `/api/cycles`, `/api/rule_sets`, `/api/experiments`, and the admin roles/permissions catalog — touched once as smoke reads, not exercised for filters/scopes/non-admin 403.
- **−1** for unverifiable operational claims (nightly scheduler firing, real p95 under production hardware, real restore after KEK rotation): static audit cannot raise these above Cannot Confirm Statistically.

What keeps the score high despite those deductions: genuine end-to-end Playwright coverage across `nginx → api → db`, non-mocked API tests asserting payload shapes on 60+ endpoints, unit tests that pin deterministic scoring / guardrail math / state transitions, a load tier that asserts the p95 budget, and a `run_tests.sh` that executes every tier inside containers with no host-language dependencies for the main flow.

---

## Key Gaps

In priority order:

1. **No integrity test for feedback `(experiment_id, arm, model_version_id)` binding.** Add a `repo/api/tests/api/test_feedback.py` case that posts `arm="A"` with a model version belonging to arm B, expecting `409 feedback_arm_model_mismatch`. Root cause in `repo/api/app/services/feedback.py:107-116`.
2. **No rejection test for make-up window > 5 business days.** Add an API test in `test_cycles_lifecycle.py` asserting `422` when `makeup_business_days=6` is posted to `POST /api/cycles`. Root schema constraint lives in `repo/api/app/schemas/cycles.py:49`.
3. **`DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` has no direct test.** Endpoint at `repo/api/app/routes/cycles.py:277`. Add success path + audit row assertion + non-admin 403 + unknown-id 404.
4. **Client subtotal parity with server scoring is unverified.** Add a `repo/web/tests/component/EvaluationForm.test.ts` case covering `ZERO_FILL` missing items and asserting the weighted subtotal matches the server-equivalent formula (denominator includes the missing item's weight).
5. **Plan version copy workflow has no endpoint and therefore no test.** Prompt requires "create, copy, and compare"; copy is missing entirely. Add both the endpoint at `repo/api/app/routes/plans.py` and an API test.
6. **Digest banner is mounted only in `CyclesView` (`repo/web/src/views/CyclesView.vue:101`).** Add a component test covering shell-level mount so the reminder surfaces across routes per prompt.
7. **Thin read coverage on `GET /api/plans`, `GET /api/cycles`, `GET /api/rule_sets`, `GET /api/experiments`, `GET /api/admin/roles`, `GET /api/admin/permissions`.** Add filter/scope tests and non-admin 403 assertions for the admin catalog endpoints.
8. **Runtime-dependent claims remain Cannot Confirm Statistically:** actual scheduler fires at the configured hour, true p95 on production hardware, and end-to-end restore correctness under KEK mismatch. Not blockers, but worth a manual verification note in the runbook.

None of these gaps break the core product paths; they are the precise surfaces where a regression could ship without being caught by the current suite.

---

## README Audit (Rule 5.b lane)

Included because the earlier review (Rule 5.b) requires a README audit lane in this file in addition to the four outputs above. Source file: `repo/README.md` (159 lines).

### R.1 Structural Check

| Expected section | Present? | Evidence |
|------------------|----------|----------|
| Title / one-line description | yes | `repo/README.md:1-8` |
| Architecture / Tech Stack | yes | `repo/README.md:10-18` |
| Project Structure tree | yes | `repo/README.md:19-44` |
| Prerequisites | yes | `repo/README.md:46-51` |
| Running the Application | yes | `repo/README.md:53-88` (5 numbered steps + stop) |
| Testing | yes | `repo/README.md:90-127` (script + tiers + artifacts) |
| Seeded Credentials | yes | `repo/README.md:129-142` |
| Non-negotiables / Invariants | yes | `repo/README.md:144-152` |
| Related Documents | yes | `repo/README.md:154-158` |

### R.2 Factual / Freshness Check

| # | Claim | Location | Verdict | Evidence |
|---|-------|----------|---------|----------|
| R-1 | "alembic versions 0001 … 0009" | `repo/README.md:25` | **incorrect** | Repo has `0001…0011` under `repo/api/migrations/versions/` (11 files, not 9). Same finding as `.tmp/audit_report-2.md:205`. |
| R-2 | First administrator provisioned via KEK-verified `seed_admin` CLI | `repo/README.md:73-78` | accurate | `repo/api/app/scripts/seed_admin.py` exists and is invoked exactly as shown. |
| R-3 | "Frontend: http://localhost:8080" and "Backend API: http://localhost:8000/api" | `repo/README.md:81-82` | accurate | `repo/docker-compose.yml:39,53` publishes `8080:80` and `8000:8000`. |
| R-4 | "API Documentation (dev only): http://localhost:8000/api/docs" | `repo/README.md:83` | accurate | `repo/api/app/app.py:65-67` exposes `/api/docs` only when `environment != "production"`. |
| R-5 | "Every mutating endpoint writes exactly one semantic `audit_logs` row" | `repo/README.md:149` | consistent with code | Audit writes present across all mutating routes (`plans.py`, `cycles.py`, `assignments.py`, `models.py`, `experiments.py`, `feedback.py`, `admin_backups.py`). |
| R-6 | "Template, rule-set, and plan versions are immutable once saved" | `repo/README.md:152` | consistent with code | No UPDATE routes for `template_versions`, `rule_set_versions`, `plan_versions`; rollback writes a new version. |
| R-7 | "e2e_admin / E2E-Admin-Pass-1" only in disposable test DB | `repo/README.md:141` | consistent with code | Seeded by `repo/run_tests.sh:83-85` against the test overlay stack only. |
| R-8 | Tier table (backend unit, API integration, frontend component, E2E, load) | `repo/README.md:110-116` | accurate | Matches `repo/api/tests/{unit,api,load}`, `repo/web/tests/component`, `repo/e2e/tests`. |
| R-9 | "`plan.md` — phased implementation plan and testing protocol" | `repo/README.md:156` | needs manual check | Referenced path exists per README; content drift vs. actual phases is out of scope statically. |
| R-10 | "No outbound network calls at runtime — everything works air-gapped" | `repo/README.md:148` | consistent | No HTTP client to external hosts observed in `repo/api/app/**`; docker-compose has no outbound bindings. |

### R.3 README Issues

| # | Severity | Title | Evidence | Minimum Fix |
|---|----------|-------|----------|-------------|
| RM-1 | Low | Migration range is stale | `repo/README.md:25` says `alembic versions 0001 … 0009` but repo contains `0001…0011` | Change `0001 … 0009` → `0001 … 0011` at `repo/README.md:25`. Same issue tracked at `.tmp/audit_report-2.md:205`. |

All other structural and factual elements are consistent with the current repository.
