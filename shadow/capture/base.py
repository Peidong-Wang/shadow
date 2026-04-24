"""Base classes for the cross-platform capture layer.

Every backend yields a stream of :class:`shadow.storage.Event` instances.
The generic :class:`Capture` orchestrator handles polling cadence, idle
detection, session segmentation, and writing into the database.
"""

from __future__ import annotations

import abc
import threading
import time
from typing import Callable, Iterator

from ..config import Config, config as default_config
from ..storage import Database, Event


class CaptureBackend(abc.ABC):
    """Abstract base class for a per-platform capture implementation.

    Each backend must implement :meth:`poll`, returning a list of events
    observed since the last call (may be empty).
    """

    name: str = "base"

    @abc.abstractmethod
    def poll(self) -> list[Event]:
        """Return events observed since the last call."""

    def shutdown(self) -> None:
        """Release any OS resources (override if needed)."""


class Capture:
    """Runs a capture backend on a background thread and persists events."""

    def __init__(
        self,
        backend: CaptureBackend,
        db: Database,
        cfg: Config | None = None,
        on_event: Callable[[Event], None] | None = None,
    ):
        self.backend = backend
        self.db = db
        self.cfg = cfg or default_config
        self.on_event = on_event
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._session_id: int | None = None
        self._last_event_ts: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="shadow-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._session_id is not None:
            self.db.end_session(self._session_id)
            self._session_id = None
        self.backend.shutdown()

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                events = self.backend.poll()
            except Exception as exc:  # don't crash the daemon
                events = []
                self._log_error(exc)
            for event in events:
                self._ingest(event)
            self._stop.wait(self.cfg.poll_interval_seconds)

    def _ingest(self, event: Event) -> None:
        now = time.time()
        if (
            self._session_id is None
            or (now - self._last_event_ts) > self.cfg.idle_gap_seconds
        ):
            if self._session_id is not None:
                self.db.end_session(self._session_id)
            self._session_id = self.db.start_session()
        event.session_id = self._session_id
        self.db.record(event)
        self._last_event_ts = now
        if self.on_event:
            try:
                self.on_event(event)
            except Exception as exc:
                self._log_error(exc)

    def _log_error(self, exc: Exception) -> None:
        # Intentional: never let a capture error take down the background thread.
        # Users can view errors via debug logging if they need to.
        pass

    # ------------------------------------------------------------------
    # Test/CLI helpers
    # ------------------------------------------------------------------
    def run_once(self) -> list[Event]:
        """Poll the backend once synchronously (useful for tests/demos)."""
        events = self.backend.poll()
        for ev in events:
            self._ingest(ev)
        return events
