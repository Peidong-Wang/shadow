"""Shadow configuration — single source of truth for paths, tuning, and privacy defaults."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _default_data_dir() -> Path:
    """Return the platform-appropriate data directory for Shadow."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "shadow"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Config:
    """Runtime configuration. All privacy-sensitive defaults are conservative."""

    # Storage
    data_dir: Path = field(default_factory=_default_data_dir)
    db_filename: str = "shadow.db"

    # Capture
    poll_interval_seconds: float = 1.0
    idle_gap_seconds: float = 30.0  # >idle_gap means new session
    store_window_titles: bool = True
    store_urls: bool = True
    store_keystrokes: bool = False  # Never store raw keystrokes by default
    hash_sensitive_values: bool = True

    # Pattern detection
    min_pattern_length: int = 3
    min_pattern_occurrences: int = 3
    similarity_threshold: float = 0.8

    # Intent extraction — multi-provider support
    intent_provider: str = "auto"  # "auto" | "claude" | "openai" | "openclaw" | "ollama" | "local" | "offline"
    
    # Claude intent extraction
    anthropic_api_key: str | None = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY"))
    claude_model: str = "claude-sonnet-4-5-20241022"

    # OpenAI intent extraction
    openai_api_key: str | None = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY"))
    openai_model: str = "gpt-4o"

    # OpenClaw intent extraction
    openclaw_api_key: str | None = field(default_factory=lambda: os.environ.get("OPENCLAW_API_KEY"))
    openclaw_model: str = "openclaw-default"

    # Ollama local models
    ollama_model: str = "llama3"
    ollama_host: str = "http://localhost:11434"

    # Local on-device model (transformers)
    local_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

    # Dashboard
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 4747

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_filename


# Module-level default instance — callers can override.
config = Config()
