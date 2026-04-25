# Test Coverage Audit

## Scope & Method
- Method: static inspection only (no test/runtime execution).
- Project type declaration: `fullstack` explicitly stated in README (`README.md:3`).
- Backend router root prefix: `/api` (`api/app/app.py:75-92`).

## Backend Endpoint Inventory

| # | Endpoint (METHOD + PATH) | Route evidence |
|---|---|---|
| 1 | `GET /api/health` | `api/app/routes/health.py:10` |
| 2 | `GET /api/health/ready` | `api/app/routes/health.py:15` |
| 3 | `POST /api/auth/login` | `api/app/routes/auth.py:49` |
| 4 | `POST /api/auth/logout` | `api/app/routes/auth.py:136` |
| 5 | `POST /api/auth/change-password` | `api/app/routes/auth.py:161` |
| 6 | `GET /api/auth/me` | `api/app/routes/auth.py:191` |
| 7 | `POST /api/auth/me/timezone` | `api/app/routes/auth.py:211` |
| 8 | `GET /api/admin/users` | `api/app/routes/admin_users.py:40` |
| 9 | `POST /api/admin/users` | `api/app/routes/admin_users.py:54` |
| 10 | `POST /api/admin/users/{user_id}/unlock` | `api/app/routes/admin_users.py:109` |
| 11 | `GET /api/admin/roles` | `api/app/routes/admin_roles.py:16` |
| 12 | `GET /api/admin/permissions` | `api/app/routes/admin_roles.py:43` |
| 13 | `GET /api/admin/audit/logs` | `api/app/routes/admin_audit.py:22` |
| 14 | `GET /api/admin/backups` | `api/app/routes/admin_backups.py:67` |
| 15 | `POST /api/admin/backups` | `api/app/routes/admin_backups.py:79` |
| 16 | `POST /api/admin/backups/{archive_id}/stage` | `api/app/routes/admin_backups.py:98` |
| 17 | `POST /api/admin/backups/{archive_id}/commit` | `api/app/routes/admin_backups.py:160` |
| 18 | `POST /api/admin/backups/{archive_id}/abort` | `api/app/routes/admin_backups.py:236` |
| 19 | `POST /api/admin/backups/prune` | `api/app/routes/admin_backups.py:270` |
| 20 | `GET /api/templates` | `api/app/routes/templates.py:33` |
| 21 | `POST /api/templates` | `api/app/routes/templates.py:47` |
| 22 | `POST /api/templates/{template_id}/versions` | `api/app/routes/templates.py:94` |
| 23 | `GET /api/cycles` | `api/app/routes/cycles.py:67` |
| 24 | `POST /api/cycles` | `api/app/routes/cycles.py:90` |
| 25 | `GET /api/cycles/digest` | `api/app/routes/cycles.py:159` |
| 26 | `GET /api/cycles/{cycle_id}/assignments` | `api/app/routes/cycles.py:190` |
| 27 | `POST /api/cycles/{cycle_id}/assignments` | `api/app/routes/cycles.py:216` |
| 28 | `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` | `api/app/routes/cycles.py:277` |
| 29 | `GET /api/assignments/{assignment_id}` | `api/app/routes/assignments.py:96` |
| 30 | `GET /api/assignments/{assignment_id}/form` | `api/app/routes/assignments.py:107` |
| 31 | `POST /api/assignments/{assignment_id}/save` | `api/app/routes/assignments.py:127` |
| 32 | `POST /api/assignments/{assignment_id}/submit` | `api/app/routes/assignments.py:157` |
| 33 | `POST /api/assignments/{assignment_id}/return` | `api/app/routes/assignments.py:226` |
| 34 | `POST /api/assignments/{assignment_id}/approve` | `api/app/routes/assignments.py:252` |
| 35 | `GET /api/assignments/mine/active` | `api/app/routes/assignments.py:277` |
| 36 | `GET /api/submissions/{submission_id}` | `api/app/routes/submissions.py:72` |
| 37 | `GET /api/submissions/{submission_id}/trace` | `api/app/routes/submissions.py:94` |
| 38 | `POST /api/submissions/{submission_id}/grades/{item_key}` | `api/app/routes/submissions.py:117` |
| 39 | `GET /api/plans` | `api/app/routes/plans.py:134` |
| 40 | `POST /api/plans` | `api/app/routes/plans.py:150` |
| 41 | `POST /api/plans/{plan_id}/versions` | `api/app/routes/plans.py:214` |
| 42 | `POST /api/plans/{plan_id}/versions/{version_id}/copy` | `api/app/routes/plans.py:277` |
| 43 | `GET /api/plans/{plan_id}/versions/{version_id}` | `api/app/routes/plans.py:337` |
| 44 | `GET /api/plans/{plan_id}/versions/{version_id}/diff` | `api/app/routes/plans.py:357` |
| 45 | `GET /api/plans/{plan_id}/versions/{version_id}/export` | `api/app/routes/plans.py:409` |
| 46 | `POST /api/plans/{plan_id}/versions/{version_id}/rollback` | `api/app/routes/plans.py:460` |
| 47 | `POST /api/plans/{plan_id}/versions/{version_id}/share` | `api/app/routes/plans.py:520` |
| 48 | `GET /api/plans/share-links/mine` | `api/app/routes/plans.py:569` |
| 49 | `DELETE /api/plans/share-links/{link_id}` | `api/app/routes/plans.py:596` |
| 50 | `GET /api/rule_sets` | `api/app/routes/rule_sets.py:57` |
| 51 | `POST /api/rule_sets` | `api/app/routes/rule_sets.py:73` |
| 52 | `POST /api/rule_sets/{rule_set_id}/versions` | `api/app/routes/rule_sets.py:110` |
| 53 | `GET /api/share/{token}` | `api/app/routes/share.py:21` |
| 54 | `GET /api/models` | `api/app/routes/models.py:81` |
| 55 | `POST /api/models` | `api/app/routes/models.py:104` |
| 56 | `POST /api/models/{model_id}/versions` | `api/app/routes/models.py:136` |
| 57 | `POST /api/models/{model_id}/versions/{version_id}/runs` | `api/app/routes/models.py:201` |
| 58 | `POST /api/models/{model_id}/versions/{version_id}/runs/{run_id}/complete` | `api/app/routes/models.py:237` |
| 59 | `GET /api/models/{model_id}/versions/{version_id}/runs` | `api/app/routes/models.py:283` |
| 60 | `POST /api/models/{model_id}/versions/{version_id}/promote` | `api/app/routes/models.py:305` |
| 61 | `GET /api/experiments` | `api/app/routes/experiments.py:67` |
| 62 | `POST /api/experiments` | `api/app/routes/experiments.py:94` |
| 63 | `POST /api/experiments/{experiment_id}/toggle` | `api/app/routes/experiments.py:164` |
| 64 | `POST /api/experiments/{experiment_id}/routing` | `api/app/routes/experiments.py:194` |
| 65 | `POST /api/experiments/{experiment_id}/rollback` | `api/app/routes/experiments.py:222` |
| 66 | `POST /api/inference/predict` | `api/app/routes/inference.py:25` |
| 67 | `GET /api/metrics` | `api/app/routes/metrics.py:10` |
| 68 | `POST /api/feedback` | `api/app/routes/feedback.py:29` |
| 69 | `GET /api/feedback/signals/{experiment_id}` | `api/app/routes/feedback.py:84` |
| 70 | `GET /api/feedback/blocks/{subject_key}` | `api/app/routes/feedback.py:117` |

