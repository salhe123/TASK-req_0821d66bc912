# Delivery Acceptance and Project Architecture Audit (Static-Only)

## 1. Verdict
- Overall conclusion: **Partial Pass**

## 2. Scope and Static Verification Boundary
- What was reviewed:
  - Documentation/config/manifests: `README.md`, `runbook.md`, `.env.example`, `docker-compose.yml`, `docker-compose.test.yml`, `.gitignore`.
  - Backend entrypoints/middleware/routes/services/models/migrations under `api/app` and `api/migrations`.
  - Frontend routes/views/components/stores/API client under `web/src`.
  - Static tests in `api/tests` (unit/api/load), `web/tests/component`, and `e2e/tests`.
- What was not reviewed:
  - Runtime behavior in a live environment, container orchestration execution, browser rendering/runtime behavior, network interactions, real DB restore execution outcomes.
- What was intentionally not executed:
  - Project startup, Docker, test runs, migrations, scripts.
- Claims requiring manual verification:
  - Real restore correctness and operational RTO/RPO.
  - Real p95 inference latency under target hardware/network.
  - End-to-end browser UX behavior across devices.

## 3. Repository / Requirement Mapping Summary
- Prompt core business goal mapped:
  - Offline model governance workbench with regulated scoring lifecycle, plan/BOM governance, model registry/routing/rollback, and feedback loop.
- Main flows/constraints mapped to implementation:
  - Evaluation cycle + assignment lifecycle + deterministic scoring traces: `api/app/routes/cycles.py`, `api/app/routes/assignments.py`, `api/app/services/scoring.py`, `api/app/services/submissions.py`.
  - Plan compare/export/share governance: `api/app/routes/plans.py`, `api/app/routes/share.py`, `api/app/services/plan_export.py`.
  - Model ops/routing/rollback + inference: `api/app/routes/models.py`, `api/app/routes/experiments.py`, `api/app/routes/inference.py`.
  - Feedback/toggles/signals/blocks: `api/app/routes/feedback.py`, `api/app/services/feedback.py`.
  - Security + audit + backup surfaces: `api/app/routes/auth.py`, `api/app/middleware/auth.py`, `api/app/routes/admin_audit.py`, `api/app/routes/admin_backups.py`.

## 4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Documentation and static verifiability
- Conclusion: **Pass**
- Rationale: Startup/run/test/config instructions and project structure are clear and statically consistent.
- Evidence:
  - `README.md:19`, `README.md:53`, `README.md:90`
  - `runbook.md:64`, `runbook.md:75`
  - `docker-compose.yml:17`, `docker-compose.test.yml:11`
- Manual verification note: None.

#### 1.2 Material deviation from Prompt
- Conclusion: **Partial Pass**
- Rationale: Core domains are implemented, but several prompt-specific requirements are weakened or incomplete (copy workflow, strict makeup cap, feedback-model integrity).
- Evidence:
  - No explicit plan version copy operation in API/UI (`api/app/routes/plans.py:213`, `web/src/views/PlansView.vue:190`)
  - Makeup window allows up to 30 business days, not prompt-capped 5 (`api/app/schemas/cycles.py:49`)
  - Feedback accepts arbitrary model version IDs without binding to experiment arm (`api/app/services/feedback.py:107`, `api/app/services/feedback.py:114`)
- Manual verification note: None.

### 2. Delivery Completeness

#### 2.1 Core explicit requirements coverage
- Conclusion: **Partial Pass**
- Rationale:
  - Implemented: role-based auth, cycle/assignment state machine, traceable scoring ledger, plan diff/export/share links, model run/promotion/routing/rollback, feedback toggles/signals/blocks, backup APIs.
  - Gaps: strict 5-day makeup contract not enforced; copy-version workflow not explicit; feedback-event/model-version linkage integrity is weak.
- Evidence:
  - Implemented: `api/app/routes/assignments.py:157`, `api/app/services/scoring.py:71`, `api/app/routes/plans.py:296`, `api/app/routes/models.py:305`, `api/app/routes/experiments.py:222`, `api/app/routes/feedback.py:29`
  - Gap: `api/app/schemas/cycles.py:49`, `api/app/routes/plans.py:213`, `api/app/services/feedback.py:107`
