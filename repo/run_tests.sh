#!/usr/bin/env bash
# Thin orchestrator for the four-tier test suite. No assertions live here —
# all pass/fail logic is inside the native test runners (pytest, vitest, playwright).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

log() { printf '\n\033[1;36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }

# Detect which Compose CLI is available — v2 plugin (`docker compose`) or the
# standalone `docker-compose` binary. Bail with a clear message if neither is
# present. Do NOT quote $COMPOSE when invoking it; it must split on spaces.
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose -f docker-compose.yml -f docker-compose.test.yml"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose -f docker-compose.yml -f docker-compose.test.yml"
else
  log "neither 'docker compose' (v2 plugin) nor 'docker-compose' (standalone) is installed"
  log "install one of: https://docs.docker.com/compose/install/"
  exit 1
fi
log "using compose: $COMPOSE"

cleanup() {
  log "tearing down stack"
  $COMPOSE down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "generating dev secrets"
bash scripts/generate_dev_secrets.sh

log "preparing coverage output dir"
mkdir -p coverage
rm -f coverage/*.xml coverage/*.lcov

log "building images"
# Build all services so test runners (api_tests, web_tests, load_tests) pick
# up any source edits since the last run.
$COMPOSE build

log "bringing up stack (db + api + web)"
$COMPOSE up -d db api web

log "waiting for api readiness"
for i in $(seq 1 60); do
  if $COMPOSE exec -T api curl -fsS http://localhost:8000/api/health/ready >/dev/null 2>&1; then
    log "api ready after ${i}s"
    break
  fi
  sleep 1
  if [[ $i -eq 60 ]]; then
    log "api never became ready"
    $COMPOSE logs api
    exit 1
  fi
done

log "waiting for web readiness"
for i in $(seq 1 30); do
  if $COMPOSE exec -T web wget -q -T 2 -O /dev/null http://127.0.0.1/ 2>/dev/null; then
    log "web ready after ${i}s"
    break
  fi
  sleep 1
  if [[ $i -eq 30 ]]; then
    log "web never became ready — dumping diagnostics"
    $COMPOSE ps
    $COMPOSE logs --tail=100 web
    $COMPOSE logs --tail=20 api
    exit 1
  fi
done

log "tier 1+3 — backend unit + api tests (pytest)"
$COMPOSE run --rm api_tests

log "tier 2 — frontend component tests (vitest)"
$COMPOSE run --rm web_tests

log "seeding e2e admin user"
$COMPOSE exec -T \
  -e SEED_ADMIN_PASSWORD=E2E-Admin-Pass-1 \
  api python -m app.scripts.seed_admin --username e2e_admin

log "tier 4 — e2e tests (playwright)"
$COMPOSE run --rm e2e

log "tier 5 — load gate (inference p95 ≤ 150ms)"
$COMPOSE run --rm load_tests

log "all tiers green"
