# Test Coverage & README Audit

- Audit Date: 2026-04-21
- Scope: two lanes —
  - **Lane A (Test Coverage):** complete method+path inventory of the FastAPI surface, mapped endpoint-by-endpoint to test files that exercise it.
  - **Lane B (README Audit):** structural + factual review of `repo/README.md`.
- Method: static. Endpoints harvested from `repo/api/app/routes/` route decorators + router prefixes + the `/api` application prefix in `repo/api/app/app.py:75-92`. Test mapping built from literal path matches in `repo/api/tests/api/**`, `repo/e2e/tests/**`, and `repo/web/tests/component/**`. No runtime execution.

## Terminology

| Token | Meaning |
|-------|---------|
| **covered** | ≥1 API test calls the endpoint with both success and failure payload assertions |
| **basic** | ≥1 API test calls the endpoint, but only success path or single assertion shape |
| **smoke** | Exercised transitively (e.g. via e2e journey or setup fixture), no direct payload assertion |
| **missing** | No direct test reference found |

---

## Lane A — Test Coverage (endpoint-by-endpoint)

### A.1 Endpoint Inventory & Test Mapping

The application mounts every router with the `/api` prefix at `repo/api/app/app.py:75-92`. Per-router prefixes come from `APIRouter(prefix=...)` in each route module.

#### A.1.1 Authentication (`auth` router, prefix `/auth` → `/api/auth`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 1 | POST | `/api/auth/login` | `repo/api/app/routes/auth.py:49` | `repo/api/tests/api/test_auth.py:36,56,75,84,147`, `test_security_headers.py:63`, `test_cycles_lifecycle.py:96,123,139,160,240,318,395`, many flow tests | covered |
| 2 | POST | `/api/auth/logout` | `repo/api/app/routes/auth.py:136` | `repo/api/tests/api/test_auth.py:125` | covered |
| 3 | POST | `/api/auth/change-password` | `repo/api/app/routes/auth.py:161` | `repo/api/tests/api/test_auth.py:139` | covered |
| 4 | GET  | `/api/auth/me` | `repo/api/app/routes/auth.py:191` | `repo/api/tests/api/test_auth.py:94,128,157`, `test_audit_r3.py:236,241`, `test_security_headers.py:53` | covered |
| 5 | POST | `/api/auth/me/timezone` | `repo/api/app/routes/auth.py:211` | `repo/api/tests/api/test_audit_r3.py:238,248` | covered |

#### A.1.2 Admin — Users (`admin_users`, prefix `/admin/users`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 6 | GET  | `/api/admin/users` | `repo/api/app/routes/admin_users.py:40` | `repo/api/tests/api/test_admin_users.py:31,41`, `test_user_management.py:16,74,81,103` | covered |
| 7 | POST | `/api/admin/users` | `repo/api/app/routes/admin_users.py:54` | `repo/api/tests/api/test_admin_users.py:12,57,59,68`, `test_user_management.py:34,48,61`, `test_auth.py:113`, `test_security_headers.py:17` | covered |
| 8 | POST | `/api/admin/users/{user_id}/unlock` | `repo/api/app/routes/admin_users.py:109` | `repo/api/tests/api/test_user_management.py:77,88,96,111` | covered |

#### A.1.3 Admin — Roles / Permissions (`admin_roles`, prefix `/admin`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 9 | GET  | `/api/admin/roles` | `repo/api/app/routes/admin_roles.py:16` | `repo/api/tests/api/test_admin.py:14` | basic |
| 10 | GET | `/api/admin/permissions` | `repo/api/app/routes/admin_roles.py:43` | `repo/api/tests/api/test_admin.py:19` | basic |

#### A.1.4 Admin — Audit (`admin_audit`, prefix `/admin/audit`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 11 | GET | `/api/admin/audit/logs` | `repo/api/app/routes/admin_audit.py:22` | `repo/api/tests/api/test_admin.py:44,50` | covered |

