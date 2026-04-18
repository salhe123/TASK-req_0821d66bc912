# Test Coverage Details

## Project Shape

- Type: Fullstack (`api` + `web` + `e2e`)
- Backend: FastAPI (Python)
- Frontend: Vue 3 (TypeScript)
- E2E: Playwright (TypeScript)
- Test orchestration: `run_tests.sh` + Docker Compose

## Current Static Sufficiency Score

- **Score: 92 / 100**
- Basis: static inspection of repository test files and test orchestration (no runtime execution in this review).

## Tests Check

### 1) Backend Unit Tests (Python)

- Location: `api/tests/unit/`
- Status: **Strong**
- Coverage intent:
  - Core business logic: scoring, routing, state machine, RBAC, masking
  - Security primitives: passwords, session tokens, lockout math
  - Integrity helpers: canonicalization, plan export/signature, schema hashing
  - Operational helpers: retention, backup archive behavior

### 2) API / Integration Tests (Python + real HTTP requests)

- Location: `api/tests/api/`
- Status: **Strong**
- Coverage intent:
  - Real request/response path assertions with payload checks (not status-only)
  - Success + failure behavior for key domains:
    - Auth/session/CSRF
    - Cycles + assignments lifecycle
    - Plans + share links + rollback
    - Models + experiments + routing + rollback
    - Feedback + signals + rate limiting
    - Admin users, audit, backups, prune
  - Includes previously weak surfaces:
    - `test_experiment_routing_update.py`
    - `test_template_versions.py`
    - `test_submission_detail.py`
    - `test_user_management.py`
    - `test_share_links_listing.py`
    - `test_admin_backups_extended.py`

### 3) Frontend Component/View Tests (TypeScript)

- Location: `web/tests/component/`
- Status: **Strong**
- Coverage intent:
  - Core components and major views:
    - Login, Admin, Cycles, Plans, Models
    - RoutingConsole, ShareLinkModal, DigestBanner, FeedbackControl
  - User-visible behavior:
    - Tab switching
    - Modal lifecycle
    - Error messaging
    - Permission-driven UI behavior

### 4) End-to-End Tests (Playwright)

- Location: `e2e/tests/`
- Status: **Strong**
- Coverage intent:
  - Browser-driven journeys (`ui_*_journey.spec.ts`) using real DOM actions
  - Fullstack API-driven journeys for complex state-machine coverage
  - Key flows represented:
    - Login/session/nav behavior
    - Cycle lifecycle visibility and transitions
    - Plans diff/share/revoke/rollback
    - Models promote/routing/rollback
    - Feedback signal and gating behavior

## `run_tests.sh` Review

- File exists: `run_tests.sh`
- Result: **Compliant with expected shape**
  - Docker-first orchestration with Compose services
  - Main test execution inside containers:
    - `api_tests`
    - `web_tests`
    - `e2e`
    - `load_tests`
  - No Bash-level test assertions
  - No host Python/Node dependency for main test execution path

## Coverage Artifacts

- Coverage output directory: `coverage/`
- Documentation: `coverage/README.md`
- Expected generated artifacts after test run:
  - `coverage/api-coverage.xml`
  - `coverage/web-lcov/`
  - `e2e/playwright-report/`

## Why Score Is Not 100

- Some overlap exists between API-heavy Playwright tests and backend API pytest coverage, which increases maintenance burden.
- A small number of lower-priority endpoint branches may still be less directly targeted than core flows.
- Static review did not execute tests; score reflects repository evidence and test intent quality.

## Recommended Next Increment (Optional)

1. Add a lightweight traceability matrix mapping major requirements -> specific test files.
2. Add a CI summary job that publishes latest coverage percentages and links artifacts.
3. Periodically prune duplicate assertions between API pytest and Playwright API-style tests.

