"""A cross-platform fallback backend.

Uses ``psutil`` to observe the currently-focused process and (best effort)
active window title via platform hooks. It captures coarse-grained signal
only — app switches and window title changes — which is enough to seed
the pattern engine even when the full-fat native backend is unavailable.
"""

from __future__ import annotations

import time

from ..storage import Event
from .base import CaptureBackend


class GenericBackend(CaptureBackend):
    name = "generic"

    def __init__(self):
        self._last_app: str | None = None
        self._last_title: str | None = None

    def _active_window_info(self) -> tuple[str | None, str | None]:
        """Return ``(app_name, window_title)`` on a best-effort basis."""
        try:
            # Optional: pygetwindow works on Win/Mac/Linux (X11) without root.
            import pygetwindow as gw  # type: ignore
            win = gw.getActiveWindow()
            if win is None:
                return None, None
            title = getattr(win, "title", None)
            return title, title  # app name is not reliably available here
        except Exception:
            pass

        try:
            import psutil  # type: ignore
            # Rough heuristic: use the process that owns the foreground task.
            # This isn't truly "active window" but gives *something* useful.
            procs = sorted(
                (p for p in psutil.process_iter(["name", "cpu_percent"]) if p.info["name"]),
                key=lambda p: p.info.get("cpu_percent") or 0,
                reverse=True,
            )
            if procs:
                return procs[0].info["name"], None
        except Exception:
            pass

        return None, None

    def poll(self) -> list[Event]:
        app, title = self._active_window_info()
        events: list[Event] = []
        if app and app != self._last_app:
            events.append(Event(
                ts=time.time(),
                event_type="app_focus",
                app=app,
                window_title=title,
            ))
            self._last_app = app
        elif title and title != self._last_title:
            events.append(Event(
                ts=time.time(),
                event_type="window_change",
                app=app,
                window_title=title,
            ))
        if title is not None:
            self._last_title = title
        return events