- Manual verification note: Real low-latency behavior and restore reliability remain runtime checks.

#### 2.2 End-to-end 0→1 deliverable vs partial/demo
- Conclusion: **Pass**
- Rationale: Repository is a full-stack, multi-module product-shaped delivery with migrations/docs/tests, not a code fragment.
- Evidence:
  - `README.md:21`, `api/app/app.py:75`, `web/src/router/index.ts:13`
  - `api/tests/api/test_cycles_lifecycle.py:17`, `web/tests/component/CyclesView.test.ts:1`, `e2e/tests/full_flow.spec.ts:1`
- Manual verification note: None.

### 3. Engineering and Architecture Quality

#### 3.1 Structure and decomposition
- Conclusion: **Pass**
- Rationale: Clean domain decomposition across backend routes/services/models and frontend views/components/stores.
- Evidence:
  - `api/app/app.py:75`
  - `api/app/services/scoring.py:1`, `api/app/services/feedback.py:1`, `api/app/services/backup_archive.py:1`
  - `web/src/views/CyclesView.vue:1`, `web/src/components/EvaluationForm.vue:1`, `web/src/stores/session.ts:1`
- Manual verification note: None.

#### 3.2 Maintainability and extensibility
- Conclusion: **Partial Pass**
- Rationale: Versioned entities and modular services are maintainable, but key semantics are inconsistently encoded (e.g., governance caps and cross-entity integrity checks).
- Evidence:
  - Versioning patterns: `api/app/routes/templates.py:94`, `api/app/routes/rule_sets.py:110`, `api/app/routes/plans.py:213`, `api/app/routes/models.py:136`
  - Weak integrity point: `api/app/services/feedback.py:107`
- Manual verification note: None.

### 4. Engineering Details and Professionalism

#### 4.1 Error handling, logging, validation, API design
- Conclusion: **Partial Pass**
- Rationale: Strong error envelope and structured request logging are present; key validation/authorization gaps remain for prompt-critical semantics.
- Evidence:
  - Error envelope: `api/app/middleware/error_envelope.py:10`
  - Request logging + request ID: `api/app/middleware/request_context.py:37`, `api/app/core/logging.py:10`
  - Auth/CSRF enforcement: `api/app/middleware/auth.py:46`
  - Gap (makeup cap): `api/app/schemas/cycles.py:49`
  - Gap (feedback-model binding): `api/app/services/feedback.py:107`
- Manual verification note: None.

#### 4.2 Product/service realism vs demo
- Conclusion: **Pass**
- Rationale: Backup/encryption/inference paths are implemented as concrete services (not static placeholders), with operational endpoints and tests.
- Evidence:
  - Real encrypted backup framing and pg_dump/pg_restore paths: `api/app/services/backup_archive.py:71`, `api/app/services/backup_archive.py:122`, `api/app/services/backup_archive.py:148`
  - Restore workflow endpoints: `api/app/routes/admin_backups.py:98`, `api/app/routes/admin_backups.py:160`
- Manual verification note:
  - **Manual Verification Required** for actual restore behavior under failure/load conditions.

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Business goal/scenario/constraints fit
- Conclusion: **Partial Pass**
- Rationale: The solution aligns strongly with the governance architecture, but misses strict fit on some explicit prompt semantics.
- Evidence:
  - Strong alignment: `README.md:3`, `api/migrations/versions/0002_phase1_identity.py:24`, `api/app/routes/experiments.py:222`
  - Semantics gap: strict makeup cap (`api/app/schemas/cycles.py:49`), copy workflow absence (`web/src/views/PlansView.vue:190`), feedback-model linkage (`api/app/services/feedback.py:107`)
- Manual verification note: None.

### 6. Aesthetics (frontend-only/full-stack)

#### 6.1 Visual/interaction design quality
- Conclusion: **Pass**
- Rationale: UI is coherent and functional with clear section separation, badges, tables, modal actions, and form feedback states.
- Evidence:
  - `web/src/components/AppShell.vue:46`, `web/src/views/CyclesView.vue:123`, `web/src/components/TimelineBadge.vue:25`, `web/src/views/PlansView.vue:160`
