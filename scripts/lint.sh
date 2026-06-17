#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Auth Insight lint"

status=0

if command -v python3 >/dev/null; then
  while IFS= read -r -d '' file; do
    python3 -m py_compile "$file" || status=1
  done < <(find umc/python tests -name '*.py' -print0)
fi

if command -v xmllint >/dev/null; then
  xmllint --noout umc/authin.xml || status=1
fi

if command -v shellcheck >/dev/null; then
  shellcheck -e SC2012 scripts/*.sh || status=1
else
  echo "WARN: shellcheck not installed, skipping"
fi

# Basic JS sanity
if ! grep -q 'authin/test_credentials' umc/js/authin.js; then
  echo "JS missing credential test command" >&2
  status=1
fi

exit "$status"
