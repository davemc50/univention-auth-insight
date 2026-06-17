# Auth Insight — product scope

**Auth Insight** (`authin`) is a Univention Management Console (UMC) module for
domain administrators troubleshooting login and LDAP authentication problems.

## Problem statement

UCS records authentication events across several log files (`auth.log`, UMC server
logs, Samba, optional external sources such as Authelia on a reverse proxy), but
there is **no per-user log viewer in UMC**. Admins currently `grep` logs manually
and must interpret raw PAM/LDAP error codes.

Real example (Gustavo Moraga, 2026-06-16):

| User input | Log signal | Classification |
|------------|------------|----------------|
| `gustavo.moraga@thinkstep-anz.com` | PAM 10 / Authelia "user not found" | Wrong identity (secondary mail alias, not accepted as login principal) |
| `gustavom` | LDAP 49 / PAM 7 | Correct username, **wrong password** (UCS domain password ≠ M365 password) |
| `gustavo.m` | user not found | Near-miss username |

## Goals (MVP)

### 1. Per-user authentication log viewer

- Search by username, e-mail fragment, or free-text pattern.
- Time range filter (default: last 48 hours).
- Parse and normalise events from configurable local sources:
  - `/var/log/auth.log` (PAM: portal, SSH, sudo, Samba session hooks)
  - `/var/log/univention/management-console-server.log`
  - `/var/log/samba/` (when present)
- Classify each event:
  - `user_not_found` — unknown principal / PAM 10 / LDAP 32
  - `invalid_credentials` — wrong password / PAM 7 / LDAP 49
  - `account_locked` / `account_disabled` — when detectable
  - `server_error` — bind/service failures
  - `success` — successful authentication (when logged)
- Show timestamp, service (`univention-management-console`, `sshd`, `sudo`, …),
  source file, raw line (truncated), and human-readable summary.
- **LDAP near-match suggestions** when the typed identity does not resolve:
  match against UCS `username`, `mailPrimaryAddress`, and `e-mail` aliases using
  fuzzy string similarity.

### 2. Admin credential test panel

A dedicated UI panel (not mixed with end-user self-service):

- Fields: **username / identity**, **password**, optional **service context**
  (LDAP bind, UMC/PAM path).
- **Test** button runs an immediate check server-side and returns structured
  feedback:
  - resolved LDAP DN and canonical username (if found)
  - bind/authentication result (success / invalid credentials / user not found /
    account disabled / server error)
  - correlated recent log lines for that identity (last few minutes)
- Password is **never** written to logs, audit files, or returned in the API
  response.
- Restricted to UMC operators with domain-admin-level module access.

### 3. Packaging and operations

- Standard UCS UMC Debian package: `univention-management-console-module-authin`
- `scripts/install.sh` / `scripts/uninstall.sh` for beach-style dev deploy
- `scripts/lint.sh`, `scripts/test.sh`, `scripts/compatibility-check.sh`
- Join script registers UMC operation `authin/*` for `default-umc-all` policy.

## Non-goals (v1)

- Multi-node log aggregation (Backup DCs, remote Authelia hosts) — document
  optional extra log paths via UCR; central collector is phase 2.
- Real-time streaming / tail -f in the browser.
- End-user self-service (password reset remains UCS Self Service).
- Storing or replaying credentials beyond the immediate test request.

## Future (phase 2+)

- UCR `authin/logs/extra` for paths such as Authelia docker logs (SSH tail from
  douglas or syslog forwarder).
- App Center packaging and i18n (DE/EN).
- Account lockout counter display (`auth/faillog`).
- Export CSV for support tickets (admin-audited).

## UCR variables (planned)

| Variable | Default | Purpose |
|----------|---------|---------|
| `authin/logs/auth` | `/var/log/auth.log` | Primary PAM log |
| `authin/logs/umc` | `/var/log/univention/management-console-server.log` | UMC server |
| `authin/logs/samba` | `/var/log/samba` | Samba directory (glob) |
| `authin/logs/extra` | empty | Comma-separated additional paths |
| `authin/search/default_hours` | `48` | Default look-back window |
| `authin/search/max_lines` | `5000` | Per-file read cap |

## Access control

- Module visible only to principals granted `authin/*` via UMC policy (installed
  for `default-umc-all` → typically Domain Admins).
- Credential test API rejects unauthenticated UMC sessions.

## References

- [UCS UMC module development](https://docs.software-univention.de/developer-reference/latest/en/umc/local-system-module.html)
- [UCS App Tutorial](https://docs.software-univention.de/app-tutorial.html)
- Internal case study: Gustavo `gustavom` / Thinkstep e-mail alias / separate
  M365 vs UCS passwords (beach + douglas Authelia logs, 2026-06-16).
