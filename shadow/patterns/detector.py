"""Offline pattern detection over captured event streams.

Algorithm: sliding n-gram frequency count over event signatures. For each
length ``n`` in ``[min_length, max_length]``, count how often each n-gram
appears across the user's historical sessions. Those exceeding the
occurrence threshold become candidate patterns.

The "similarity" of a candidate is 1.0 (exact signatures match) — the
engine is intentionally simple in v0.1 and will be upgraded to
edit-distance clustering in a later release.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from ..config import Config, config as default_config
from ..storage import Database, Event


@dataclass
class Pattern:
    signature: tuple[str, ...]
    occurrences: int
    similarity: float
    sample_event_ids: list[int]

    @property
    def length(self) -> int:
        return len(self.signature)

    def describe(self) -> str:
        return " → ".join(s.split("|")[1] or s.split("|")[0] for s in self.signature)


class PatternDetector:
    def __init__(self, db: Database, cfg: Config | None = None):
        self.db = db
        self.cfg = cfg or default_config

    def detect(self, max_length: int = 6) -> list[Pattern]:
        sessions = self.db.list_sessions(limit=200)
        min_len = self.cfg.min_pattern_length
        min_occ = self.cfg.min_pattern_occurrences

        # For each n, collect n-grams across all sessions, with one sample
        # set of event ids per n-gram.
        counts: dict[int, Counter[tuple[str, ...]]] = defaultdict(Counter)
        samples: dict[int, dict[tuple[str, ...], list[int]]] = defaultdict(dict)

        for session in sessions:
            events = self.db.events_in_session(session.id)
            signatures = [e.signature() for e in events]
            ids = [e.id for e in events]
            for n in range(min_len, max_length + 1):
                if n > len(signatures):
                    continue
                for i in range(len(signatures) - n + 1):
                    ngram = tuple(signatures[i:i + n])
                    counts[n][ngram] += 1
                    samples[n].setdefault(ngram, ids[i:i + n])

        patterns: list[Pattern] = []
        for n, ngrams in counts.items():
            for ngram, count in ngrams.items():
                if count >= min_occ:
                    patterns.append(Pattern(
                        signature=ngram,
                        occurrences=count,
                        similarity=1.0,
                        sample_event_ids=samples[n][ngram],
                    ))

        # Favor longer, more-frequent patterns.
        patterns.sort(key=lambda p: (p.length, p.occurrences), reverse=True)
        return patterns

    def detect_and_persist(self) -> list[int]:
        """Detect patterns and save any new ones. Returns list of pattern row ids."""
        patterns = self.detect()
        existing_sigs = {tuple(p["signature"].split("\n")) for p in self.db.list_patterns()}
        new_ids: list[int] = []
        for p in patterns:
            if p.signature in existing_sigs:
                continue
            row_id = self.db.save_pattern(
                signature="\n".join(p.signature),
                occurrence_count=p.occurrences,
                avg_similarity=p.similarity,
                sample_event_ids=p.sample_event_ids,
            )
            new_ids.append(row_id)
        return new_ids
