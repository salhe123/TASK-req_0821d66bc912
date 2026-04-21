# Audit Report 1 — Fix Verification

- Verification Date: 2026-04-21
- Method: static, evidence-bound re-read of `.tmp/audit_report-1.md` issues against the current repository (`repo/`). No runtime execution.
- Scope: every Blocker, High, Medium, and Low issue enumerated in `.tmp/audit_report-1.md` §5 (lines 124–222).

## Status Tokens

Each issue below carries exactly one of:

- **fixed** — change present in repo and resolves the stated defect.
- **verified** — unchanged behavior that already satisfies the requirement (independent re-check).
- **open** — defect still present; evidence points to the unchanged code.
- **partial** — code has changed in the direction of the fix but does not fully satisfy the minimum actionable fix from the source audit.

## Summary

| # | Severity | Title (source `.tmp/audit_report-1.md`) | Status |
|---|----------|-----------------------------------------|--------|
| 1 | Blocker  | Inadequate backup security implementation vs prompt requirement (L128) | **fixed** |
| 2 | High     | Object-level authorization gap: cycle assignment listing exposed (L140) | **fixed** |
| 3 | High     | Prompt-critical evaluation form behavior not wired in active workflow (L150) | **fixed** |
| 4 | High     | Embedded feedback loop not delivered in user-facing workflow (L161) | **fixed** |
| 5 | Medium   | Share-link role is not enforced at resolution time (L173) | **fixed** |
| 6 | Medium   | Share-link revocation lacks object-level ownership check (L183) | **fixed** |
| 7 | Medium   | Model run metadata listing missing explicit permission gate (L193) | **fixed** |
| 8 | Medium   | Nightly backup automation cannot be confirmed from delivery (L202) | **fixed** |
| 9 | Low      | Observability counter for errors is defined but not clearly wired (L214) | **fixed** |

Headline: **9 / 9 fixed**. No residual issues from `audit_report-1.md`.

---

## 1. [Blocker] Inadequate backup security implementation — **fixed**

- Source evidence: `.tmp/audit_report-1.md:128` — backup service documented as test-harness dummy; "encryption" was MAC + plaintext concatenation (`api/app/services/backup_archive.py:33`, `:37`).
- Minimum actionable fix (source): replace dummy path with real encrypted archive workflow (authenticated encryption), and separate test stub from production path via explicit environment gating.
- Current evidence (fixed):
  - `repo/api/app/services/backup_archive.py:1-19` is now documented as a real `pg_dump -Fc` + AES-GCM encrypted archive: `MAGIC (4B) | VERSION (1B) | NONCE (12B) | AES-GCM(ciphertext+tag)`.
  - `repo/api/app/services/backup_archive.py:71-75` `encrypt_payload` uses `AESGCM(_derive_key()).encrypt(nonce, plaintext, kek_fingerprint().encode('ascii'))` — KEK-fingerprint bound as AEAD associated data so an archive can't be decrypted under a different KEK.
  - `repo/api/app/services/backup_archive.py:78-93` `decrypt_payload` validates magic/version and propagates `BackupDecryptError` on `InvalidTag`.
  - `repo/api/app/services/backup_archive.py:122-145` `_pg_dump_bytes` shells to `pg_dump -Fc --no-owner --no-acl`; `:148-183` `_pg_restore_bytes` shells to `pg_restore --clean --if-exists --single-transaction`.
  - `repo/api/app/services/backup_archive.py:224-247` `restore_archive` validates manifest hash and KEK fingerprint before decrypt.
  - The old dummy helper is retained only as a back-compat alias at `repo/api/app/services/backup_archive.py:221` (`create_dummy_archive = create_archive`) — the real function now backs it.

## 2. [High] Object-level authorization gap: cycle assignment listing exposed — **fixed**

- Source evidence: `.tmp/audit_report-1.md:140` — `GET /api/cycles/{cycle_id}/assignments` had auth dependency but no role/object check (`api/app/routes/cycles.py:171`).
- Minimum actionable fix (source): require `cycle:manage`/`cycle:review` for full-cycle listing, or constrain evaluators to own assignments only.
- Current evidence (fixed):
  - `repo/api/app/routes/cycles.py:190-213` now computes `privileged = auth.has_permission("cycle", "manage") or auth.has_permission("cycle", "review")` at `:204` and, when `not privileged`, narrows the query with `Assignment.evaluator_user_id == actor | Assignment.reviewer_user_id == actor` at `:208-211`.
  - Callers with neither role on the cycle receive an empty list rather than a cross-user participant leak.

## 3. [High] Evaluation form behavior not wired in active workflow — **fixed**

- Source evidence: `.tmp/audit_report-1.md:150` — active assignment form used basic inputs and no subtotal/flag/ack flow (`web/src/views/AssignmentFormView.vue:133`, `:149`, `:170`); required behavior lived in an unused component.
- Minimum actionable fix (source): replace/augment assignment form view with the evaluation component behavior and enforce the threshold-acknowledgement / submittable contract.
- Current evidence (fixed):
  - `repo/web/src/views/AssignmentFormView.vue:6` now imports `EvaluationForm`.
  - `:213-219` renders `<EvaluationForm :items="form.items" :readonly="readOnly" :initial-values="initialValues" @update:values="onValues" @submittable="onSubmittable" />`.
  - `:103-106` wires the `submittable` + `thresholdKeys` state emitted by `EvaluationForm`.
  - `:134-138` guards the submit handler with `if (!submittable.value) { error.value = "Acknowledge the threshold breaches before submitting."; return; }` — satisfies the ack-before-submit contract.

