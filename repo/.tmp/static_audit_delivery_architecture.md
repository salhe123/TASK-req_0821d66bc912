# Static Audit Report — Delivery Acceptance & Project Architecture

## 1. Verdict
- Overall conclusion: **Fail**

## 2. Scope and Static Verification Boundary
- Reviewed:
  - Backend FastAPI routes/services/models/migrations, frontend Vue routes/views/components, documentation, docker/test orchestration, and unit/API/component/E2E/load test sources.
- Not reviewed:
  - Runtime behavior under real execution, browser rendering at runtime, DB contents after execution, Docker orchestration behavior, and true latency/security behavior in deployment.
- Intentionally not executed:
  - Project startup, tests, Docker, migrations, external services.
- Manual verification required for:
  - Real p95 latency compliance in target hardware/network.
  - End-to-end offline deployment operations (backup/restore jobs, restore safety under real failure conditions).
  - Actual UI/UX rendering and interactive quality in browser.

## 3. Repository / Requirement Mapping Summary
- Prompt core goal: offline-first governance workbench with strict role-based workflows for evaluation lifecycle, plan/BOM governance, model registry/routing/rollback, feedback loop, security controls, traceability ledger, and backup/restore.
- Mapped implementation areas:
  - Backend modules for auth/RBAC/cycles/assignments/submissions/plans/share/models/experiments/inference/feedback/backups.
  - Vue SPA modules for login, cycles, plans, models, admin.
  - Persistence via SQLAlchemy models + Alembic revisions.
  - Tests across unit/API/component/E2E/load.
- Primary result: substantial implementation exists, but several blocker/high gaps remain in requirement completeness and authorization/object isolation.

## 4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Documentation and static verifiability
- Conclusion: **Partial Pass**
- Rationale: startup/test/config instructions are present and mostly coherent, but README references required documents that are absent (`plan.md`, `runbook.md`), reducing static verifiability completeness.
- Evidence:
  - `README.md:41`
  - `README.md:42`
  - `README.md:156`
  - `README.md:157`
  - `README.md:53`
  - `README.md:90`
- Manual verification note: N/A.

#### 1.2 Material deviation from Prompt
- Conclusion: **Fail**
- Rationale: core prompt flows are not fully delivered in product shape: evaluator workflow is read-only in UI (no cycle-selection-to-form completion flow), training/evaluation run workflow is absent, and feedback page route is advertised but not implemented.
- Evidence:
  - `web/src/views/CyclesView.vue:31`
  - `web/src/views/CyclesView.vue:47`
  - `e2e/tests/ui_cycles_journey.spec.ts:10`
  - `e2e/tests/ui_cycles_journey.spec.ts:11`
  - `api/app/routes/models.py:89`
  - `api/app/routes/models.py:121`
  - `api/app/routes/models.py:157`
  - `web/src/components/AppShell.vue:21`
  - `web/src/router/index.ts:13`
- Manual verification note: N/A (static mismatch is explicit).

### 2. Delivery Completeness

#### 2.1 Coverage of explicit core requirements
- Conclusion: **Fail**
- Rationale:
  - Delivered: cycle/assignment states, scoring trace ledger, plans diff/export/share/rollback, model register/promote/routing, feedback events, backup staging.
  - Missing/insufficient against explicit prompt requirements: end-user evaluation completion flow in UI, model training/evaluation run workflow, and clear role-bounded object authorization in several sensitive endpoints.
- Evidence:
  - `api/app/routes/assignments.py:107`
  - `api/app/services/submissions.py:58`
  - `api/app/routes/plans.py:282`
  - `api/app/routes/plans.py:332`
  - `api/app/routes/plans.py:383`
  - `api/app/routes/experiments.py:183`
  - `api/app/routes/experiments.py:211`
  - `web/src/views/CyclesView.vue:22`
  - `api/app/routes/models.py:121`
- Manual verification note: performance SLO adherence remains manual.

#### 2.2 Basic end-to-end 0→1 deliverable vs partial/demo
- Conclusion: **Partial Pass**
- Rationale: repository structure is full-stack and non-trivial, but key UX flows remain partial (notably evaluator completion flow), and at least one primary nav surface points to a non-existent route.
- Evidence:
  - `README.md:21`
  - `web/src/components/AppShell.vue:21`
  - `web/src/router/index.ts:20`
  - `e2e/tests/ui_cycles_journey.spec.ts:10`
- Manual verification note: N/A.

