"""Use Claude to turn a raw repeated event sequence into a generalized agent spec.

Nothing in this module reads raw keystrokes or file contents — the
prompt only sees the app name, event type, and (optionally) window
titles or URLs, which the user already controls via ``Config``.
"""

from __future__ import annotations

import json
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


class IntentExtractor:
    def __init__(self, db: Database, cfg: Config | None = None):
        self.db = db
        self.cfg = cfg or default_config

    def available(self) -> bool:
        return bool(self.cfg.anthropic_api_key)

    def extract(self, pattern: Pattern) -> AgentSpec:
        if not self.available():
            # Offline fallback: synthesize a best-effort spec without calling Claude.
            return self._offline_spec(pattern)

        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package not installed. Run `pip install shadow[intent]`."
            ) from exc

        client = anthropic.Anthropic(api_key=self.cfg.anthropic_api_key)
        prompt = _pattern_to_prompt(pattern, self.db)
        msg = client.messages.create(
            model=self.cfg.claude_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        # Claude responses are a list of content blocks — we expect one text block.
        text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
        spec_json = _extract_json(text)
        return AgentSpec(**spec_json)

    def _offline_spec(self, pattern: Pattern) -> AgentSpec:
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
                "Generated offline — set ANTHROPIC_API_KEY to enable Claude-powered "
                "intent extraction for a richer, generalized agent spec."
            ),
        )


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
