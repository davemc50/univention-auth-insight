#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Development install on a UCS primary/backup node.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

./scripts/test.sh

echo "==> Building Debian package"
dpkg-buildpackage -us -uc -b
DEB="$(find .. -maxdepth 1 -name 'univention-management-console-module-authin_*.deb' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
echo "==> Installing $DEB"
dpkg -i "$DEB"

echo "==> Running join script"
run_join_script() {
  if command -v univention-run-join-scripts >/dev/null; then
    univention-run-join-scripts --run-scripts 35univention-management-console-module-authin.inst
  else
    /usr/lib/univention-install/35univention-management-console-module-authin.inst
  fi
}
run_join_script

echo "==> Restarting UMC server"
systemctl restart univention-management-console-server

echo "Installed Auth Insight. Open UMC → Users → Auth Insight."
