# SPDX-License-Identifier: AGPL-3.0-only
"""Resolve and fuzzy-match UCS user identities."""

from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional, Sequence


@dataclass(frozen=True)
class UserCandidate:
    username: str
    dn: str
    mail_primary: str
    mail_aliases: tuple
    disabled: bool
    score: float
    matched_on: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["mail_aliases"] = list(self.mail_aliases)
        return data


def normalize_identity(value: str) -> str:
    value = (value or "").strip()
    if "\\" in value:
        value = value.rsplit("\\", 1)[-1]
    if "@" in value:
        value = value.split("@", 1)[0]
    return value.lower()


def _similarity(needle: str, haystack: str) -> float:
    if not needle or not haystack:
        return 0.0
    needle = needle.lower()
    haystack = haystack.lower()
    if needle == haystack:
        return 1.0
    if needle in haystack or haystack in needle:
        return 0.92
    return difflib.SequenceMatcher(None, needle, haystack).ratio()


def _get_prop(props, name, default=""):
    value = getattr(props, name, None)
    if value not in (None, ""):
        return value
    info = getattr(props, "info", None)
    if isinstance(info, dict) and name in info:
        value = info.get(name)
        if value not in (None, ""):
            return value
    if hasattr(props, "__getitem__"):
        try:
            value = props[name]
            if value not in (None, ""):
                return value
        except (KeyError, TypeError):
            pass
    return default


def _collect_aliases(props) -> tuple:
    aliases = []
    primary = str(_get_prop(props, "mailPrimaryAddress", "") or "")
    if primary:
        aliases.append(primary)
    for key in ("e-mail", "mailAlternativeAddress"):
        raw = _get_prop(props, key, None)
        if not raw:
            continue
        if isinstance(raw, (list, tuple)):
            aliases.extend(str(item) for item in raw if item)
        else:
            aliases.append(str(raw))
    return tuple(dict.fromkeys(aliases))


def score_user(props, dn: str, needle: str) -> Optional[UserCandidate]:
    username = str(_get_prop(props, "username", "") or "")
    if not username:
        return None

    aliases = _collect_aliases(props)
    fields = {
        "username": username,
        "mail_primary": str(_get_prop(props, "mailPrimaryAddress", "") or ""),
    }
    for alias in aliases:
        fields.setdefault("mail_alias", alias)

    best_score = 0.0
    matched_on = ""
    for field_name, field_value in fields.items():
        if not field_value:
            continue
        for mode in (needle, normalize_identity(needle)):
            score = _similarity(mode, field_value)
            if field_name == "username" and normalize_identity(needle) == field_value.lower():
                score = max(score, 0.98)
            if score > best_score:
                best_score = score
                matched_on = field_name

    if best_score < 0.45:
        return None

    disabled = str(_get_prop(props, "disabled", "0")) in ("1", "True", "true")
    return UserCandidate(
        username=username,
        dn=dn,
        mail_primary=str(_get_prop(props, "mailPrimaryAddress", "") or ""),
        mail_aliases=aliases,
        disabled=disabled,
        score=round(best_score, 3),
        matched_on=matched_on,
    )


def suggest_users(
    needle: str,
    *,
    lookup_users: Callable[[], Sequence[tuple]],
    limit: int = 10,
) -> List[dict]:
    needle = (needle or "").strip()
    if len(needle) < 2:
        return []

    candidates: List[UserCandidate] = []
    for dn, props in lookup_users():
        scored = score_user(props, dn, needle)
        if scored:
            candidates.append(scored)

    candidates.sort(key=lambda item: (-item.score, item.username))
    return [item.to_dict() for item in candidates[: max(1, limit)]]


def resolve_username(
    identity: str,
    *,
    lookup_users: Callable[[], Sequence[tuple]],
) -> Optional[UserCandidate]:
    identity = (identity or "").strip()
    if not identity:
        return None

    exact_filters = [
        identity,
        normalize_identity(identity),
    ]
    if "@" in identity:
        exact_filters.append(identity.lower())

    best: Optional[UserCandidate] = None
    for dn, props in lookup_users():
        username = str(_get_prop(props, "username", "") or "")
        primary = str(_get_prop(props, "mailPrimaryAddress", "") or "").lower()
        aliases = [value.lower() for value in _collect_aliases(props)]
        identity_lower = identity.lower()
        if identity_lower in ({username.lower(), primary} | set(aliases)):
            candidate = score_user(props, dn, identity)
            if candidate:
                candidate = UserCandidate(
                    username=candidate.username,
                    dn=candidate.dn,
                    mail_primary=candidate.mail_primary,
                    mail_aliases=candidate.mail_aliases,
                    disabled=candidate.disabled,
                    score=1.0,
                    matched_on="exact",
                )
                return candidate
        for candidate in [score_user(props, dn, value) for value in exact_filters]:
            if candidate and (best is None or candidate.score > best.score):
                best = candidate
    return best
