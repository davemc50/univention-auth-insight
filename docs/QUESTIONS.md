# Open questions / next steps

Items to decide before App Center or wider rollout.

## Product

1. **Log sources on douglas** — Authelia docker logs (`docker logs authelia`) live on douglas, not beach. Phase 2 options:
   - syslog forward to beach
   - `authin/logs/extra` pointing at an SSH-mounted path
   - optional small agent on douglas

2. **UMC policy** — Join script grants `authin/*` to `default-umc-all` (same as Diagnostic). Tighter option: dedicated policy for Domain Admins only.

3. **Credential test scope** — MVP tests **LDAP bind** (what Authelia uses). Should we also test:
   - Kerberos (`kinit`)?
   - UMC PAM stack (`pam_authenticate`)?

4. **Audit trail** — Should credential tests be logged to a dedicated admin audit file (who tested which username, never the password)?

## Technical

5. **Browser QA** — Frontend built from UMC template patterns but not yet verified in a live UMC session (Grid `setData` / `TitlePane` embedding may need adjustment).

6. **UCR registration** — Template file exists under `etc/univention/templates/...` but is **not** wired into the Debian package yet. Defaults are hard-coded in Python until registered.

7. **Git hosting** — Repo is local at `/root/internal/authin`. Push target: `git.in.ecotegral.com/internal/authin`?

8. **i18n** — German stubs only; English strings are inline in JS. Full `univention-l10n-build` workflow for App Center.

9. **Icon** — Placeholder SVG lock; replace before App Store listing.

## Verified on beach (2026-06-17)

- `dpkg-buildpackage` succeeds
- Package installs; join script creates `authin-all` UMC operation
- Python log search finds Gustavo entries after whole-file read fix (auth.log ~16k lines)
- Unit tests: 7 passing
