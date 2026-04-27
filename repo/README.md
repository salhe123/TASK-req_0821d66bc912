# Model Governance & Evaluation Workbench

A fullstack, offline-first web application for **regulated model governance**:
evaluation cycles with deterministic scoring, versioned build plans with
line-level BOM diffs, ML model registry with A/B routing + guardrail-driven
rollback, and a closed end-user feedback loop. Every mutation is audited,
every sensitive column is encrypted at rest, and the whole stack runs
air-gapped on a single host.

## Architecture & Tech Stack

* **Frontend:** Vue 3 + Pinia + Vue Router (SPA served by nginx)
* **Backend:** FastAPI + SQLAlchemy 2 (async) + Alembic
* **Database:** PostgreSQL 16 + `pgcrypto` (KEK-keyed at-rest encryption)
* **Containerization:** Docker & Docker Compose (required)
* **Testing:** pytest (unit + API), vitest + @vue/test-utils (component),
  Playwright (browser E2E), asyncio load driver

## Project Structure

```text
.
├── api/                    # FastAPI backend, SQLAlchemy, Alembic, Dockerfile
│   ├── app/                # source (routes, services, models, middleware)
│   ├── migrations/         # alembic versions 0001 … 0009
│   └── tests/              # unit/, api/, load/
├── web/                    # Vue 3 SPA + Dockerfile + nginx.conf
│   ├── src/                # views, components, stores, lib
│   └── tests/component/    # vitest suites
├── e2e/                    # Playwright E2E tests + Dockerfile
│   └── tests/              # ui_*_journey + *_flow + smoke/security
├── infra/
│   ├── db/init.sql         # pgcrypto bootstrap
│   └── secrets/            # operator-mounted KEK + session signing key
├── scripts/                # dev helpers (generate_dev_secrets.sh)
├── coverage/               # run_tests.sh output (git-ignored)
├── .env.example            # environment variable template
├── docker-compose.yml      # dev/runtime orchestration (MANDATORY)
├── docker-compose.test.yml # test tier overlay
├── run_tests.sh            # standardized test runner (MANDATORY)
├── plan.md                 # phased implementation schedule
├── runbook.md              # operator runbook (KEK, backup, restore, rollback)
└── README.md
```

## Prerequisites

This project is designed to run entirely within containers. You must have:

* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/) (v2 plugin or standalone)

## Running the Application

1. **Copy the environment template** (every variable has a sensible dev default
   baked into `docker-compose.yml`, so this step is optional but makes
   overrides explicit):
   ```bash
   cp .env.example .env
   ```

2. **Provision dev secrets** — generates a random 32-byte KEK and session
   signing key under `infra/secrets/`:
   ```bash
   bash scripts/generate_dev_secrets.sh
   ```

3. **Build and start the stack:**
   ```bash
   docker-compose up --build -d
   ```
   Equivalent on Compose v2 plugin:
   ```bash
   docker compose up --build -d
   ```

4. **Seed the first administrator** (one-shot, KEK-verified; you choose the
   password via `SEED_ADMIN_PASSWORD`):
   ```bash
   docker-compose exec -e SEED_ADMIN_PASSWORD='AdminTest123!' api \
     python -m app.scripts.seed_admin --username admin
   ```

5. **Access the app:**
   * Frontend: `http://localhost:8080`
   * Backend API: `http://localhost:8000/api`
   * API Documentation (dev only): `http://localhost:8000/api/docs`

6. **Stop the application:**
   ```bash
   docker-compose down -v
   ```

## Verification (Required)

Use both API and UI checks to confirm the system is healthy.

### API Verification (curl/Postman)

1. Health check:
   ```bash
   curl -i http://localhost:8000/api/health
   ```
   Expected: HTTP `200` and body containing `"status":"ok"`.

2. Login check (replace credentials if you changed them):
   ```bash
   curl -i http://localhost:8000/api/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"AdminTest123!"}'
   ```
   Expected: HTTP `200` and JSON including `session_token` and `csrf_token`.

3. Authenticated check in Postman (or equivalent):
   - `GET http://localhost:8000/api/auth/me`
   - Header `Authorization: Bearer <session_token from login>`
   - Header `X-CSRF-Token: <csrf_token from login>`
   Expected: HTTP `200` and role/permission payload.

### UI Verification

