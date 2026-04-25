"""Marketplace for discovering and installing agent templates."""

from __future__ import annotations

from .library import get_all_templates, get_template_by_name
from ..intent import AgentSpec
from ..storage import Database


def list_templates() -> list[AgentSpec]:
    """Get list of all available templates."""
    return get_all_templates()


class Marketplace:
    """Handles agent template discovery and installation."""

    def __init__(self, db: Database):
        self.db = db

    def list_templates(self) -> list[AgentSpec]:
        """Return all available agent templates."""
        return get_all_templates()

    def get_template(self, name: str) -> AgentSpec | None:
        """Get a template by its kebab-case name."""
        return get_template_by_name(name)

    def install_template(self, name: str) -> int:
        """Install a template into the database as a pattern.

        Returns the pattern ID.
        """
        spec = self.get_template(name)
        if spec is None:
            raise ValueError(f"Template '{name}' not found")

        # Create a synthetic pattern for this agent spec
        # (In reality, patterns come from detected behaviors, but templates
        # are pre-made specs that get installed directly)
        pattern_id = self.db.save_pattern(
            signature=f"template|{name}",
            occurrence_count=0,  # Templates haven't been observed yet
            avg_similarity=1.0,  # Perfect match to template
            sample_event_ids=[],  # No sample events for templates
            intent_summary=spec.summary,
            agent_spec=spec.to_dict(),
        )
        return pattern_id

    def to_dict(self) -> dict:
        """Serialize marketplace info (for API responses)."""
        return {
            "templates": [
                {
                    "name": spec.name,
                    "summary": spec.summary,
                    "trigger": spec.trigger,
                    "inputs": spec.inputs,
                    "notes": spec.notes,
                }
                for spec in self.list_templates()
            ]
        }
