#!/usr/bin/env bash
# Generates dev-only secrets for the test stack. DO NOT use these in production.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)/infra/secrets"
mkdir -p "$DIR"

if [[ ! -f "$DIR/kek" ]]; then
  head -c 32 /dev/urandom > "$DIR/kek"
  chmod 600 "$DIR/kek"
  echo "generated $DIR/kek"
fi

if [[ ! -f "$DIR/session_signing_key" ]]; then
  head -c 32 /dev/urandom > "$DIR/session_signing_key"
  chmod 600 "$DIR/session_signing_key"
  echo "generated $DIR/session_signing_key"
fi
