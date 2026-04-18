# Delivery Acceptance and Project Architecture Static Audit

## 1. Verdict
- Overall conclusion: **Partial Pass**

## 2. Scope and Static Verification Boundary
- Reviewed:
  - Documentation, run/config/test instructions, env templates, compose manifests, and operational runbook (`README.md`, `runbook.md`, `.env.example`, `docker-compose.yml`, `docker-compose.test.yml`, `run_tests.sh`).
  - Backend entrypoints/middleware/routes/services/models/migrations for authn/authz, object-level controls, scoring, plans/BOM/share links, models/experiments/inference, feedback, backups, audit, and logging.
  - Frontend router/views/components/styles and test suites.
  - Unit/API/load/component/E2E test code and test harness.
- Not reviewed:
  - Runtime behavior, live DB state, browser execution, container execution, performance measurements, external integrations.
- Intentionally not executed:
  - Project startup, Docker, tests, migrations, scripts, network calls.
- Manual verification required for claims depending on runtime:
  - p95 inference latency contract under production hardware (`api/tests/load/test_inference_p95.py:146`).
  - Real backup encryption/restore behavior beyond static code path.

## 3. Repository / Requirement Mapping Summary
- Prompt core goal mapped: offline model governance workbench with regulated scoring lifecycle, plan/version/BOM governance, model registry + routing/rollback, and feedback loop.
- Main implementation areas mapped:
  - Evaluation cycles/assignments/submissions/scoring traces (`api/app/routes/cycles.py`, `assignments.py`, `submissions.py`, `api/app/services/scoring.py`).
  - Plan versions/diffs/exports/share links (`api/app/routes/plans.py`, `share.py`, `api/app/services/plan_export.py`).
  - Model registry/runs/promotion/experiments/inference (`api/app/routes/models.py`, `experiments.py`, `inference.py`).
  - Feedback ingest/signals/blocks (`api/app/routes/feedback.py`, `api/app/services/feedback.py`).
  - Security and governance controls (auth/session/RBAC/audit/backups/logging).

## 4. Section-by-section Review

### 4.1 Hard Gates

#### 4.1.1 Documentation and static verifiability
- Conclusion: **Pass**
- Rationale: Startup/run/test/config docs are present and consistent with repository structure and entrypoints.
- Evidence:
  - Startup and seed flow documented (`README.md:53`, `README.md:73`).
  - Test orchestration documented and script present (`README.md:90`, `run_tests.sh:1`).
  - Coverage caveats explicitly documented (`coverage/README.md:5`).

#### 4.1.2 Material deviation from Prompt
- Conclusion: **Partial Pass**
- Rationale: Core domains exist, but key prompt-critical UX/behavior is not fully delivered in wired flows (evaluation form behavior and embedded feedback loop), and backup implementation is explicitly non-production placeholder.
- Evidence:
  - Assignment form view lacks prompt-required real-time subtotal/flagging behavior (`web/src/views/AssignmentFormView.vue:133`).
  - Feedback page is read-only blocks list, not embedded Like/Not Interested/Block workflow (`web/src/views/FeedbackView.vue:39`).
  - Backup service explicitly uses dummy archive + MAC framing placeholder (`api/app/services/backup_archive.py:4`, `api/app/services/backup_archive.py:33`).

### 4.2 Delivery Completeness

#### 4.2.1 Core explicit requirements coverage
- Conclusion: **Partial Pass**
- Rationale: Many explicit requirements are implemented (state machine, trace ledger, plan diff/export/share, model promotion gates, rollback, feedback signals), but several explicit items are incomplete or weakened.
- Evidence:
  - Implemented: scoring trace with missing/outlier handling (`api/app/services/scoring.py:16`, `api/app/services/scoring.py:117`).
  - Implemented: plan compare/export/share/rollback (`api/app/routes/plans.py:296`, `api/app/routes/plans.py:348`, `api/app/routes/plans.py:459`, `api/app/routes/plans.py:399`).
  - Gap: assignment form wired UI does not provide required subtotal/flags prompts (`web/src/views/AssignmentFormView.vue:149`).
  - Gap: backup path is placeholder, not production-grade encrypted backup process (`api/app/services/backup_archive.py:33`).

