"""Base class and registry for API adapters."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

log = logging.getLogger("shadow.adapters")


class Adapter(ABC):
    """Abstract base class for API adapters."""

    name: str
    description: str
    required_config: list[str]

    @abstractmethod
    def available(self) -> bool:
        """Check if this adapter is available (required packages/config installed)."""
        pass

    @abstractmethod
    def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute an action with the given parameters."""
        pass

    @abstractmethod
    def list_actions(self) -> list[dict[str, str]]:
        """Return list of available actions with descriptions."""
        pass

    def _check_env_vars(self, *var_names: str) -> bool:
        """Check if all required environment variables are set."""
        return all(os.getenv(var) for var in var_names)


class AdapterRegistry:
    """Singleton registry for managing adapters."""

    _instance: AdapterRegistry | None = None
    _adapters: dict[str, type[Adapter]] = {}

    def __new__(cls) -> AdapterRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, adapter_cls: type[Adapter]):
        """Decorator to register an adapter class."""
        registry = cls()
        if not hasattr(adapter_cls, "name"):
            raise ValueError(f"Adapter {adapter_cls} must have a 'name' class variable")
        registry._adapters[adapter_cls.name] = adapter_cls
        log.debug(f"Registered adapter: {adapter_cls.name}")
        return adapter_cls

    def get(self, name: str) -> Adapter | None:
        """Get an instance of a registered adapter by name."""
        adapter_cls = self._adapters.get(name)
        if adapter_cls is None:
            return None
        return adapter_cls()

    def list_available(self) -> list[Adapter]:
        """Return list of all available (configured) adapters."""
        available = []
        for adapter_cls in self._adapters.values():
            adapter = adapter_cls()
            if adapter.available():
                available.append(adapter)
        return available

    def list_all(self) -> list[Adapter]:
        """Return list of all registered adapters (available or not)."""
        return [adapter_cls() for adapter_cls in self._adapters.values()]

    def has(self, name: str) -> bool:
        """Check if an adapter with the given name is registered."""
        return name in self._adapters

    def is_available(self, name: str) -> bool:
        """Check if an adapter is available."""
        adapter = self.get(name)
        return adapter is not None and adapter.available()
