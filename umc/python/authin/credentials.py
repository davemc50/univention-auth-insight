# SPDX-License-Identifier: AGPL-3.0-only
"""Admin credential test helpers (LDAP bind + Kerberos)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional

import ldap

from univention.admin import uldap
from univention.config_registry import ucr

from .ldap_match import UserCandidate, resolve_username


@dataclass(frozen=True)
class CredentialTestResult:
    ok: bool
    classification: str
    summary: str
    username: str = ""
    dn: str = ""
    disabled: bool = False
    krb5_principal: str = ""
    ldap_classification: str = ""
    krb5_classification: str = ""
    log_hits: Optional[List[dict]] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if data["log_hits"] is None:
            data["log_hits"] = []
        return data


def _ldap_server_uri() -> str:
    host = ucr.get("ldap/server/name", ucr.get("hostname", "localhost"))
    port = ucr.get("ldap/server/port", "7389")
    return f"ldap://{host}:{port}"


def _find_user_dn(username: str) -> tuple[Optional[str], Optional[UserCandidate]]:
    import univention.admin.modules as udm_modules
    from univention.management.console.ldap import get_admin_connection

    udm_modules.update()
    users_mod = udm_modules.get("users/user")
    lo, _po = get_admin_connection()

    def lookup_users():
        for user in users_mod.lookup(None, lo, "username=*", superordinate="cn=users"):
            yield user.dn, user

    candidate = resolve_username(username, lookup_users=lookup_users)
    if candidate is None:
        return None, None
    return candidate.dn, candidate


def _read_krb5_principal(dn: str) -> str:
    try:
        lo = uldap.access(host=ucr.get("ldap/server/name"), port=int(ucr.get("ldap/server/port", 7389)))
        result = lo.get(dn, attr=["krb5PrincipalName"])
        values = result.get("krb5PrincipalName", [])
        return values[0].decode() if values else ""
    except Exception:
        return ""


def _test_krb5(principal: str, password: str) -> tuple[str, str]:
    if not principal:
        return "skipped", "No Kerberos principal on LDAP object."
    ccache = os.path.join(tempfile.gettempdir(), f"authin-kinit-{os.getpid()}")
    env = os.environ.copy()
    env["KRB5CCNAME"] = f"FILE:{ccache}"
    try:
        proc = subprocess.run(
            ["kinit", "--password-file=STDIN", principal],
            input=f"{password}\n",
            text=True,
            capture_output=True,
            timeout=15,
            env=env,
            check=False,
        )
        if proc.returncode == 0:
            return "success", "Kerberos ticket obtained (kinit succeeded)."
        stderr = (proc.stderr or proc.stdout or "").strip()
        lowered = stderr.lower()
        if "preauthentication failed" in lowered or "password incorrect" in lowered:
            return "invalid_credentials", "Kerberos pre-authentication failed (wrong password)."
        if "client not found" in lowered or "principal unknown" in lowered:
            return "user_not_found", "Kerberos principal not found."
        return "auth_failure", stderr or "Kerberos authentication failed."
    except FileNotFoundError:
        return "skipped", "kinit not available on this host."
    except subprocess.TimeoutExpired:
        return "server_error", "Kerberos test timed out."
    finally:
        try:
            os.unlink(ccache)
        except OSError:
            pass


def test_credentials(
    identity: str,
    password: str,
    *,
    fetch_recent_logs: Optional[Callable[[str], List[dict]]] = None,
) -> dict:
    identity = (identity or "").strip()
    if not identity:
        return CredentialTestResult(
            ok=False,
            classification="invalid_input",
            summary="Username or identity is required.",
        ).to_dict()
    if not password:
        return CredentialTestResult(
            ok=False,
            classification="invalid_input",
            summary="Password is required for credential test.",
        ).to_dict()

    dn, candidate = _find_user_dn(identity)
    if dn is None or candidate is None:
        return CredentialTestResult(
            ok=False,
            classification="user_not_found",
            summary=f"No LDAP user matches identity {identity!r}.",
        ).to_dict()

    if candidate.disabled:
        return CredentialTestResult(
            ok=False,
            classification="account_disabled",
            summary=f"Account {candidate.username} is disabled in LDAP.",
            username=candidate.username,
            dn=candidate.dn,
            disabled=True,
        ).to_dict()

    uri = _ldap_server_uri()
    connection = ldap.initialize(uri)
    connection.protocol_version = ldap.VERSION3
    ldap_classification = "server_error"
    try:
        connection.start_tls_s()
        connection.simple_bind_s(dn, password)
        ldap_classification = "success"
    except ldap.INVALID_CREDENTIALS:
        ldap_classification = "invalid_credentials"
    except ldap.NO_SUCH_OBJECT:
        ldap_classification = "user_not_found"
    except ldap.LDAPError:
        ldap_classification = "server_error"
    finally:
        try:
            connection.unbind_s()
        except Exception:
            pass

    krb5_principal = _read_krb5_principal(dn)
    krb5_classification, krb5_summary = _test_krb5(krb5_principal, password)

    ok = ldap_classification == "success" and krb5_classification in ("success", "skipped")
    if ldap_classification == "success" and krb5_classification == "success":
        summary = "LDAP bind and Kerberos (kinit) both succeeded."
        classification = "success"
    elif ldap_classification == "success":
        summary = f"LDAP bind succeeded. Kerberos: {krb5_summary}"
        classification = "partial_success"
    elif krb5_classification == "success":
        summary = "Kerberos succeeded but LDAP bind failed."
        classification = "partial_success"
    elif ldap_classification == "invalid_credentials":
        summary = "LDAP bind failed: invalid credentials (wrong password)."
        classification = "invalid_credentials"
    elif ldap_classification == "user_not_found":
        summary = "LDAP user DN not found during bind."
        classification = "user_not_found"
    else:
        summary = "Credential test failed (LDAP and/or Kerberos)."
        classification = ldap_classification

    log_hits: List[dict] = []
    if fetch_recent_logs is not None:
        log_hits = fetch_recent_logs(candidate.username)

    return CredentialTestResult(
        ok=ok,
        classification=classification,
        summary=summary,
        username=candidate.username,
        dn=dn,
        disabled=candidate.disabled,
        krb5_principal=krb5_principal,
        ldap_classification=ldap_classification,
        krb5_classification=krb5_classification,
        log_hits=log_hits,
    ).to_dict()
