"""Linux capture backend using xdotool / X11 introspection.

Wayland support is partial — Shadow relies on ``wmctrl`` or ``xdotool``
which work reliably under XWayland. AT-SPI2 integration is on the roadmap
for full accessibility-tree capture under GNOME/KDE.
"""

from __future__ import annotations

import shutil
import subprocess
import time

from ..storage import Event
from .base import CaptureBackend


class LinuxBackend(CaptureBackend):
    name = "linux"

    def __init__(self):
        self._last_app: str | None = None
        self._last_title: str | None = None
        self._has_xdotool = shutil.which("xdotool") is not None
        self._has_wmctrl = shutil.which("wmctrl") is not None
        self._fallback = None
        if not (self._has_xdotool or self._has_wmctrl):
            from .generic import GenericBackend
            self._fallback = GenericBackend()

    def _run(self, cmd: list[str]) -> str | None:
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2)
            return out.decode("utf-8", errors="replace").strip()
        except Exception:
            return None

    def _active_info(self) -> tuple[str | None, str | None]:
        if self._fallback:
            return self._fallback._active_window_info()  # type: ignore[attr-defined]

        title = None
        app = None
        if self._has_xdotool:
            wid = self._run(["xdotool", "getactivewindow"])
            if wid:
                title = self._run(["xdotool", "getwindowname", wid])
                cls = self._run(["xdotool", "getwindowclassname", wid])
                if cls:
                    app = cls
        if not title and self._has_wmctrl:
            # `wmctrl -lp` lists windows with PIDs; the ":ACTIVE:" entry is the focused one.
            lines = (self._run(["wmctrl", "-l"]) or "").splitlines()
            if lines:
                # As a rough heuristic just take the last listed (most recently active).
                parts = lines[-1].split(None, 3)
                if len(parts) == 4:
                    title = parts[3]
        return app, title

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
