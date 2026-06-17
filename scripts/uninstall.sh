#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

PKG=univention-management-console-module-authin

echo "==> Removing $PKG"
apt-get remove -y "$PKG" || dpkg -r "$PKG" || true

echo "==> Restarting UMC server"
systemctl restart univention-management-console-server || true

echo "Uninstalled $PKG"
