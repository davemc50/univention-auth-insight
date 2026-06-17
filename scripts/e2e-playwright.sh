#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Preflight: Auth Insight UMC module via Playwright (optional).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

UMC_URL="${UMC_AUTHIN_URL:-https://beach.ecotegral.com/univention/management/}"
UMC_USER="${UMC_AUTHIN_USER:-Administrator}"
UMC_PASSWORD="${UMC_AUTHIN_PASSWORD:-}"

if [ -z "$UMC_PASSWORD" ]; then
  echo "Set UMC_AUTHIN_PASSWORD to run browser e2e tests." >&2
  exit 2
fi

if ! command -v npx >/dev/null; then
  echo "npx not found; install Node.js/npm." >&2
  exit 1
fi

export UMC_AUTHIN_URL UMC_AUTHIN_USER UMC_AUTHIN_PASSWORD
npx --yes playwright@1.52.0 test -c "$ROOT/tests/e2e/playwright.config.js"
