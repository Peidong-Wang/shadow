"""Local-only intent extraction using small on-device models.

No API key required — runs entirely on the user's machine using
transformers + a small instruction-following model. Falls back to
a rule-based heuristic if the model isn't available.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .base import (
    AgentSpec,
    BaseExtractor,
    SYSTEM_PROMPT,
    _extract_json,
    _offline_spec,
    _pattern_to_prompt,
)
from ..config import Config, config as default_config
from ..patterns import Pattern
from ..storage import Database

log = logging.getLogger("shadow.intent.local")


class LocalExtractor(BaseExtractor):
    """Extract intent using a local model via Hugging Face transformers.

    Uses a small instruction-following model (default: TinyLlama-1.1B-Chat)
    so no API key or network access is needed. Quality is lower than
    cloud providers but works fully offline.

    Set ``cfg.local_model`` to override the model name.
    """

    def __init__(self, db: Database, cfg: Config | None = None):
        super().__init__(db, cfg)
        self._pipeline = None

    def available(self) -> bool:
        """Check if transformers and torch are installed."""
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_pipeline(self):
        """Lazy-load the text generation pipeline."""
        if self._pipeline is not None:
            return self._pipeline

        try:
            from transformers import pipeline

            model_name = getattr(self.cfg, "local_model", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
            log.info("Loading local model: %s (first run may download ~2GB)", model_name)

            self._pipeline = pipeline(
                "text-generation",
                model=model_name,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.3,
                top_p=0.9,
            )
            return self._pipeline
        except Exception as exc:
            log.error("Failed to load local model: %s", exc)
            raise

    def extract(self, pattern: Pattern) -> AgentSpec:
        """Extract intent using the local model."""
        if not self.available():
            return _offline_spec(pattern)

        try:
            pipe = self._get_pipeline()
        except Exception:
            log.warning("Local model unavailable, falling back to heuristic extraction")
            return self._heuristic_extract(pattern)

        prompt = _pattern_to_prompt(pattern, self.db)

        # Format as a chat-style prompt for instruction models
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            result = pipe(messages)
            text = result[0]["generated_text"]
            # The pipeline returns the full conversation; extract the last assistant message
            if isinstance(text, list):
                text = text[-1].get("content", "")
            elif isinstance(text, str) and "assistant" in text.lower():
                # Try to extract just the assistant response
                parts = text.rsplit("assistant", 1)
                if len(parts) > 1:
                    text = parts[-1].strip().lstrip(":").strip()

            spec_json = _extract_json(text)
            return AgentSpec(**spec_json)
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            log.warning("Local model returned unparseable output, using heuristic: %s", exc)
            return self._heuristic_extract(pattern)

    def _heuristic_extract(self, pattern: Pattern) -> AgentSpec:
        """Rule-based fallback when the local model can't produce valid JSON.

        Analyzes the pattern structure to infer a reasonable agent spec
        without any ML model. Better than the bare offline spec because
        it attempts to identify the workflow type and suggest triggers.
        """
        apps = []
        actions = []
        for sig in pattern.signature:
            parts = (sig.split("|") + ["", "", ""])[:3]
            event_type, app, target = parts
            if app and app not in apps:
                apps.append(app)
            actions.append({"action": event_type or "replay_event", "target": target or app})

        # Infer trigger from first app
        first_app = apps[0] if apps else "unknown"
        trigger = f"when user opens {first_app}"

        # Infer workflow name from apps involved
        app_slug = "-".join(a.lower().replace(" ", "-") for a in apps[:3])
        name = f"workflow-{app_slug}" if app_slug else "workflow-auto"

        # Build summary
        if len(apps) == 1:
            summary = f"Automated workflow in {apps[0]} ({pattern.occurrences} times observed)"
        elif len(apps) == 2:
            summary = f"Workflow between {apps[0]} and {apps[1]} ({pattern.occurrences} times)"
        else:
            summary = (
                f"Multi-app workflow across {', '.join(apps[:3])} "
                f"({pattern.occurrences} times, {len(pattern.signature)} steps)"
            )

        steps = []
        for i, sig in enumerate(pattern.signature):
            parts = (sig.split("|") + ["", "", ""])[:3]
            event_type, app, target = parts
            if event_type == "focus":
                steps.append({"action": "open_app", "target": app})
            elif event_type == "navigate":
                steps.append({"action": "navigate", "target": target or app})
            else:
                steps.append({"action": event_type or "replay_event", "target": target or sig})

        return AgentSpec(
            name=name[:40],
            summary=summary,
            trigger=trigger,
            steps=steps,
            notes=(
                "Generated by local heuristic analysis. For richer agent specs, "
                "install a local model: pip install shadow[local] or configure "
                "a cloud provider (Claude, OpenAI, OpenClaw)."
            ),
        )
