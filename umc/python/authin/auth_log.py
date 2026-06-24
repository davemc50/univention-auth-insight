# SPDX-License-Identifier: AGPL-3.0-only
"""Parse and classify authentication-related log lines."""

from __future__ import annotations

import glob
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Iterator, List, Optional, Sequence


# syslog: 2026-06-16T12:15:23.684719+12:00 host ...
_SYSLOG_TS = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?)"
)
# UMC log: 2026-06-16T12:15:25.480739+12:00    ERROR ...
_UMC_TS = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?)"
)

_PAM_USER = re.compile(r"\buser=(?P<user>[^\s]+)")
_PAM_LOGNAME = re.compile(r"logname=(?P<user>[^\s]+)")
_PAM_CODE = re.compile(
    r"received for user (?P<user>[^:]+):\s*(?P<code>\d+)\s*\((?P<msg>[^)]+)\)"
)
_UNIX_CHKPWD = re.compile(r"password check failed for user \((?P<user>[^)]+)\)")
_PAM_SERVICE = re.compile(r"pam_\w+\((?P<service>[^:)]+)")
_UMC_PAM_ERR = re.compile(
    r"PAM: authentication error: \('(?P<msg>[^']+)',\s*(?P<code>\d+)\)"
)
_AUTHELIA_USER = re.compile(
    r"Unsuccessful 1FA authentication attempt by user '(?P<user>[^']+)'"
)
_AUTHELIA_NOT_FOUND = re.compile(
    r"username input '(?P<user>[^']+)' which usually indicates they do not exist"
)
_LDAP_CODE = re.compile(r"LDAP Result Code (?P<code>\d+)\s+\"(?P<msg>[^\"]+)\"")
_AUTHELIA_TS = re.compile(r'time="(?P<ts>[^"]+)"')
_CLIENT_PATTERNS = (
    re.compile(r"remote_ip=(?P<client>[^\s\"']+)"),
    re.compile(r"\bfrom (?P<client>\d{1,3}(?:\.\d{1,3}){3}) port \d+"),
    re.compile(r"\brhost=(?P<client>[^\s]+)"),
    re.compile(r"\bclient=(?P<client>[^\s,;]+)"),
    re.compile(r"\bremote (?:(?:addr|address))=(?P<client>[^\s]+)"),
    re.compile(r"\bx-forwarded-for[=:]\s*(?P<client>[^\s,;]+)", re.IGNORECASE),
)

_PAM_CODE_LABELS = {
    "7": "invalid_credentials",
    "10": "user_not_found",
}

_LDAP_CODE_LABELS = {
    "32": "user_not_found",
    "49": "invalid_credentials",
    "53": "server_error",
    "81": "server_error",
}


@dataclass(frozen=True)
class AuthEvent:
    id: str
    timestamp: str
    identity: str
    classification: str
    summary: str
    service: str
    source: str
    raw: str
    code: str = ""
    client: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchResult:
    events: List[dict]
    remote_status: List[dict]

    def to_dict(self) -> dict:
        return {
            "events": self.events,
            "remote_status": self.remote_status,
        }