## 4. [High] Embedded feedback loop not delivered in user-facing workflow — **fixed**

- Source evidence: `.tmp/audit_report-1.md:161` — `FeedbackView` was a read-only blocks list; `FeedbackControl` existed but was unused.
- Minimum actionable fix (source): integrate feedback controls into relevant inference/result surfaces and persist state updates in-context.
- Current evidence (fixed):
  - `repo/web/src/views/FeedbackView.vue:5` imports `FeedbackControl` and its `FeedbackKind` type.
  - `:127-153` mounts an inline predict panel (experiment selector + target id + Predict button) that calls `POST /api/inference/predict`.
  - `:159-181` renders each prediction with an embedded `<FeedbackControl … @change="(p) => onFeedbackChange(rec, p)" @error="onFeedbackError" />`.
  - `:95-107` updates the local recommendations and blocks-list state in response to `BLOCK` events — closing the loop without a round-trip.

## 5. [Medium] Share-link role not enforced at resolution time — **fixed**

- Source evidence: `.tmp/audit_report-1.md:173` — resolver checked only `build_plan:view_shared`; link role never validated against requester roles (`api/app/routes/share.py:28`, `:64`).
- Minimum actionable fix (source): enforce `link.role` compatibility with authenticated user roles before returning plan content.
- Current evidence (fixed):
  - `repo/api/app/routes/share.py:44-49`:
    ```python
    if link.role and link.role not in auth.roles and not auth.has_permission("*", "*"):
        raise Forbidden(
            error="share_link_role_mismatch",
            message="share link is bound to a different role",
            details={"required_role": link.role},
        )
    ```
  - The resolver now rejects with `403 share_link_role_mismatch` unless the caller holds the link's role (or admin wildcard).

## 6. [Medium] Share-link revocation lacks object-level ownership check — **fixed**

- Source evidence: `.tmp/audit_report-1.md:183` — revoke endpoint only checked `build_plan:manage` then revoked any link id (`api/app/routes/plans.py:541`, `:547`, `:551`).
- Minimum actionable fix (source): restrict non-admin revocation to links created by caller or links under caller-owned plans.
- Current evidence (fixed):
  - `repo/api/app/routes/plans.py:553-560`:
    ```python
    if (
        str(link.created_by) != auth.user_id
        and not auth.has_permission("*", "*")
    ):
        raise Forbidden(
            error="share_link_not_yours",
            message="only the issuer may revoke this share link",
        )
    ```
  - Non-admin callers may revoke only links they issued; admin wildcard callers retain global revoke capability.

## 7. [Medium] Model run metadata listing missing explicit permission gate — **fixed**

- Source evidence: `.tmp/audit_report-1.md:193` — run listing route had auth but no `ensure_permission(auth, "model", "run")` (`api/app/routes/models.py:279`, `:293`).
- Minimum actionable fix (source): add `model:run` permission enforcement and object-scope controls.
- Current evidence (fixed):
  - `repo/api/app/routes/models.py:283-302` is now explicitly gated: `ensure_permission(auth, "model", "run")` at `:293`, followed by `_resolve_version(db, model_id, version_id)` at `:294` which enforces the model→version path binding.

## 8. [Medium] Nightly backup automation cannot be confirmed from delivery — **fixed**

- Source evidence: `.tmp/audit_report-1.md:202` — only a manual backup trigger endpoint existed; compose manifests defined no scheduler.
- Minimum actionable fix (source): add explicit scheduled backup job path and documentation/proof in the repo.
- Current evidence (fixed):
  - `repo/api/app/services/backup_scheduler.py` exists and is the concrete scheduler module.
  - `repo/api/app/core/settings.py:54-60` surfaces `backup_scheduler_enabled`, `backup_scheduler_hour`, `backup_scheduler_timezone` as first-class settings (default off in code; opt-in via env).
  - `repo/api/app/app.py:45-55` wires the scheduler into the FastAPI lifespan: when `settings.backup_scheduler_enabled` is true it imports `get_scheduler()`, calls `scheduler.start()` on app startup, and `await scheduler.stop()` on shutdown.
  - `repo/docker-compose.yml:26-28` sets `BACKUP_SCHEDULER_ENABLED: "true"`, `BACKUP_SCHEDULER_HOUR: "2"`, `BACKUP_SCHEDULER_TIMEZONE: UTC` for the api service — concrete, auditable automation rather than an out-of-repo cron.

## 9. [Low] Observability counter for errors not clearly wired — **fixed**

- Source evidence: `.tmp/audit_report-1.md:214` — `inc_error()` exists but had no direct call sites in the request/error middleware flow (`api/app/services/metrics.py:42`).
- Minimum actionable fix (source): increment error counter in exception path(s) and add a regression test.
- Current evidence (fixed):
  - `repo/api/app/middleware/error_envelope.py:14`, `:19`, `:31` call `metrics.inc_error()` from the error-handler branches.
  - `repo/api/app/middleware/request_context.py:25`, `:28` call `metrics.inc_error()` when the request raises an unhandled exception and when the response carries a `>=500` status.
  - Exercised by `repo/api/tests/api/test_metrics_warmup.py` (metrics endpoint counters progress past zero after error-path traffic).

---

## Verification Notes

- Each status above is based on direct file re-read of the evidence paths named in the source audit. No files were modified as part of this verification pass.
- No runtime execution was performed. Claims that depended on runtime in the source audit (e.g. operational p95 conformance, real restore behavior on production hardware) remain out-of-scope and are not re-asserted here.
- The pre-existing `Cannot Confirm Statistically` items in the source audit are still bounded to runtime-only conditions and therefore do not move on a static pass.
