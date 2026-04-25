"""Linear API adapter."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .base import Adapter, AdapterRegistry

log = logging.getLogger("shadow.adapters.linear")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@AdapterRegistry.register
class LinearAdapter(Adapter):
    """Adapter for Linear API (GraphQL)."""

    name = "linear"
    description = "Create and manage issues in Linear"
    required_config = ["LINEAR_API_KEY"]

    def available(self) -> bool:
        """Check if Linear adapter is available."""
        if not HTTPX_AVAILABLE:
            return False
        api_key = os.getenv("LINEAR_API_KEY")
        return bool(api_key)

    def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Linear action."""
        if action == "create_issue":
            return self._create_issue(params)
        elif action == "list_issues":
            return self._list_issues(params)
        elif action == "update_issue":
            return self._update_issue(params)
        elif action == "list_projects":
            return self._list_projects(params)
        else:
            raise ValueError(f"Unknown Linear action: {action}")

    def list_actions(self) -> list[dict[str, str]]:
        """Return available Linear actions."""
        return [
            {
                "name": "create_issue",
                "description": "Create a new issue",
                "params": ["title", "description", "project_id"],
            },
            {
                "name": "list_issues",
                "description": "List issues in a project",
                "params": ["project_id", "limit"],
            },
            {
                "name": "update_issue",
                "description": "Update an issue",
                "params": ["issue_id", "title", "description", "status"],
            },
            {
                "name": "list_projects",
                "description": "List all projects",
                "params": [],
            },
        ]

    def _graphql_query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query against Linear API."""
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx not installed")

        api_key = os.getenv("LINEAR_API_KEY")
        if not api_key:
            raise ValueError("LINEAR_API_KEY not set")

        try:
            with httpx.Client() as client:
                response = client.post(
                    "https://api.linear.app/graphql",
                    json={"query": query, "variables": variables or {}},
                    headers={"Authorization": api_key, "Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                if "errors" in data:
                    return {"error": data["errors"]}
                return data.get("data", {})
        except Exception as e:
            log.error(f"GraphQL query failed: {e}")
            return {"error": str(e)}

    def _create_issue(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a new issue in Linear."""
        title = params.get("title")
        description = params.get("description", "")
        project_id = params.get("project_id")

        if not title or not project_id:
            return {"error": "Missing 'title' or 'project_id' parameter"}

        query = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                }
            }
        }
        """
        variables = {
            "input": {
                "title": title,
                "description": description,
                "projectId": project_id,
            }
        }

        result = self._graphql_query(query, variables)
        if "error" in result:
            log.error(f"Failed to create issue: {result['error']}")
            return result

        issue_data = result.get("issueCreate", {}).get("issue", {})
        log.info(f"Created issue {issue_data.get('identifier')}")
        return {"ok": True, "issue_id": issue_data.get("id")}

    def _list_issues(self, params: dict[str, Any]) -> dict[str, Any]:
        """List issues in a project."""
        project_id = params.get("project_id")
        limit = params.get("limit", 10)

        if not project_id:
            return {"error": "Missing 'project_id' parameter"}

        query = """
        query ListIssues($filter: IssueFilter!) {
            issues(filter: $filter, first: %d) {
                nodes {
                    id
                    identifier
                    title
                    status {
                        name
                    }
                }
            }
        }
        """ % limit
        variables = {
            "filter": {"project": {"id": {"eq": project_id}}}
        }

        result = self._graphql_query(query, variables)
        if "error" in result:
            log.error(f"Failed to list issues: {result['error']}")
            return result

        issues = result.get("issues", {}).get("nodes", [])
        log.info(f"Found {len(issues)} issues in project {project_id}")
        return {
            "ok": True,
            "issues": [
                {
                    "id": i["id"],
                    "identifier": i["identifier"],
                    "title": i["title"],
                    "status": i.get("status", {}).get("name"),
                }
                for i in issues
            ],
        }

    def _update_issue(self, params: dict[str, Any]) -> dict[str, Any]:
        """Update an issue."""
        issue_id = params.get("issue_id")
        title = params.get("title")
        description = params.get("description")
        status = params.get("status")

        if not issue_id:
            return {"error": "Missing 'issue_id' parameter"}

        update_input = {}
        if title:
            update_input["title"] = title
        if description:
            update_input["description"] = description
        if status:
            update_input["stateId"] = status

        query = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                }
            }
        }
        """
        variables = {
            "id": issue_id,
            "input": update_input,
        }

        result = self._graphql_query(query, variables)
        if "error" in result:
            log.error(f"Failed to update issue: {result['error']}")
            return result

        log.info(f"Updated issue {issue_id}")
        return {"ok": True}

    def _list_projects(self, params: dict[str, Any]) -> dict[str, Any]:
        """List all projects."""
        query = """
        query ListProjects {
            projects(first: 100) {
                nodes {
                    id
                    name
                    identifier
                }
            }
        }
        """

        result = self._graphql_query(query, {})
        if "error" in result:
            log.error(f"Failed to list projects: {result['error']}")
            return result

        projects = result.get("projects", {}).get("nodes", [])
        log.info(f"Found {len(projects)} projects")
        return {
            "ok": True,
            "projects": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "identifier": p["identifier"],
                }
                for p in projects
            ],
        }