1. Open `http://localhost:8080`.
2. Log in with `admin / AdminTest123!`.
3. Confirm these pages load without auth errors:
   - `Dashboard`
   - `Evaluation Cycles`
   - `Build Plans`
   - `Model Registry`
   - `Feedback`
   - `Administration`
4. In `Administration`, confirm users and audit tabs load data.

## Testing

All unit, integration, component, browser E2E, and load tests are executed via
a single standardized shell script. It spins up a disposable Compose stack,
applies migrations, seeds a known E2E admin, runs every tier in its native
runner, and tears the stack down on exit. The script is a thin orchestrator —
no Bash-level assertions.

Make the script executable, then run it:

```bash
chmod +x run_tests.sh
./run_tests.sh
```

*The script exits with `0` on full green and a non-zero code on any tier
failure, for CI/CD integration.*

### Tiers

| # | Tier | Runner | Scope |
|:-:|:-----|:-------|:------|
| 1 | Backend unit | `pytest` | services, scoring, RBAC, masking, lockout math, diff, signatures, token skew |
| 2 | API integration | `pytest` + `httpx` | real HTTP against the live api container; every endpoint has success + failure payload-shape assertions |
| 3 | Frontend component | `vitest` + `@vue/test-utils` | reusable components and view-level behaviors (tabs, modals, permission gating) |
| 4 | E2E | `playwright` | *browser journeys* driving the real DOM plus *full-stack API journeys* through nginx→api→db |
| 5 | Load gate | asyncio httpx driver | approved-route inference `p95 ≤ 150 ms` (configurable via `P95_BUDGET_MS`) |

### Coverage artifacts

After a run, `coverage/` holds:

* `coverage/api-coverage.xml` — Cobertura from the api unit + API tier
* `coverage/web-lcov/` — lcov + HTML from the vitest tier
* `e2e/playwright-report/` — HTML trace bundle from the E2E run

See `coverage/README.md` for scope caveats (what is / isn't line-instrumented
across the two container processes).

## Seeded Credentials

Production seeds **no credentials**. The first administrator is provisioned
via the KEK-verified `seed_admin` CLI (step 4 above), so the password is
operator-chosen rather than a hard-coded default — a requirement of the
regulated / air-gapped design.

For local demo/login and role-based checks, use this explicit matrix.

| Role | Username | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `AdminTest123!` | Set by you in step 4; full access to every module. |
| **Evaluator** | `demo_evaluator` | `Demo-Password-123!` | Use for evaluator-only flows and permission checks. |
| **Reviewer** | `demo_reviewer` | `Demo-Password-123!` | Use for review/approval permission checks. |
| **Plan Owner** | `demo_plan_owner` | `Demo-Password-123!` | Use for share-link and build-plan permission checks. |
| **ML Engineer** | `demo_ml_engineer` | `Demo-Password-123!` | Use for model registry and routing permission checks. |
| **Administrator** (test only) | `e2e_admin` | `E2E-Admin-Pass-1` | Seeded by `run_tests.sh` before the Playwright tier; lives only in the disposable test DB and is torn down with the stack. |

Create the four demo role users above from the running stack with the admin account:

```bash
docker-compose exec api python - <<'PY'
import asyncio, httpx

API = "http://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "AdminTest123!"
PASSWORD = "Demo-Password-123!"

USERS = [
    ("demo_evaluator", ["Evaluator"]),
    ("demo_reviewer", ["Reviewer"]),
    ("demo_plan_owner", ["Plan Owner"]),
    ("demo_ml_engineer", ["ML Engineer"]),
]

async def main():
    async with httpx.AsyncClient(base_url=API, timeout=10.0) as c:
        r = await c.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        r.raise_for_status()
        body = r.json()
        c.headers["Authorization"] = f"Bearer {body['session_token']}"
        c.headers["X-CSRF-Token"] = body["csrf_token"]

        for username, roles in USERS:
            resp = await c.post(
                "/api/admin/users",
                json={
                    "username": username,
                    "display_name": username,
                    "password": PASSWORD,
                    "roles": roles,
                },
            )
            if resp.status_code in (200, 201, 409):
                print(f"{username}: {resp.status_code}")
            else:
                raise RuntimeError(f"{username}: {resp.status_code} {resp.text}")

asyncio.run(main())
PY
```
