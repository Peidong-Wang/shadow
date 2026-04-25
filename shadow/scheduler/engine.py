"""Scheduler for cron-based and event-triggered agent execution.

Supports:
- Cron expressions (minute hour dom month dow)
- Event-based triggers (e.g., "app_focus:Slack")
- Background thread that checks cron rules every 60s
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage import Database
    from ..config import Config
    from ..storage.db import Event
    from ..runtime.executor import AgentExecutor

log = logging.getLogger("shadow.scheduler")


@dataclass
class ScheduleRule:
    """A schedule rule that triggers execution of a pattern/agent."""

    id: int | None
    pattern_id: int
    cron_expr: str | None = None
    event_trigger: str | None = None
    enabled: bool = True
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.cron_expr and not self.event_trigger:
            raise ValueError("Either cron_expr or event_trigger must be provided")


@dataclass
class ScheduledRun:
    """A record of a scheduled rule execution."""

    id: int | None
    rule_id: int
    started_at: float
    ended_at: float | None
    status: str  # "running", "completed", "failed"
    result_json: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "result_json": self.result_json,
        }


class CronMatcher:
    """Simple cron expression parser and matcher.

    Supports: minute hour day-of-month month day-of-week
    Supports: * and ranges (e.g., 1-5, 0-23)
    Does NOT support: step values (*/5), lists (1,3,5), or L/W modifiers
    """

    def __init__(self, cron_expr: str):
        """Initialize with a cron expression like '0 9 * * 1-5'."""
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression: {cron_expr}. "
                "Expected 5 fields: minute hour dom month dow"
            )
        self.minute_expr = parts[0]
        self.hour_expr = parts[1]
        self.dom_expr = parts[2]
        self.month_expr = parts[3]
        self.dow_expr = parts[4]

    def matches(self, dt: datetime) -> bool:
        """Check if the given datetime matches this cron rule."""
        return (
            self._matches_field(self.minute_expr, dt.minute, 0, 59)
            and self._matches_field(self.hour_expr, dt.hour, 0, 23)
            and self._matches_field(self.dom_expr, dt.day, 1, 31)
            and self._matches_field(self.month_expr, dt.month, 1, 12)
            and self._matches_dow(self.dow_expr, dt.weekday())
        )

    @staticmethod
    def _matches_field(expr: str, value: int, min_val: int, max_val: int) -> bool:
        """Check if value matches the cron field expression."""
        if expr == "*":
            return True

        # Handle ranges: "1-5", "0-23", etc.
        if "-" in expr:
            parts = expr.split("-")
            if len(parts) == 2:
                try:
                    start = int(parts[0])
                    end = int(parts[1])
                    return start <= value <= end
                except ValueError:
                    return False

        # Handle single values
        try:
            return int(expr) == value
        except ValueError:
            return False

    @staticmethod
    def _matches_dow(expr: str, py_weekday: int) -> bool:
        """Check if day-of-week matches (cron uses 0=Sunday, Python uses 0=Monday)."""
        if expr == "*":
            return True

        # Convert Python weekday (0=Mon) to cron weekday (0=Sun)
        cron_dow = (py_weekday + 1) % 7

        # Handle ranges: "1-5" (Mon-Fri in cron), etc.
        if "-" in expr:
            parts = expr.split("-")
            if len(parts) == 2:
                try:
                    start = int(parts[0])
                    end = int(parts[1])
                    return start <= cron_dow <= end
                except ValueError:
                    return False

        # Handle single values
        try:
            return int(expr) == cron_dow
        except ValueError:
            return False


class Scheduler:
    """Manages scheduled rule execution via cron and event triggers."""

    def __init__(self, db: Database, cfg: Config):
        self.db = db
        self.cfg = cfg
        self._running = False
        self._thread: threading.Thread | None = None
        self._rules_cache: list[ScheduleRule] = []
        self._last_check_minute = -1

    def add_rule(
        self,
        pattern_id: int,
        cron_expr: str | None = None,
        event_trigger: str | None = None,
    ) -> ScheduleRule:
        """Add a new schedule rule."""
        if not cron_expr and not event_trigger:
            raise ValueError("Either cron_expr or event_trigger must be provided")

        rule = ScheduleRule(
            id=None,
            pattern_id=pattern_id,
            cron_expr=cron_expr,
            event_trigger=event_trigger,
            created_at=time.time(),
        )
        rule.id = self.db.save_rule(
            pattern_id=pattern_id,
            cron_expr=cron_expr,
            event_trigger=event_trigger,
        )
        self._reload_rules_cache()
        return rule

    def remove_rule(self, rule_id: int) -> None:
        """Remove a schedule rule by ID."""
        self.db.delete_rule(rule_id)
        self._reload_rules_cache()

    def list_rules(self) -> list[ScheduleRule]:
        """Get all schedule rules."""
        return self._rules_cache

    def run_history(self, limit: int = 50) -> list[ScheduledRun]:
        """Get recent scheduled run records."""
        return self.db.list_runs(limit=limit)

    def start(self) -> None:
        """Start the scheduler background thread."""
        if self._running:
            return
        self._running = True
        self._reload_rules_cache()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        log.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler background thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Scheduler stopped")

    def check_event_triggers(self, event: Event) -> None:
        """Check if any event_trigger rules match the given event."""
        for rule in self._rules_cache:
            if not rule.enabled or not rule.event_trigger:
                continue
            if self._event_matches_trigger(event, rule.event_trigger):
                self._execute_rule(rule)

    def _reload_rules_cache(self) -> None:
        """Reload rules from the database."""
        self._rules_cache = self.db.list_rules()

    def _run_loop(self) -> None:
        """Main scheduler loop — checks cron rules every 60 seconds."""
        while self._running:
            try:
                self._check_cron_rules()
            except Exception as e:
                log.error(f"Error in scheduler loop: {e}", exc_info=True)
            time.sleep(60)

    def _check_cron_rules(self) -> None:
        """Check all cron-based rules."""
        now = datetime.now()
        current_minute = now.hour * 60 + now.minute

        # Only check once per minute to avoid duplicate executions
        if current_minute == self._last_check_minute:
            return

        self._last_check_minute = current_minute

        for rule in self._rules_cache:
            if not rule.enabled or not rule.cron_expr:
                continue
            try:
                matcher = CronMatcher(rule.cron_expr)
                if matcher.matches(now):
                    self._execute_rule(rule)
            except ValueError as e:
                log.error(f"Invalid cron expression in rule {rule.id}: {e}")

    @staticmethod
    def _event_matches_trigger(event: Event, trigger: str) -> bool:
        """Check if event matches the trigger pattern.

        Trigger format: "event_type:app" or just "event_type"
        Example: "app_focus:Slack", "clipboard_change"
        """
        parts = trigger.split(":")
        if len(parts) == 2:
            event_type, app = parts
            return event.event_type == event_type and event.app == app
        else:
            return event.event_type == trigger

    def _execute_rule(self, rule: ScheduleRule) -> None:
        """Execute a rule by loading the agent spec and running it."""
        started_at = time.time()
        try:
            # Load the pattern from the database
            patterns = self.db.list_patterns()
            pattern = next((p for p in patterns if p["id"] == rule.pattern_id), None)
            if not pattern:
                log.warning(f"Pattern {rule.pattern_id} not found for rule {rule.id}")
                self.db.log_run(
                    rule_id=rule.id,
                    started_at=started_at,
                    ended_at=time.time(),
                    status="failed",
                    result_json=json.dumps({"error": "pattern_not_found"}),
                )
                return

            agent_spec_data = pattern.get("agent_spec")
            if not agent_spec_data:
                log.warning(f"Pattern {rule.pattern_id} has no agent spec")
                self.db.log_run(
                    rule_id=rule.id,
                    started_at=started_at,
                    ended_at=time.time(),
                    status="failed",
                    result_json=json.dumps({"error": "no_agent_spec"}),
                )
                return

            # Import here to avoid circular imports
            from ..intent import AgentSpec
            from ..runtime.executor import AgentExecutor

            agent_spec = AgentSpec.from_dict(agent_spec_data)
            executor = AgentExecutor(agent_spec, live=self.cfg.live_mode)
            results = executor.run()

            # Determine overall status
            status = "completed" if all(r.ok for r in results) else "failed"
            result_summary = [
                {"step": r.step_index, "ok": r.ok, "message": r.message}
                for r in results
            ]

            self.db.log_run(
                rule_id=rule.id,
                started_at=started_at,
                ended_at=time.time(),
                status=status,
                result_json=json.dumps(result_summary),
            )
            log.info(
                f"Executed rule {rule.id} (pattern {rule.pattern_id}): {status}"
            )
        except Exception as e:
            log.error(f"Error executing rule {rule.id}: {e}", exc_info=True)
            self.db.log_run(
                rule_id=rule.id,
                started_at=started_at,
                ended_at=time.time(),
                status="failed",
                result_json=json.dumps({"error": str(e)}),
            )
