"""Offline pattern detection over captured event streams.

Algorithm: sliding n-gram frequency count over event signatures. For each
length ``n`` in ``[min_length, max_length]``, count how often each n-gram
appears across the user's historical sessions. Those exceeding the
occurrence threshold become candidate patterns.

Candidates are then clustered using edit-distance (Levenshtein) to merge
near-duplicates. Each pattern receives a confidence score based on frequency,
recency, and consistency.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from ..config import Config, config as default_config
from ..storage import Database, Event


def _levenshtein_distance(seq1: tuple[str, ...], seq2: tuple[str, ...]) -> int:
    """Compute edit distance between two sequences using dynamic programming.

    Standard Levenshtein implementation for tuple comparison.
    """
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    return dp[m][n]


def _compute_signature_similarity(sig1: tuple[str, ...], sig2: tuple[str, ...]) -> float:
    """Compute similarity between two signatures as 1 - normalized_distance.

    Normalization uses the maximum length to ensure 0-1 range.
    """
    if sig1 == sig2:
        return 1.0
    max_len = max(len(sig1), len(sig2))
    if max_len == 0:
        return 1.0
    distance = _levenshtein_distance(sig1, sig2)
    return 1.0 - (distance / max_len)


@dataclass
class Pattern:
    signature: tuple[str, ...]
    occurrences: int
    similarity: float
    sample_event_ids: list[int]
    confidence: float = 0.0

    @property
    def length(self) -> int:
        return len(self.signature)

    def describe(self) -> str:
        description = " → ".join(s.split("|")[1] or s.split("|")[0] for s in self.signature)
        confidence_pct = int(self.confidence * 100)
        return f"{description} ({confidence_pct}% confidence)"


class PatternDetector:
    def __init__(self, db: Database, cfg: Config | None = None):
        self.db = db
        self.cfg = cfg or default_config

    def _cluster_patterns(self, patterns: list[Pattern]) -> list[Pattern]:
        """Cluster patterns by edit-distance similarity and merge near-duplicates.

        For each pair of patterns, compute signature similarity. If it meets the
        threshold, merge them: keep the most-frequent signature, sum occurrences,
        average similarities, and union sample event IDs (capped at 10).

        Uses O(n²) comparison — pattern counts are expected to be small.
        """
        if not patterns:
            return patterns

        threshold = self.cfg.similarity_threshold
        merged = {id(p): p for p in patterns}
        processed = set()

        for i, p1 in enumerate(patterns):
            if id(p1) in processed:
                continue
            for j, p2 in enumerate(patterns[i + 1:], start=i + 1):
                if id(p2) in processed:
                    continue

                similarity = _compute_signature_similarity(p1.signature, p2.signature)

                if similarity >= threshold:
                    # Merge p2 into p1: keep the higher-occurrence signature
                    if p2.occurrences > p1.occurrences:
                        sig = p2.signature
                    else:
                        sig = p1.signature

                    merged_pattern = Pattern(
                        signature=sig,
                        occurrences=p1.occurrences + p2.occurrences,
                        similarity=(p1.similarity + p2.similarity + similarity) / 3.0,
                        sample_event_ids=list(
                            {*p1.sample_event_ids, *p2.sample_event_ids}
                        )[:10],
                        confidence=0.0,  # Will be computed later
                    )
                    merged[id(p1)] = merged_pattern
                    processed.add(id(p2))

        return list(merged.values())

    def _score_confidence(
        self, pattern: Pattern, all_events: list[Event]
    ) -> float:
        """Score pattern confidence: weighted average of frequency, recency, and consistency.

        - Frequency (0-1): min(1.0, occurrences / (min_occurrences * 3))
        - Recency (0-1): exponential decay with 7-day half-life
        - Consistency (0-1): pattern.similarity (from clustering)
        - Final: 0.4 * freq + 0.35 * recency + 0.25 * consistency
        """
        min_occ = self.cfg.min_pattern_occurrences
        frequency_score = min(1.0, pattern.occurrences / (min_occ * 3))

        # Recency: use most recent sample event timestamp
        recency_score = 0.0
        if pattern.sample_event_ids and all_events:
            # Create a map of event id to timestamp
            event_map = {e.id: e.ts for e in all_events if e.id}
            most_recent_ts = max(
                (event_map[eid] for eid in pattern.sample_event_ids if eid in event_map),
                default=None,
            )
            if most_recent_ts is not None:
                # Find the newest event in the entire DB
                newest_ts = max((e.ts for e in all_events), default=0.0)
                age_seconds = max(0.0, newest_ts - most_recent_ts)
                half_life_seconds = 7 * 24 * 60 * 60  # 7 days
                recency_score = 2.0 ** (-age_seconds / half_life_seconds)
            else:
                recency_score = 0.0
        else:
            recency_score = 0.1  # Minimal recency if no samples

        consistency_score = pattern.similarity

        confidence = (
            0.4 * frequency_score
            + 0.35 * recency_score
            + 0.25 * consistency_score
        )
        return min(1.0, max(0.0, confidence))

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
                        confidence=0.0,
                    ))

        # Cluster near-duplicates
        patterns = self._cluster_patterns(patterns)

        # Get all events for confidence scoring
        all_events: list[Event] = []
        for session in sessions:
            all_events.extend(self.db.events_in_session(session.id))

        # Score confidence for each pattern
        for pattern in patterns:
            pattern.confidence = self._score_confidence(pattern, all_events)

        # Favor higher confidence, then longer, then more-frequent patterns
        patterns.sort(
            key=lambda p: (p.confidence, p.length, p.occurrences),
            reverse=True,
        )
        return patterns

    def detect_and_persist(self) -> list[int]:
        """Detect patterns and save any new ones. Returns list of pattern row ids."""
        patterns = self.detect()
        existing_sigs = {tuple(p["signature"].split("\x00")) for p in self.db.list_patterns()}
        new_ids: list[int] = []
        for p in patterns:
            if p.signature in existing_sigs:
                continue
            row_id = self.db.save_pattern(
                signature="\x00".join(p.signature),
                occurrence_count=p.occurrences,
                avg_similarity=p.similarity,
                sample_event_ids=p.sample_event_ids,
            )
            new_ids.append(row_id)
        return new_ids
