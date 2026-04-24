"""Cross-platform desktop activity capture.

The `Capture` class is the user-facing entry point; it picks a platform
backend automatically and exposes a uniform event stream.
"""

from __future__ import annotations

import sys

from .base import CaptureBackend, Capture

__all__ = ["CaptureBackend", "Capture", "default_backend"]


def default_backend() -> CaptureBackend:
    """Return the best-available backend for the current platform."""
    if sys.platform == "darwin":
        from .macos import MacOSBackend
        return MacOSBackend()
    if sys.platform == "win32":
        from .windows import WindowsBackend
        return WindowsBackend()
    if sys.platform.startswith("linux"):
        from .linux import LinuxBackend
        return LinuxBackend()
    # Fallback: a cross-platform "generic" backend using psutil only.
    from .generic import GenericBackend
    return GenericBackend()
