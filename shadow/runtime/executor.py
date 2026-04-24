"""Dry-run executor for an AgentSpec.

The executor ships in "preview mode" for safety: it walks through each
step and logs what it *would* do. Real browser and OS automation is
gated behind ``--live`` so users never have a learned agent hijack their
desktop by accident.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from ..intent import AgentSpec


log = logging.getLogger("shadow.runtime")


@dataclass
class ExecutionResult:
    step_index: int
    ok: bool
    message: str


class AgentExecutor:
    def __init__(self, spec: AgentSpec, live: bool = False):
        self.spec = spec
        self.live = live
        self._handlers: dict[str, Callable[[dict], str]] = {
            "open_app": self._handle_open_app,
            "navigate": self._handle_navigate,
            "click": self._handle_click,
            "type": self._handle_type,
            "wait": self._handle_wait,
            "api_call": self._handle_api_call,
            "replay_event": self._handle_replay_event,
        }

    def run(self) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        for i, step in enumerate(self.spec.steps):
            action = step.get("action", "unknown")
            handler = self._handlers.get(action, self._handle_unknown)
            try:
                msg = handler(step)
                results.append(ExecutionResult(i, True, msg))
            except Exception as exc:
                results.append(ExecutionResult(i, False, f"{action} failed: {exc}"))
                break
        return results

    # ------------------------------------------------------------------
    # Handlers — each returns a human-readable summary
    # ------------------------------------------------------------------
    def _prefix(self) -> str:
        return "[LIVE]" if self.live else "[DRY-RUN]"

    def _handle_open_app(self, step: dict) -> str:
        target = step.get("target") or step.get("args", {}).get("app")
        if self.live:
            import webbrowser  # stdlib — safe enough for a demo
            if target and (target.startswith("http://") or target.startswith("https://")):
                webbrowser.open(target)
        return f"{self._prefix()} open app: {target}"

    def _handle_navigate(self, step: dict) -> str:
        url = step.get("target") or step.get("args", {}).get("url")
        if self.live and url:
            import webbrowser
            webbrowser.open(url)
        return f"{self._prefix()} navigate to: {url}"

    def _handle_click(self, step: dict) -> str:
        return f"{self._prefix()} click: {step.get('target')}"

    def _handle_type(self, step: dict) -> str:
        text = step.get("args", {}).get("text", "<input>")
        return f"{self._prefix()} type into {step.get('target')}: {text!r}"

    def _handle_wait(self, step: dict) -> str:
        seconds = step.get("args", {}).get("seconds", 1)
        if self.live:
            import time
            time.sleep(min(float(seconds), 10))
        return f"{self._prefix()} wait {seconds}s"

    def _handle_api_call(self, step: dict) -> str:
        endpoint = step.get("target") or step.get("args", {}).get("endpoint")
        return f"{self._prefix()} api_call: {endpoint} (never executed in v0.1)"

    def _handle_replay_event(self, step: dict) -> str:
        return f"{self._prefix()} replay: {step.get('target')}"

    def _handle_unknown(self, step: dict) -> str:
        return f"{self._prefix()} unknown action: {step!r}"
