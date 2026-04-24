"""Dashboard — a small stdlib HTTP server serving a single-page app.

We deliberately avoid Flask/FastAPI here so ``pip install shadow`` has
zero runtime deps beyond the stdlib for the dashboard. The entire UI is
a self-contained HTML file that talks to the local API over JSON.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..config import Config, config as default_config
from ..intent import IntentExtractor
from ..patterns import PatternDetector
from ..runtime import AgentExecutor
from ..intent import AgentSpec
from ..storage import Database


INDEX_HTML = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")


def _json_response(handler: BaseHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    data = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class _Handler(BaseHTTPRequestHandler):
    db: Database
    cfg: Config

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default logging
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path == "/index.html":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/stats":
            _json_response(self, {
                "event_count": self.db.event_count(),
                "session_count": len(self.db.list_sessions(limit=10000)),
                "pattern_count": len(self.db.list_patterns()),
                "db_path": str(self.cfg.db_path),
            })
            return

        if self.path == "/api/events":
            events = [
                {
                    "id": e.id,
                    "ts": e.ts,
                    "app": e.app,
                    "event_type": e.event_type,
                    "window_title": e.window_title,
                    "url": e.url,
                }
                for e in self.db.recent_events(limit=100)
            ]
            _json_response(self, events)
            return

        if self.path == "/api/patterns":
            _json_response(self, self.db.list_patterns())
            return

        if self.path == "/api/sessions":
            _json_response(self, [
                {"id": s.id, "started_at": s.started_at, "ended_at": s.ended_at, "label": s.label}
                for s in self.db.list_sessions()
            ])
            return

        _json_response(self, {"error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/detect":
            det = PatternDetector(self.db, self.cfg)
            new_ids = det.detect_and_persist()
            _json_response(self, {"new_pattern_ids": new_ids})
            return

        if self.path.startswith("/api/patterns/") and self.path.endswith("/extract"):
            try:
                pattern_id = int(self.path.split("/")[3])
            except Exception:
                _json_response(self, {"error": "bad pattern id"}, status=400)
                return
            rows = self.db.list_patterns()
            row = next((r for r in rows if r["id"] == pattern_id), None)
            if row is None:
                _json_response(self, {"error": "unknown pattern"}, status=404)
                return
            from ..patterns import Pattern
            signature = tuple(row["signature"].split("\n"))
            pattern = Pattern(
                signature=signature,
                occurrences=row["occurrence_count"],
                similarity=row["avg_similarity"],
                sample_event_ids=row["sample_event_ids"],
            )
            extractor = IntentExtractor(self.db, self.cfg)
            try:
                spec = extractor.extract(pattern)
            except Exception as exc:
                _json_response(self, {"error": str(exc)}, status=500)
                return
            self.db.attach_intent(pattern_id, spec.summary, spec.to_dict())
            _json_response(self, spec.to_dict())
            return

        if self.path.startswith("/api/patterns/") and self.path.endswith("/run"):
            try:
                pattern_id = int(self.path.split("/")[3])
            except Exception:
                _json_response(self, {"error": "bad pattern id"}, status=400)
                return
            rows = self.db.list_patterns()
            row = next((r for r in rows if r["id"] == pattern_id), None)
            if row is None or not row.get("agent_spec"):
                _json_response(self, {"error": "no agent spec — run /extract first"}, status=400)
                return
            spec = AgentSpec(**row["agent_spec"])
            results = AgentExecutor(spec, live=False).run()
            _json_response(self, [
                {"step": r.step_index, "ok": r.ok, "message": r.message} for r in results
            ])
            return

        _json_response(self, {"error": "not_found"}, status=404)


def create_app(db: Database, cfg: Config | None = None) -> ThreadingHTTPServer:
    cfg = cfg or default_config
    handler_cls = type("BoundHandler", (_Handler,), {"db": db, "cfg": cfg})
    server = ThreadingHTTPServer((cfg.dashboard_host, cfg.dashboard_port), handler_cls)
    return server


def run(db: Database, cfg: Config | None = None) -> None:
    cfg = cfg or default_config
    server = create_app(db, cfg)
    print(f"Shadow dashboard listening on http://{cfg.dashboard_host}:{cfg.dashboard_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
