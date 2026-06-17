#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/compatibility-check.sh
./scripts/lint.sh

if [ -n "${UMC_AUTHIN_PASSWORD:-}" ]; then
  ./scripts/e2e-playwright.sh || exit 1
else
  echo "Skip Playwright e2e (set UMC_AUTHIN_PASSWORD to enable)."
fi

if python3 -c 'import pytest' 2>/dev/null; then
  PYTHONPATH="$ROOT/umc/python" python3 -m pytest -q tests
else
  echo "pytest not installed; running unittest"
  PYTHONPATH="$ROOT/umc/python" python3 -m unittest discover -s tests -t "$ROOT" -p 'test_*.py' -v
fi

echo "All tests passed."
