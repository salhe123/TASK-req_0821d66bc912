# Test Coverage Audit

## Project Type Detection
- README declaration: `fullstack` is explicitly stated at top (`README.md`, line 3: "A fullstack, offline-first web application...").
- Effective type used for audit: **fullstack**.

## Backend Endpoint Inventory
Resolved from `api/app/app.py` router mounting (`/api` prefix) and route decorators in `api/app/routes/*.py`.

1. `GET /api/admin/audit/logs` (`api/app/routes/admin_audit.py::list_audit_logs`)
2. `GET /api/admin/backups` (`api/app/routes/admin_backups.py::list_backups`)
3. `POST /api/admin/backups` (`api/app/routes/admin_backups.py::create_archive_now`)
4. `POST /api/admin/backups/{archive_id}/stage` (`api/app/routes/admin_backups.py::stage_restore`)
5. `POST /api/admin/backups/{archive_id}/commit` (`api/app/routes/admin_backups.py::commit_restore`)
6. `POST /api/admin/backups/{archive_id}/abort` (`api/app/routes/admin_backups.py::abort_restore`)
7. `POST /api/admin/backups/prune` (`api/app/routes/admin_backups.py::prune_backups`)
8. `GET /api/admin/roles` (`api/app/routes/admin_roles.py::list_roles`)
9. `GET /api/admin/permissions` (`api/app/routes/admin_roles.py::list_permissions`)
10. `GET /api/admin/users` (`api/app/routes/admin_users.py::list_users`)
11. `POST /api/admin/users` (`api/app/routes/admin_users.py::create_user`)
12. `POST /api/admin/users/{user_id}/unlock` (`api/app/routes/admin_users.py::unlock_user`)
13. `GET /api/assignments/{assignment_id}` (`api/app/routes/assignments.py::get_assignment`)
14. `GET /api/assignments/{assignment_id}/form` (`api/app/routes/assignments.py::get_assignment_form`)
15. `POST /api/assignments/{assignment_id}/save` (`api/app/routes/assignments.py::save_draft`)
16. `POST /api/assignments/{assignment_id}/submit` (`api/app/routes/assignments.py::submit`)
17. `POST /api/assignments/{assignment_id}/return` (`api/app/routes/assignments.py::return_for_revision`)
18. `POST /api/assignments/{assignment_id}/approve` (`api/app/routes/assignments.py::approve`)
19. `GET /api/assignments/mine/active` (`api/app/routes/assignments.py::my_active`)
20. `POST /api/auth/login` (`api/app/routes/auth.py::login`)
21. `POST /api/auth/logout` (`api/app/routes/auth.py::logout`)
22. `POST /api/auth/change-password` (`api/app/routes/auth.py::change_password`)
23. `GET /api/auth/me` (`api/app/routes/auth.py::me`)
24. `POST /api/auth/me/timezone` (`api/app/routes/auth.py::update_timezone`)
25. `GET /api/cycles` (`api/app/routes/cycles.py::list_cycles`)
26. `POST /api/cycles` (`api/app/routes/cycles.py::create_cycle`)
27. `GET /api/cycles/digest` (`api/app/routes/cycles.py::get_digest`)
28. `GET /api/cycles/{cycle_id}/assignments` (`api/app/routes/cycles.py::list_assignments`)
29. `POST /api/cycles/{cycle_id}/assignments` (`api/app/routes/cycles.py::add_assignment`)
30. `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` (`api/app/routes/cycles.py::drop_assignment`)
31. `GET /api/experiments` (`api/app/routes/experiments.py::list_experiments`)
32. `POST /api/experiments` (`api/app/routes/experiments.py::create_experiment`)
33. `POST /api/experiments/{experiment_id}/toggle` (`api/app/routes/experiments.py::toggle`)
34. `POST /api/experiments/{experiment_id}/routing` (`api/app/routes/experiments.py::update_routing`)
35. `POST /api/experiments/{experiment_id}/rollback` (`api/app/routes/experiments.py::rollback`)
36. `POST /api/feedback` (`api/app/routes/feedback.py::submit_feedback`)
37. `GET /api/feedback/signals/{experiment_id}` (`api/app/routes/feedback.py::get_signals`)
38. `GET /api/feedback/blocks/{subject_key}` (`api/app/routes/feedback.py::get_blocks`)
39. `GET /api/health` (`api/app/routes/health.py::health`)
40. `GET /api/health/ready` (`api/app/routes/health.py::health_ready`)
41. `POST /api/inference/predict` (`api/app/routes/inference.py::predict`)
42. `GET /api/metrics` (`api/app/routes/metrics.py::get_metrics`)
43. `GET /api/models` (`api/app/routes/models.py::list_models`)
44. `POST /api/models` (`api/app/routes/models.py::create_model`)
45. `POST /api/models/{model_id}/versions` (`api/app/routes/models.py::register_version`)
46. `POST /api/models/{model_id}/versions/{version_id}/runs` (`api/app/routes/models.py::start_run`)
47. `POST /api/models/{model_id}/versions/{version_id}/runs/{run_id}/complete` (`api/app/routes/models.py::complete_run`)
48. `GET /api/models/{model_id}/versions/{version_id}/runs` (`api/app/routes/models.py::list_runs`)
49. `POST /api/models/{model_id}/versions/{version_id}/promote` (`api/app/routes/models.py::promote_version`)
50. `GET /api/plans` (`api/app/routes/plans.py::list_plans`)
51. `POST /api/plans` (`api/app/routes/plans.py::create_plan`)
52. `POST /api/plans/{plan_id}/versions` (`api/app/routes/plans.py::create_version`)
53. `POST /api/plans/{plan_id}/versions/{version_id}/copy` (`api/app/routes/plans.py::copy_version`)
54. `GET /api/plans/{plan_id}/versions/{version_id}` (`api/app/routes/plans.py::get_version`)
55. `GET /api/plans/{plan_id}/versions/{version_id}/diff` (`api/app/routes/plans.py::compare_version`)
56. `GET /api/plans/{plan_id}/versions/{version_id}/export` (`api/app/routes/plans.py::export_bundle`)
57. `POST /api/plans/{plan_id}/versions/{version_id}/rollback` (`api/app/routes/plans.py::rollback_version`)
58. `POST /api/plans/{plan_id}/versions/{version_id}/share` (`api/app/routes/plans.py::issue_share_link`)
59. `GET /api/plans/share-links/mine` (`api/app/routes/plans.py::list_my_share_links`)
60. `DELETE /api/plans/share-links/{link_id}` (`api/app/routes/plans.py::revoke_share_link`)
61. `GET /api/rule_sets` (`api/app/routes/rule_sets.py::list_rule_sets`)
62. `POST /api/rule_sets` (`api/app/routes/rule_sets.py::create_rule_set`)
63. `POST /api/rule_sets/{rule_set_id}/versions` (`api/app/routes/rule_sets.py::publish_version`)
64. `GET /api/share/{token}` (`api/app/routes/share.py::resolve_share`)
65. `GET /api/submissions/{submission_id}` (`api/app/routes/submissions.py::get_submission`)
66. `GET /api/submissions/{submission_id}/trace` (`api/app/routes/submissions.py::get_trace`)
67. `POST /api/submissions/{submission_id}/grades/{item_key}` (`api/app/routes/submissions.py::edit_grade`)
68. `GET /api/templates` (`api/app/routes/templates.py::list_templates`)
69. `POST /api/templates` (`api/app/routes/templates.py::create_template`)
70. `POST /api/templates/{template_id}/versions` (`api/app/routes/templates.py::publish_version`)