### 3. Engineering and Architecture Quality

#### 3.1 Engineering structure and module decomposition
- Conclusion: **Pass**
- Rationale: backend/frontend split, route/service/model separation, migrations, and layered tests are well-decomposed; no single-file monolith pattern observed.
- Evidence:
  - `api/app/app.py:64`
  - `api/app/routes/models.py:31`
  - `api/app/services/scoring.py:71`
  - `web/src/router/index.ts:11`
  - `README.md:21`
- Manual verification note: N/A.

#### 3.2 Maintainability/extensibility
- Conclusion: **Partial Pass**
- Rationale: many modules are extendable, but object-level authorization is inconsistently enforced and some route contracts ignore path resource binding (`plan_id` vs `version_id`), increasing long-term risk.
- Evidence:
  - `api/app/routes/plans.py:262`
  - `api/app/routes/plans.py:270`
  - `api/app/routes/plans.py:291`
  - `api/app/routes/plans.py:340`
  - `api/app/routes/plans.py:456`
- Manual verification note: N/A.

### 4. Engineering Details and Professionalism

#### 4.1 Error handling/logging/validation/API design
- Conclusion: **Partial Pass**
- Rationale: strong envelope/error conventions and request logging exist, with broad input validation; however, security-critical authorization omissions materially reduce API professionalism.
- Evidence:
  - `api/app/middleware/error_envelope.py:9`
  - `api/app/middleware/request_context.py:34`
  - `api/app/schemas/cycles.py:19`
  - `api/app/routes/submissions.py:37`
  - `api/app/routes/feedback.py:91`
- Manual verification note: N/A.

#### 4.2 Product-like organization vs demo
- Conclusion: **Partial Pass**
- Rationale: codebase looks product-oriented, but explicit test comments acknowledge read-only UI for critical workflow and some nav surfaces are placeholders.
- Evidence:
  - `e2e/tests/ui_cycles_journey.spec.ts:10`
  - `e2e/tests/ui_cycles_journey.spec.ts:11`
  - `web/tests/component/AppShell.test.ts:37`
- Manual verification note: N/A.

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Business goal and implicit constraints fit
- Conclusion: **Fail**
- Rationale: major business constraints are partially implemented but key semantics are missed: assignment/reviewer object scoping, anti-replay implementation fidelity, and complete evaluator/model-iteration workflows.
- Evidence:
  - `api/app/routes/assignments.py:183`
  - `api/app/routes/assignments.py:207`
  - `api/app/routes/submissions.py:43`
  - `api/app/services/session_tokens.py:97`
  - `api/app/services/session_tokens.py:98`
  - `api/app/services/session_tokens.py:99`
  - `web/src/views/CyclesView.vue:31`
  - `api/app/routes/models.py:121`
- Manual verification note: N/A.

### 6. Aesthetics (Frontend)

#### 6.1 Visual and interaction quality
- Conclusion: **Partial Pass**
- Rationale: layouts are coherent, visual hierarchy exists, and interaction affordances are present; however, prompt-specified primary workflow UX is incomplete (missing operational screens/flows), so scenario fit is partial.
- Evidence:
  - `web/src/views/PlansView.vue:149`
  - `web/src/components/TimelineBadge.vue:7`
  - `web/src/components/DigestBanner.vue:37`
  - `web/src/views/CyclesView.vue:31`
  - `web/src/router/index.ts:13`
- Manual verification note: browser-level accessibility/visual polish requires manual run.

## 5. Issues / Suggestions (Severity-Rated)

### Blocker

1. **Severity:** Blocker
- **Title:** Submission detail/trace endpoints expose cross-user data without object-level authorization
- **Conclusion:** Fail
- **Evidence:**
  - `api/app/routes/submissions.py:37`
  - `api/app/routes/submissions.py:43`
  - `api/app/routes/submissions.py:54`
  - `api/app/routes/submissions.py:60`
- **Impact:** Any authenticated user can fetch other users’ submission metadata and full calculation traces, violating confidentiality and regulated access boundaries.
- **Minimum actionable fix:** Enforce permission + ownership/reviewer checks before returning submission/trace (e.g., evaluator owner or assigned reviewer/admin only).

2. **Severity:** Blocker
- **Title:** Reviewer actions are not bound to assigned reviewer (object-level authorization gap)
- **Conclusion:** Fail
- **Evidence:**
  - `api/app/routes/assignments.py:183`
  - `api/app/routes/assignments.py:184`
  - `api/app/routes/assignments.py:207`
  - `api/app/routes/assignments.py:208`
  - `api/app/models/cycle.py:119`
