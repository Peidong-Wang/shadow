"""Local-first, privacy-preserving event store.

All events live in a single SQLite database in the user's data directory.
Nothing leaves the machine unless the user explicitly triggers a Claude
intent-extraction request.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    ended_at REAL,
    label TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    app TEXT,
    event_type TEXT NOT NULL,
    window_title TEXT,
    url TEXT,
    target_element TEXT,
    value_hash TEXT,
    extra_json TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_app ON events(app);

CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discovered_at REAL NOT NULL,
    occurrence_count INTEGER NOT NULL,
    avg_similarity REAL NOT NULL,
    signature TEXT NOT NULL,
    sample_event_ids_json TEXT NOT NULL,
    intent_summary TEXT,
    agent_spec_json TEXT
);
"""


@dataclass
class Event:
    ts: float
    event_type: str
    app: str | None = None
    window_title: str | None = None
    url: str | None = None
    target_element: str | None = None
    value_hash: str | None = None
    extra: dict = field(default_factory=dict)
    session_id: int | None = None
    id: int | None = None

    def signature(self) -> str:
        """A short, sensitivity-free fingerprint used for pattern matching."""
        parts = [self.event_type, self.app or "", self.target_element or ""]
        return "|".join(parts)


@dataclass
class Session:
    id: int
    started_at: float
    ended_at: float | None
    label: str | None


def hash_value(value: str | bytes) -> str:
    """One-way hash for sensitive values we never want to persist in plaintext."""
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:16]


class Database:
    """Thin wrapper around sqlite3 with session-aware event ingestion."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    def start_session(self, label: str | None = None) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (started_at, label) VALUES (?, ?)",
                (time.time(), label),
            )
            return int(cur.lastrowid)

    def end_session(self, session_id: int) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (time.time(), session_id),
            )

    def list_sessions(self, limit: int = 50) -> list[Session]:
        cur = self._conn.execute(
            "SELECT id, started_at, ended_at, label FROM sessions "
            "ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        return [Session(**dict(row)) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def record(self, event: Event) -> int:
        if event.session_id is None:
            raise ValueError("Event must have session_id")
        payload = (
            event.session_id,
            event.ts,
            event.app,
            event.event_type,
            event.window_title,
            event.url,
            event.target_element,
            event.value_hash,
            json.dumps(event.extra) if event.extra else None,
        )
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO events "
                "(session_id, ts, app, event_type, window_title, url, "
                " target_element, value_hash, extra_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                payload,
            )
            return int(cur.lastrowid)

    def record_many(self, events: Iterable[Event]) -> None:
        for ev in events:
            self.record(ev)

    def recent_events(self, limit: int = 200) -> list[Event]:
        cur = self._conn.execute(
            "SELECT * FROM events ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_event(row) for row in cur.fetchall()]

    def events_in_session(self, session_id: int) -> list[Event]:
        cur = self._conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY ts ASC",
            (session_id,),
        )
        return [self._row_to_event(row) for row in cur.fetchall()]

    def event_count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM events")
        return int(cur.fetchone()[0])

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        extra = json.loads(row["extra_json"]) if row["extra_json"] else {}
        return Event(
            id=row["id"],
            session_id=row["session_id"],
            ts=row["ts"],
            app=row["app"],
            event_type=row["event_type"],
            window_title=row["window_title"],
            url=row["url"],
            target_element=row["target_element"],
            value_hash=row["value_hash"],
            extra=extra,
        )

    # ------------------------------------------------------------------
    # Patterns
    # ------------------------------------------------------------------
    def save_pattern(
        self,
        signature: str,
        occurrence_count: int,
        avg_similarity: float,
        sample_event_ids: list[int],
        intent_summary: str | None = None,
        agent_spec: dict | None = None,
    ) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO patterns "
                "(discovered_at, occurrence_count, avg_similarity, signature, "
                " sample_event_ids_json, intent_summary, agent_spec_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    occurrence_count,
                    avg_similarity,
                    signature,
                    json.dumps(sample_event_ids),
                    intent_summary,
                    json.dumps(agent_spec) if agent_spec else None,
                ),
            )
            return int(cur.lastrowid)

    def list_patterns(self) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM patterns ORDER BY discovered_at DESC"
        )
        out = []
        for row in cur.fetchall():
            d = dict(row)
            d["sample_event_ids"] = json.loads(d.pop("sample_event_ids_json") or "[]")
            if d.get("agent_spec_json"):
                d["agent_spec"] = json.loads(d.pop("agent_spec_json"))
            else:
                d["agent_spec"] = None
                d.pop("agent_spec_json", None)
            out.append(d)
        return out

    def attach_intent(self, pattern_id: int, intent_summary: str, agent_spec: dict) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE patterns SET intent_summary = ?, agent_spec_json = ? WHERE id = ?",
                (intent_summary, json.dumps(agent_spec), pattern_id),
            )
