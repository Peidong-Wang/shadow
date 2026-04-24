import time
from pathlib import Path

from shadow.storage import Database, Event


def _fresh_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_record_and_read(tmp_path):
    db = _fresh_db(tmp_path)
    sid = db.start_session("smoke")
    eid = db.record(Event(
        ts=time.time(),
        event_type="app_focus",
        app="TestApp",
        window_title="hello",
        session_id=sid,
    ))
    assert eid > 0
    events = db.recent_events()
    assert len(events) == 1
    assert events[0].app == "TestApp"


def test_session_listing(tmp_path):
    db = _fresh_db(tmp_path)
    sid = db.start_session()
    db.end_session(sid)
    sessions = db.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].ended_at is not None


def test_pattern_save_and_load(tmp_path):
    db = _fresh_db(tmp_path)
    pid = db.save_pattern(
        signature="app_focus|A|\napp_focus|B|",
        occurrence_count=5,
        avg_similarity=1.0,
        sample_event_ids=[1, 2],
    )
    patterns = db.list_patterns()
    assert any(p["id"] == pid for p in patterns)
    assert patterns[0]["sample_event_ids"] == [1, 2]
