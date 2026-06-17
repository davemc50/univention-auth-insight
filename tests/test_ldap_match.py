# SPDX-License-Identifier: AGPL-3.0-only

import unittest
from types import SimpleNamespace

from authin import ldap_match


class _Props(SimpleNamespace):
    pass


def _user(username, primary="", aliases=(), disabled="0"):
    props = _Props(
        username=username,
        mailPrimaryAddress=primary,
        **{"e-mail": list(aliases)},
        disabled=disabled,
    )
    return f"uid={username},cn=users,dc=example,dc=com", props


class LdapMatchTests(unittest.TestCase):

    def test_normalize_identity(self):
        self.assertEqual(ldap_match.normalize_identity("ECOTEGRAL\\gustavom"), "gustavom")
        self.assertEqual(ldap_match.normalize_identity("gustavo.moraga@ecotegral.com"), "gustavo.moraga")

    def test_suggest_near_match(self):
        users = [
            _user("gustavom", "gustavo.moraga@ecotegral.com", ["gustavo.moraga@thinkstep-anz.com"]),
            _user("davidmc", "david.mc@ecotegral.com"),
        ]
        rows = ldap_match.suggest_users("gustavo.m", lookup_users=lambda: users, limit=5)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["username"], "gustavom")

    def test_resolve_exact_mail_alias(self):
        users = [
            _user("gustavom", "gustavo.moraga@ecotegral.com", ["gustavo.moraga@thinkstep-anz.com"]),
        ]
        resolved = ldap_match.resolve_username(
            "gustavo.moraga@thinkstep-anz.com",
            lookup_users=lambda: users,
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.username, "gustavom")
        self.assertEqual(resolved.score, 1.0)


if __name__ == "__main__":
    unittest.main()
