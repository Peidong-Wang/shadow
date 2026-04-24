"""Seed a synthetic workflow so you can try the full pipeline without
actually doing anything repetitive on your real computer first.

    python examples/demo.py
    shadow dashboard

Then open http://127.0.0.1:4747 and click "Detect patterns".
"""

from __future__ import annotations

import time

from shadow.config import config
from shadow.intent import IntentExtractor
from shadow.patterns import PatternDetector
from shadow.storage import Database, Event


def seed() -> None:
    db = Database(config.db_path)
    workflow = [
        ("Mail", "Inbox"),
        ("Mail", "Reply — Weekly update"),
        ("Calendar", "Today"),
        ("Notion", "Team wiki"),
        ("Notion", "Weekly update"),
    ]
    # Simulate 5 repetitions of the same morning workflow.
    for rep in range(5):
        sid = db.start_session(f"morning-{rep}")
        t = time.time() + rep * 1000
        for i, (app, title) in enumerate(workflow):
            db.record(Event(
                ts=t + i,
                event_type="app_focus" if i == 0 else "window_change",
                app=app,
                window_title=title,
                session_id=sid,
            ))
        db.end_session(sid)

    print(f"Seeded {db.event_count()} events across 5 sessions.")
    print(f"DB: {config.db_path}")

    det = PatternDetector(db, config)
    patterns = det.detect()
    print(f"Detected {len(patterns)} patterns:")
    for p in patterns[:5]:
        print(f"  ({p.occurrences}×) {p.describe()}")

    ex = IntentExtractor(db, config)
    if patterns:
        spec = ex.extract(patterns[0])
        print("\nTop pattern → AgentSpec:")
        print(f"  name:    {spec.name}")
        print(f"  summary: {spec.summary}")
        print(f"  trigger: {spec.trigger}")
        print(f"  steps:   {len(spec.steps)}")


if __name__ == "__main__":
    seed()
