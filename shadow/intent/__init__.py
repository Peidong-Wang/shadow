"""Intent extraction with multi-provider support."""

from .base import BaseExtractor, AgentSpec
from .claude_extractor import ClaudeExtractor
from .openai_extractor import OpenAIExtractor
from .openclaw_extractor import OpenClawExtractor
from .ollama_extractor import OllamaExtractor
from .local_extractor import LocalExtractor

__all__ = [
    "BaseExtractor",
    "AgentSpec",
    "ClaudeExtractor",
    "OpenAIExtractor",
    "OpenClawExtractor",
    "OllamaExtractor",
    "LocalExtractor",
    "create_extractor",
    "IntentExtractor",  # backward compatibility
]


def create_extractor(db, cfg=None) -> BaseExtractor:
    """Factory function to create the best available intent extractor.
    
    Priority order:
    1. If cfg.intent_provider is explicitly set, use that (must be available)
    2. Claude (if API key configured and package installed)
    3. OpenAI (if API key configured and package installed)
    4. OpenClaw (if API key configured and package installed)
    5. Ollama (if package installed)
    6. Offline fallback (always available)
    
    Args:
        db: Database instance
        cfg: Config instance (uses default if None)
        
    Returns:
        BaseExtractor subclass instance
    """
    from ..config import config as default_config
    
    cfg = cfg or default_config
    provider = getattr(cfg, "intent_provider", "auto").lower()
    
    # Explicit provider selection
    if provider == "claude":
        extractor = ClaudeExtractor(db, cfg)
        if extractor.available():
            return extractor
        raise RuntimeError(
            "Claude provider requested but not available. "
            "Set ANTHROPIC_API_KEY and install 'pip install shadow[intent]'."
        )
    elif provider == "openai":
        extractor = OpenAIExtractor(db, cfg)
        if extractor.available():
            return extractor
        raise RuntimeError(
            "OpenAI provider requested but not available. "
            "Set OPENAI_API_KEY and install 'pip install shadow[openai]'."
        )
    elif provider == "openclaw":
        extractor = OpenClawExtractor(db, cfg)
        if extractor.available():
            return extractor
        raise RuntimeError(
            "OpenClaw provider requested but not available. "
            "Set OPENCLAW_API_KEY and install 'pip install shadow[openclaw]'."
        )
    elif provider == "ollama":
        extractor = OllamaExtractor(db, cfg)
        if extractor.available():
            return extractor
        raise RuntimeError(
            "Ollama provider requested but not available. "
            "Install 'pip install shadow[ollama]' and ensure Ollama is running."
        )
    elif provider == "local":
        extractor = LocalExtractor(db, cfg)
        if extractor.available():
            return extractor
        raise RuntimeError(
            "Local provider requested but not available. "
            "Install 'pip install shadow[local]' (requires transformers + torch)."
        )
    elif provider == "offline":
        # Create a minimal extractor that always returns offline specs
        from .base import _offline_spec
        class OfflineExtractor(BaseExtractor):
            def available(self) -> bool:
                return False
            def extract(self, pattern):
                return _offline_spec(pattern)
        return OfflineExtractor(db, cfg)
    
    # Auto mode: try in priority order
    if provider != "auto":
        raise ValueError(f"Unknown intent_provider: {provider}")
    
    # Try Claude first
    extractor = ClaudeExtractor(db, cfg)
    if extractor.available():
        return extractor
    
    # Try OpenAI
    extractor = OpenAIExtractor(db, cfg)
    if extractor.available():
        return extractor
    
    # Try OpenClaw
    extractor = OpenClawExtractor(db, cfg)
    if extractor.available():
        return extractor
    
    # Try Ollama
    extractor = OllamaExtractor(db, cfg)
    if extractor.available():
        return extractor

    # Try local model
    extractor = LocalExtractor(db, cfg)
    if extractor.available():
        return extractor

    # Fallback to offline
    from .base import _offline_spec
    class OfflineExtractor(BaseExtractor):
        def available(self) -> bool:
            return False
        def extract(self, pattern):
            return _offline_spec(pattern)
    return OfflineExtractor(db, cfg)


# Backward compatibility: alias for existing code
IntentExtractor = create_extractor