#### 4.2.2 End-to-end 0→1 deliverable (not fragment/demo)
- Conclusion: **Pass**
- Rationale: Full project structure across API/web/tests/e2e/migrations/docs is present with integrated routes and multi-tier tests.
- Evidence:
  - Full stack routing and modules (`api/app/app.py:64`).
  - Web app routes and shell (`web/src/router/index.ts:13`, `web/src/components/AppShell.vue:45`).
  - API/unit/load/component/e2e test suites present (`api/tests/api/test_cycles_lifecycle.py:16`, `web/tests/component/CyclesView.test.ts:13`, `e2e/tests/cycle_lifecycle.spec.ts:11`).

### 4.3 Engineering and Architecture Quality

#### 4.3.1 Reasonable structure and decomposition
- Conclusion: **Pass**
- Rationale: Backend is modularized by domain routes/services/models; frontend has separated views/components/store/api client.
- Evidence:
  - API modular composition (`api/app/app.py:64`).
  - Domain services split (`api/app/services/scoring.py:1`, `api/app/services/feedback.py:1`, `api/app/services/plan_export.py:1`).
  - Frontend decomposition (`web/src/views/PlansView.vue:1`, `web/src/components/BomDiffView.vue:1`).

#### 4.3.2 Maintainability/extensibility
- Conclusion: **Partial Pass**
- Rationale: Overall maintainable structure, but critical security boundaries depend on ad hoc per-route checks and miss object-level guards in some endpoints.
- Evidence:
  - RBAC primitive exists (`api/app/services/rbac.py:31`).
  - Missing object-level checks on participant listing and run listing (`api/app/routes/cycles.py:171`, `api/app/routes/models.py:279`).

### 4.4 Engineering Details and Professionalism

#### 4.4.1 Error handling, logging, validation, API design
- Conclusion: **Partial Pass**
- Rationale: Envelope-based errors, request IDs, CSRF/session validation, and typed schemas are good; however, key authorization and backup security details have material defects.
- Evidence:
  - Error envelope middleware (`api/app/middleware/error_envelope.py:9`).
  - Request logging with request ID (`api/app/middleware/request_context.py:17`, `api/app/core/logging.py:10`).
  - CSRF/session checks (`api/app/middleware/auth.py:46`).
  - Authz gaps (`api/app/routes/cycles.py:171`, `api/app/routes/models.py:279`).

#### 4.4.2 Product-level completeness vs demo-only
- Conclusion: **Partial Pass**
- Rationale: Project resembles a product service, but some prompt-critical capabilities are implemented as placeholders or unwired components.
- Evidence:
  - Placeholder backup implementation (`api/app/services/backup_archive.py:4`).
  - Required evaluation UX behaviors in component but not integrated with active workflow (`web/src/components/EvaluationForm.vue:31`, `web/src/views/AssignmentFormView.vue:133`).

### 4.5 Prompt Understanding and Requirement Fit

#### 4.5.1 Business goal/scenario/constraints fit
- Conclusion: **Partial Pass**
- Rationale: Architecture aligns with governance domains and offline stack, but misses some semantic requirements (embedded feedback loop usage, evaluation-form interaction guarantees, backup expectation).
- Evidence:
  - Offline-local stack and APIs (`README.md:3`, `README.md:48`, `api/app/app.py:64`).
  - Missing embedded feedback flow in active UX (`web/src/views/FeedbackView.vue:39`).
  - Backup expectation weakened by dummy implementation (`api/app/services/backup_archive.py:4`).

### 4.6 Aesthetics (frontend)

#### 4.6.1 Visual/interaction quality fit
- Conclusion: **Pass**
- Rationale: UI is consistent and functional with clear hierarchy, badges, tables, dialogs, and interaction feedback; visual style is utilitarian.
- Evidence:
  - Consistent shell/nav/layout (`web/src/styles.css:20`, `web/src/components/AppShell.vue:46`).
  - Timeline states and cues (`web/src/components/TimelineBadge.vue:7`).
  - Modal/action affordances (`web/src/views/AdminView.vue:177`, `web/src/views/PlansView.vue:130`).
- Manual verification note: Responsive behavior across target breakpoints is **Cannot Confirm Statistically** without runtime rendering.

## 5. Issues / Suggestions (Severity-Rated)

### Blocker

