"""Slack API adapter."""

from __future__ import annotations

import logging
import os
from typing import Any

from .base import Adapter, AdapterRegistry

log = logging.getLogger("shadow.adapters.slack")

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False


@AdapterRegistry.register
class SlackAdapter(Adapter):
    """Adapter for Slack API."""

    name = "slack"
    description = "Send messages and manage Slack workspace"
    required_config = ["SLACK_TOKEN"]

    def __init__(self):
        self._client = None

    def available(self) -> bool:
        """Check if Slack adapter is available."""
        if not SLACK_AVAILABLE:
            return False
        token = os.getenv("SLACK_TOKEN")
        return bool(token)

    def _get_client(self) -> WebClient:
        """Lazy-load Slack client."""
        if self._client is not None:
            return self._client

        if not SLACK_AVAILABLE:
            raise ImportError("slack_sdk not installed")

        token = os.getenv("SLACK_TOKEN")
        if not token:
            raise ValueError("SLACK_TOKEN not set")

        self._client = WebClient(token=token)
        return self._client

    def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Slack action."""
        if action == "send_message":
            return self._send_message(params)
        elif action == "search_messages":
            return self._search_messages(params)
        elif action == "list_channels":
            return self._list_channels(params)
        elif action == "react":
            return self._react(params)
        else:
            raise ValueError(f"Unknown Slack action: {action}")

    def list_actions(self) -> list[dict[str, str]]:
        """Return available Slack actions."""
        return [
            {
                "name": "send_message",
                "description": "Send a message to a channel or user",
                "params": ["channel", "text"],
            },
            {
                "name": "search_messages",
                "description": "Search messages in the workspace",
                "params": ["query"],
            },
            {
                "name": "list_channels",
                "description": "List all channels in the workspace",
                "params": [],
            },
            {
                "name": "react",
                "description": "Add a reaction to a message",
                "params": ["channel", "timestamp", "emoji"],
            },
        ]

    def _send_message(self, params: dict[str, Any]) -> dict[str, Any]:
        """Send a message to a Slack channel."""
        client = self._get_client()
        channel = params.get("channel")
        text = params.get("text")

        if not channel or not text:
            return {"error": "Missing 'channel' or 'text' parameter"}

        try:
            response = client.chat_postMessage(channel=channel, text=text)
            log.info(f"Sent message to {channel}")
            return {"ok": True, "ts": response.get("ts")}
        except SlackApiError as e:
            log.error(f"Failed to send message: {e.response['error']}")
            return {"error": str(e)}

    def _search_messages(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search messages in Slack workspace."""
        client = self._get_client()
        query = params.get("query")

        if not query:
            return {"error": "Missing 'query' parameter"}

        try:
            response = client.search_messages(query=query)
            matches = response.get("messages", {}).get("matches", [])
            log.info(f"Found {len(matches)} messages matching '{query}'")
            return {"ok": True, "count": len(matches), "sample_matches": matches[:5]}
        except SlackApiError as e:
            log.error(f"Failed to search messages: {e.response['error']}")
            return {"error": str(e)}

    def _list_channels(self, params: dict[str, Any]) -> dict[str, Any]:
        """List all channels in the workspace."""
        client = self._get_client()
        try:
            response = client.conversations_list()
            channels = response.get("channels", [])
            log.info(f"Found {len(channels)} channels")
            return {
                "ok": True,
                "channels": [{"id": c["id"], "name": c["name"]} for c in channels],
            }
        except SlackApiError as e:
            log.error(f"Failed to list channels: {e.response['error']}")
            return {"error": str(e)}

    def _react(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add a reaction to a message."""
        client = self._get_client()
        channel = params.get("channel")
        timestamp = params.get("timestamp")
        emoji = params.get("emoji")

        if not channel or not timestamp or not emoji:
            return {"error": "Missing 'channel', 'timestamp', or 'emoji' parameter"}

        try:
            client.reactions_add(channel=channel, timestamp=timestamp, name=emoji)
            log.info(f"Added :{emoji}: reaction to message in {channel}")
            return {"ok": True}
        except SlackApiError as e:
            log.error(f"Failed to add reaction: {e.response['error']}")
            return {"error": str(e)}
