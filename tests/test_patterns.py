import time
from pathlib import Path

from shadow.config import Config
from shadow.patterns import PatternDetector
from shadow.storage import Database, Event


def _seeded_db(tmp_path: Path) -> tuple[Database, Config]:
    db = Database(tmp_path / "p.db")
    cfg = Config(data_dir=tmp_path, min_pattern_length=2, min_pattern_occurrences=3)
    # Simulate 3 sessions of the same 3-step workflow: Gmail -> Calendar -> Notion
    for _ in range(3):
        sid = db.start_session()
        t = time.time()
        for i, app in enumerate(["Gmail", "Calendar", "Notion"]):
            db.record(Event(
                ts=t + i,
                event_type="app_focus",
                app=app,
                session_id=sid,
            ))
        db.end_session(sid)
    return db, cfg


def test_detects_repeated_workflow(tmp_path):
    db, cfg = _seeded_db(tmp_path)
    det = PatternDetector(db, cfg)
    patterns = det.detect()
    assert patterns, "expected at least one pattern"
    # The longest pattern should be the full 3-step workflow.
    best = patterns[0]
    assert best.occurrences >= 3
    assert best.length >= 2


def test_persist_patterns_idempotent(tmp_path):
    db, cfg = _seeded_db(tmp_path)
    det = PatternDetector(db, cfg)
    first = det.detect_and_persist()
    second = det.detect_and_persist()
    # Second call shouldn't rediscover patterns we already stored.
    assert first
    assert not second