- **Impact:** Any user with `cycle:review` can return/approve any assignment, bypassing assignment-level reviewer ownership.
- **Minimum actionable fix:** Require `assignment.reviewer_user_id == auth.user_id` (or explicit admin override permission) for return/approve endpoints.

3. **Severity:** Blocker
- **Title:** Core evaluator workflow is incomplete in the delivered UI
- **Conclusion:** Fail
- **Evidence:**
  - `web/src/views/CyclesView.vue:22`
  - `web/src/views/CyclesView.vue:31`
  - `web/src/views/CyclesView.vue:47`
  - `e2e/tests/ui_cycles_journey.spec.ts:10`
  - `e2e/tests/ui_cycles_journey.spec.ts:11`
- **Impact:** Prompt’s primary left-to-right evaluator journey (cycle selection, participants review, form completion/submission) is not delivered as an end-user UI flow.
- **Minimum actionable fix:** Implement assignment detail/form screens and cycle-driven workflow UI wired to `/save` and `/submit` APIs.

4. **Severity:** Blocker
- **Title:** Anti-replay requirement is not implemented to prompt intent
- **Conclusion:** Fail
- **Evidence:**
  - `api/app/services/session_tokens.py:97`
  - `api/app/services/session_tokens.py:98`
  - `api/app/services/session_tokens.py:99`
  - `api/app/core/settings.py:43`
- **Impact:** Token verification only rejects far-future timestamps; it does not provide robust replay resistance consistent with “anti-replay timestamps (60-second skew)” requirement.
- **Minimum actionable fix:** Add per-request freshness checks (nonce/timestamp binding or rotating token claims with bounded acceptance window and replay cache).

### High

5. **Severity:** High
- **Title:** Plan endpoints accept mismatched `plan_id` and `version_id` on multiple routes
- **Conclusion:** Fail
- **Evidence:**
  - `api/app/routes/plans.py:262`
  - `api/app/routes/plans.py:270`
  - `api/app/routes/plans.py:282`
  - `api/app/routes/plans.py:291`
  - `api/app/routes/plans.py:332`
  - `api/app/routes/plans.py:340`
  - `api/app/routes/plans.py:448`
  - `api/app/routes/plans.py:456`
- **Impact:** Cross-resource access confusion; callers can reference a version unrelated to path `plan_id`, weakening object integrity and audit trust.
- **Minimum actionable fix:** Validate `version.plan_id == plan_id` consistently on get/diff/export/share endpoints.

6. **Severity:** High
- **Title:** Subject block lookup endpoint lacks authorization and caller scoping
- **Conclusion:** Fail
- **Evidence:**
  - `api/app/routes/feedback.py:91`
  - `api/app/routes/feedback.py:97`
  - `api/app/routes/feedback.py:100`
- **Impact:** Any authenticated user can enumerate block preferences for arbitrary `subject_key`, exposing user preference/security signals.
- **Minimum actionable fix:** Require `feedback:submit` + subject ownership constraint (or privileged permission for cross-subject reads).

7. **Severity:** High
- **Title:** Prompt-required model training/evaluation run workflow is absent
- **Conclusion:** Fail
- **Evidence:**
  - `api/app/routes/models.py:89`
  - `api/app/routes/models.py:121`
  - `api/app/routes/models.py:157`
  - `web/src/views/ModelsView.vue:73`
- **Impact:** ML Engineer responsibilities in prompt (sample build, training runs, evaluation runs) are not delivered; only registry/promotion/routing are present.
- **Minimum actionable fix:** Add backend + UI workflow for training/evaluation job lifecycle and promotion gating by evaluated results.

### Medium

8. **Severity:** Medium
- **Title:** Navigation advertises `/feedback` route that is not implemented
- **Conclusion:** Fail
- **Evidence:**
  - `web/src/components/AppShell.vue:21`
  - `web/src/router/index.ts:13`
  - `web/src/router/index.ts:20`
- **Impact:** Broken information architecture and user confusion in primary navigation.
- **Minimum actionable fix:** Implement `FeedbackView` route or remove nav item until implemented.

9. **Severity:** Medium
- **Title:** Documentation references missing `plan.md` and `runbook.md`
- **Conclusion:** Fail
- **Evidence:**
  - `README.md:41`
  - `README.md:42`
  - `README.md:156`
  - `README.md:157`
