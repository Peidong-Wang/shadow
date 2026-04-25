"""Ollama local model intent extractor implementation."""

from __future__ import annotations

from .base import BaseExtractor, AgentSpec, SYSTEM_PROMPT, _pattern_to_prompt, _extract_json
from ..patterns import Pattern


class OllamaExtractor(BaseExtractor):
    """Intent extractor using local Ollama models."""

    def available(self) -> bool:
        """Check if Ollama is available (no API key needed, just package)."""
        try:
            import ollama  # type: ignore  # noqa: F401
            return True
        except ImportError:
            return False

    def extract(self, pattern: Pattern) -> AgentSpec:
        """Extract agent spec using Ollama local models."""
        if not self.available():
            from .base import _offline_spec
            return _offline_spec(pattern)

        try:
            import ollama  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "ollama package not installed. Run `pip install shadow[ollama]`."
            ) from exc

        prompt = _pattern_to_prompt(pattern, self.db)
        
        # Ollama API is message-based like OpenAI
        response = ollama.chat(
            model=self.cfg.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        text = response.message.content if hasattr(response, "message") else response.get("message", {}).get("content", "")
        spec_json = _extract_json(text)
        return AgentSpec(**spec_json)
