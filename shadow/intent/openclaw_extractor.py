"""OpenClaw intent extractor implementation."""

from __future__ import annotations

from .base import BaseExtractor, AgentSpec, SYSTEM_PROMPT, _pattern_to_prompt, _extract_json
from ..patterns import Pattern


class OpenClawExtractor(BaseExtractor):
    """Intent extractor using OpenClaw framework."""

    def available(self) -> bool:
        """Check if OpenClaw API is available."""
        return bool(self.cfg.openclaw_api_key)

    def extract(self, pattern: Pattern) -> AgentSpec:
        """Extract agent spec using OpenClaw API."""
        if not self.available():
            from .base import _offline_spec
            return _offline_spec(pattern)

        try:
            from openclaw import Client  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "openclaw package not installed. Run `pip install shadow[openclaw]`."
            ) from exc

        client = Client(api_key=self.cfg.openclaw_api_key)
        prompt = _pattern_to_prompt(pattern, self.db)
        
        # OpenClaw typically uses message-based API similar to OpenAI
        response = client.chat.completions.create(
            model=self.cfg.openclaw_model,
            max_tokens=1024,
            system_prompt=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content or ""
        spec_json = _extract_json(text)
        return AgentSpec(**spec_json)