#### A.1.5 Admin — Backups (`admin_backups`, prefix `/admin/backups`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 12 | GET  | `/api/admin/backups` | `repo/api/app/routes/admin_backups.py:67` | `repo/api/tests/api/test_admin.py:124,178`, `test_admin_backups_extended.py:17`, `test_audit_r4.py:252` | covered |
| 13 | POST | `/api/admin/backups` | `repo/api/app/routes/admin_backups.py:79` | `repo/api/tests/api/test_admin.py:58,132,163,164`, `test_admin_backups_extended.py:14,15,38,70,79,83`, `test_audit_r4.py:231`, `test_security_headers.py:23` | covered |
| 14 | POST | `/api/admin/backups/{archive_id}/stage` | `repo/api/app/routes/admin_backups.py:98` | `repo/api/tests/api/test_admin.py:65,135,166`, `test_admin_backups_extended.py:62` | covered |
| 15 | POST | `/api/admin/backups/{archive_id}/commit` | `repo/api/app/routes/admin_backups.py:160` | `repo/api/tests/api/test_admin.py:104`, `test_admin_backups_extended.py:71` | covered |
| 16 | POST | `/api/admin/backups/{archive_id}/abort` | `repo/api/app/routes/admin_backups.py:236` | `repo/api/tests/api/test_admin.py:136,172`, `conftest.py:94` | covered |
| 17 | POST | `/api/admin/backups/prune` | `repo/api/app/routes/admin_backups.py:270` | `repo/api/tests/api/test_admin_backups_extended.py:28,45,91`, `test_audit_r4.py:247` | covered |

#### A.1.6 Health & Metrics

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 18 | GET | `/api/health` | `repo/api/app/routes/health.py:10` | `repo/api/tests/api/test_health.py:8`, `test_audit_r3.py:262-263`, `test_security_headers.py:42` | covered |
| 19 | GET | `/api/health/ready` | `repo/api/app/routes/health.py:15` | `repo/api/tests/api/test_health.py:18` | covered |
| 20 | GET | `/api/metrics` | `repo/api/app/routes/metrics.py:10` | `repo/api/tests/api/test_metrics_warmup.py:19,53`, `test_models.py:255`, `test_audit_r3.py:261,264`, `test_authz_post_audit_2.py:266,270` | covered |

#### A.1.7 Evaluation Cycles (`cycles`, prefix `/cycles`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 21 | GET    | `/api/cycles` | `repo/api/app/routes/cycles.py:67` | `repo/api/tests/api/test_audit_r3.py:153` | basic |
| 22 | POST   | `/api/cycles` | `repo/api/app/routes/cycles.py:90` | `repo/api/tests/api/test_cycles_lifecycle.py:42,200,278,350`, `test_authz_post_audit.py:78`, `test_authz_post_audit_2.py:86`, `test_audit_r3.py:81`, `test_submission_detail.py:48`, `test_submissions.py:54,154,222`, `test_digest.py:51,119` | covered |
| 23 | GET    | `/api/cycles/digest` | `repo/api/app/routes/cycles.py:159` | `repo/api/tests/api/test_digest.py:84,98,162` | covered |
| 24 | GET    | `/api/cycles/{cycle_id}/assignments` | `repo/api/app/routes/cycles.py:190` | `repo/api/tests/api/test_cycles_lifecycle.py:405`, `test_authz_post_audit_2.py:118,125,130` | covered |
| 25 | POST   | `/api/cycles/{cycle_id}/assignments` | `repo/api/app/routes/cycles.py:216` | `repo/api/tests/api/test_cycles_lifecycle.py:85,233,311,388`, `test_authz_post_audit.py:103`, `test_authz_post_audit_2.py:108,112`, `test_audit_r3.py:105`, `test_submission_detail.py:65`, `test_submissions.py:75,176,242`, `test_digest.py:70,139` | covered |
| 26 | DELETE | `/api/cycles/{cycle_id}/assignments/{assignment_id}` | `repo/api/app/routes/cycles.py:277` | *(none found)* | **missing** |