1. **[Blocker] Inadequate backup security implementation vs prompt requirement**
- Conclusion: **Fail**
- Evidence:
  - Backup service documents test-harness dummy behavior (`api/app/services/backup_archive.py:4`).
  - “Encryption” is MAC + plaintext concatenation, not confidential encryption (`api/app/services/backup_archive.py:33`, `api/app/services/backup_archive.py:37`).
- Impact:
  - Violates explicit requirement for nightly encrypted backups in regulated environment; backup confidentiality is not met by current implementation.
- Minimum actionable fix:
  - Replace dummy path with real encrypted archive workflow (e.g., authenticated encryption at rest), and separate test stub from production path via explicit environment gating.

### High

2. **[High] Object-level authorization gap: cycle assignment listing exposed to any authenticated user**
- Conclusion: **Fail**
- Evidence:
  - Endpoint has auth dependency but no role/object check (`api/app/routes/cycles.py:171`).
  - Returns evaluator/reviewer identifiers for full cycle (`api/app/routes/cycles.py:183`, `api/app/routes/cycles.py:58`).
- Impact:
  - Cross-user participant disclosure and assignment metadata leakage.
- Minimum actionable fix:
  - Require `cycle:manage`/`cycle:review` for full-cycle listing, or constrain evaluators to own assignments only.

3. **[High] Prompt-critical evaluation form behavior not wired in active workflow**
- Conclusion: **Fail**
- Evidence:
  - Active assignment form uses basic input fields only (`web/src/views/AssignmentFormView.vue:133`).
  - No wired subtotal/flag/ack flow in this view (`web/src/views/AssignmentFormView.vue:149`, `web/src/views/AssignmentFormView.vue:170`).
  - Required behavior exists in separate component but not integrated (`web/src/components/EvaluationForm.vue:31`, `web/src/components/EvaluationForm.vue:55`).
- Impact:
  - Misses core prompt requirement for real-time subtotal rollups and missing/threshold signaling in evaluator flow.
- Minimum actionable fix:
  - Replace/augment assignment form view with the evaluation component behavior and enforce the threshold acknowledgement/submittable contract.

4. **[High] Embedded feedback loop not delivered in user-facing workflow**
- Conclusion: **Fail**
- Evidence:
  - Feedback page only displays previously blocked items (`web/src/views/FeedbackView.vue:39`, `web/src/views/FeedbackView.vue:47`).
  - Like/Not Interested/Block control component exists but is not used by routed views (`web/src/components/FeedbackControl.vue:71`, `web/src/router/index.ts:22`).
- Impact:
  - Prompt’s “close the loop through embedded feedback controls” is not materially realized in the working UI flow.
- Minimum actionable fix:
  - Integrate feedback controls into relevant inference/result surfaces and persist state updates in-context.

### Medium

5. **[Medium] Share-link role is not enforced at resolution time**
- Conclusion: **Fail**
- Evidence:
  - Resolver checks only `build_plan:view_shared` (`api/app/routes/share.py:28`).
  - Link’s `role` is returned but never validated against requester roles (`api/app/routes/share.py:64`).
- Impact:
  - Any user with generic shared-view permission can open links intended for specific role context.
- Minimum actionable fix:
  - Enforce `link.role` compatibility with authenticated user roles before returning plan content.

6. **[Medium] Share-link revocation lacks object-level ownership check**
- Conclusion: **Fail**
- Evidence:
  - Revoke endpoint only checks `build_plan:manage`, then revokes any link ID (`api/app/routes/plans.py:541`, `api/app/routes/plans.py:547`).
  - No `created_by`/plan ownership validation (`api/app/routes/plans.py:551`).
- Impact:
  - Lateral administrative impact among non-admin plan owners with shared permission scope.
- Minimum actionable fix:
  - Restrict non-admin revocation to links created by caller or links under caller-owned plans.

7. **[Medium] Model run metadata listing missing explicit permission gate**
- Conclusion: **Partial Fail**
- Evidence:
  - Run listing route has auth but no `ensure_permission(auth, "model", "run")` (`api/app/routes/models.py:279`, `api/app/routes/models.py:293`).
- Impact:
  - Potential exposure of training/evaluation metadata to unrelated authenticated roles.
- Minimum actionable fix:
  - Add `model:run` (or read-equivalent) permission enforcement and object-scope controls.

8. **[Medium] Nightly backup automation cannot be confirmed from delivery**
- Conclusion: **Cannot Confirm Statistically**
- Evidence:
  - Only manual backup trigger endpoint exists (`api/app/routes/admin_backups.py:76`).
  - Compose/runtime manifests do not define backup scheduler/cron job (`docker-compose.yml:1`).
