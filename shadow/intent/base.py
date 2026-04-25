"""Base classes and utilities for LLM-powered intent extraction.

Supports multiple providers: Claude, OpenAI, OpenClaw, Ollama, with offline fallback.
Nothing in this module reads raw keystrokes or file contents — the
prompt only sees the app name, event type, and (optionally) window
titles or URLs, which the user already controls via ``Config``.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..config import Config, config as default_config
from ..patterns import Pattern
from ..storage import Database


@dataclass
class AgentSpec:
    """Structured, executable description of a learnable workflow."""

    name: str
    summary: str
    trigger: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "trigger": self.trigger,
            "steps": self.steps,
            "inputs": self.inputs,
            "notes": self.notes,
        }


SYSTEM_PROMPT = """You are analyzing a repeated desktop workflow captured
from a user. Your job is to infer what the user is trying to accomplish
and describe the workflow as a generalized, executable agent spec.

Reply ONLY with a JSON object matching this schema:
{
  "name": "short-kebab-case-id",
  "summary": "1 sentence in plain English",
  "trigger": "when this agent should run (e.g. 'every weekday at 9am' or 'when user opens Gmail')",
  "steps": [
     {"action": "open_app" | "navigate" | "click" | "type" | "wait" | "api_call",
      "target": "...",
      "args": {...}}
  ],
  "inputs": [{"name": "...", "type": "string|number|date", "description": "..."}],
  "notes": "any caveats or things that need user confirmation before running"
}
"""


def _pattern_to_prompt(pattern: Pattern, db: Database) -> str:
    """Convert a pattern to a natural language prompt for LLM analysis."""
    lines = [f"Pattern observed {pattern.occurrences} times.",
             "Each occurrence consists of these steps (in order):"]
    for i, sig in enumerate(pattern.signature, 1):
        event_type, app, target = (sig.split("|") + ["", ""])[:3]
        lines.append(f"  {i}. [{event_type}] app={app!r} target={target!r}")
    # Include one concrete example with window titles for richer context.
    lines.append("\nOne concrete example (window titles shown for context):")
    for ev_id in pattern.sample_event_ids:
        ev = next((e for e in db.recent_events(limit=5000) if e.id == ev_id), None)
        if ev is None:
            continue
        lines.append(
            f"  - ts={int(ev.ts)} app={ev.app!r} event={ev.event_type!r} "
            f"window_title={ev.window_title!r} url={ev.url!r}"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a model response, tolerant to fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # Remove leading language tag like ```json
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


def _offline_spec(pattern: Pattern) -> AgentSpec:
    """Generate a fallback spec when no provider is available."""
    apps = sorted({sig.split("|")[1] for sig in pattern.signature if sig.split("|")[1]})
    return AgentSpec(
        name=f"auto-{'-'.join(a.lower().replace(' ', '-') for a in apps)[:40]}",
        summary=(
            f"Repeated workflow across {', '.join(apps) or 'apps'} "
            f"({pattern.occurrences} occurrences, {len(pattern.signature)} steps)"
        ),
        trigger="manual (review and schedule after first run)",
        steps=[{"action": "replay_event", "target": sig} for sig in pattern.signature],
        notes=(
            "Generated offline — configure an LLM provider (Claude, OpenAI, OpenClaw, Ollama) "
            "to enable intent extraction for a richer, generalized agent spec."
        ),
    )


class BaseExtractor(ABC):
    """Abstract base class for intent extractors using various LLM providers."""

    def __init__(self, db: Database, cfg: Config | None = None):
        self.db = db
        self.cfg = cfg or default_config

    @abstractmethod
    def available(self) -> bool:
        """Check if this provider is available (API key configured, package installed)."""
        pass

    @abstractmethod
    def extract(self, pattern: Pattern) -> AgentSpec:
        """Extract an agent spec from a pattern using the LLM provider."""
        pass

    def _safe_extract(self, pattern: Pattern) -> AgentSpec:
        """Safely extract with offline fallback on failure."""
        if not self.available():
            return _offline_spec(pattern)
        try:
            return self.extract(pattern)
        except Exception:
            return _offline_spec(pattern)