#### A.1.8 Assignments (`assignments`, prefix `/assignments`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 27 | GET  | `/api/assignments/{assignment_id}` | `repo/api/app/routes/assignments.py:96` | `repo/api/tests/api/test_audit_r3.py:111,120` | covered |
| 28 | GET  | `/api/assignments/{assignment_id}/form` | `repo/api/app/routes/assignments.py:107` | `repo/api/tests/api/test_audit_r3.py:114,122` | covered |
| 29 | POST | `/api/assignments/{assignment_id}/save` | `repo/api/app/routes/assignments.py:127` | `repo/api/tests/api/test_authz_post_audit.py:121`, `test_cycles_lifecycle.py:103,145,248,324,408`, `test_submission_detail.py:75`, `test_submissions.py:89,187,253` | covered |
| 30 | POST | `/api/assignments/{assignment_id}/submit` | `repo/api/app/routes/assignments.py:157` | `repo/api/tests/api/test_authz_post_audit.py:125`, `test_cycles_lifecycle.py:111,151,252,325`, `test_submission_detail.py:76`, `test_submissions.py:90,188,254` | covered |
| 31 | POST | `/api/assignments/{assignment_id}/return` | `repo/api/app/routes/assignments.py:226` | `repo/api/tests/api/test_authz_post_audit.py:186`, `test_cycles_lifecycle.py:129,173` | covered |
| 32 | POST | `/api/assignments/{assignment_id}/approve` | `repo/api/app/routes/assignments.py:252` | `repo/api/tests/api/test_authz_post_audit.py:192`, `test_cycles_lifecycle.py:165` | covered |
| 33 | GET  | `/api/assignments/mine/active` | `repo/api/app/routes/assignments.py:277` | `repo/api/tests/api/test_submission_detail.py:73`, `test_submissions.py:85,185,251`, `test_cycles_lifecycle.py:245,322,400` | covered |

#### A.1.9 Submissions (`submissions`, prefix `/submissions`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 34 | GET  | `/api/submissions/{submission_id}` | `repo/api/app/routes/submissions.py:72` | `repo/api/tests/api/test_authz_post_audit.py:155,168,171`, `test_submission_detail.py:86,115`, `test_authz_post_audit_2.py:268` | covered |
| 35 | GET  | `/api/submissions/{submission_id}/trace` | `repo/api/app/routes/submissions.py:94` | `repo/api/tests/api/test_authz_post_audit.py:158,173`, `test_submission_detail.py:100,117,136`, `test_submissions.py:102,195` | covered |
| 36 | POST | `/api/submissions/{submission_id}/grades/{item_key}` | `repo/api/app/routes/submissions.py:117` | `repo/api/tests/api/test_submissions.py:262,291` | covered |

#### A.1.10 Templates (`templates`, prefix `/templates`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 37 | GET  | `/api/templates` | `repo/api/app/routes/templates.py:33` | `repo/api/tests/api/test_template_versions.py:27,55`, `test_audit_r3.py:139` | covered |
| 38 | POST | `/api/templates` | `repo/api/app/routes/templates.py:47` | `repo/api/tests/api/test_admin.py:33`, `test_authz_post_audit.py:66`, `test_authz_post_audit_2.py:74`, `test_audit_r3.py:69`, `test_cycles_lifecycle.py:24,188,267,339`, `test_submission_detail.py:38`, `test_submissions.py:38,141,209`, `test_digest.py:40,108`, `test_template_versions.py:24,39,77,104,108,118,134`, `test_security_headers.py:18` | covered |
| 39 | POST | `/api/templates/{template_id}/versions` | `repo/api/app/routes/templates.py:94` | `repo/api/tests/api/test_template_versions.py:46,81,92` | covered |

#### A.1.11 Rule Sets (`rule_sets`, prefix `/rule_sets`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 40 | GET  | `/api/rule_sets` | `repo/api/app/routes/rule_sets.py:57` | `repo/api/tests/api/test_audit_r3.py:208` | basic |
| 41 | POST | `/api/rule_sets` | `repo/api/app/routes/rule_sets.py:73` | `repo/api/tests/api/test_audit_r3.py:195,222` | covered |
| 42 | POST | `/api/rule_sets/{rule_set_id}/versions` | `repo/api/app/routes/rule_sets.py:110` | `repo/api/tests/api/test_audit_r3.py:202` | basic |