- Manual verification note:
  - **Cannot Confirm Statistically** for final rendering fidelity/responsiveness across browser/device matrix.

## 5. Issues / Suggestions (Severity-Rated)

### Blocker / High First

1. Severity: **Blocker**
- Title: Secret key material is present in delivery workspace
- Conclusion: **Fail**
- Evidence:
  - `infra/secrets/kek` (32-byte key file present)
  - `infra/secrets/session_signing_key` (32-byte key file present)
  - Policy contradiction: `infra/secrets/README.md:6` (“never stored in git or the DB”)
- Impact:
  - In a regulated environment, bundling actual KEK/session signing key material is a critical supply-chain and credential hygiene failure.
- Minimum actionable fix:
  - Ensure these files are never included in distributable artifacts/repo history; ship placeholders only and require operator provisioning.

2. Severity: **High**
- Title: Feedback events are not integrity-bound to experiment routing arm/model
- Conclusion: **Fail**
- Evidence:
  - Caller-supplied `model_version_id` is accepted if it merely exists: `api/app/services/feedback.py:107`, `api/app/services/feedback.py:114`
  - No validation that submitted model version matches experiment routing arm (`A/B`) at event time.
- Impact:
  - Governance signals/audit trail can be polluted with feedback attributed to unrelated model versions.
- Minimum actionable fix:
  - Validate `(experiment_id, arm, model_version_id)` consistency against `inference_routing` before persisting event.

3. Severity: **High**
- Title: Prompt contract “make-up up to 5 business days” is not enforced
- Conclusion: **Fail**
- Evidence:
  - Schema permits up to 30 days: `api/app/schemas/cycles.py:49`
- Impact:
  - Violates explicit business rule and can materially alter regulated scoring windows.
- Minimum actionable fix:
  - Constrain `makeup_business_days` to `le=5` and add regression tests for rejection of `>5`.

4. Severity: **High**
- Title: Plan version “copy” workflow is not explicitly delivered
- Conclusion: **Partial Fail**
- Evidence:
  - API exposes create-version/rollback/diff/export/share but no dedicated copy operation: `api/app/routes/plans.py:213`, `api/app/routes/plans.py:399`
  - UI actions expose Share/Rollback only for selected version: `web/src/views/PlansView.vue:190`, `web/src/views/PlansView.vue:193`
- Impact:
  - Prompt-required “create, copy, and compare versions” is only partially supported (compare yes; copy not explicit for users).
- Minimum actionable fix:
  - Add explicit copy-version endpoint/UI action that clones selected version lines and metadata into a new draft version.

### Medium

5. Severity: **Medium**
- Title: Client-side subtotal logic diverges from server scoring missing-strategy semantics
- Conclusion: **Partial Fail**
- Evidence:
  - UI subtotal skips all missing values (`continue`), ignoring `ZERO_FILL` denominator semantics: `web/src/components/EvaluationForm.vue:35`, `web/src/components/EvaluationForm.vue:36`
  - Server scoring applies `ZERO_FILL` vs `EXCLUDE_FROM_DENOMINATOR` differently: `api/app/services/scoring.py:134`, `api/app/services/scoring.py:137`
- Impact:
  - Real-time subtotal shown to evaluator may not match deterministic backend scoring behavior.
- Minimum actionable fix:
  - Mirror server missing-strategy math in UI subtotal computation.

6. Severity: **Medium**
- Title: Digest reminder is mounted only in cycles page, not broadly as in-app reminder surface
- Conclusion: **Partial Fail**
- Evidence:
  - Digest banner mounted in `CyclesView` only: `web/src/views/CyclesView.vue:101`
- Impact:
  - Reminder visibility depends on navigating to cycles page, weakening “in-app banner” behavior.
- Minimum actionable fix:
  - Mount digest/reminder banner at shell/dashboard level with role-aware visibility.

7. Severity: **Low**
- Title: README migration-range statement is stale
- Conclusion: **Partial Fail**
- Evidence:
  - README says migrations `0001 … 0009`: `README.md:25`
  - Repository includes `0010`: `api/migrations/versions/0010_phase9_rule_set_perm_user_tz.py:1`