- Impact:
  - Retention/SLA obligations (“nightly”) may be operationally unmet unless external scheduler exists.
- Minimum actionable fix:
  - Add explicit scheduled backup job path and documentation/proof in repo.

### Low

9. **[Low] Observability counter for errors is defined but not clearly wired**
- Conclusion: **Partial Fail**
- Evidence:
  - `inc_error()` exists (`api/app/services/metrics.py:42`).
  - No direct call sites in request/error middleware flow.
- Impact:
  - Metrics may under-report API errors.
- Minimum actionable fix:
  - Increment error counter in exception path(s) and add a regression test.

## 6. Security Review Summary

- **Authentication entry points**: **Pass**
  - Evidence: login/logout/me/password change with session issuance, lockout, and token verification (`api/app/routes/auth.py:42`, `api/app/services/session_tokens.py:77`, `api/app/services/lockout.py:42`).

- **Route-level authorization**: **Partial Pass**
  - Evidence: many routes enforce permissions (`api/app/routes/plans.py:138`, `api/app/routes/admin_backups.py:69`).
  - Gap: some routes lack explicit permission checks (`api/app/routes/cycles.py:171`, `api/app/routes/models.py:279`).

- **Object-level authorization**: **Fail**
  - Evidence: good controls in submissions/reviewer actions (`api/app/routes/submissions.py:37`, `api/app/routes/assignments.py:35`).
  - Failures: cycle assignment listing leakage and share-link ownership/role gaps (`api/app/routes/cycles.py:171`, `api/app/routes/plans.py:535`, `api/app/routes/share.py:21`).

- **Function-level authorization**: **Partial Pass**
  - Evidence: role-based checks in most mutating handlers (`api/app/services/rbac.py:31`, `api/app/routes/experiments.py:190`).
  - Gap: selective read functions still under-protected (`api/app/routes/models.py:279`).

- **Tenant/user data isolation**: **Partial Pass**
  - Evidence: assignment/submission ownership checks exist (`api/app/routes/assignments.py:119`, `api/app/routes/submissions.py:60`).
  - Gap: participant listing endpoint discloses cross-user assignment data (`api/app/routes/cycles.py:171`).

- **Admin/internal/debug protection**: **Pass**
  - Evidence: admin routes require auth + permission (`api/app/routes/admin_users.py:45`, `api/app/routes/admin_audit.py:31`, `api/app/routes/admin_backups.py:69`).

## 7. Tests and Logging Review

- **Unit tests**: **Pass**
  - Evidence: core logic covered for scoring, tokens, business-day math, RBAC, lockout, routing, backup helpers (`api/tests/unit/test_scoring.py:22`, `api/tests/unit/test_session_tokens.py:25`, `api/tests/unit/test_business_days.py:13`).

- **API/integration tests**: **Partial Pass**
  - Evidence: broad endpoint coverage incl. auth, lifecycle, plans, models, feedback, backups, authz regressions (`api/tests/api/test_auth.py:28`, `api/tests/api/test_cycles_lifecycle.py:16`, `api/tests/api/test_authz_post_audit.py:141`).
  - Gap: no negative authorization test for `/api/cycles/{cycle_id}/assignments` listing exposure; no role-match test for share token resolution.

- **Logging categories/observability**: **Partial Pass**
  - Evidence: structured JSON logs, request IDs, and metrics endpoint (`api/app/core/logging.py:10`, `api/app/middleware/request_context.py:34`, `api/app/routes/metrics.py:10`).
  - Gap: error counter wiring unclear (`api/app/services/metrics.py:42`).

