"""Dry-run executor for an AgentSpec.

The executor ships in "preview mode" for safety: it walks through each
step and logs what it *would* do. Real browser and OS automation is
gated behind ``--live`` so users never have a learned agent hijack their
desktop by accident.

With adapters available and live mode on, API calls can be executed
against real services (Gmail, Slack, Linear, Notion).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from ..intent import AgentSpec

if TYPE_CHECKING:
    from ..adapters import AdapterRegistry

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
        """Handle API calls, optionally using adapters in live mode."""
        endpoint = step.get("target") or step.get("args", {}).get("endpoint")
        method = step.get("args", {}).get("method", "GET")
        params = step.get("args", {}).get("params", {})

        # Dry-run message
        msg = f"{self._prefix()} api_call: {method} {endpoint}"

        # Try to execute in live mode if adapters are available
        if self.live:
            msg = self._try_execute_api_call(endpoint, method, params, msg)

        return msg

    def _try_execute_api_call(
        self, endpoint: str, method: str, params: dict, fallback_msg: str
    ) -> str:
        """Try to execute an API call using registered adapters."""
        try:
            # Import here to avoid circular dependency
            from ..adapters import AdapterRegistry

            registry = AdapterRegistry()

            # Parse endpoint to find adapter
            # Expected format: "gmail:send_email", "slack:send_message", etc.
            if ":" not in endpoint:
                return fallback_msg

            adapter_name, action = endpoint.split(":", 1)
            adapter = registry.get(adapter_name)

            if not adapter:
                log.warning(f"Adapter '{adapter_name}' not found")
                return f"{fallback_msg} (adapter not found)"

            if not adapter.available():
                log.warning(f"Adapter '{adapter_name}' not available")
                return f"{fallback_msg} (adapter not available)"

            # Execute the action
            result = adapter.execute(action, params)

            if result.get("ok"):
                return f"[LIVE] api_call executed: {endpoint} (success)"
            else:
                error = result.get("error", "unknown error")
                log.error(f"API call failed: {error}")
                return f"[LIVE] api_call executed: {endpoint} (failed: {error})"

        except Exception as e:
            log.error(f"Error executing API call: {e}", exc_info=True)
            return f"{fallback_msg} (execution error: {e})"

    def _handle_replay_event(self, step: dict) -> str:
        return f"{self._prefix()} replay: {step.get('target')}"

    def _handle_unknown(self, step: dict) -> str:
        return f"{self._prefix()} unknown action: {step!r}"