- Impact:
  - Minor documentation drift.
- Minimum actionable fix:
  - Update README migration range.

## 6. Security Review Summary

- Authentication entry points: **Pass**
  - Evidence: login/logout/me/password/timezone endpoints and token verification path (`api/app/routes/auth.py:49`, `api/app/services/session_tokens.py:77`, `api/app/services/auth_context.py:17`).

- Route-level authorization: **Pass**
  - Evidence: permission checks across admin/cycle/plan/model/feedback/metrics/inference routes (`api/app/routes/admin_users.py:45`, `api/app/routes/plans.py:138`, `api/app/routes/models.py:293`, `api/app/routes/inference.py:33`).

- Object-level authorization: **Partial Pass**
  - Evidence: assignment/submission scoped checks (`api/app/routes/assignments.py:47`, `api/app/routes/submissions.py:43`), share-link role checks (`api/app/routes/share.py:44`).
  - Gap: feedback event model-version integrity not scoped to experiment routing (`api/app/services/feedback.py:107`).

- Function-level authorization: **Pass**
  - Evidence: reviewer actions bound to assigned reviewer (`api/app/routes/assignments.py:35`, `api/app/routes/submissions.py:128`).

- Tenant / user data isolation: **Partial Pass**
  - Evidence: cycle assignment listing is scoped for non-privileged callers (`api/app/routes/cycles.py:206`), cross-subject block reads restricted (`api/app/routes/feedback.py:128`).
  - Gap: inference accepts arbitrary `subject_key` values without binding to authenticated user (`api/app/routes/inference.py:27`).

- Admin / internal / debug protection: **Pass**
  - Evidence: admin routes require auth + permissions (`api/app/routes/admin_backups.py:72`, `api/app/routes/admin_audit.py:34`), docs disabled in production (`api/app/app.py:65`).

## 7. Tests and Logging Review

- Unit tests: **Pass**
  - Evidence: coverage for scoring/session/rbac/business-day/guardrail/masking/routing (`api/tests/unit/test_scoring.py:1`, `api/tests/unit/test_session_tokens.py:1`, `api/tests/unit/test_guardrail.py:1`).

- API / integration tests: **Partial Pass**
  - Evidence: broad route coverage including auth, lifecycle, plans, models, feedback, authz regressions (`api/tests/api/test_auth.py:28`, `api/tests/api/test_cycles_lifecycle.py:17`, `api/tests/api/test_plans.py:31`, `api/tests/api/test_models.py:12`, `api/tests/api/test_feedback.py:55`).
  - Gap: no test asserting feedback model-version must match routing arm/experiment.

- Logging categories / observability: **Pass**
  - Evidence: structured JSON logging with request IDs + metrics endpoint (`api/app/core/logging.py:10`, `api/app/middleware/request_context.py:38`, `api/app/routes/metrics.py:10`).

