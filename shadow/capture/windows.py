"""Windows capture backend using the Win32 API via pywin32.

Dependencies (``shadow[windows]``): pywin32, psutil.

Falls back to the generic backend if pywin32 is unavailable.
"""

from __future__ import annotations

import time

from ..storage import Event
from .base import CaptureBackend


class WindowsBackend(CaptureBackend):
    name = "windows"

    def __init__(self):
        self._last_app: str | None = None
        self._last_title: str | None = None
        self._fallback = None
        try:
            import win32gui  # type: ignore  # noqa: F401
        except Exception:
            from .generic import GenericBackend
            self._fallback = GenericBackend()

    def _active_info(self) -> tuple[str | None, str | None]:
        if self._fallback:
            return self._fallback._active_window_info()  # type: ignore[attr-defined]

        import win32gui  # type: ignore
        import win32process  # type: ignore
        import psutil  # type: ignore

        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                app = proc.name()
            except Exception:
                app = None
            return app, title
        except Exception:
            return None, None

    def poll(self) -> list[Event]:
        app, title = self._active_info()
        events: list[Event] = []
        if app and app != self._last_app:
            events.append(Event(
                ts=time.time(),
                event_type="app_focus",
                app=app,
                window_title=title,
            ))
            self._last_app = app
        elif title and title != self._last_title and app is not None:
            events.append(Event(
                ts=time.time(),
                event_type="window_change",
                app=app,
                window_title=title,
            ))
        if title is not None:
            self._last_title = title
        return events
