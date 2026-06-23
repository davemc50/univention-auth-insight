#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Enable Auth Insight remote docker log fetch from configured SSO hosts.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

ENV_FILE="${AUTHIN_ENV_FILE:-$ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
elif [[ -f "$ROOT/.env.example" ]]; then
  echo "No $ENV_FILE found. Copy .env.example to .env and customize host settings." >&2
  exit 1
fi

ENABLED="${AUTHIN_REMOTE_ENABLED:-false}"
HOSTS_JSON="${AUTHIN_REMOTE_HOSTS_JSON:-}"

if [[ -z "$HOSTS_JSON" ]]; then
  HOST="${AUTHIN_REMOTE_HOST:-}"
  USER="${AUTHIN_REMOTE_USER:-}"
  CONTAINERS="${AUTHIN_REMOTE_CONTAINERS:-}"
  if [[ -z "$HOST" || -z "$CONTAINERS" ]]; then
    echo "Set AUTHIN_REMOTE_HOSTS_JSON or AUTHIN_REMOTE_HOST + AUTHIN_REMOTE_CONTAINERS in .env" >&2
    exit 1
  fi
fi

verify_host() {
  local host="$1"
  local user="$2"
  local sudo_flag="$3"
  local container="$4"
  local target="${user:+${user}@}${host}"
  local docker_cmd="docker logs --tail 1 ${container}"
  if [[ "$sudo_flag" == "true" ]]; then
    docker_cmd="sudo -n ${docker_cmd}"
  fi
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$target" "$docker_cmd" >/dev/null
}

echo "==> Verifying remote docker log access"
if [[ -n "$HOSTS_JSON" ]]; then
  AUTHIN_REMOTE_HOSTS_JSON="$HOSTS_JSON" python3 <<'PY'
import json, os, subprocess

hosts = json.loads(os.environ["AUTHIN_REMOTE_HOSTS_JSON"])
for entry in hosts:
    host = entry.get("host", "")
    user = entry.get("user", "")
    sudo = bool(entry.get("sudo"))
    target = f"{user}@{host}" if user and "@" not in host else host
    for container in entry.get("containers") or []:
        name = container["name"] if isinstance(container, dict) else container
        cmd = f"docker logs --tail 1 {name}"
        if sudo:
            cmd = f"sudo -n {cmd}"
        subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", target, cmd],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"  ok: {entry.get('name', host)}:{name}")
PY
else
  IFS=',' read -r -a container_list <<< "${CONTAINERS}"
  for container in "${container_list[@]}"; do
    container="${container// /}"
    verify_host "$HOST" "$USER" "${AUTHIN_REMOTE_SUDO:-false}" "$container"
    echo "  ok: ${HOST}:${container}"
  done
fi

echo "==> Setting UCR"
if [[ -n "$HOSTS_JSON" ]]; then
  ucr set authin/remote/enabled="${ENABLED}" authin/remote/hosts="${HOSTS_JSON}"
else
  ucr set \
    authin/remote/enabled="${ENABLED}" \
    authin/remote/host="${HOST}" \
    authin/remote/user="${USER}" \
    authin/remote/containers="${CONTAINERS}" \
    authin/remote/labels="${AUTHIN_REMOTE_LABELS:-}" \
    authin/remote/sudo="${AUTHIN_REMOTE_SUDO:-false}"
fi
ucr set authin/remote/max_lines="${AUTHIN_REMOTE_MAX_LINES:-5000}"

echo "==> Restarting UMC server"
systemctl restart univention-management-console-server

echo "Done. Auth Insight remote docker log sources are configured."
