from shadow.intent import AgentSpec
from shadow.runtime import AgentExecutor


def test_dry_run_walks_all_steps():
    spec = AgentSpec(
        name="demo",
        summary="Demo workflow",
        trigger="manual",
        steps=[
            {"action": "open_app", "target": "Gmail"},
            {"action": "click", "target": "compose button"},
            {"action": "type", "target": "to:", "args": {"text": "team@example.com"}},
            {"action": "wait", "args": {"seconds": 1}},
        ],
    )
    results = AgentExecutor(spec, live=False).run()
    assert len(results) == 4
    assert all(r.ok for r in results)
    assert "DRY-RUN" in results[0].message
