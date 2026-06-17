#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Auth Insight compatibility check"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "MISSING: $1" >&2
    exit 1
  }
}

need python3
need dpkg-buildpackage

if ! dpkg -l univention-management-console-server >/dev/null 2>&1; then
  echo "WARN: univention-management-console-server not installed (expected on UCS)" >&2
fi

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Python: $PY_VERSION"

for mod in ldap univention.config_registry univention.management.console.modules; do
  python3 -c "import ${mod//./}; print('ok:', '$mod')" 2>/dev/null || {
    echo "WARN: Python module $mod not importable (credential test needs UCS runtime)" >&2
  }
done

test -f umc/authin.xml || { echo "missing umc/authin.xml"; exit 1; }
test -f debian/univention-management-console-module-authin.umc-modules || exit 1
grep -q 'authin/test_credentials' umc/authin.xml
grep -q 'dh.*umc' debian/rules

echo "Compatibility check passed."
