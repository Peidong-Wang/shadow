"""Notion API adapter."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .base import Adapter, AdapterRegistry

log = logging.getLogger("shadow.adapters.notion")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@AdapterRegistry.register
class NotionAdapter(Adapter):
    """Adapter for Notion API."""

    name = "notion"
    description = "Create and manage pages in Notion"
    required_config = ["NOTION_API_KEY"]

    def available(self) -> bool:
        """Check if Notion adapter is available."""
        if not HTTPX_AVAILABLE:
            return False
        api_key = os.getenv("NOTION_API_KEY")
        return bool(api_key)

    def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Notion action."""
        if action == "create_page":
            return self._create_page(params)
        elif action == "search":
            return self._search(params)
        elif action == "update_page":
            return self._update_page(params)
        elif action == "list_databases":
            return self._list_databases(params)
        else:
            raise ValueError(f"Unknown Notion action: {action}")

    def list_actions(self) -> list[dict[str, str]]:
        """Return available Notion actions."""
        return [
            {
                "name": "create_page",
                "description": "Create a new page in a database",
                "params": ["parent_id", "title"],
            },
            {
                "name": "search",
                "description": "Search for pages and databases",
                "params": ["query"],
            },
            {
                "name": "update_page",
                "description": "Update a page's properties",
                "params": ["page_id", "properties"],
            },
            {
                "name": "list_databases",
                "description": "List all accessible databases",
                "params": [],
            },
        ]

    def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the Notion API."""
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx not installed")

        api_key = os.getenv("NOTION_API_KEY")
        if not api_key:
            raise ValueError("NOTION_API_KEY not set")

        try:
            with httpx.Client() as client:
                response = client.request(
                    method,
                    f"https://api.notion.com/v1/{endpoint}",
                    json=json_data,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            log.error(f"Notion API request failed: {e}")
            return {"error": str(e)}

    def _create_page(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a new page in a Notion database."""
        parent_id = params.get("parent_id")
        title = params.get("title")

        if not parent_id or not title:
            return {"error": "Missing 'parent_id' or 'title' parameter"}

        payload = {
            "parent": {"database_id": parent_id},
            "properties": {
                "title": {
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": title},
                        }
                    ]
                }
            },
        }

        result = self._make_request("POST", "pages", payload)
        if "error" in result:
            log.error(f"Failed to create page: {result['error']}")
            return result

        log.info(f"Created Notion page: {title}")
        return {"ok": True, "page_id": result.get("id")}

    def _search(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search for pages and databases in Notion."""
        query = params.get("query")

        if not query:
            return {"error": "Missing 'query' parameter"}

        payload = {
            "query": query,
            "page_size": 10,
        }

        result = self._make_request("POST", "search", payload)
        if "error" in result:
            log.error(f"Failed to search: {result['error']}")
            return result

        results = result.get("results", [])
        log.info(f"Found {len(results)} results for '{query}'")
        return {
            "ok": True,
            "results": [
                {
                    "id": r["id"],
                    "type": r["object"],
                    "title": r.get("properties", {})
                    .get("title", {})
                    .get("title", [{}])[0]
                    .get("plain_text", "(untitled)"),
                }
                for r in results
            ],
        }

    def _update_page(self, params: dict[str, Any]) -> dict[str, Any]:
        """Update a page's properties."""
        page_id = params.get("page_id")
        properties = params.get("properties", {})

        if not page_id:
            return {"error": "Missing 'page_id' parameter"}

        payload = {"properties": properties}

        result = self._make_request("PATCH", f"pages/{page_id}", payload)
        if "error" in result:
            log.error(f"Failed to update page: {result['error']}")
            return result

        log.info(f"Updated Notion page: {page_id}")
        return {"ok": True}

    def _list_databases(self, params: dict[str, Any]) -> dict[str, Any]:
        """List all accessible Notion databases."""
        result = self._make_request("POST", "search", {"filter": {"value": "database", "property": "object"}})

        if "error" in result:
            log.error(f"Failed to list databases: {result['error']}")
            return result

        databases = [r for r in result.get("results", []) if r["object"] == "database"]
        log.info(f"Found {len(databases)} databases")
        return {
            "ok": True,
            "databases": [
                {
                    "id": db["id"],
                    "title": db.get("title", [{}])[0].get("plain_text", "(untitled)")
                    if db.get("title")
                    else "(untitled)",
                }
                for db in databases
            ],
        }
