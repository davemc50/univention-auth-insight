# Auth Insight for Univention UCS

**Auth Insight** (`authin`) is a [Univention Management Console (UMC)](https://docs.software-univention.de/) module for domain administrators who need to troubleshoot login and LDAP authentication problems without SSH and manual `grep`.

| | |
|---|---|
| Module ID | `authin` |
| Debian package | `univention-management-console-module-authin` |
| UMC category | **Users** |
| License | [AGPL-3.0-only](LICENSE) |
| Upstream | https://github.com/davemc50/univention-auth-insight |

## Features

- Search authentication events by username, e-mail fragment, wildcards (`mart*`), or `*` (all entries)
- Time window filter (default 48 hours; increase for older events)
- Parses local logs: `auth.log`, UMC server log, Samba (when present)
- Optional remote **Authelia** / SSO docker logs over SSH (multi-host)
- Classifies results: user not found, invalid credentials, success, etc.
- **Client** column when the log records origin IP (Authelia, SSH, PAM `rhost`)
- LDAP near-match suggestions for typos and wrong e-mail aliases
- **Open user** — jump from a log line to the user object in UMC Users
- Admin **credential test** panel (LDAP bind + Kerberos; password never stored)

## Requirements

- Univention Corporate Server with UMC (tested on UCS 5.x-style installs)
- Package build deps (on the UCS node): `univention-management-console-dev`, `debhelper`, `dh-python`, `python3-ldap`, `gettext`
- Runtime: `univention-management-console-server`, `python3-ldap`, `openssh-client` (for optional remote logs)
- UMC access: module grants `authin/*` to the built-in **Administrators** group via join script

## Install from pre-built package

Download the latest `.deb` from the [Releases](https://github.com/davemc50/univention-auth-insight/releases) page (or from `dist/` in this repository), then on your **UCS primary or backup** node:

```bash
sudo dpkg -i univention-management-console-module-authin_*_all.deb
sudo univention-run-join-scripts --run-scripts 35univention-management-console-module-authin.inst
sudo systemctl restart univention-management-console-server
```

Open UMC in the browser, then go to **Users → Auth Insight**. After upgrading, do a full page reload of UMC (the package sets Dojo `cacheBust` and disables long-lived cache for the module JS).

If `dpkg` reports missing dependencies:

```bash
sudo apt-get install -f
```

## Build and install from source

On the UCS node (or a build host with UCS dev packages):

```bash
git clone git@github.com:davemc50/univention-auth-insight.git
cd univention-auth-insight
./scripts/compatibility-check.sh
./scripts/test.sh
dpkg-buildpackage -us -uc -b
sudo dpkg -i ../univention-management-console-module-authin_*_all.deb
sudo univention-run-join-scripts --run-scripts 35univention-management-console-module-authin.inst
sudo systemctl restart univention-management-console-server
```

Or use the convenience script (runs tests, builds, installs, join script, restart):

```bash
sudo ./scripts/install.sh
```

## Uninstall

```bash
sudo ./scripts/uninstall.sh
```

## Usage tips

| Task | How |
|------|-----|
| Show all recent auth events | Leave search empty or enter `*`, set **Hours** (e.g. 48 or 720), click **Search** |
| Find one user | Enter username or e-mail fragment; use **720+** hours for older logins |
| Open LDAP user | Click **Identity** or select row → **Open user** |
| Test password | **Credential test** tab — LDAP + Kerberos bind (does not change the password) |

After upgrading, confirm the subtitle shows the expected **Module debug version**; if not, log out of UMC and hard-refresh — the browser may cache old JavaScript.

## Optional: remote SSO / Authelia docker logs

When Authelia (or similar) runs on separate docker hosts, Auth Insight can tail container logs over SSH during each search. Local UCS logs are always searched; unreachable hosts are listed as unavailable without failing the search.

1. Copy `.env.example` to `.env` and set your SSH hosts (see [docs/remote-docker-logs.md](docs/remote-docker-logs.md)).
2. Run:

```bash
sudo ./scripts/setup-remote-logs.sh
sudo systemctl restart univention-management-console-server
```

Alternatively set UCR directly:

```bash
ucr set authin/remote/enabled=true
ucr set authin/remote/hosts='[{"name":"sso","host":"docker-host.example.com","user":"deploy","containers":[{"name":"authelia","label":"SSO"}]}]'
```

See also [docs/syslog-authelia.md](docs/syslog-authelia.md) for syslog forwarding instead of SSH.

## Configuration (UCR)

| Variable | Default | Purpose |
|----------|---------|---------|
| `authin/logs/auth` | `/var/log/auth.log` | PAM / SSH auth log |
| `authin/logs/umc` | `.../management-console-server.log` | UMC server log |
| `authin/logs/samba` | `/var/log/samba` | Samba log directory |
| `authin/logs/extra` | (empty) | Comma-separated extra paths |
| `authin/search/max_lines` | `5000` | Max lines read per local file |
| `authin/remote/enabled` | `false` | Enable SSH docker log fetch |
| `authin/remote/hosts` | `[]` | JSON array of remote hosts |

Template definitions: `etc/univention/templates/files/etc/univention/registry.info/variables/univention-management-console-module-authin.cfg`

## Documentation

- [Product scope and roadmap](docs/SCOPE.md)
- [Remote docker SSO logs](docs/remote-docker-logs.md)
- [Syslog forwarding for Authelia](docs/syslog-authelia.md)
- [Open questions / roadmap](docs/QUESTIONS.md)

## Development

```bash
./scripts/lint.sh          # py_compile, xmllint, shellcheck, site-name scan
./scripts/test.sh          # unit tests
./scripts/e2e-playwright.sh   # optional browser tests (needs .env.e2e)
```

Site-specific host names and URLs belong in `.env` only (gitignored). `.env.example` shows the schema with placeholder hostnames.

## Repository layout

```
debian/                  Debian packaging (dh-umc-module)
dist/                    Pre-built .deb packages for release
docs/                    Scope, remote logs, syslog notes
scripts/                 install, lint, test, remote setup
tests/                   Python unit tests; optional Playwright e2e
umc/
  authin.xml             Module declaration
  python/authin/         Python backend
  js/                    UMC frontend (Dojo)
  icons/                 Module icons
```

## License

Copyright © 2026 Dave McDonald and contributors.  
Released under the [GNU Affero General Public License v3.0 or later](LICENSE).
