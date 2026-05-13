from __future__ import annotations

import time
from dataclasses import dataclass

import ahocorasick
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.risk import RiskKeyword

# Matcher cache TTL: re-query DB after this many seconds to pick up keyword changes.
# Separate concern from risk_dedup_window_sec (which controls alert dedup, not cache refresh).
_TTL_SEC = 60


@dataclass
class KeywordHit:
    keyword: str
    category: str
    level: str
    keyword_id: int
    span: tuple[int, int]  # (start_inclusive, end_inclusive) from AC automaton


class RiskKeywordMatcher:
    """Aho-Corasick matcher for one (tenant_id, speaker) pair.

    Loaded lazily from DB; refreshed after _TTL_SEC seconds.
    """

    def __init__(self, tenant_id: int, speaker: str) -> None:
        self.tenant_id = tenant_id
        self.speaker = speaker
        self._automaton: ahocorasick.Automaton | None = None
        self._loaded_at: float = 0.0

    async def ensure_loaded(self, db: Session) -> None:
        if self._automaton is None or (time.monotonic() - self._loaded_at) > _TTL_SEC:
            self._load_from_db(db)  # no await — sync call

    def _load_from_db(self, db: Session) -> None:
        rows = (
            db.execute(
                select(RiskKeyword).where(
                    or_(RiskKeyword.tenant_id == self.tenant_id, RiskKeyword.tenant_id.is_(None)),
                    RiskKeyword.speaker == self.speaker,
                    RiskKeyword.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )

        A: ahocorasick.Automaton = ahocorasick.Automaton()
        for row in rows:
            A.add_word(row.keyword, (row.keyword, row.category, row.level, row.id))
        if len(A):
            A.make_automaton()
        self._automaton = A
        self._loaded_at = time.monotonic()

    def match(self, text: str) -> list[KeywordHit]:
        if self._automaton is None or not len(self._automaton):
            return []
        results: list[KeywordHit] = []
        for end_idx, (kw, cat, lv, kid) in self._automaton.iter(text):
            start_idx = end_idx - len(kw) + 1
            results.append(
                KeywordHit(
                    keyword=kw,
                    category=cat,
                    level=lv,
                    keyword_id=kid,
                    span=(start_idx, end_idx),
                )
            )
        return results


# Global singleton cache: (tenant_id, speaker) -> RiskKeywordMatcher
_matchers: dict[tuple[int, str], RiskKeywordMatcher] = {}


def get_matcher(tenant_id: int, speaker: str) -> RiskKeywordMatcher:
    key = (tenant_id, speaker)
    if key not in _matchers:
        _matchers[key] = RiskKeywordMatcher(tenant_id=tenant_id, speaker=speaker)
    return _matchers[key]
