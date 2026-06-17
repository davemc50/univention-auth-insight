# SPDX-License-Identifier: AGPL-3.0-only
"""Auth Insight UMC module backend."""

from __future__ import annotations

import univention.admin.modules as udm_modules
from univention.config_registry import ucr
from univention.lib.i18n import Translation
from univention.management.console.ldap import get_admin_connection
from univention.management.console.modules import Base
from univention.management.console.modules.decorators import sanitize, simple_response
from univention.management.console.modules.sanitizers import IntegerSanitizer, StringSanitizer

from . import auth_log, credentials, ldap_match


_ = Translation("univention-management-console-module-authin").translate


class Instance(Base):

    def init(self) -> None:
        super().init()
        udm_modules.update()
        self._users_mod = udm_modules.get("users/user")

    def _log_paths(self) -> list[str]:
        return auth_log.default_log_paths_from_ucr(ucr.get)

    def _lookup_users(self):
        lo, _po = get_admin_connection()
        for user in self._users_mod.lookup(None, lo, "username=*", superordinate="cn=users"):
            yield user.dn, user

    @sanitize(
        pattern=StringSanitizer(required=False, default=""),
        hours=IntegerSanitizer(required=False, minimum=1, maximum=720, default=48),
        limit=IntegerSanitizer(required=False, minimum=1, maximum=1000, default=200),
    )
    @simple_response
    def query(self, pattern="", hours=48, limit=200):
        return auth_log.search(
            pattern,
            hours=hours,
            limit=limit,
            log_paths=self._log_paths(),
            max_lines_per_file=int(ucr.get("authin/search/max_lines", "5000") or 5000),
        )

    @sanitize(
        pattern=StringSanitizer(required=True, minimum=2),
        limit=IntegerSanitizer(required=False, minimum=1, maximum=50, default=10),
    )
    @simple_response
    def suggest(self, pattern, limit=10):
        return ldap_match.suggest_users(
            pattern,
            lookup_users=self._lookup_users,
            limit=limit,
        )

    @sanitize(
        identity=StringSanitizer(required=True, minimum=1),
        password=StringSanitizer(required=True, minimum=1),
    )
    @simple_response
    def test_credentials(self, identity, password):
        def fetch_recent_logs(username: str):
            hits = auth_log.search(
                username,
                hours=24,
                limit=50,
                log_paths=self._log_paths(),
                max_lines_per_file=int(ucr.get("authin/search/max_lines", "5000") or 5000),
            )
            if identity.lower() != username.lower():
                hits.extend(
                    auth_log.search(
                        identity,
                        hours=24,
                        limit=50,
                        log_paths=self._log_paths(),
                        max_lines_per_file=int(ucr.get("authin/search/max_lines", "5000") or 5000),
                    )
                )
            seen = set()
            merged = []
            for row in hits:
                key = row.get("id") or row.get("raw")
                if key in seen:
                    continue
                seen.add(key)
                merged.append(row)
            merged.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
            return merged[:50]

        try:
            return credentials.test_credentials(
                identity,
                password,
                fetch_recent_logs=fetch_recent_logs,
            )
        finally:
            password = ""

    @simple_response
    def sources(self):
        return [{"path": path} for path in self._log_paths() if path]