- Sensitive-data leakage risk in logs / responses: **Partial Pass**
  - Evidence: masking utility and masked audit/submission fields (`api/app/services/masking.py:10`, `api/app/routes/admin_audit.py:67`, `api/app/routes/submissions.py:80`).
  - Risk: secret files present in delivery workspace (`infra/secrets/kek`, `infra/secrets/session_signing_key`).

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Unit tests exist: Yes (`api/tests/unit`).
- API/integration tests exist: Yes (`api/tests/api`).
- Load tests exist: Yes (`api/tests/load/test_inference_p95.py`).
- Frontend component tests exist: Yes (`web/tests/component`).
- E2E tests exist: Yes (`e2e/tests`).
- Test frameworks: `pytest`, `vitest`, `playwright` (`README.md:16`).
- Test entry points documented: Yes (`README.md:90`, `run_tests.sh:76`).

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|---|
| Auth login/lockout/session invalidation | `api/tests/api/test_auth.py:29`, `api/tests/api/test_auth.py:68`, `api/tests/api/test_auth.py:123` | 401/423 paths, logout invalidates session | sufficient | None material | Add API test for expired token path via time control if available. |
| CSRF enforcement on mutating endpoints | `api/tests/api/test_security_headers.py:10` | 403 `csrf_missing` across endpoint sample set | basically covered | Sample-based, not exhaustive | Add generated endpoint matrix smoke for mutating routes. |
| Assignment lifecycle and state machine | `api/tests/api/test_cycles_lifecycle.py:17` | Return/resubmit/archive transitions, invalid terminal transition | sufficient | None material | Add explicit transition actor mismatch negative assertions for each edge. |
| Deadline + makeup behavior | `api/tests/api/test_cycles_lifecycle.py:181`, `api/tests/api/test_cycles_lifecycle.py:261` | Post-deadline rejection and late-flag in makeup window | basically covered | Missing enforcement test for prompt cap `<=5` | Add test expecting 422/409 when `makeup_business_days > 5`. |
| Submission detail/trace object authz | `api/tests/api/test_authz_post_audit.py:142`, `api/tests/api/test_authz_post_audit.py:155` | 403 stranger; owner/reviewer allowed | sufficient | None material | Add assigned-reviewer grade-edit positive/negative pair. |
| Plan diff/export/share/revoke authz | `api/tests/api/test_plans.py:31`, `api/tests/api/test_plans.py:171`, `api/tests/api/test_authz_post_audit_2.py:136` | Role mismatch, revoke ownership, diff correctness | sufficient | Copy workflow absent from tests and implementation | Add copy-version API + tests. |
| Model promotion guard + schema consistency | `api/tests/api/test_models.py:13`, `api/tests/api/test_models.py:47` | Eval-run-required promote helper + schema mismatch 409 | sufficient | None material | Add test for promote rejection on missing evaluation run directly. |
| Inference permission and apply toggle | `api/tests/api/test_audit_r4.py:89`, `api/tests/api/test_models.py:213` | 403 without `feedback:submit`; 409 when apply disabled | sufficient | No subject ownership assertion in predict path | Add test preventing cross-subject predict if required by policy. |
| Feedback rate-limit/toggles/rollback isolation | `api/tests/api/test_feedback.py:56`, `api/tests/api/test_feedback.py:91`, `api/tests/api/test_feedback.py:170` | 429 rate limit, ingest-disabled behavior, rollback isolation | basically covered | No integrity test for `model_version_id` consistency with routing arm | Add negative test: feedback with mismatched model_version_id should 409. |
| Backup stage/commit/abort/prune surfaces | `api/tests/api/test_admin_backups_extended.py:12`, `api/tests/api/test_audit_r4.py:210` | list/prune/state-machine and encryption helper round-trip | basically covered | No end-to-end restore correctness assertion | Add integration test proving DB state restoration after commit. |
| 150ms p95 budget contract | `api/tests/load/test_inference_p95.py:88` | p95 asserted against env-default budget | basically covered | Runtime-dependent; static audit cannot prove deployment compliance | Keep CI budget pinned and archive load reports. |

### 8.3 Security Coverage Audit
- Authentication: **Covered well** by API + unit tests.
- Route authorization: **Covered well** for major routes; inference permission check is covered by `test_audit_r4`.
- Object-level authorization: **Partially covered**; assignment/submission/share cases covered, feedback model-version integrity is untested.
- Tenant / data isolation: **Partially covered**; read isolation tests exist, cross-subject predict semantics are not tested.
- Admin / internal protection: **Covered** by non-admin forbidden tests for admin surfaces.

### 8.4 Final Coverage Judgment
**Partial Pass**

- Covered major risks:
  - Auth/session/CSRF, lifecycle transitions, core plan/model/feedback happy paths, several authorization regressions.
- Uncovered risks that could still allow severe defects:
  - Feedback event integrity binding (`experiment/arm/model_version`) and real restore correctness under commit path.

## 9. Final Notes
- This report is static-only and evidence-bound.
- No runtime claim is made for restore reliability, real production p95 latency, or live browser behavior.
- Highest-priority remediation sequence:
  1. Remove secret key material from delivered artifacts and enforce clean secret provisioning.
  2. Enforce feedback event routing/model integrity constraints.
  3. Enforce prompt-accurate makeup cap (<=5) and add tests.
  4. Add explicit plan copy workflow.
