# SPDX-License-Identifier: AGPL-3.0-only
"""Fetch authentication logs from remote docker hosts via SSH."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, replace
from typing import Callable, Iterable, List, Sequence


_CONTAINER_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
_HOST_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")


class RemoteLogError(RuntimeError):
    """Remote log fetch failed."""


@dataclass(frozen=True)
class RemoteSource:
    host_id: str
    host: str
    user: str
    container: str
    label: str = ""
    sudo: bool = False

    def display_source(self) -> str:
        if self.label:
            return self.label
        return f"{self.host_id}:{self.container}"


@dataclass(frozen=True)
class RemoteFetchStatus:
    host_id: str
    host: str
    container: str
    label: str
    status: str
    message: str = ""
    line_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in ("true", "1", "yes", "on")


def _parse_container_entry(entry: dict, host_id: str, host: str, user: str, sudo: bool) -> RemoteSource | None:
    name = str(entry.get("name", "")).strip()
    if not name or not _CONTAINER_NAME.match(name):
        return None
    label = str(entry.get("label", "")).strip()
    return RemoteSource(
        host_id=host_id,
        host=host,
        user=user,
        container=name,
        label=label,
        sudo=sudo,
    )


def _parse_host_entry(entry: dict) -> List[RemoteSource]:
    host_id = str(entry.get("name", "")).strip()
    host = str(entry.get("host", "")).strip()
    if not host_id or not _HOST_ID.match(host_id) or not host:
        return []
    user = str(entry.get("user", "")).strip()
    sudo = _truthy(str(entry.get("sudo", "")))
    containers = entry.get("containers") or []
    sources: List[RemoteSource] = []
    if isinstance(containers, list):
        for container in containers:
            if isinstance(container, dict):
                source = _parse_container_entry(container, host_id, host, user, sudo)
                if source:
                    sources.append(source)
            elif isinstance(container, str):
                name = container.strip()
                if name and _CONTAINER_NAME.match(name):
                    sources.append(
                        RemoteSource(
                            host_id=host_id,
                            host=host,
                            user=user,
                            container=name,
                            sudo=sudo,
                        )
                    )
    return sources


def parse_remote_sources_from_ucr(get_ucr: Callable) -> List[RemoteSource]:
    if not _truthy(get_ucr("authin/remote/enabled", "false")):
        return []

    raw_hosts = (get_ucr("authin/remote/hosts", "") or "").strip()
    if raw_hosts:
        try:
            parsed = json.loads(raw_hosts)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        sources: List[RemoteSource] = []
        for entry in parsed:
            if isinstance(entry, dict):
                sources.extend(_parse_host_entry(entry))
        return sources

    host = (get_ucr("authin/remote/host", "") or "").strip()
    if not host:
        return []

    host_id = (get_ucr("authin/remote/name", "remote") or "remote").strip()
    if not _HOST_ID.match(host_id):
        host_id = "remote"
    user = (get_ucr("authin/remote/user", "") or "").strip()
    sudo = _truthy(get_ucr("authin/remote/sudo", "false"))
    containers = get_ucr("authin/remote/containers", "") or ""
    labels = get_ucr("authin/remote/labels", "") or ""

    label_map = {}
    for part in labels.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, label = part.split("=", 1)
        name = name.strip()
        label = label.strip()
        if name and label:
            label_map[name] = label

    sources: List[RemoteSource] = []
    for name in containers.split(","):
        name = name.strip()
        if not name or not _CONTAINER_NAME.match(name):
            continue
        sources.append(
            RemoteSource(
                host_id=host_id,
                host=host,
                user=user,
                container=name,
                label=label_map.get(name, ""),
                sudo=sudo,
            )
        )
    return sources


def _ssh_target(source: RemoteSource) -> str:
    if "@" in source.host:
        return source.host
    if source.user:
        return f"{source.user}@{source.host}"
    return source.host


def fetch_docker_logs(
    source: RemoteSource,
    *,
    max_lines: int = 5000,
    timeout: int = 20,
) -> List[str]:
    if not _CONTAINER_NAME.match(source.container):
        raise RemoteLogError(f"invalid container name: {source.container!r}")

    tail = max(100, min(int(max_lines), 50000))
    docker_cmd = f"docker logs --tail {tail} {source.container} 2>&1"
    if source.sudo:
        remote_cmd = f"sudo -n {docker_cmd}"
    else:
        remote_cmd = docker_cmd
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
        _ssh_target(source),
        remote_cmd,
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RemoteLogError("connection timed out") from exc
    except OSError as exc:
        raise RemoteLogError(str(exc)) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        if len(detail) > 200:
            detail = detail[:197] + "..."
        raise RemoteLogError(detail or f"exit code {completed.returncode}")

    return completed.stdout.splitlines()


def _status_for_source(source: RemoteSource) -> RemoteFetchStatus:
    return RemoteFetchStatus(
        host_id=source.host_id,
        host=source.host,
        container=source.container,
        label=source.display_source(),
        status="unavailable",
        message="",
        line_count=0,
    )


def fetch_remote_logs(
    sources: Sequence[RemoteSource],
    *,
    max_lines_per_container: int = 5000,
) -> tuple[List[tuple[str, str]], List[RemoteFetchStatus]]:
    """Return parsed log lines and per-source availability status."""
    rows: List[tuple[str, str]] = []
    statuses: List[RemoteFetchStatus] = []
    for source in sources:
        status = _status_for_source(source)
        try:
            lines = fetch_docker_logs(source, max_lines=max_lines_per_container)
        except RemoteLogError as exc:
            statuses.append(
                replace(status, message=str(exc) or "unavailable")
            )
            continue
        statuses.append(
            replace(status, status="ok", line_count=len(lines))
        )
        label = source.display_source()
        for line in lines:
            rows.append((line, label))
    return rows, statuses
