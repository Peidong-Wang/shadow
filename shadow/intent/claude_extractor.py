"""Claude Anthropic intent extractor implementation."""

from __future__ import annotations

from .base import BaseExtractor, AgentSpec, SYSTEM_PROMPT, _pattern_to_prompt, _extract_json
from ..patterns import Pattern


class ClaudeExtractor(BaseExtractor):
    """Intent extractor using Claude from Anthropic."""

    def available(self) -> bool:
        """Check if Claude API is available."""
        return bool(self.cfg.anthropic_api_key)

    def extract(self, pattern: Pattern) -> AgentSpec:
        """Extract agent spec using Claude API."""
        if not self.available():
            from .base import _offline_spec
            return _offline_spec(pattern)

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