- **Sensitive-data leakage risk in logs/responses**: **Partial Pass**
  - Evidence: audit payload for grade edits stores hashes only (`api/app/routes/submissions.py:175`; validated by test `api/tests/api/test_submissions.py:269`).
  - Gap: participant/submission metadata exposure from under-authorized reads (security issues above).

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Unit tests exist: yes (`api/tests/unit/*.py`).
- API/integration tests exist: yes (`api/tests/api/*.py`).
- Load tests exist: yes (`api/tests/load/test_inference_p95.py:88`).
- Frontend component tests exist: yes (`web/tests/component/*.test.ts`).
- Browser E2E tests exist: yes (`e2e/tests/*.spec.ts`).
- Test frameworks: `pytest`, `vitest`, `playwright` (`README.md:16`, `README.md:110`).
- Test entry points and commands are documented (`README.md:90`, `run_tests.sh:76`).
- Coverage caveats documented (`coverage/README.md:5`).

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|---|
| Authn + lockout + CSRF | `api/tests/api/test_auth.py:28`, `api/tests/api/test_security_headers.py:10` | 401/423 envelope and CSRF 403 assertions (`test_auth.py:58`, `test_auth.py:116`) | sufficient | none material | n/a |
| Assignment lifecycle state machine | `api/tests/api/test_cycles_lifecycle.py:17`, `e2e/tests/cycle_lifecycle.spec.ts:11` | Transition assertions to ARCHIVED and terminal 409 (`test_cycles_lifecycle.py:165`, `cycle_lifecycle.spec.ts:130`) | sufficient | none material | n/a |
| Submission trace determinism and flags | `api/tests/api/test_submissions.py:34`, `api/tests/unit/test_scoring.py:22` | Trace hash/flags/missing strategy assertions (`test_submissions.py:105`, `test_scoring.py:66`) | sufficient | none material | n/a |
| Object-level submission access | `api/tests/api/test_authz_post_audit.py:142` | 403 `not_your_submission` and reviewer allow (`test_authz_post_audit.py:149`, `:163`) | sufficient | none material | n/a |
| Plan version path integrity | `api/tests/api/test_authz_post_audit.py:191` | Mismatched plan/version returns 404 (`:237`, `:241`, `:245`) | sufficient | none material | n/a |
| Share-link resolve permission | `api/tests/api/test_plans.py:235`, `e2e/tests/plan_flow.spec.ts:132` | Evaluator denied 403 (`test_plans.py:258`) | basically covered | Link `role` claim is not validated by tests | Add API test: user with `view_shared` but role mismatch gets 403 |
| Cycle assignment participant isolation | No direct negative test found | Existing tests cover save/submit ownership, not cycle participant listing (`test_cycles_lifecycle.py:333`) | missing | `/api/cycles/{id}/assignments` authz hole not exercised | Add API test: evaluator not in cycle cannot list participants |
| Model promotion gate and schema consistency | `api/tests/api/test_models.py:47`, `api/tests/api/test_model_runs.py:38` | `feature_schema_mismatch` and `evaluation_run_required` assertions (`test_models.py:79`, `test_model_runs.py:45`) | sufficient | none material | n/a |
| Backup restore flow + maintenance gating | `api/tests/api/test_admin.py:55`, `api/tests/api/test_admin_backups_extended.py:60` | Stage/commit/abort and maintenance 503 assertions (`test_admin.py:67`, `:99`) | basically covered | Does not prove true encryption/nightly automation | Add tests only after production backup implementation is added |
| Frontend evaluation form prompt behavior in active route | `web/tests/component/EvaluationForm.test.ts:24` only for isolated component | Assignment route tests absent; active view not asserting subtotal/flags | insufficient | Core evaluator page can regress undetected | Add component/integration test for `AssignmentFormView` enforcing subtotal/flags/ack behavior |

### 8.3 Security Coverage Audit
- Authentication: **covered meaningfully** (login, invalid creds, lockout, token tamper, csrf).
- Route authorization: **partially covered**; many 403 tests exist, but at least one major untested read route remained vulnerable.
- Object-level authorization: **partially covered**; submissions/reviewer scope are tested well, but cycle participant listing was not covered and appears exposed.
- Tenant/data isolation: **partially covered**; own-assignment checks tested, but cross-user listing gaps remain.
- Admin/internal protection: **mostly covered** for backup/admin surfaces with non-admin 403 tests.

### 8.4 Final Coverage Judgment
- **Partial Pass**
- Covered well: authentication/CSRF basics, lifecycle state transitions, submission trace behavior, model promotion and rollback paths.
- Uncovered enough to matter: tests do not sufficiently guard against certain authorization/data-isolation defects (notably cycle participant listing and share-link role binding), so severe defects could still pass CI.

## 9. Final Notes
- This audit is static-only; no runtime success claims were made.
- Strong conclusions are tied to explicit file/line evidence.
- Items requiring execution/performance/environment validation are marked as **Cannot Confirm Statistically**.