- **Impact:** Reduces operator/reviewer ability to statically verify operational and phased-delivery claims.
- **Minimum actionable fix:** Add referenced docs or remove claims and replace with existing source-of-truth docs.

10. **Severity:** Medium
- **Title:** Test coverage instrumentation excludes route/middleware execution paths by design
- **Conclusion:** Partial Pass
- **Evidence:**
  - `coverage/README.md:7`
  - `coverage/README.md:8`
  - `api/pyproject.toml:39`
  - `api/pyproject.toml:40`
- **Impact:** High-risk API authorization defects can remain undetected despite green coverage metrics.
- **Minimum actionable fix:** Add combined coverage across API service process or enforce explicit endpoint-level authz tests for all sensitive routes.

### Low

11. **Severity:** Low
- **Title:** `secure=False` session cookie in login response
- **Conclusion:** Partial Pass
- **Evidence:**
  - `api/app/routes/auth.py:110`
- **Impact:** In non-TLS deployments this is expected, but when HTTPS exists cookie transport protections are weakened.
- **Minimum actionable fix:** Make `secure` environment-sensitive (`True` in production/TLS environments).

## 6. Security Review Summary

- **Authentication entry points:** **Partial Pass**
  - Evidence: `api/app/routes/auth.py:41`, `api/app/services/passwords.py:6`, `api/app/services/lockout.py:42`.
  - Reasoning: password hashing + lockout + session tracking exist; anti-replay semantics are insufficiently implemented (`api/app/services/session_tokens.py:97`).

- **Route-level authorization:** **Partial Pass**
  - Evidence: `api/app/routes/admin_users.py:45`, `api/app/routes/metrics.py:12`, `api/app/routes/feedback.py:35`.
  - Reasoning: many routes enforce permission, but sensitive routes lack explicit checks (`api/app/routes/submissions.py:37`, `api/app/routes/feedback.py:91`).

- **Object-level authorization:** **Fail**
  - Evidence: `api/app/routes/assignments.py:183`, `api/app/routes/assignments.py:207`, `api/app/routes/submissions.py:43`.
  - Reasoning: reviewer-resource binding and submission ownership checks are missing.

- **Function-level authorization:** **Partial Pass**
  - Evidence: `api/app/services/rbac.py:31`, `api/app/routes/plans.py:124`.
  - Reasoning: helper exists and is widely used, but inconsistently applied in sensitive handlers.

- **Tenant / user data isolation:** **Fail**
  - Evidence: `api/app/routes/submissions.py:43`, `api/app/routes/feedback.py:97`.
  - Reasoning: endpoints allow cross-subject/user read access without ownership boundaries.

- **Admin / internal / debug endpoint protection:** **Pass**
  - Evidence: `api/app/routes/admin_backups.py:69`, `api/app/routes/admin_audit.py:31`, `api/app/routes/admin_users.py:45`.
  - Reasoning: admin surfaces require explicit permissions; no open debug/admin endpoints observed.

## 7. Tests and Logging Review

- **Unit tests:** **Pass**
  - Evidence: `api/tests/unit/test_scoring.py`, `api/tests/unit/test_session_tokens.py:24`, `api/tests/unit/test_digest_time_gate.py:44`.
  - Notes: strong service-level coverage for scoring, RBAC, digest/business-day math, token validation primitives.

- **API / integration tests:** **Partial Pass**
  - Evidence: `api/tests/api/test_auth.py:28`, `api/tests/api/test_cycles_lifecycle.py:16`, `api/tests/api/test_plans.py:30`, `api/tests/api/test_feedback.py:53`.
  - Notes: broad happy/failure flows covered; critical authz gaps (submission read isolation, assigned-reviewer enforcement, subject block read scoping) are not covered.

- **Logging categories / observability:** **Pass**
  - Evidence: `api/app/middleware/request_context.py:34`, `api/app/core/logging.py:10`, `api/app/services/audit.py:12`.
  - Notes: structured JSON request logs + audit logs are present and coherent.

