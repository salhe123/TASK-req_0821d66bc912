# Audit Report 2 — Fix Verification

- Verification Date: 2026-04-21
- Method: static, evidence-bound re-read of `.tmp/audit_report-2.md` issues against the current repository (`repo/`). No runtime execution.
- Scope: every Blocker, High, Medium, and Low issue enumerated in `.tmp/audit_report-2.md` §5 (lines 136–214).

## Status Tokens

Each issue below carries exactly one of:

- **fixed** — change present in repo and resolves the stated defect.
- **verified** — unchanged behavior that already satisfies the requirement (independent re-check).
- **open** — defect still present; evidence points to the unchanged code.
- **partial** — code has changed in the direction of the fix but does not fully satisfy the minimum actionable fix from the source audit.

## Summary

| # | Severity | Title (source `.tmp/audit_report-2.md`) | Status |
|---|----------|------------------------------------------|--------|
| 1 | Blocker  | Secret key material is present in delivery workspace (L139) | **fixed** |
| 2 | High     | Feedback events are not integrity-bound to experiment routing arm/model (L151) | **open** |
| 3 | High     | Prompt contract "make-up up to 5 business days" is not enforced (L162) | **open** |
| 4 | High     | Plan version "copy" workflow is not explicitly delivered (L171) | **open** |
| 5 | Medium   | Client-side subtotal logic diverges from server scoring missing-strategy semantics (L184) | **open** |
| 6 | Medium   | Digest reminder is mounted only in cycles page (L195) | **open** |
| 7 | Low      | README migration-range statement is stale (L205) | **open** |

Headline: **1 / 7 fixed** (Blocker only). All six post-Blocker issues remain open.

---

## 1. [Blocker] Secret key material is present in delivery workspace — **fixed**

- Source evidence: `.tmp/audit_report-2.md:139` ("Secret key material is present in delivery workspace"), policy quote at `repo/infra/secrets/README.md:6`.
- Minimum actionable fix (source): "Ensure these files are never included in distributable artifacts/repo history; ship placeholders only and require operator provisioning."
- Current evidence (fixed):
  - `.gitignore` explicitly excludes the two files at `repo/.gitignore:29` (`infra/secrets/kek`) and `repo/.gitignore:30` (`infra/secrets/session_signing_key`), under the comment at `repo/.gitignore:28` `# Secrets (dev-only mount — never commit real KEK material)`.
  - `git ls-files --error-unmatch infra/secrets/kek infra/secrets/session_signing_key` → `error: pathspec … did not match any file(s) known to git` for both files (files are not tracked in repo history).
  - `repo/infra/secrets/README.md:9` documents that the dev values are generated locally via `scripts/generate_dev_secrets.sh` rather than committed.
- Residual note (non-blocking): the files still exist locally on disk (32 bytes each, mode `-rw-------`) because the Compose stack mounts them at runtime. This is the intended dev-stack behavior; delivery hygiene is enforced at the git boundary, not at the filesystem.

## 2. [High] Feedback events are not integrity-bound to experiment routing arm/model — **open**

- Source evidence: `.tmp/audit_report-2.md:151` — caller-supplied `model_version_id` accepted if it merely exists (`api/app/services/feedback.py:107`, `:114`).
- Minimum actionable fix (source): validate `(experiment_id, arm, model_version_id)` consistency against `inference_routing` before persisting.
- Current evidence (still open):
  - `repo/api/app/services/feedback.py:99-103` loads `InferenceRouting` for the experiment but only uses it to *default* `model_version_id` when the caller omits it.
  - `repo/api/app/services/feedback.py:107-116` accepts a caller-supplied `resolved_mv` and validates only that a `ModelVersion` row with that id exists (`scalar_one_or_none()` at `:114`). There is no cross-check that `resolved_mv` matches `routing.model_a_id` when `arm == "A"` or `routing.model_b_id` when `arm == "B"`.
  - No regression test exists for this constraint (confirmed below in §8 of the rewritten coverage report).
- Recommended fix location: add an arm→model_version assertion between `repo/api/app/services/feedback.py:116` and `:118`, raising `Conflict(error="feedback_arm_model_mismatch", ...)`.

## 3. [High] Prompt contract "make-up up to 5 business days" is not enforced — **open**

- Source evidence: `.tmp/audit_report-2.md:162` — schema permits up to 30 days (`api/app/schemas/cycles.py:49`).
- Minimum actionable fix (source): constrain `makeup_business_days` to `le=5` and add regression tests.
- Current evidence (still open):
  - `repo/api/app/schemas/cycles.py:49` still reads `makeup_business_days: int = Field(default=5, ge=0, le=30)`. The upper bound is 30, not 5.
  - Lifecycle tests (`repo/api/tests/api/test_cycles_lifecycle.py`) do not assert a `>5` rejection path.
