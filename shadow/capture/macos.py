"""macOS capture backend using AppKit and the Accessibility API.

Requires the user to grant Accessibility permission in
``System Settings → Privacy & Security → Accessibility`` for the terminal
or packaged app running Shadow.

Dependencies (installed via ``shadow[macos]``):
    pyobjc-core, pyobjc-framework-AppKit, pyobjc-framework-Quartz

If those aren't importable we fall back to the generic backend cleanly.
"""

from __future__ import annotations

import time

from ..storage import Event
from .base import CaptureBackend


class MacOSBackend(CaptureBackend):
    name = "macos"

    def __init__(self):
        self._last_app: str | None = None
        self._last_title: str | None = None
        self._nsworkspace = None
        self._fallback = None
        try:
            from AppKit import NSWorkspace  # type: ignore
            self._nsworkspace = NSWorkspace.sharedWorkspace()
        except Exception:
            from .generic import GenericBackend
            self._fallback = GenericBackend()

    def _active_info(self) -> tuple[str | None, str | None]:
        if self._fallback:
            return self._fallback._active_window_info()  # type: ignore[attr-defined]

        try:
            app = self._nsworkspace.frontmostApplication()
            app_name = app.localizedName() if app else None
        except Exception:
            return None, None

        # Window title via Quartz (best-effort — returns the frontmost window's owner).
        title: str | None = None
        try:
            from Quartz import (  # type: ignore
                CGWindowListCopyWindowInfo,
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
            )
            windows = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            )
            for w in windows:
                owner = w.get("kCGWindowOwnerName")
                if owner == app_name:
                    title = w.get("kCGWindowName") or None
                    if title:
                        break
        except Exception:
            pass
        return app_name, title

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