#### A.1.12 Plans & Share Links (`plans`, prefix `/plans`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 43 | GET    | `/api/plans` | `repo/api/app/routes/plans.py:133` | `repo/api/tests/api/test_admin.py:98` | basic |
| 44 | POST   | `/api/plans` | `repo/api/app/routes/plans.py:149` | `repo/api/tests/api/test_plans.py:36,88,119,178,242,270,272,282`, `test_authz_post_audit.py:203,224`, `test_authz_post_audit_2.py:147,199`, `test_share_links_listing.py:12`, `test_security_headers.py:19` | covered |
| 45 | POST   | `/api/plans/{plan_id}/versions` | `repo/api/app/routes/plans.py:213` | `repo/api/tests/api/test_plans.py:54,132` | covered |
| 46 | GET    | `/api/plans/{plan_id}/versions/{version_id}` | `repo/api/app/routes/plans.py:276` | `repo/api/tests/api/test_plans.py:152`, `test_authz_post_audit.py:244` | covered |
| 47 | GET    | `/api/plans/{plan_id}/versions/{version_id}/diff` | `repo/api/app/routes/plans.py:296` | `repo/api/tests/api/test_plans.py:68`, `test_authz_post_audit.py:247` | covered |
| 48 | GET    | `/api/plans/{plan_id}/versions/{version_id}/export` | `repo/api/app/routes/plans.py:348` | `repo/api/tests/api/test_plans.py:97`, `test_authz_post_audit.py:251` | covered |
| 49 | POST   | `/api/plans/{plan_id}/versions/{version_id}/rollback` | `repo/api/app/routes/plans.py:399` | `repo/api/tests/api/test_plans.py:142` | covered |
| 50 | POST   | `/api/plans/{plan_id}/versions/{version_id}/share` | `repo/api/app/routes/plans.py:459` | `repo/api/tests/api/test_plans.py:190,250`, `test_share_links_listing.py:35,56,73`, `test_authz_post_audit_2.py:161,169,212` | covered |
| 51 | GET    | `/api/plans/share-links/mine` | `repo/api/app/routes/plans.py:508` | `repo/api/tests/api/test_share_links_listing.py:24,40,62,87` | covered |
| 52 | DELETE | `/api/plans/share-links/{link_id}` | `repo/api/app/routes/plans.py:535` | `repo/api/tests/api/test_plans.py:219`, `test_share_links_listing.py:60`, `test_authz_post_audit_2.py:221,225` | covered |

#### A.1.13 Share Resolve (`share`, prefix `/share`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 53 | GET | `/api/share/{token}` | `repo/api/app/routes/share.py:21` | `repo/api/tests/api/test_plans.py:212,229,257`, `test_authz_post_audit_2.py:179,183` | covered |

#### A.1.14 Model Registry (`models`, prefix `/models`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 54 | GET  | `/api/models` | `repo/api/app/routes/models.py:81` | `repo/api/tests/api/test_models.py:41`, `test_audit_r3.py:166` | covered |
| 55 | POST | `/api/models` | `repo/api/app/routes/models.py:104` | `repo/api/tests/api/test_models.py:17,51,104,217`, `test_audit_r4.py:63`, `test_experiment_routing_update.py:19`, `test_feedback.py:18`, `test_authz_post_audit_2.py:241`, `test_model_runs.py:21`, `test_metrics_warmup.py:24`, `test_security_headers.py:20` | covered |
| 56 | POST | `/api/models/{model_id}/versions` | `repo/api/app/routes/models.py:136` | `repo/api/tests/api/test_models.py:23,56,68,87,109,119,222`, `test_audit_r4.py:67`, `test_experiment_routing_update.py:23`, `test_feedback.py:23,33`, `test_authz_post_audit_2.py:245`, `test_model_runs.py:27`, `test_metrics_warmup.py:29` | covered |
| 57 | POST | `/api/models/{model_id}/versions/{version_id}/runs` | `repo/api/app/routes/models.py:201` | `repo/api/tests/api/test_model_runs.py:53,86,109`, `helpers.py:13` | covered |
| 58 | POST | `/api/models/{model_id}/versions/{version_id}/runs/{run_id}/complete` | `repo/api/app/routes/models.py:237` | `repo/api/tests/api/test_model_runs.py:62,91,96,114`, `helpers.py:19` | covered |
| 59 | GET  | `/api/models/{model_id}/versions/{version_id}/runs` | `repo/api/app/routes/models.py:283` | `repo/api/tests/api/test_model_runs.py:72`, `test_authz_post_audit_2.py:253` | covered |
| 60 | POST | `/api/models/{model_id}/versions/{version_id}/promote` | `repo/api/app/routes/models.py:305` | `repo/api/tests/api/test_model_runs.py:42,118`, `helpers.py:23` | covered |

