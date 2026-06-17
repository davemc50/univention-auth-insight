# SPDX-License-Identifier: AGPL-3.0-only

import unittest
from datetime import datetime, timezone

from authin import auth_log


class AuthLogTests(unittest.TestCase):

    def test_parse_user_not_known(self):
        line = (
            "2026-06-16T12:15:23.684719+12:00 beach python3: pam_sss(univention-management-console:auth): "
            "received for user gustavo.moraga@thinkstep-anz.com: 10 (User not known to the underlying authentication module)"
        )
        event = auth_log.parse_line(line, source="/var/log/auth.log")
        self.assertIsNotNone(event)
        self.assertEqual(event.classification, "user_not_found")
        self.assertIn("gustavo.moraga", event.identity)

    def test_parse_invalid_credentials_pam7(self):
        line = (
            "2026-06-16T09:56:02.213374+12:00 beach sudo: pam_sss(sudo-i:auth): "
            "received for user davidmc: 7 (Authentication failure)"
        )
        event = auth_log.parse_line(line)
        self.assertIsNotNone(event)
        self.assertEqual(event.classification, "invalid_credentials")
        self.assertEqual(event.identity, "davidmc")

    def test_parse_authelia_ldap49(self):
        line = (
            'time="2026-06-16T12:15:01+12:00" level=error msg="Unsuccessful 1FA authentication attempt by user \'gustavom\'" '
            'error="authentication failed. Cause: error occurred performing bind: LDAP Result Code 49 \\"Invalid Credentials\\": "'
        )
        event = auth_log.parse_line(line, source="authelia.log")
        self.assertIsNotNone(event)
        self.assertEqual(event.identity, "gustavom")
        self.assertEqual(event.classification, "invalid_credentials")

    def test_search_fixture_file(self):
        now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
        results = auth_log.search(
            "gustavo",
            hours=240,
            limit=50,
            log_paths=["tests/fixtures/sample_auth.log"],
            now=now,
        )
        self.assertGreaterEqual(len(results), 2)
        classes = {row["classification"] for row in results}
        self.assertIn("user_not_found", classes)
        self.assertIn("invalid_credentials", classes)


if __name__ == "__main__":
    unittest.main()
