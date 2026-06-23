#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Preflight: Auth Insight UMC module via Playwright (optional).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f "$ROOT/.env.e2e" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env.e2e"
  set +a
fi

if [ -z "${UMC_AUTHIN_PASSWORD:-}" ]; then
  echo "Set UMC_AUTHIN_PASSWORD (or create $ROOT/.env.e2e from .env.e2e.example)." >&2
  exit 2
fi

if [ -z "${UMC_AUTHIN_URL:-}" ]; then
  echo "Set UMC_AUTHIN_URL (or create $ROOT/.env.e2e from .env.e2e.example)." >&2
  exit 2
fi

export UMC_AUTHIN_URL
export UMC_AUTHIN_USER="${UMC_AUTHIN_USER:-Administrator}"

E2E_DIR="$ROOT/tests/e2e"

if ! command -v npx >/dev/null; then
  echo "npx not found; install Node.js/npm." >&2
  exit 1
fi

if [ ! -d "$E2E_DIR/node_modules/@playwright/test" ]; then
  echo "==> Installing Playwright test dependencies"
  npm --prefix "$E2E_DIR" install --no-fund --no-audit
fi

"$E2E_DIR/node_modules/.bin/playwright" install chromium
"$E2E_DIR/node_modules/.bin/playwright" test -c "$E2E_DIR/playwright.config.js" "$@"
