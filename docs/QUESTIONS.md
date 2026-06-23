# Open questions / next steps

## Product

1. **Credential test scope** — MVP tests LDAP bind and Kerberos. Add UMC PAM path?
2. **Audit trail** — Log credential tests to a dedicated admin audit file?
3. **App Center** — i18n workflow and icon polish for public listing.

## Technical

4. **UCR registration** — Template exists under `etc/univention/templates/...` but is not wired into the Debian package postinst yet.
5. **Browser QA** — Playwright e2e under `tests/e2e/` (requires `.env.e2e`).

## Deployment

Site-specific host names and URLs belong in `.env` (see `.env.example`), not in
source code. Internal runbooks live in the ops wiki.