## API Test Mapping Table

| Endpoint | Covered | Test type | Test files | Evidence (file + test ref) |
|---|---|---|---|---|
| `GET /api/health` | yes | true no-mock HTTP | `api/tests/api/test_health.py` | `test_health_liveness` |
| `GET /api/health/ready` | yes | true no-mock HTTP | `api/tests/api/test_health.py` | `test_health_ready_payload_shape` |
| `POST /api/auth/login` | yes | true no-mock HTTP | `api/tests/api/test_auth.py` | `test_login_returns_full_envelope` |
| `POST /api/auth/logout` | yes | true no-mock HTTP | `api/tests/api/test_auth.py` | `test_logout_revokes_session` |
| `POST /api/auth/change-password` | yes | true no-mock HTTP | `api/tests/api/test_auth.py` | `test_change_password_then_relogin` |
| `GET /api/auth/me` | yes | true no-mock HTTP | `api/tests/api/test_auth.py` | `test_me_returns_permissions_and_allowlist` |
| `POST /api/auth/me/timezone` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_user_timezone_round_trip` |
| `GET /api/admin/users` | yes | true no-mock HTTP | `api/tests/api/test_admin_users.py` | `test_admin_lists_users` |
| `POST /api/admin/users` | yes | true no-mock HTTP | `api/tests/api/test_admin_users.py` | `test_admin_creates_user_and_audits` |
| `POST /api/admin/users/{user_id}/unlock` | yes | true no-mock HTTP | `api/tests/api/test_user_management.py` | `test_unlock_user_clears_locked_until` |
| `GET /api/admin/roles` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `test_list_roles_and_permissions` |
| `GET /api/admin/permissions` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `test_list_roles_and_permissions` |
| `GET /api/admin/audit/logs` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `test_audit_log_filters_by_action_and_resource` |
| `GET /api/admin/backups` | yes | true no-mock HTTP | `api/tests/api/test_admin_backups_extended.py` | `test_list_backups_orders_newest_first` |
| `POST /api/admin/backups` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `test_backup_create_stage_commit_flow` |
| `POST /api/admin/backups/{archive_id}/stage` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `test_backup_create_stage_commit_flow` |
| `POST /api/admin/backups/{archive_id}/commit` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `test_backup_create_stage_commit_flow` |
| `POST /api/admin/backups/{archive_id}/abort` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `test_abort_leaves_state_untouched` |
| `POST /api/admin/backups/prune` | yes | true no-mock HTTP | `api/tests/api/test_admin_backups_extended.py` | `test_prune_removes_rows_older_than_retention` |
| `GET /api/templates` | yes | true no-mock HTTP | `api/tests/api/test_template_versions.py` | `test_list_templates_returns_latest_only_info` |
| `POST /api/templates` | yes | true no-mock HTTP | `api/tests/api/test_template_versions.py` | `test_publish_new_version_bumps_number` |
| `POST /api/templates/{template_id}/versions` | yes | true no-mock HTTP | `api/tests/api/test_template_versions.py` | `test_publish_new_version_bumps_number` |
| `GET /api/cycles` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_cycles_listing_empty_for_non_participant` |
| `POST /api/cycles` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `GET /api/cycles/digest` | yes | true no-mock HTTP | `api/tests/api/test_digest.py` | `test_digest_hidden_before_9am_and_shown_once_after` |
| `GET /api/cycles/{cycle_id}/assignments` | yes | true no-mock HTTP | `api/tests/api/test_authz_post_audit_2.py` | `test_cycle_assignment_listing_hides_other_participants` |
| `POST /api/cycles/{cycle_id}/assignments` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` | no | unit-only / indirect | none | no `delete` request match in `api/tests/api/*.py` |
| `GET /api/assignments/{assignment_id}` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_unassigned_reviewer_cannot_read_assignment_detail` |
| `GET /api/assignments/{assignment_id}/form` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_unassigned_reviewer_cannot_read_assignment_detail` |
| `POST /api/assignments/{assignment_id}/save` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `POST /api/assignments/{assignment_id}/submit` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `POST /api/assignments/{assignment_id}/return` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `POST /api/assignments/{assignment_id}/approve` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `GET /api/assignments/mine/active` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py` | `test_submit_after_deadline_without_makeup_rejected` |
| `GET /api/submissions/{submission_id}` | yes | true no-mock HTTP | `api/tests/api/test_submission_detail.py` | `test_submission_detail_payload_shape` |
| `GET /api/submissions/{submission_id}/trace` | yes | true no-mock HTTP | `api/tests/api/test_submission_detail.py` | `test_submission_trace_payload_shape` |
| `POST /api/submissions/{submission_id}/grades/{item_key}` | yes | true no-mock HTTP | `api/tests/api/test_submissions.py` | `test_grade_edit_audits_content_hash_not_raw` |
| `GET /api/plans` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `test_non_admin_forbidden_on_backup_endpoints` |
| `POST /api/plans` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_plan_lifecycle_create_version_compare` |
| `POST /api/plans/{plan_id}/versions` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_plan_lifecycle_create_version_compare` |
| `POST /api/plans/{plan_id}/versions/{version_id}/copy` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_copy_version_creates_sibling_with_same_lines` |
| `GET /api/plans/{plan_id}/versions/{version_id}` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_copy_version_creates_sibling_with_same_lines` |
| `GET /api/plans/{plan_id}/versions/{version_id}/diff` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_plan_lifecycle_create_version_compare` |
| `GET /api/plans/{plan_id}/versions/{version_id}/export` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_export_bundle_signature_verifies` |
| `POST /api/plans/{plan_id}/versions/{version_id}/rollback` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_rollback_creates_version_and_audits` |
| `POST /api/plans/{plan_id}/versions/{version_id}/share` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_share_link_issue_revoke_and_resolution` |
| `GET /api/plans/share-links/mine` | yes | true no-mock HTTP | `api/tests/api/test_share_links_listing.py` | `test_mine_returns_issued_links_with_expected_shape` |
| `DELETE /api/plans/share-links/{link_id}` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_share_link_issue_revoke_and_resolution` |
| `GET /api/rule_sets` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_rule_set_lifecycle_create_and_publish_version` |
| `POST /api/rule_sets` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_rule_set_lifecycle_create_and_publish_version` |
| `POST /api/rule_sets/{rule_set_id}/versions` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_rule_set_lifecycle_create_and_publish_version` |
| `GET /api/share/{token}` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `test_share_link_issue_revoke_and_resolution` |
| `GET /api/models` | yes | true no-mock HTTP | `api/tests/api/test_models.py` | `test_register_and_promote_first_version_pins_live_schema` |
| `POST /api/models` | yes | true no-mock HTTP | `api/tests/api/test_models.py` | `test_register_and_promote_first_version_pins_live_schema` |
| `POST /api/models/{model_id}/versions` | yes | true no-mock HTTP | `api/tests/api/test_models.py` | `test_register_and_promote_first_version_pins_live_schema` |
| `POST /api/models/{model_id}/versions/{version_id}/runs` | yes | true no-mock HTTP | `api/tests/api/test_model_runs.py` | `test_run_lifecycle_start_then_complete` |
| `POST /api/models/{model_id}/versions/{version_id}/runs/{run_id}/complete` | yes | true no-mock HTTP | `api/tests/api/test_model_runs.py` | `test_run_lifecycle_start_then_complete` |
| `GET /api/models/{model_id}/versions/{version_id}/runs` | yes | true no-mock HTTP | `api/tests/api/test_authz_post_audit_2.py` | `test_run_listing_requires_model_run_permission` |
| `POST /api/models/{model_id}/versions/{version_id}/promote` | yes | true no-mock HTTP | `api/tests/api/test_model_runs.py` | `test_promote_rejected_without_successful_evaluation_run` |
| `GET /api/experiments` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_experiments_listing_empty_for_unrelated_role` |
| `POST /api/experiments` | yes | true no-mock HTTP | `api/tests/api/test_models.py` | `test_experiment_routing_predict_and_rollback` |
| `POST /api/experiments/{experiment_id}/toggle` | yes | true no-mock HTTP | `api/tests/api/test_models.py` | `test_predict_blocked_when_apply_disabled` |
| `POST /api/experiments/{experiment_id}/routing` | yes | true no-mock HTTP | `api/tests/api/test_experiment_routing_update.py` | `test_routing_update_changes_weights_and_audits` |
| `POST /api/experiments/{experiment_id}/rollback` | yes | true no-mock HTTP | `api/tests/api/test_models.py` | `test_experiment_routing_predict_and_rollback` |
| `POST /api/inference/predict` | yes | true no-mock HTTP | `api/tests/api/test_audit_r4.py` | `test_inference_allowed_with_feedback_submit` |
| `GET /api/metrics` | yes | true no-mock HTTP | `api/tests/api/test_models.py` | `test_metrics_endpoint_shape` |
| `POST /api/feedback` | yes | true no-mock HTTP | `api/tests/api/test_feedback.py` | `test_rate_limit_60_per_minute_per_subject` |
| `GET /api/feedback/signals/{experiment_id}` | yes | true no-mock HTTP | `api/tests/api/test_feedback.py` | `test_rollback_preserves_events_and_isolates_arms` |
| `GET /api/feedback/blocks/{subject_key}` | yes | true no-mock HTTP | `api/tests/api/test_feedback.py` | `test_block_persists_independently_of_toggle` |

## API Test Classification

1. True No-Mock HTTP
- `api/tests/api/conftest.py:73-114` uses real `httpx.AsyncClient(base_url=api_base_url)`.
- `api/tests/api/*.py` send real HTTP requests to `/api/...` endpoints.
- `api/tests/load/test_inference_p95.py:90-132` performs real HTTP load requests.
- `e2e/tests/helpers/auth.ts:22-24` and related Playwright request flows use real `/api` endpoints.

2. HTTP with Mocking
- None detected in backend/API HTTP suites.

3. Non-HTTP (unit/integration without HTTP)
- Backend unit: `api/tests/unit/*.py` (pure function/service-level).
- Frontend unit/component: `web/tests/component/*.test.ts`.

## Mock Detection

### API-layer mock check (required rules)
- `jest.mock`, `vi.mock`, `sinon.stub`, dependency-overrides, service/controller stubs in `api/tests/api`: not found.
- Evidence: global scan only found `monkeypatch` in unit tests, not API tests.

### Detected mocking outside API layer
- Frontend component/unit tests mock transport (`fetch`):
  - `web/tests/component/AppShell.test.ts:41-48` (`vi.stubGlobal("fetch", ...)`)
  - `web/tests/component/LoginView.test.ts:30` (`vi.stubGlobal("fetch", ...)`)
  - `web/tests/component/api.test.ts` (`fetch` mocked for client behavior)
  - `web/tests/component/session.test.ts:9` (`vi.stubGlobal("fetch", ...)`)

## Coverage Summary
- Total backend endpoints: **70**
- Endpoints with HTTP tests: **69**
- Endpoints with true no-mock HTTP tests: **69**
- HTTP coverage: **98.57%**
- True API coverage: **98.57%**

Uncovered endpoint:
- `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` (`api/app/routes/cycles.py:277`)

## Unit Test Summary

### Backend Unit Tests
- Test files: `api/tests/unit/test_*.py` (20 files).
- Modules covered (evidence by file naming/imports):
  - services: scoring, guardrail, lockout, masking, routing, business_days, backup_archive, plan_export, model_schema, share_tokens, state_machine, session_tokens, passwords, canonical, bom_diff.
  - core: settings, error envelope.
  - auth/rbac logic: `test_rbac.py`.
- Important backend modules NOT unit-tested (direct unit evidence absent):
  - `api/app/services/inference.py`
  - `api/app/services/submissions.py`
  - `api/app/services/auth_context.py`
  - `api/app/services/metrics.py`
  - `api/app/services/maintenance.py`
  - `api/app/services/backup_scheduler.py`
  - `api/app/services/audit.py`
  - middleware units: `api/app/middleware/auth.py`, `maintenance.py`, `request_context.py`

### Frontend Unit Tests (STRICT)
- Frontend test files detected: `web/tests/component/*.test.ts` (18 files).
- Framework/tools detected:
  - Vitest (`web/package.json`, `scripts.test:component`)
  - `@vue/test-utils` (`web/package.json`, imports in component tests)
  - jsdom (`web/package.json`)
- Components/modules covered (direct file evidence):
  - Components: `AppShell`, `RoutingConsole`, `EvaluationForm`, `TimelineBadge`, `MaintenanceBanner`, `FeedbackControl`, `ShareLinkModal`, `TraceViewer`, `DigestBanner`, `BomDiffView`.
  - Views: `LoginView`, `PlansView`, `ModelsView`, `CyclesView`, `AdminView`.
  - Frontend logic modules: `web/src/lib/api.ts`, `web/src/stores/session.ts`.
- Important frontend modules NOT tested (direct test-file evidence absent):
  - `web/src/views/DashboardView.vue`
  - `web/src/views/AssignmentFormView.vue`
  - `web/src/views/FeedbackView.vue`
  - `web/src/router/index.ts`

**Frontend unit tests: PRESENT**

### Cross-Layer Observation
- Backend and frontend both have substantial tests (API + unit + component + E2E).
- Coverage is backend-heavy in endpoint rigor; frontend has good component breadth but some key views/router lack direct tests.

## API Observability Check
- Observability quality: **strong overall**.
- Evidence of explicit request + response assertions:
  - Request payloads asserted in API tests (e.g., `api/tests/api/test_plans.py`, `test_models.py`).
  - Response envelope/status/content assertions are explicit (e.g., `api/tests/api/test_auth.py`, `test_submission_detail.py`, `test_security_headers.py`).
- Weakness noted:
  - One endpoint entirely unexercised (`DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}`), so no observability for that behavior.

## Tests Check
- Success paths: present across core domains (auth, plans, models, cycles, feedback).
- Failure/validation paths: strong (401/403/404/409/423/429 cases present).
- Auth/permissions checks: strong (`test_authz_post_audit*.py`, `test_security_headers.py`).
- Integration boundaries: present via true HTTP API tests and Playwright E2E request/browser journeys.
- Over-mocking risk: low in backend API tests; frontend component tests intentionally mock `fetch`.

### `run_tests.sh` compliance
- Docker-based orchestration: **OK** (`run_tests.sh:14-91`).
- Local dependency install steps in script: **not detected**.

## Test Coverage Score (0–100)
- **90/100**

## Score Rationale
- + Very high true HTTP endpoint coverage.
- + Strong negative-path and authz validation depth.
- + Multi-layer strategy (unit + API + E2E + load).
- - One real route is untested (`DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}`).
- - Some important backend services/middleware lack direct unit tests.
- - Some frontend critical views/router lack direct unit coverage.

## Key Gaps
1. Missing test coverage for `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` (critical endpoint-level gap).
2. Missing direct unit tests for inference/submissions/maintenance/audit/auth-context service logic.
3. Missing direct frontend unit tests for `DashboardView`, `AssignmentFormView`, `FeedbackView`, and router guards.

## Confidence & Assumptions
- Confidence: **high** for static endpoint/test mapping.
- Assumptions:
  - Endpoint coverage counted only when explicit method+path request evidence exists in test code.
  - Indirect UI-triggered API calls were not counted unless explicit request evidence was visible.

## Test Coverage Verdict
- **PARTIAL PASS** (high coverage, but not complete; one backend endpoint uncovered).

---

# README Audit

## README Location Check
- Required path exists: `README.md` (project root).

## Hard Gate Evaluation

### Formatting
- Pass: Markdown is structured and readable.

### Startup Instructions (fullstack requirement)
- **FAIL (Hard Gate)**
- Requirement: must include `docker-compose up` explicitly.
- Found: `docker compose up --build -d` (`README.md:70`), but not explicit `docker-compose up` string.

### Access Method
- Pass: frontend/backend URLs + ports are present (`README.md:80-83`).

### Verification Method
- **FAIL (Hard Gate)**
- Missing explicit "how to confirm system works" steps (e.g., curl/Postman API verification or explicit UI verification flow after startup).
- Existing text describes test runner tiers (`README.md:90-117`) but not a concrete post-start verification procedure.

### Environment Rules (Docker-contained)
- Pass: README does not instruct `npm install`, `pip install`, `apt-get`, runtime installs, or manual DB setup.

### Demo Credentials (auth conditional)
- **FAIL (Hard Gate)**
- Auth clearly exists (login endpoints/tests). README provides admin and e2e admin credentials, but does not provide concrete username/password pairs for **all roles** listed.
- Evidence: role row uses "created by admin / chosen on create" for Evaluator/Reviewer/Plan Owner/ML Engineer (`README.md:142`).

## Engineering Quality
- Tech stack clarity: strong (`README.md:10-17`).
- Architecture/project structure clarity: strong (`README.md:19-44`).
- Testing instruction quality: strong (`README.md:90-127`).
- Security/roles explanation: moderate (roles named, but credential completeness fails hard gate).
- Operational workflow quality: moderate-high.
- Presentation quality: high.

## High Priority Issues
1. Missing required explicit `docker-compose up` startup command string.
2. Missing explicit verification procedure for confirming successful startup behavior.
3. Missing complete role credential matrix (username/email + password for all roles when auth exists).

## Medium Priority Issues
1. Startup section mixes operator steps and local walkthrough but does not provide explicit "expected success output" checks.
2. Role provisioning text is policy-oriented but not strict-demo-oriented.

## Low Priority Issues
1. No quick troubleshooting subsection for common startup failures.

## Hard Gate Failures
1. Startup Instructions gate: failed.
2. Verification Method gate: failed.
3. Demo Credentials gate: failed.

## README Verdict
- **FAIL**

---

## Final Combined Verdict
- Test Coverage Audit: **PARTIAL PASS**
- README Audit: **FAIL**
- Overall strict audit outcome: **FAIL**

## Output Path Note
- Requested output path `/.tmp/test_coverage_and_readme_audit_report.md` is not writable in this environment (root filesystem is read-only).
- Report written to:
  - `/tmp/test_coverage_and_readme_audit_report.md`
  - `./.tmp/test_coverage_and_readme_audit_report.md`