## API Test Mapping Table

| Endpoint | Covered | Test Type | Test Files | Evidence |
|---|---|---|---|---|
| `GET /api/admin/audit/logs` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `api/tests/api/test_admin.py:44` |
| `GET /api/admin/backups` | yes | true no-mock HTTP | `api/tests/api/test_admin.py`, `api/tests/api/test_admin_backups_extended.py` | `api/tests/api/test_admin.py:58` |
| `POST /api/admin/backups` | yes | true no-mock HTTP | `api/tests/api/test_admin.py`, `e2e/tests/ui_admin_journey.spec.ts` | `api/tests/api/test_admin.py:58` |
| `POST /api/admin/backups/{archive_id}/stage` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `api/tests/api/test_admin.py:58` |
| `POST /api/admin/backups/{archive_id}/commit` | yes | true no-mock HTTP | `api/tests/api/test_admin.py`, `api/tests/api/test_admin_backups_extended.py` | `api/tests/api/test_admin.py:58` |
| `POST /api/admin/backups/{archive_id}/abort` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `api/tests/api/test_admin.py:132` |
| `POST /api/admin/backups/prune` | yes | true no-mock HTTP | `api/tests/api/test_admin_backups_extended.py`, `api/tests/api/test_audit_r4.py` | `api/tests/api/test_admin_backups_extended.py:28` |
| `GET /api/admin/roles` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `api/tests/api/test_admin.py:14` |
| `GET /api/admin/permissions` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `api/tests/api/test_admin.py:14` |
| `GET /api/admin/users` | yes | true no-mock HTTP | `api/tests/api/test_admin_users.py`, `api/tests/api/test_user_management.py` | `api/tests/api/test_admin_users.py:31` |
| `POST /api/admin/users` | yes | true no-mock HTTP | `api/tests/api/test_admin_users.py`, `e2e/tests/helpers/auth.ts` | `api/tests/api/test_admin_users.py:57` |
| `POST /api/admin/users/{user_id}/unlock` | yes | true no-mock HTTP | `api/tests/api/test_user_management.py` | `api/tests/api/test_user_management.py:77` |
| `GET /api/assignments/{assignment_id}` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_unassigned_reviewer_cannot_read_assignment_detail` |
| `GET /api/assignments/{assignment_id}/form` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_unassigned_reviewer_cannot_read_assignment_detail` |
| `POST /api/assignments/{assignment_id}/save` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py`, `e2e/tests/cycle_lifecycle.spec.ts` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `POST /api/assignments/{assignment_id}/submit` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py`, `api/tests/api/test_submissions.py` | `test_submit_writes_trace_and_returns_hash` |
| `POST /api/assignments/{assignment_id}/return` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py`, `e2e/tests/ui_cycles_journey.spec.ts` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `POST /api/assignments/{assignment_id}/approve` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py`, `e2e/tests/ui_cycles_journey.spec.ts` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `GET /api/assignments/mine/active` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py`, `api/tests/api/test_submissions.py` | `test_submit_after_deadline_without_makeup_rejected` |
| `POST /api/auth/login` | yes | true no-mock HTTP | `api/tests/api/test_auth.py`, `e2e/tests/helpers/auth.ts` | `test_login_returns_full_envelope` |
| `POST /api/auth/logout` | yes | true no-mock HTTP | `api/tests/api/test_auth.py` | `test_logout_revokes_session` |
| `POST /api/auth/change-password` | yes | true no-mock HTTP | `api/tests/api/test_auth.py` | `test_change_password_then_relogin` |
| `GET /api/auth/me` | yes | true no-mock HTTP | `api/tests/api/test_auth.py`, `api/tests/api/test_audit_r3.py` | `test_me_returns_permissions_and_allowlist` |
| `POST /api/auth/me/timezone` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_user_timezone_round_trip` |
| `GET /api/cycles` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_cycles_listing_empty_for_non_participant` |
| `POST /api/cycles` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py`, `e2e/tests/cycle_lifecycle.spec.ts` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `GET /api/cycles/digest` | yes | true no-mock HTTP | `api/tests/api/test_digest.py` | `api/tests/api/test_digest.py:84` |
| `GET /api/cycles/{cycle_id}/assignments` | yes | true no-mock HTTP | `api/tests/api/test_authz_post_audit_2.py` | `api/tests/api/test_authz_post_audit_2.py:118` |
| `POST /api/cycles/{cycle_id}/assignments` | yes | true no-mock HTTP | `api/tests/api/test_cycles_lifecycle.py`, `e2e/tests/cycle_lifecycle.spec.ts` | `test_full_lifecycle_with_return_then_resubmit_then_archive` |
| `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` | **no** | unit-only / indirect | none | no matching request in `api/tests/api` or `e2e/tests` |
| `GET /api/experiments` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_experiments_listing_empty_for_unrelated_role` |
| `POST /api/experiments` | yes | true no-mock HTTP | `api/tests/api/test_models.py`, `e2e/tests/model_flow.spec.ts` | `test_experiment_routing_predict_and_rollback` |
| `POST /api/experiments/{experiment_id}/toggle` | yes | true no-mock HTTP | `api/tests/api/test_feedback.py`, `e2e/tests/model_flow.spec.ts` | `test_ingest_disabled_records_event_but_not_signal` |
| `POST /api/experiments/{experiment_id}/routing` | yes | true no-mock HTTP | `api/tests/api/test_experiment_routing_update.py`, `e2e/tests/model_flow.spec.ts` | `test_routing_update_changes_weights_and_audits` |
| `POST /api/experiments/{experiment_id}/rollback` | yes | true no-mock HTTP | `api/tests/api/test_models.py`, `api/tests/api/test_feedback.py` | `test_experiment_routing_predict_and_rollback` |
| `POST /api/feedback` | yes | true no-mock HTTP | `api/tests/api/test_feedback.py`, `e2e/tests/feedback_flow.spec.ts` | `test_rate_limit_60_per_minute_per_subject` |
| `GET /api/feedback/signals/{experiment_id}` | yes | true no-mock HTTP | `api/tests/api/test_feedback.py`, `e2e/tests/feedback_flow.spec.ts` | `test_rollback_preserves_events_and_isolates_arms` |
| `GET /api/feedback/blocks/{subject_key}` | yes | true no-mock HTTP | `api/tests/api/test_feedback.py`, `api/tests/api/test_authz_post_audit.py` | `test_block_persists_independently_of_toggle` |
| `GET /api/health` | yes | true no-mock HTTP | `api/tests/api/test_health.py`, `e2e/tests/smoke.spec.ts` | `api/tests/api/test_health.py:8` |
| `GET /api/health/ready` | yes | true no-mock HTTP | `api/tests/api/test_health.py` | `api/tests/api/test_health.py:18` |
| `POST /api/inference/predict` | yes | true no-mock HTTP | `api/tests/api/test_models.py`, `e2e/tests/model_flow.spec.ts` | `test_experiment_routing_predict_and_rollback` |
| `GET /api/metrics` | yes | true no-mock HTTP | `api/tests/api/test_metrics_warmup.py`, `api/tests/api/test_models.py` | `test_metrics_endpoint_shape` |
| `GET /api/models` | yes | true no-mock HTTP | `api/tests/api/test_models.py`, `e2e/tests/model_flow.spec.ts` | `test_register_and_promote_first_version_pins_live_schema` |
| `POST /api/models` | yes | true no-mock HTTP | `api/tests/api/test_models.py`, `api/tests/api/test_model_runs.py` | `test_promote_blocked_on_schema_mismatch` |
| `POST /api/models/{model_id}/versions` | yes | true no-mock HTTP | `api/tests/api/test_models.py`, `api/tests/api/test_model_runs.py` | `test_run_lifecycle_start_then_complete` |
| `POST /api/models/{model_id}/versions/{version_id}/runs` | yes | true no-mock HTTP | `api/tests/api/test_model_runs.py`, `e2e/tests/helpers/auth.ts` | `test_run_lifecycle_start_then_complete` |
| `POST /api/models/{model_id}/versions/{version_id}/runs/{run_id}/complete` | yes | true no-mock HTTP | `api/tests/api/test_model_runs.py`, `e2e/tests/helpers/auth.ts` | `test_run_lifecycle_start_then_complete` |
| `GET /api/models/{model_id}/versions/{version_id}/runs` | yes | true no-mock HTTP | `api/tests/api/test_model_runs.py`, `api/tests/api/test_authz_post_audit_2.py` | `test_run_lifecycle_start_then_complete` |
| `POST /api/models/{model_id}/versions/{version_id}/promote` | yes | true no-mock HTTP | `api/tests/api/test_models.py`, `api/tests/api/test_model_runs.py` | `test_promote_rejected_without_successful_evaluation_run` |
| `GET /api/plans` | yes | true no-mock HTTP | `api/tests/api/test_admin.py` | `api/tests/api/test_admin.py:98` |
| `POST /api/plans` | yes | true no-mock HTTP | `api/tests/api/test_plans.py`, `e2e/tests/plan_flow.spec.ts` | `test_plan_lifecycle_create_version_compare` |
| `POST /api/plans/{plan_id}/versions` | yes | true no-mock HTTP | `api/tests/api/test_plans.py`, `e2e/tests/plan_flow.spec.ts` | `test_plan_lifecycle_create_version_compare` |
| `POST /api/plans/{plan_id}/versions/{version_id}/copy` | yes | true no-mock HTTP | `api/tests/api/test_plans.py` | `api/tests/api/test_plans.py:300` |
| `GET /api/plans/{plan_id}/versions/{version_id}` | yes | true no-mock HTTP | `api/tests/api/test_plans.py`, `api/tests/api/test_authz_post_audit.py` | `test_rollback_creates_version_and_audits` |
| `GET /api/plans/{plan_id}/versions/{version_id}/diff` | yes | true no-mock HTTP | `api/tests/api/test_plans.py`, `e2e/tests/plan_flow.spec.ts` | `test_plan_lifecycle_create_version_compare` |
| `GET /api/plans/{plan_id}/versions/{version_id}/export` | yes | true no-mock HTTP | `api/tests/api/test_plans.py`, `e2e/tests/plan_flow.spec.ts` | `test_export_bundle_signature_verifies` |
| `POST /api/plans/{plan_id}/versions/{version_id}/rollback` | yes | true no-mock HTTP | `api/tests/api/test_plans.py`, `e2e/tests/plan_flow.spec.ts` | `test_rollback_creates_version_and_audits` |
| `POST /api/plans/{plan_id}/versions/{version_id}/share` | yes | true no-mock HTTP | `api/tests/api/test_plans.py`, `e2e/tests/plan_flow.spec.ts` | `test_share_link_issue_revoke_and_resolution` |
| `GET /api/plans/share-links/mine` | yes | true no-mock HTTP | `api/tests/api/test_share_links_listing.py` | `api/tests/api/test_share_links_listing.py:24` |
| `DELETE /api/plans/share-links/{link_id}` | yes | true no-mock HTTP | `api/tests/api/test_share_links_listing.py`, `api/tests/api/test_plans.py` | `api/tests/api/test_share_links_listing.py:60` |
| `GET /api/rule_sets` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_rule_set_lifecycle_create_and_publish_version` |
| `POST /api/rule_sets` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_rule_set_lifecycle_create_and_publish_version` |
| `POST /api/rule_sets/{rule_set_id}/versions` | yes | true no-mock HTTP | `api/tests/api/test_audit_r3.py` | `test_rule_set_lifecycle_create_and_publish_version` |
| `GET /api/share/{token}` | yes | true no-mock HTTP | `api/tests/api/test_plans.py`, `e2e/tests/plan_flow.spec.ts` | `test_share_link_issue_revoke_and_resolution` |
| `GET /api/submissions/{submission_id}` | yes | true no-mock HTTP | `api/tests/api/test_submission_detail.py`, `api/tests/api/test_authz_post_audit.py` | `test_submission_detail_payload_shape` |
| `GET /api/submissions/{submission_id}/trace` | yes | true no-mock HTTP | `api/tests/api/test_submission_detail.py`, `api/tests/api/test_submissions.py` | `test_submission_trace_payload_shape` |
| `POST /api/submissions/{submission_id}/grades/{item_key}` | yes | true no-mock HTTP | `api/tests/api/test_submissions.py` | `test_grade_edit_audits_content_hash_not_raw` |
| `GET /api/templates` | yes | true no-mock HTTP | `api/tests/api/test_template_versions.py`, `api/tests/api/test_audit_r3.py` | `test_list_templates_returns_latest_only_info` |
| `POST /api/templates` | yes | true no-mock HTTP | `api/tests/api/test_template_versions.py`, `e2e/tests/cycle_lifecycle.spec.ts` | `test_template_name_conflict` |
| `POST /api/templates/{template_id}/versions` | yes | true no-mock HTTP | `api/tests/api/test_template_versions.py` | `test_publish_new_version_bumps_number` |

## API Test Classification
1. **True No-Mock HTTP**
- `api/tests/api/*` (httpx clients pointed at `API_BASE_URL`; requests traverse live HTTP stack)
- `e2e/tests/*` Playwright API calls via nginx proxy to backend
- Evidence: `api/tests/api/conftest.py::admin_client`, `api/tests/api/conftest.py::evaluator_client`, `e2e/tests/helpers/auth.ts` comments and real `/api/auth/login` calls.

2. **HTTP with Mocking**
- Backend API tier: **none found**.
- Frontend component tier does mocked fetch HTTP-like behavior (not real API execution): `web/tests/component/*.test.ts` using `vi.stubGlobal("fetch", ...)` and `mockResolvedValueOnce`.

3. **Non-HTTP (unit/integration without HTTP)**
- `api/tests/unit/*` pure unit tests of service/core logic.
- `web/tests/component/*` component/unit tests using Vue Test Utils + Vitest with mocked transport.

## Mock Detection
- Backend API tests (`api/tests/api`, `e2e/tests`): no `jest.mock`, `vi.mock`, `sinon.stub`, `dependency_overrides`, or service stubbing detected.
- Frontend unit tests use mocked transport:
  - `web/tests/component/LoginView.test.ts`: `vi.stubGlobal("fetch", vi.fn())`
  - `web/tests/component/PlansView.test.ts`: `mockFetch(...)` + mocked responses
  - `web/tests/component/AppShell.test.ts`: `m.mockImplementation(...)`

## Coverage Summary
- Total backend endpoints: **70**
- Endpoints with HTTP tests: **69**
- Endpoints with true no-mock HTTP tests: **69**
- HTTP coverage: **98.57%** (`69/70`)
- True API coverage: **98.57%** (`69/70`)
- Uncovered endpoint:
  - `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}` (`api/app/routes/cycles.py::drop_assignment`)

## Unit Test Summary

### Backend Unit Tests
- Files: `api/tests/unit/test_*.py` (20+ unit suites).
- Modules covered (evidence from imports/assertions):
  - controllers/routes: not directly unit-tested (covered via API tests)
  - services: `rbac`, `scoring`, `routing`, `masking`, `state_machine`, `plan_export`, `model_schema`, `share_tokens`, `backup_archive`, `canonical`, `guardrail`, `lockout`, `passwords`, `digest` math, business-days
  - repositories/data layer: no repository abstraction present; DB behavior primarily API-tested
  - auth/guards/middleware: partial (`error_envelope` unit tested); auth/session logic mostly unit-tested via service layer and API
- Important backend modules not directly unit-tested:
  - `api/app/middleware/auth.py`
  - `api/app/middleware/maintenance.py`
  - `api/app/middleware/request_context.py`
  - `api/app/services/auth_context.py`
  - `api/app/routes/*` (route handlers only API-tested)

### Frontend Unit Tests (STRICT REQUIREMENT)
- Frontend test files found: `web/tests/component/*.test.ts` (18 files).
- Frameworks/tools detected: **Vitest**, **@vue/test-utils**, **jsdom** (`web/package.json`).
- Direct component/module imports found:
  - views: `LoginView.vue`, `PlansView.vue`, `ModelsView.vue`, `CyclesView.vue`, `AdminView.vue`
  - components: `AppShell.vue`, `FeedbackControl.vue`, `DigestBanner.vue`, `BomDiffView.vue`, `RoutingConsole.vue`, `ShareLinkModal.vue`, `EvaluationForm.vue`, `TimelineBadge.vue`, `TraceViewer.vue`, `MaintenanceBanner.vue`
  - logic modules: `web/src/lib/api.ts`, `web/src/stores/session.ts`
- Important frontend components/modules not tested directly:
  - `web/src/views/DashboardView.vue`
  - `web/src/views/FeedbackView.vue`
  - `web/src/views/AssignmentFormView.vue`
  - `web/src/router/index.ts`

**Frontend unit tests: PRESENT**

### Cross-Layer Observation
- Both frontend and backend have explicit test suites.
- Backend test surface (API + unit + e2e flows) is broader than frontend unit coverage, but frontend is not untested.
- No backend-heavy / frontend-missing imbalance.

## API Observability Check
- Overall observability: **mostly strong**.
- Strong examples with explicit method/path/input/response assertions:
  - `api/tests/api/test_submissions.py::test_submit_writes_trace_and_returns_hash`
  - `api/tests/api/test_model_runs.py::test_run_lifecycle_start_then_complete`
  - `e2e/tests/plan_flow.spec.ts` (full request/response lifecycle)
- Weak spots:
  - some tests assert mostly status/error code with limited response contract checks (e.g., selected authz denial tests and smoke tests).

## Tests Check
- Success paths: covered broadly (auth, plans, models, cycles, feedback, admin).
- Failure paths: covered (permission denied, validation errors, conflict states, lockout, bad IDs).
- Edge cases: covered in several domains (rate limits, rollback behavior, schema mismatch, trace missing).
- Validation: covered (`422`/`400` checks in multiple suites).
- Auth/permissions: covered with role-based and object-level tests (`test_authz_post_audit*.py`, `test_audit_r3.py`).
- Integration boundaries: strong real-stack checks via API tests + Playwright e2e.
- Assertion quality: mostly meaningful; not purely superficial.
- `run_tests.sh`: Docker-compose based orchestration; **OK** (no local package-manager install steps required in script).

## End-to-End Expectations (Fullstack)
- Fullstack FE↔BE tests are present (`e2e/tests/*`), including UI journeys and API journeys.
- Expectation satisfied.

## Test Coverage Score (0–100)
**Score: 91/100**

## Score Rationale
- High endpoint coverage with true no-mock HTTP testing.
- Strong authz and business-rule depth.
- One concrete route uncovered (`DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}`).
- Some observability/assertion depth inconsistency in smaller tests.

## Key Gaps
1. Uncovered endpoint: `DELETE /api/cycles/{cycle_id}/assignments/{assignment_id}`.
2. Missing direct unit tests for middleware/auth-context modules.
3. Frontend direct tests missing for `FeedbackView`, `AssignmentFormView`, router guard behavior.

## Confidence & Assumptions
- Confidence: **high**.
- Assumptions:
  - Static-only analysis; no runtime execution performed.
  - Coverage classification is based on visible request calls in test sources.
  - "True no-mock" determined from visible absence of mocking/stubbing in backend API/e2e test layers.

**Test Coverage Audit Verdict: PARTIAL PASS**

---

# README Audit

## README Location
- Found at required path: `README.md` (repo root).

## Hard Gate Failures
- None.

## High Priority Issues
- None.

## Medium Priority Issues
- None.

## Low Priority Issues
- README now includes both `docker-compose` and `docker compose` forms; this is acceptable, but duplicate command variants can drift over time if not kept synchronized.

## Environment Rules (STRICT)
- No forbidden install instructions (`npm install`, `pip install`, `apt-get`, manual DB setup) found in README.
- Containerized workflow emphasis present.

## Engineering Quality
- Tech stack clarity: good.
- Architecture explanation: good high-level structure.
- Testing instructions: good runner guidance.
- Security/roles: good (explicit credentials provided for all roles, with creation procedure).
- Workflow clarity: generally good.
- Presentation quality: clean markdown, readable, structured.

## README Verdict
**PASS**

**README Audit Verdict: PASS**