- **Sensitive-data leakage risk in logs / responses:** **Partial Pass**
  - Evidence: `api/tests/api/test_submissions.py:269`, `api/app/routes/submissions.py:44`.
  - Notes: raw grade values are not logged in grade-edit audit payloads; however, unauthorized data exposure exists via open submission/trace retrieval.

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Unit tests exist: yes (`api/tests/unit/*`, `web/tests/component/*`).
- API/integration tests exist: yes (`api/tests/api/*`).
- Additional E2E/load suites exist: yes (`e2e/tests/*`, `api/tests/load/test_inference_p95.py`).
- Frameworks: `pytest`, `pytest-asyncio`, `vitest`, `playwright`.
- Test entry points documented: yes (`README.md:90`, `run_tests.sh:76`).
- Documentation provides test commands: yes (`README.md:100`, `run_tests.sh:77`).

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|---|
| Auth login + lockout | `api/tests/api/test_auth.py:28`, `api/tests/api/test_auth.py:68` | 200 login envelope + 423 after threshold | sufficient | None material | N/A |
| CSRF on mutating endpoints | `api/tests/api/test_security_headers.py:10` | 403 `csrf_missing` probes across modules | sufficient | Endpoint sample-based, not exhaustive | Add generated route matrix test |
| Evaluator own-assignment enforcement on save/submit | `api/tests/api/test_cycles_lifecycle.py:331` | stranger save attempt => 403 | basically covered | return/approve reviewer assignment not covered | Add tests for assigned reviewer mismatch |
| Submission detail/trace authorization isolation | `api/tests/api/test_submission_detail.py:83` | only admin happy-path + 404s | missing | no non-owner/non-reviewer access tests | Add evaluator-vs-other-evaluator access denial tests |
| Reviewer object-level authorization | `api/tests/api/test_cycles_lifecycle.py:118` | reviewer can return/approve | insufficient | no check reviewer is assigned reviewer | Add explicit unauthorized reviewer test |
| Plan version path/resource integrity | `api/tests/api/test_plans.py:67`, `api/tests/api/test_plans.py:141` | happy diff/rollback flows | insufficient | no mismatched `plan_id`/`version_id` negative tests | Add 404 tests for cross-plan IDs on get/diff/export/share |
| Feedback ingest/apply toggles + rollback preservation | `api/tests/api/test_feedback.py:89`, `api/tests/api/test_feedback.py:168` | signal update behavior and rollback isolation assertions | sufficient | subject block read auth absent | Add authz tests for `/feedback/blocks/{subject_key}` |
| p95 inference budget gate | `api/tests/load/test_inference_p95.py:77` | measured p95 assert vs env budget | basically covered | default test compose relaxes to 400ms | Add CI profile enforcing 150ms default |
| Daily digest 9:00 local and once/day gating | `api/tests/unit/test_digest_time_gate.py:44`, `api/tests/api/test_digest.py:34` | before/after gate and same-day suppression | basically covered | API test does not deterministically prove 9:00 wall-clock boundary | Add clock-injected integration test path |
| Security headers / envelope hygiene | `api/tests/api/test_security_headers.py:40`, `api/tests/api/test_security_headers.py:61` | request-id + envelope shape checks | insufficient | no XSS/CSP/strict transport header assertions | Add explicit response header policy tests |

### 8.3 Security Coverage Audit
- **Authentication:** basically covered (login, invalid creds, lockout, token malformed).
  - Evidence: `api/tests/api/test_auth.py:28`, `api/tests/api/test_auth.py:68`, `api/tests/api/test_auth.py:153`.
- **Route authorization:** partially covered.
  - Evidence: `api/tests/api/test_admin_users.py:39`, `api/tests/api/test_experiment_routing_update.py:95`.
  - Remaining severe risk: unguarded submission and feedback-block reads.
- **Object-level authorization:** insufficient.
  - Evidence gap: no tests asserting assigned reviewer-only return/approve or submission owner-only read.
- **Tenant/data isolation:** insufficient.
  - Evidence gap: no tests for cross-user data access denial on submission/blocks.
- **Admin/internal protection:** covered.
  - Evidence: `api/tests/api/test_admin.py:176`, `api/tests/api/test_admin_backups_extended.py:89`.

### 8.4 Final Coverage Judgment
- **Final Coverage Judgment:** **Fail**
- Explanation:
  - Major happy paths are covered.
  - But uncovered authorization/isolation risks (submission read exposure, reviewer scope, subject block exposure, plan path integrity checks) mean tests could pass while severe security defects remain.

## 9. Final Notes
- This audit is static-only; no runtime success claims were made.
- Strong conclusions are tied to file+line evidence.
- Where runtime or environment behavior is required, this report marks manual verification boundaries explicitly.
