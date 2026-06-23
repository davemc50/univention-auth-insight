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