- Recommended fix: change `le=30` → `le=5` and add an API test expecting 422 when the caller posts `makeup_business_days=6`.

## 4. [High] Plan version "copy" workflow is not explicitly delivered — **open**

- Source evidence: `.tmp/audit_report-2.md:171` — only create-version / rollback / diff / export / share exist (`api/app/routes/plans.py:213`, `:399`); no dedicated copy.
- Minimum actionable fix (source): add an explicit copy-version endpoint and a UI action that clones lines + metadata into a new draft version.
- Current evidence (still open):
  - `repo/api/app/routes/plans.py` has no route containing the token `copy`. Grep against `copy|Copy` in `repo/api/app/routes/plans.py` returns no matches.
  - The existing `POST /plans/{plan_id}/versions` at `repo/api/app/routes/plans.py:213` accepts a `parent_version_id` in the body but the caller must re-submit the full `lines` array — it is a create-with-parent-reference endpoint, not a copy-from-source endpoint.
  - `repo/web/src/views/PlansView.vue` offers Share and Rollback actions but no Copy control.
- Recommended fix: add `POST /plans/{plan_id}/versions/{version_id}/copy` that clones BOM lines + metadata into a new version, plus a matching UI button in `PlansView.vue`.

## 5. [Medium] Client subtotal logic diverges from server scoring missing-strategy semantics — **open**

- Source evidence: `.tmp/audit_report-2.md:184` — UI skips all missing values with `continue`, ignoring `ZERO_FILL` denominator semantics (`web/src/components/EvaluationForm.vue:35-36`).
- Minimum actionable fix (source): mirror server missing-strategy math in UI subtotal computation.
- Current evidence (still open):
  - `repo/web/src/components/EvaluationForm.vue:34-41` still computes:
    ```ts
    for (const item of props.items) {
      const raw = values.value[item.key];
      if (raw === null || raw === undefined) continue;
      weighted += raw * item.weight;
      weightSum += item.weight;
    }
    ```
  - The `TemplateItem` interface at `repo/web/src/components/EvaluationForm.vue:4-12` carries `missing_strategy: string`, but the subtotal computation never branches on it. Server behavior distinguishes `ZERO_FILL` (raw→0, weight kept in denominator) from `EXCLUDE_FROM_DENOMINATOR` (skip numerator + denominator) at `repo/api/app/services/scoring.py`.
- Recommended fix: branch on `item.missing_strategy` — for `ZERO_FILL`, treat missing as `0` and still include the weight in the denominator.

## 6. [Medium] Digest reminder is mounted only in cycles page — **open**

- Source evidence: `.tmp/audit_report-2.md:195` — `DigestBanner` only in `CyclesView` (`web/src/views/CyclesView.vue:101`).
- Minimum actionable fix (source): mount the reminder banner at shell/dashboard level with role-aware visibility.
- Current evidence (still open):
  - Grep for `DigestBanner` across `repo/web/src/` returns only two sites, both inside `CyclesView.vue`: the import at `:6` and the render at `:101`.
  - `repo/web/src/components/AppShell.vue` does not import or render `DigestBanner`; its template (`:41-63`) renders `RouterView` inside `app-shell__main` with no global banner slot.
- Recommended fix: mount `<DigestBanner v-if="session.hasPermission('cycle', 'participate')" />` inside `AppShell.vue` above `RouterView`, and remove the per-view mount to avoid double render.

## 7. [Low] README migration-range statement is stale — **open**

- Source evidence: `.tmp/audit_report-2.md:205` — README says migrations `0001 … 0009` but `0010` exists.
- Minimum actionable fix (source): update README migration range.
- Current evidence (still open):
  - `repo/README.md:25` reads `│   ├── migrations/         # alembic versions 0001 … 0009`.
  - Actual migration files in `repo/api/migrations/versions/`:
    ```
    0001_phase0_bootstrap.py          0007_phase6_feedback.py
    0002_phase1_identity.py           0008_phase7_backups.py
    0003_phase2_cycles.py             0009_phase8_model_runs.py
    0004_phase3_scoring.py            0010_phase9_ruleset_tz.py
    0005_phase4_plans.py              0011_admin_wildcard.py
    0006_phase5_models.py
    ```
  - Actual range is `0001 … 0011`, not `0001 … 0009`. The README drift has widened since the audit was written.
- Recommended fix: change `0001 … 0009` to `0001 … 0011` at `repo/README.md:25`.

---

## Verification Notes

- Each status above is based on direct file re-read of the evidence paths named in the source audit. No files were modified as part of this verification pass.
- No runtime execution was performed; latency / encryption / restore claims that depended on runtime in the source audit are not re-asserted here.
- Issue #1 is marked `fixed` on the delivery-artifact contract (git boundary). The dev-stack filesystem still carries the two files locally, which is the intended behavior for a dockerized dev stack; see `repo/infra/secrets/README.md:3`.
