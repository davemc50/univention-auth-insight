# SPDX-License-Identifier: AGPL-3.0-only

import unittest

from authin import ldap_match


class _Props:
    def __init__(self, **fields):
        self.info = dict(fields)
        for key, value in fields.items():
            setattr(self, key, value)


class _UdmLookupUser:
    """UDM lookup() returns username in .info, not as attributes."""

    def __init__(self, info):
        self.info = info

    def __getitem__(self, key):
        return self.info[key]


def _user(username, primary="", aliases=(), disabled="0"):
    info = {
        "username": username,
        "mailPrimaryAddress": primary,
        "e-mail": list(aliases),
        "disabled": disabled,
    }
    props = _UdmLookupUser(info)
    return f"uid={username},cn=users,dc=example,dc=com", props


class LdapMatchTests(unittest.TestCase):

    def test_normalize_identity(self):
        self.assertEqual(ldap_match.normalize_identity("EXAMPLE\\user007"), "user007")
        self.assertEqual(ldap_match.normalize_identity("user123@example.com"), "user123")

    def test_suggest_prefix_match(self):
        users = [
            _user("user007", "user123@example.com"),
            _user("user008", "user456@example.com"),
        ]
        rows = ldap_match.suggest_users("user0", lookup_users=lambda: users, limit=5)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["username"], "user007")
        self.assertGreaterEqual(rows[0]["score"], 0.9)

    def test_suggest_near_match(self):
        users = [
            _user("user007", "user123@example.com", ["user123@alias.example.com"]),
            _user("user008", "user456@example.com"),
        ]
        rows = ldap_match.suggest_users("user12", lookup_users=lambda: users, limit=5)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["username"], "user007")

    def test_resolve_exact_mail_alias(self):
        users = [
            _user("user007", "user123@example.com", ["user123@alias.example.com"]),
        ]
        resolved = ldap_match.resolve_username(
            "user123@alias.example.com",
            lookup_users=lambda: users,
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.username, "user007")
        self.assertEqual(resolved.score, 1.0)


if __name__ == "__main__":
    unittest.main()
