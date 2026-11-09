# SPDX-License-Identifier: AGPL-3.0-only

import unittest
from datetime import datetime, timezone
from unittest import mock

from authin import auth_log, remote_log


class AuthLogTests(unittest.TestCase):

    def test_parse_user_not_known(self):
        line = (
            "2026-06-16T12:15:23.684719+12:00 ucs-primary python3: pam_sss(univention-management-console:auth): "
            "received for user user123@alias.example.com: 10 (User not known to the underlying authentication module)"
        )
        event = auth_log.parse_line(line, source="/var/log/auth.log")
        self.assertIsNotNone(event)
        self.assertEqual(event.classification, "user_not_found")
        self.assertIn("user123@alias.example.com", event.identity)

    def test_parse_invalid_credentials_pam7(self):
        line = (
            "2026-06-16T09:56:02.213374+12:00 ucs-primary sudo: pam_sss(sudo-i:auth): "
            "received for user user007: 7 (Authentication failure)"
        )
        event = auth_log.parse_line(line)
        self.assertIsNotNone(event)
        self.assertEqual(event.classification, "invalid_credentials")
        self.assertEqual(event.identity, "user007")

    def test_parse_authelia_ldap49(self):
        line = (
            'time="2026-06-16T12:15:01+12:00" level=error msg="Unsuccessful 1FA authentication attempt by user \'user007\'" '
            'error="authentication failed. Cause: error occurred performing bind: LDAP Result Code 49 \\"Invalid Credentials\\": "'
        )
        event = auth_log.parse_line(line, source="authelia.log")
        self.assertIsNotNone(event)
        self.assertEqual(event.identity, "user007")
        self.assertEqual(event.classification, "invalid_credentials")

    def test_parse_authelia_client_ip(self):
        line = (
            'time="2026-06-16T12:15:01+12:00" level=error msg="Unsuccessful 1FA authentication attempt by user \'user007\'" '
            'error="authentication failed" method=POST path=/api/firstfactor remote_ip=10.0.0.136'
        )
        event = auth_log.parse_line(line, source="authelia.log")
        self.assertIsNotNone(event)
        self.assertEqual(event.client, "10.0.0.136")

    def test_parse_sshd_client_ip(self):
        line = (
            "2026-06-24T09:47:25.626224+12:00 ucs-primary sshd[2827434]: "
            "Accepted publickey for user007 from 10.64.1.32 port 59958 ssh2: RSA SHA256:abc"
        )
        event = auth_log.parse_line(line, source="/var/log/auth.log")
        self.assertIsNotNone(event)
        self.assertEqual(event.client, "10.64.1.32")

    def test_parse_session_opened(self):
        line = (
            "2026-11-10T09:56:40.232073+13:00 ucs-primary smbd[551864]: "
            "pam_unix(samba:session): session opened for user user007(uid=2098) by (uid=0)"
        )
        event = auth_log.parse_line(line, source="/var/log/auth.log")
        self.assertIsNotNone(event)
        self.assertEqual(event.classification, "success")
        self.assertEqual(event.identity, "user007")
        self.assertEqual(event.summary, "Session opened")

    def test_parse_pam_krb5_authenticated(self):
        line = (
            "2026-11-10T10:08:45.685767+13:00 ucs-primary python3: "
            "pam_krb5(univention-management-console:auth): "
            "user user007 authenticated as user007@EXAMPLE.COM"
        )
        event = auth_log.parse_line(line, source="/var/log/auth.log")
        self.assertIsNotNone(event)
        self.assertEqual(event.classification, "success")
        self.assertIn("user007", event.identity)

    def test_parse_samba_kerberos_as_req_with_fallback_ts(self):
        line = (
            "  Kerberos: AS-REQ SUCCESS ipv4:10.64.32.31:60465 "
            "user007@EXAMPLE.COM krbtgt/EXAMPLE.COM@EXAMPLE.COM pa=ENC-TS"
        )
        event = auth_log.parse_line(
            line,
            source="/var/log/samba/log.samba",
            fallback_ts="2026/11/10 10:04:48.800121",
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.classification, "success")
        self.assertEqual(event.identity, "user007@EXAMPLE.COM")
        self.assertEqual(event.client, "10.64.32.31")
        self.assertEqual(event.timestamp, "2026/11/10 10:04:48.800121")

    def test_parse_samba_preauth_ok(self):
        line = (
            "  Kerberos: ENC-TS Pre-authentication succeeded -- "
            "user007@EXAMPLE.COM using aes256-cts-hmac-sha1-96"
        )
        event = auth_log.parse_line(
            line,
            source="/var/log/samba/log.samba",
            fallback_ts="2026/11/10 10:04:48.793652",
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.classification, "success")
        self.assertEqual(event.identity, "user007@EXAMPLE.COM")

    def test_skip_err_preauth_required(self):
        line = (
            "  Kerberos: AS-REQ ERR_PREAUTH_REQUIRED ipv4:10.64.32.31:60464 "
            "user007@EXAMPLE.COM krbtgt/EXAMPLE.COM@EXAMPLE.COM"
        )
        event = auth_log.parse_line(
            line,
            source="/var/log/samba/log.samba",
            fallback_ts="2026/11/10 10:04:48.793652",
        )
        self.assertIsNone(event)

    def test_search_pairs_samba_timestamp_header(self):
        import tempfile
        import os

        now = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)
        content = (
            "[2026/11/10 10:04:48.800121,  3, pid=1] ../../source4/auth/kerberos/krb5_init_context.c:93(smb_krb5_debug_wrapper)\n"
            "  Kerberos: AS-REQ SUCCESS ipv4:10.64.32.31:60465 user007@EXAMPLE.COM "
            "krbtgt/EXAMPLE.COM@EXAMPLE.COM pa=ENC-TS\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.samba")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            result = auth_log.search(
                "user007",
                hours=48,
                limit=10,
                log_paths=[path],
                now=now,
            )
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0]["classification"], "success")
        self.assertEqual(result.events[0]["client"], "10.64.32.31")

    def test_iter_log_files_includes_samba_log_star(self):
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "app.log"), "w", encoding="utf-8").write("x\n")
            open(os.path.join(tmp, "log.samba"), "w", encoding="utf-8").write("x\n")
            open(os.path.join(tmp, "log.samba.1.gz"), "wb").write(b"x")
            open(os.path.join(tmp, "log."), "w", encoding="utf-8").write("")
            found = set(os.path.basename(p) for p in auth_log.iter_log_files([tmp]))
        self.assertEqual(found, {"app.log", "log.samba"})

    def test_search_fixture_file(self):
        now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
        result = auth_log.search(
            "user",
            hours=240,
            limit=50,
            log_paths=["tests/fixtures/sample_auth.log"],
            now=now,
        )
        self.assertGreaterEqual(len(result.events), 2)
        classes = {row["classification"] for row in result.events}
        self.assertIn("user_not_found", classes)
        self.assertIn("invalid_credentials", classes)
        self.assertEqual(result.remote_status, [])

    def test_search_star_pattern_matches_all(self):
        now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
        paths = ["tests/fixtures/sample_auth.log"]
        all_events = auth_log.search(
            "*",
            hours=240,
            limit=50,
            log_paths=paths,
            now=now,
        )
        filtered = auth_log.search(
            "user007",
            hours=240,
            limit=50,
            log_paths=paths,
            now=now,
        )
        self.assertGreater(len(all_events.events), len(filtered.events))
        empty = auth_log.search(
            "",
            hours=240,
            limit=50,
            log_paths=paths,
            now=now,
        )
        self.assertEqual(len(all_events.events), len(empty.events))

    def test_pattern_matches_all(self):
        self.assertTrue(auth_log.pattern_matches_all(""))
        self.assertTrue(auth_log.pattern_matches_all("  "))
        self.assertTrue(auth_log.pattern_matches_all("*"))
        self.assertTrue(auth_log.pattern_matches_all(" * "))
        self.assertFalse(auth_log.pattern_matches_all("user007"))
        self.assertFalse(auth_log.pattern_matches_all("*user*"))

    def test_pattern_matches_text_substring_and_wildcards(self):
        hay = "user007 success kerberos ticket granted"
        self.assertTrue(auth_log.pattern_matches_text(hay, "user007"))
        self.assertTrue(auth_log.pattern_matches_text(hay, "user"))
        self.assertFalse(auth_log.pattern_matches_text(hay, "user*x"))
        self.assertTrue(auth_log.pattern_matches_text(hay, "user*"))
        self.assertTrue(auth_log.pattern_matches_text("user007@example.com success", "user*"))
        self.assertTrue(auth_log.pattern_matches_text(hay, "*007*"))
        self.assertFalse(auth_log.pattern_matches_text(hay, "user*x"))
        # Literal asterisk must not be required in the log line.
        self.assertFalse(auth_log.pattern_matches_text("user007 success", "user007*x"))

    @mock.patch("authin.remote_log.fetch_remote_logs")
    def test_search_reports_unavailable_remote(self, mock_fetch):
        mock_fetch.return_value = (
            [],
            [
                remote_log.RemoteFetchStatus(
                    host_id="offline-host",
                    host="offline.example.com",
                    container="authelia",
                    label="Offline SSO",
                    status="unavailable",
                    message="connection timed out",
                )
            ],
        )
        from authin import remote_log as remote_log_mod

        source = remote_log_mod.RemoteSource(
            host_id="offline-host",
            host="offline.example.com",
            user="deploy",
            container="authelia",
        )
        result = auth_log.search(
            "user007",
            hours=48,
            limit=10,
            log_paths=[],
            remote_sources=[source],
        )
        self.assertEqual(result.events, [])
        self.assertEqual(result.remote_status[0]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