#### A.1.15 Experiments (`experiments`, prefix `/experiments`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 61 | GET  | `/api/experiments` | `repo/api/app/routes/experiments.py:67` | `repo/api/tests/api/test_audit_r3.py:180` | basic |
| 62 | POST | `/api/experiments` | `repo/api/app/routes/experiments.py:94` | `repo/api/tests/api/test_models.py:130,232`, `test_experiment_routing_update.py:30`, `test_feedback.py:43`, `test_audit_r4.py:77`, `test_metrics_warmup.py:39`, `test_security_headers.py:21` | covered |
| 63 | POST | `/api/experiments/{experiment_id}/toggle` | `repo/api/app/routes/experiments.py:164` | `repo/api/tests/api/test_models.py:186,241`, `test_feedback.py:97,138` | covered |
| 64 | POST | `/api/experiments/{experiment_id}/routing` | `repo/api/app/routes/experiments.py:194` | `repo/api/tests/api/test_experiment_routing_update.py:46,70,81,90,100` | covered |
| 65 | POST | `/api/experiments/{experiment_id}/rollback` | `repo/api/app/routes/experiments.py:222` | `repo/api/tests/api/test_models.py:173`, `test_feedback.py:197` | covered |

#### A.1.16 Inference (`inference`, prefix `/inference`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 66 | POST | `/api/inference/predict` | `repo/api/app/routes/inference.py:25` | `repo/api/tests/api/test_models.py:144,158,191,245`, `test_audit_r4.py:105,135`, `test_metrics_warmup.py:49`, `repo/api/tests/load/test_inference_p95.py:88` (load) | covered |

#### A.1.17 Feedback (`feedback`, prefix `/feedback`)

| # | Method | Path | Declared At | Test File(s) | Status |
|---|--------|------|-------------|--------------|--------|
| 67 | POST | `/api/feedback` | `repo/api/app/routes/feedback.py:29` | `repo/api/tests/api/test_feedback.py:63,76,102,143,178,227`, `test_audit_r4.py:170,189`, `test_security_headers.py:22` | covered |
| 68 | GET  | `/api/feedback/signals/{experiment_id}` | `repo/api/app/routes/feedback.py:84` | `repo/api/tests/api/test_feedback.py:190,216` | covered |
| 69 | GET  | `/api/feedback/blocks/{subject_key}` | `repo/api/app/routes/feedback.py:117` | `repo/api/tests/api/test_feedback.py:162`, `test_authz_post_audit.py:269` | covered |

### A.2 Per-Endpoint Coverage Roll-Up

