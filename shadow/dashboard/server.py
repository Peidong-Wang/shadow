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
from ..intent import AgentSpec
from ..patterns import PatternDetector
from ..runtime import AgentExecutor
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

        if self.path == "/api/providers":
            providers = ["claude", "openai", "openai-compatible", "ollama"]
            active = "claude"
            _json_response(self, {"providers": providers, "active": active})
            return

        if self.path == "/api/adapters":
            _json_response(self, {
                "adapters": [
                    {"name": "macos", "available": True, "status": "active"},
                    {"name": "windows", "available": True, "status": "inactive"},
                    {"name": "linux", "available": True, "status": "inactive"},
                ]
            })
            return

        if self.path == "/api/schedule/rules":
            _json_response(self, self.db.list_schedule_rules())
            return

        if self.path == "/api/schedule/history":
            _json_response(self, self.db.get_schedule_history(limit=100))
            return

        if self.path == "/api/settings":
            _json_response(self, {
                "anthropic_api_key": "***" if self.cfg.anthropic_api_key else None,
                "dashboard_host": self.cfg.dashboard_host,
                "dashboard_port": self.cfg.dashboard_port,
                "capture_poll_interval": getattr(self.cfg, "capture_poll_interval", 5),
                "capture_idle_gap": getattr(self.cfg, "capture_idle_gap", 60),
                "store_titles": getattr(self.cfg, "store_titles", True),
                "store_urls": getattr(self.cfg, "store_urls", True),
                "privacy_enabled": getattr(self.cfg, "privacy_enabled", False),
            })
            return

        if self.path == "/api/marketplace":
            try:
                from ..agents import Marketplace
                marketplace = Marketplace(self.db)
                templates = []
                for spec in marketplace.list_templates():
                    templates.append({
                        "name": spec.name,
                        "summary": spec.summary,
                        "trigger": spec.trigger,
                        "inputs": spec.inputs,
                        "notes": spec.notes,
                        "steps_count": len(spec.steps),
                    })
                _json_response(self, {"templates": templates})
            except ImportError:
                _json_response(self, {"error": "agents module not available"}, status=503)
            return

        _json_response(self, {"error": "not_found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/detect":
            det = PatternDetector(self.db, self.cfg)
            new_ids = det.detect_and_persist()
            _json_response(self, {"new_pattern_ids": new_ids})
            return

        if self.path.startswith("/api/patterns/") and self.path.endswith("/pin"):
            try:
                pattern_id = int(self.path.split("/")[3])
            except Exception:
                _json_response(self, {"error": "bad pattern id"}, status=400)
                return
            new_state = self.db.toggle_pin(pattern_id)
            _json_response(self, {"pinned": new_state})
            return

        if self.path.startswith("/api/patterns/") and self.path.endswith("/archive"):
            try:
                pattern_id = int(self.path.split("/")[3])
            except Exception:
                _json_response(self, {"error": "bad pattern id"}, status=400)
                return
            new_state = self.db.toggle_archive(pattern_id)
            _json_response(self, {"archived": new_state})
            return

        if self.path == "/api/schedule/rules":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body)
                pattern_id = data.get("pattern_id")
                cron_expr = data.get("cron_expr")
                event_trigger = data.get("event_trigger")
                if not pattern_id or not cron_expr:
                    _json_response(self, {"error": "missing pattern_id or cron_expr"}, status=400)
                    return
                rule_id = self.db.create_schedule_rule(pattern_id, cron_expr, event_trigger)
                _json_response(self, {"id": rule_id, "pattern_id": pattern_id, "cron_expr": cron_expr})
            except Exception as exc:
                _json_response(self, {"error": str(exc)}, status=400)
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
            signature = tuple(row["signature"].split("\x00"))
            pattern = Pattern(
                signature=signature,
                occurrences=row["occurrence_count"],
                similarity=row["avg_similarity"],
                sample_event_ids=row["sample_event_ids"],
            )
            try:
                from ..intent import IntentExtractor
                extractor = IntentExtractor(self.db, self.cfg)
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

        if self.path.startswith("/api/marketplace/") and self.path.endswith("/install"):
            try:
                template_name = self.path.split("/")[3]
                from ..agents import Marketplace
                marketplace = Marketplace(self.db)
                pattern_id = marketplace.install_template(template_name)
                _json_response(self, {"pattern_id": pattern_id, "name": template_name})
            except ValueError as exc:
                _json_response(self, {"error": str(exc)}, status=404)
            except Exception as exc:
                _json_response(self, {"error": str(exc)}, status=500)
            return

        _json_response(self, {"error": "not_found"}, status=404)

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path.startswith("/api/schedule/rules/"):
            try:
                rule_id = int(self.path.split("/")[-1])
            except Exception:
                _json_response(self, {"error": "bad rule id"}, status=400)
                return
            self.db.delete_schedule_rule(rule_id)
            _json_response(self, {"deleted": True})
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
