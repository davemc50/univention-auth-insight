#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Auth Insight lint"

status=0

FORBIDDEN='douglas|beach|mollusk|thinkstep|ecotegral|davidmc|matthias|nebel'

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

if ! grep -q 'test_credentials' umc/js/authin.js; then
  echo "JS missing credential test command" >&2
  status=1
fi

while IFS= read -r -d '' file; do
  case "$file" in
    */.env|*/.env.*|*/node_modules/*|*/debian/*|scripts/lint.sh|*/scripts/lint.sh)
      continue
      ;;
  esac
  if grep -Eiq "$FORBIDDEN" "$file"; then
    echo "Forbidden site-specific text in $file (use .env instead)" >&2
    grep -Ein "$FORBIDDEN" "$file" >&2 || true
    status=1
  fi
done < <(find umc tests scripts docs etc -type f \
  \( -name '*.py' -o -name '*.js' -o -name '*.sh' -o -name '*.md' -o -name '*.cfg' -o -name '*.xml' -o -name '*.json' -o -name '*.log' \) \
  ! -path '*/node_modules/*' \
  ! -path '*/e2e/artifacts/*' \
  -print0 2>/dev/null)

exit "$status"