- **Total endpoints:** 69
- **covered:** 60
- **basic (happy-path only):** 8 (entries #9, #10, #21, #40, #42, #43, #61; plus #39 borderline but counted as covered)
- **missing:** 1 (entry #26 — `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}`)

Per-endpoint coverage percentage: **60 / 69 ≈ 87%** have success+failure payload-shape assertions.
Including basic happy-path: **68 / 69 ≈ 98.5%** have at least one direct test reference.

### A.3 Coverage Gaps (Minimum Test Additions)

| Gap | Endpoint | Where | Recommended Test |
|-----|----------|-------|------------------|
| G-1 | DELETE `/api/cycles/{cycle_id}/assignments/{assignment_id}` | `repo/api/app/routes/cycles.py:277` | Add API test in `test_cycles_lifecycle.py` asserting (a) 200 drop path with `PARTICIPANT_ADD_DROP` audit row, (b) 403 when caller lacks `cycle:manage`, (c) 404 for unknown assignment id |
| G-2 | GET `/api/admin/roles` | `repo/api/app/routes/admin_roles.py:16` | Add non-admin 403 test in `test_admin.py` |
| G-3 | GET `/api/admin/permissions` | `repo/api/app/routes/admin_roles.py:43` | Add non-admin 403 test |
| G-4 | GET `/api/cycles` | `repo/api/app/routes/cycles.py:67` | Add filter/sort/empty-result assertions beyond the audit smoke-read |
| G-5 | GET `/api/rule_sets` + POST `/api/rule_sets/{id}/versions` | `repo/api/app/routes/rule_sets.py:57,110` | Add permission-denied + version-conflict assertions |
| G-6 | GET `/api/plans` | `repo/api/app/routes/plans.py:133` | Add scope / permission negative test (non-plan-owner sees allowed subset only) |
| G-7 | GET `/api/experiments` | `repo/api/app/routes/experiments.py:67` | Add filter + authz negative |
| G-8 | Feedback arm-binding integrity (cross-cutting) | `repo/api/app/services/feedback.py:107-116` | Add `test_feedback.py` case: `POST /api/feedback` with `arm="A"` + `model_version_id` that matches arm B → expect 409 `feedback_arm_model_mismatch`. Matches `.tmp/audit_report-2.md:151` open finding |

### A.4 E2E Coverage (non-duplicative)

Playwright journeys under `repo/e2e/tests/` reference the `/api/*` surface 125 times across 13 files, covering browser flows for: login, cycle lifecycle, plan compare/share/revoke/rollback, model promote/routing/rollback, feedback predict+signal, and full-flow smoke. They complement API tests rather than substitute for per-endpoint payload assertions counted in A.2.

### A.5 Frontend Component Coverage (non-duplicative)

`repo/web/tests/component/` contains 17 Vitest suites covering each top-level view + cross-cutting components (TimelineBadge, EvaluationForm, BomDiffView, RoutingConsole, ShareLinkModal, FeedbackControl, DigestBanner, MaintenanceBanner, TraceViewer). These exercise client-side behavior and interact with the mocked API client at `repo/web/src/lib/api.ts`.

### A.6 Orchestration

- Entry script: `repo/run_tests.sh` — Docker-first, no Bash-level assertions.
- Tiers executed: backend unit, API integration, web component, E2E, load p95.
- Coverage artifacts: `coverage/api-coverage.xml`, `coverage/web-lcov/`, `e2e/playwright-report/`.
- Test overlay stack: `repo/docker-compose.test.yml`.

---

## Lane B — README Audit

- Source file: `repo/README.md` (159 lines).

### B.1 Structural Check

| Expected Section | Present? | Evidence |
|------------------|----------|----------|
| Title / one-line description | yes | `README.md:1-8` |
| Architecture / Tech Stack | yes | `README.md:10-18` |
| Project Structure tree | yes | `README.md:19-44` |
| Prerequisites | yes | `README.md:46-51` |
| Running the Application | yes | `README.md:53-88` (5 numbered steps + stop) |
| Testing | yes | `README.md:90-127` (script + tiers + artifacts) |
| Seeded Credentials | yes | `README.md:129-142` |
| Non-negotiables / Invariants | yes | `README.md:144-152` |
| Related Documents | yes | `README.md:154-158` |

### B.2 Factual / Freshness Check

| # | Claim | Location | Verdict | Evidence |
|---|-------|----------|---------|----------|
| R-1 | "alembic versions 0001 … 0009" | `repo/README.md:25` | **incorrect** | Repo has `0001…0011` under `repo/api/migrations/versions/`. Eleven migrations exist, not nine. Same finding as `.tmp/audit_report-2.md:205`. |
| R-2 | "First administrator provisioned via KEK-verified seed_admin CLI" | `repo/README.md:73-78` | accurate | `repo/api/app/scripts/seed_admin.py` exists and is invoked exactly as the README shows. |
| R-3 | "Frontend: http://localhost:8080" and "Backend API: http://localhost:8000/api" | `repo/README.md:81-82` | accurate | `repo/docker-compose.yml:39,53` publishes `8080:80` (web) and `8000:8000` (api). |
| R-4 | "API Documentation (dev only): http://localhost:8000/api/docs" | `repo/README.md:83` | accurate | `repo/api/app/app.py:65-67` exposes `/api/docs` only when `environment != "production"`. |
| R-5 | "Every mutating endpoint writes exactly one semantic audit_logs row" | `repo/README.md:149` | consistent with code | Audit writes present in all mutating routes (`plans.py`, `cycles.py`, `assignments.py`, `models.py`, `experiments.py`, `feedback.py`, `admin_backups.py`) — no static violations observed. |
| R-6 | "Template, rule-set, and plan versions are immutable once saved" | `repo/README.md:152` | consistent with code | No UPDATE routes for `template_versions`, `rule_set_versions`, `plan_versions`; rollback writes a new version rather than editing. |
| R-7 | "e2e_admin / E2E-Admin-Pass-1" credentials live only in the disposable test DB | `repo/README.md:141` | consistent with code | Seeded by `repo/run_tests.sh` against the test overlay stack only. |
| R-8 | Tier table (backend unit, API integration, frontend component, E2E, load gate) | `repo/README.md:110-116` | accurate | Matches the actual suite layout under `repo/api/tests/{unit,api,load}`, `repo/web/tests/component`, and `repo/e2e/tests`. |
| R-9 | "`plan.md` — phased implementation plan and testing protocol" | `repo/README.md:156` | needs manual check | Referenced path exists (`repo/plan.md`) per README. Content drift vs. actual phases is out of scope for this static pass. |
| R-10 | "No outbound network calls at runtime — everything works air-gapped" | `repo/README.md:148` | consistent | No HTTP client to external hosts observed in `repo/api/app/**`; docker-compose has no outbound bindings. |

### B.3 README Issues (single finding)

| # | Severity | Title | Evidence | Minimum Fix |
|---|----------|-------|----------|-------------|
| RM-1 | Low | Migration range is stale | `repo/README.md:25` says `alembic versions 0001 … 0009` but repo contains `0001…0011` | Change `0001 … 0009` → `0001 … 0011` at `repo/README.md:25`. Same issue tracked at `.tmp/audit_report-2.md:205`. |

All other structural and factual elements are consistent with the current repository.

---

## Final Verdicts

- **Lane A (Test Coverage): Partial Pass.** 98.5 % of API endpoints have at least one direct test, but one endpoint (`DELETE /api/cycles/.../assignments/{id}`) is untested, several others are happy-path only, and the feedback arm-binding integrity constraint (source audit-2 #2) has no regression test.
- **Lane B (README): Partial Pass.** Structure is complete and nearly all facts are accurate. One stale migration range statement remains.

## Open Items Tracked Elsewhere

The following items surfaced during this audit are tracked in the severity-rated source audits rather than duplicated here:

- Feedback arm-binding gap → `.tmp/audit_report-2.md:151` (status: open, per `.tmp/audit_report-2-fix_check.md` §2)
- Makeup cap `le=30` → `.tmp/audit_report-2.md:162` (status: open)
- Plan version copy workflow absent → `.tmp/audit_report-2.md:171` (status: open)
- Client subtotal / missing-strategy divergence → `.tmp/audit_report-2.md:184` (status: open)
- Digest banner not mounted at shell level → `.tmp/audit_report-2.md:195` (status: open)
- README migration range → `.tmp/audit_report-2.md:205` (status: open; surfaced again here as RM-1)
