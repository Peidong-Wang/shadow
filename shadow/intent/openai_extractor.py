"""OpenAI intent extractor implementation."""

from __future__ import annotations

from .base import BaseExtractor, AgentSpec, SYSTEM_PROMPT, _pattern_to_prompt, _extract_json
from ..patterns import Pattern


class OpenAIExtractor(BaseExtractor):
    """Intent extractor using OpenAI's GPT models."""

    def available(self) -> bool:
        """Check if OpenAI API is available."""
        return bool(self.cfg.openai_api_key)

    def extract(self, pattern: Pattern) -> AgentSpec:
        """Extract agent spec using OpenAI API."""
        if not self.available():
            from .base import _offline_spec
            return _offline_spec(pattern)

        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run `pip install shadow[openai]`."
            ) from exc

        client = OpenAI(api_key=self.cfg.openai_api_key)
        prompt = _pattern_to_prompt(pattern, self.db)
        response = client.chat.completions.create(
            model=self.cfg.openai_model,
            max_tokens=1024,
            system_prompt=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content or ""
        spec_json = _extract_json(text)
        return AgentSpec(**spec_json)