def _parse_timestamp(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            dt = datetime.strptime(raw.replace("Z", "+00:00"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _classify_pam_code(code: str, msg: str = "") -> str:
    label = _PAM_CODE_LABELS.get(code)
    if label:
        return label
    lowered = msg.lower()
    if "user not known" in lowered or "no such user" in lowered:
        return "user_not_found"
    if "authentication failure" in lowered or "invalid credentials" in lowered:
        return "invalid_credentials"
    if "account" in lowered and "lock" in lowered:
        return "account_locked"
    if "disabled" in lowered:
        return "account_disabled"
    return "auth_failure"


def _classify_ldap_code(code: str) -> str:
    return _LDAP_CODE_LABELS.get(code, "auth_failure")


def _extract_service(line: str) -> str:
    lowered = line.lower()
    match = _PAM_SERVICE.search(line)
    if match:
        return match.group("service")
    if "univention-management-console-server" in line:
        return "univention-management-console"
    if "sshd" in line:
        return "sshd"
    if "sudo" in line:
        return "sudo"
    if "smbd" in line or "samba" in line:
        return "samba"
    if "krb5" in lowered or "kinit" in lowered or "kerberos" in lowered:
        return "kerberos"
    if "authelia" in line.lower():
        return "authelia"
    return "unknown"


def _extract_identity(line: str) -> str:
    for pattern in (_PAM_CODE, _PAM_USER, _PAM_LOGNAME, _UNIX_CHKPWD, _AUTHELIA_USER, _AUTHELIA_NOT_FOUND):
        match = pattern.search(line)
        if match:
            user = match.group("user").strip()
            if user and user not in ("", "uid=0"):
                return user
    return ""


def _extract_client(line: str) -> str:
    for pattern in _CLIENT_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        client = (match.group("client") or "").strip().strip("\"'")
        if client and client not in ("", "-", "?", "unknown", "0.0.0.0"):
            return client
    return ""


def parse_line(line: str, source: str = "") -> Optional[AuthEvent]:
    line = line.rstrip("\n")
    if not line.strip():
        return None

    lowered = line.lower()
    if not any(
        token in lowered
        for token in (
            "authentication",
            "auth):",
            "pam:",
            "invalid credentials",
            "password check failed",
            "user not known",
            "authelia",
            "krb5",
            "kinit",
            "kerberos",
            "preauthentication",
            "ldap result code",
            "failed password",
            "accepted publickey",
            "authentication failure",
        )
    ):
        return None

    ts_raw = ""
    authelia_ts = _AUTHELIA_TS.search(line)
    if authelia_ts:
        ts_raw = authelia_ts.group("ts")
    if not ts_raw:
        for pattern in (_SYSLOG_TS, _UMC_TS):
            match = pattern.match(line)
            if match:
                ts_raw = match.group("ts")
                break
    if not ts_raw:
        return None

    identity = _extract_identity(line)
    client = _extract_client(line)
    service = _extract_service(line)
    classification = "auth_failure"
    summary = "Authentication event"
    code = ""

    pam_code = _PAM_CODE.search(line)
    if pam_code:
        code = pam_code.group("code")
        classification = _classify_pam_code(code, pam_code.group("msg"))
        summary = pam_code.group("msg").strip()
        identity = identity or pam_code.group("user").strip()

    umc_err = _UMC_PAM_ERR.search(line)
    if umc_err:
        code = umc_err.group("code")
        classification = _classify_pam_code(code, umc_err.group("msg"))
        summary = umc_err.group("msg")

    ldap_code = _LDAP_CODE.search(line)
    if ldap_code:
        code = ldap_code.group("code")
        classification = _classify_ldap_code(code)
        summary = ldap_code.group("msg")

    if _AUTHELIA_NOT_FOUND.search(line):
        classification = "user_not_found"
        summary = "User not found (Authelia)"
    elif _AUTHELIA_USER.search(line) and classification == "auth_failure":
        classification = "invalid_credentials"
        summary = "LDAP bind failed (Authelia)"

    if "password check failed" in lowered:
        classification = "invalid_credentials"
        summary = "Password check failed"

    if "session opened for user" in lowered and "authentication failure" not in lowered:
        classification = "success"
        summary = "Session opened"

    if "accepted publickey for" in lowered or "accepted password for" in lowered:
        classification = "success"
        summary = "SSH login accepted"
        ssh_user = re.search(r"for (?P<user>[^\s]+) from ", line)
        if ssh_user:
            identity = ssh_user.group("user").strip()

    if "failed password for" in lowered:
        classification = "invalid_credentials"
        summary = "SSH password failed"
        ssh_user = re.search(r"for (?P<user>[^\s]+) from ", line)
        if ssh_user:
            identity = ssh_user.group("user").strip()

    if not identity and classification == "auth_failure" and not code:
        return None
    if not identity:
        identity = "(unknown)"

    raw = line if len(line) <= 500 else line[:497] + "..."
    event_id = f"{ts_raw}:{identity}:{service}:{hash(line) & 0xFFFFFF:06x}"
    return AuthEvent(
        id=event_id,
        timestamp=ts_raw,
        identity=identity,
        classification=classification,
        summary=summary,
        service=service,
        source=source,
        raw=raw,
        code=code,
        client=client,
    )


def iter_log_files(paths: Sequence[str]) -> Iterator[str]:
    seen: set[str] = set()
    for path in paths:
        path = path.strip()
        if not path:
            continue
        if os.path.isdir(path):
            for match in sorted(glob.glob(os.path.join(path, "*.log"))):
                if match not in seen and os.path.isfile(match):
                    seen.add(match)
                    yield match
            continue
        if os.path.isfile(path) and path not in seen:
            seen.add(path)
            yield path


def _read_tail(path: str, max_lines: int) -> List[str]:
    try:
        size = os.path.getsize(path)
    except OSError:
        return []
    # Small/medium logs: read whole file so older events within the time window are not missed.
    if size <= 20 * 1024 * 1024:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.readlines()
        except OSError:
            return []
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.readlines()[-max_lines:]
    except OSError:
        return []


def pattern_matches_all(pattern: str) -> bool:
    """True when the search should return all auth events (no identity/text filter)."""
    return not (pattern or "").strip() or (pattern or "").strip() == "*"


def search(
    pattern: str = "",
    *,
    hours: int = 48,
    limit: int = 200,
    log_paths: Sequence[str],
    max_lines_per_file: int = 5000,
    remote_sources: Optional[Sequence] = None,
    max_lines_per_remote: int = 5000,
    now: Optional[datetime] = None,
) -> SearchResult:
    match_all = pattern_matches_all(pattern)
    pattern_lower = "" if match_all else (pattern or "").strip().lower()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max(1, hours))

    events: List[AuthEvent] = []
    remote_status: List[dict] = []

    def _collect_line(line: str, source: str) -> None:
        event = parse_line(line, source=source)
        if event is None:
            return
        if pattern_lower:
            haystack = " ".join(
                (
                    event.identity,
                    event.summary,
                    event.service,
                    event.raw,
                    event.classification,
                    event.client,
                )
            ).lower()
            if pattern_lower not in haystack:
                return
        event_time = _parse_timestamp(event.timestamp)
        if event_time and event_time < cutoff:
            return
        events.append(event)

    for path in iter_log_files(log_paths):
        for line in _read_tail(path, max_lines_per_file):
            _collect_line(line, path)

    if remote_sources:
        from . import remote_log

        remote_lines, statuses = remote_log.fetch_remote_logs(
            remote_sources,
            max_lines_per_container=max_lines_per_remote,
        )
        remote_status = [status.to_dict() for status in statuses]
        for line, source in remote_lines:
            _collect_line(line, source)

    events.sort(key=lambda item: item.timestamp, reverse=True)
    return SearchResult(
        events=[event.to_dict() for event in events[: max(1, limit)]],
        remote_status=remote_status,
    )


def default_log_paths_from_ucr(get_ucr) -> List[str]:
    paths = [
        get_ucr("authin/logs/auth", "/var/log/auth.log"),
        get_ucr("authin/logs/umc", "/var/log/univention/management-console-server.log"),
        get_ucr("authin/logs/samba", "/var/log/samba"),
    ]
    extra = get_ucr("authin/logs/extra", "") or ""
    paths.extend(part.strip() for part in extra.split(",") if part.strip())
    return paths
