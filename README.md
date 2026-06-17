# Auth Insight (`authin`)

UMC module for **per-user authentication log search** and **admin credential
testing** on Univention Corporate Server.

| | |
|---|---|
| Module ID | `authin` |
| Debian package | `univention-management-console-module-authin` |
| Category | System |
| License | AGPL-3.0-only |

## Documentation

- [Product scope and roadmap](docs/SCOPE.md)

## Quick start (development install on UCS)

```bash
cd /root/internal/authin
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

**MVP in progress** — log parsing, LDAP suggestions, and credential test panel
implemented; App Center packaging and multi-node aggregation not yet done.
