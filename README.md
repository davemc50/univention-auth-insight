# Auth Insight (`authin`)

UMC module for **per-user authentication log search** and **admin credential
testing** on Univention Corporate Server.

| | |
|---|---|
| Module ID | `authin` |
| Debian package | `univention-management-console-module-authin` |
| Category | Users |
| License | AGPL-3.0-only |

## Documentation

- [Product scope and roadmap](docs/SCOPE.md)
- [Remote docker SSO logs](docs/remote-docker-logs.md)

Site-specific deployment (host names, SSH users) belongs in `.env` — see
`.env.example`. Internal runbooks: ops wiki **Auth Insight** page.

## Quick start (development install on UCS)

```bash
cd authin
./scripts/lint.sh
./scripts/test.sh
sudo ./scripts/install.sh
```

Open UMC → **System** → **Auth Insight**.

Remove with:

```bash
sudo ./scripts/uninstall.sh
```

## Build Debian package

```bash
./scripts/compatibility-check.sh
dpkg-buildpackage -us -uc -b
sudo dpkg -i ../univention-management-console-module-authin_*.deb
sudo univention-run-join-scripts
systemctl restart univention-management-console-server
```

## Repository layout

```
authin/
  debian/                  Debian packaging (dh-umc-module)
  umc/
    authin.xml             Module declaration
    python/authin/         Python backend
    js/                    Dojo/UMC frontend
    icons/                 Module icons
  tests/                   pytest unit tests
  scripts/                 install, lint, test, compatibility
  docs/SCOPE.md            Scope document
```

## Status

**MVP** — log parsing, LDAP suggestions, credential test, remote Authelia docker
logs with graceful offline handling. App Center packaging in progress.
