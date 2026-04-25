"""Gmail API adapter."""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from .base import Adapter, AdapterRegistry

log = logging.getLogger("shadow.adapters.gmail")

try:
    from google.auth.transport.requests import Request
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False


@AdapterRegistry.register
class GmailAdapter(Adapter):
    """Adapter for Gmail API."""

    name = "gmail"
    description = "Send and manage emails via Gmail API"
    required_config = ["GMAIL_CREDENTIALS_PATH"]

    def __init__(self):
        self._service = None

    def available(self) -> bool:
        """Check if Gmail adapter is available."""
        if not GMAIL_AVAILABLE:
            return False
        creds_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        return bool(creds_path and os.path.exists(creds_path))

    def _get_service(self):
        """Lazy-load Gmail service."""
        if self._service is not None:
            return self._service

        if not GMAIL_AVAILABLE:
            raise ImportError("google-api-python-client not installed")

        creds_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        if not creds_path or not os.path.exists(creds_path):
            raise ValueError("GMAIL_CREDENTIALS_PATH not set or file not found")

        try:
            creds = Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/gmail.send"]
            )
            self._service = build("gmail", "v1", credentials=creds)
            return self._service
        except Exception as e:
            log.error(f"Failed to initialize Gmail service: {e}")
            raise

    def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Gmail action."""
        if action == "send_email":
            return self._send_email(params)
        elif action == "search_emails":
            return self._search_emails(params)
        elif action == "read_email":
            return self._read_email(params)
        elif action == "create_draft":
            return self._create_draft(params)
        else:
            raise ValueError(f"Unknown Gmail action: {action}")

    def list_actions(self) -> list[dict[str, str]]:
        """Return available Gmail actions."""
        return [
            {
                "name": "send_email",
                "description": "Send an email",
                "params": ["to", "subject", "body"],
            },
            {
                "name": "search_emails",
                "description": "Search emails",
                "params": ["query", "max_results"],
            },
            {
                "name": "read_email",
                "description": "Read an email by ID",
                "params": ["message_id"],
            },
            {
                "name": "create_draft",
                "description": "Create a draft email",
                "params": ["to", "subject", "body"],
            },
        ]

    def _send_email(self, params: dict[str, Any]) -> dict[str, Any]:
        """Send an email."""
        service = self._get_service()
        to = params.get("to")
        subject = params.get("subject", "")
        body = params.get("body", "")

        if not to:
            return {"error": "Missing 'to' parameter"}

        try:
            message = {
                "raw": base64.urlsafe_b64encode(
                    f"To: {to}\nSubject: {subject}\n\n{body}".encode()
                ).decode()
            }
            result = service.users().messages().send(userId="me", body=message).execute()
            log.info(f"Sent email to {to}")
            return {"ok": True, "message_id": result.get("id")}
        except Exception as e:
            log.error(f"Failed to send email: {e}")
            return {"error": str(e)}

    def _search_emails(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search emails."""
        service = self._get_service()
        query = params.get("query", "")
        max_results = params.get("max_results", 10)

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = results.get("messages", [])
            log.info(f"Found {len(messages)} emails matching '{query}'")
            return {"ok": True, "message_ids": [m["id"] for m in messages]}
        except Exception as e:
            log.error(f"Failed to search emails: {e}")
            return {"error": str(e)}

    def _read_email(self, params: dict[str, Any]) -> dict[str, Any]:
        """Read an email."""
        service = self._get_service()
        message_id = params.get("message_id")

        if not message_id:
            return {"error": "Missing 'message_id' parameter"}

        try:
            message = service.users().messages().get(userId="me", id=message_id).execute()
            headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}
            log.info(f"Read email {message_id}")
            return {
                "ok": True,
                "from": headers.get("From"),
                "subject": headers.get("Subject"),
                "snippet": message.get("snippet"),
            }
        except Exception as e:
            log.error(f"Failed to read email: {e}")
            return {"error": str(e)}

    def _create_draft(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a draft email."""
        service = self._get_service()
        to = params.get("to")
        subject = params.get("subject", "")
        body = params.get("body", "")

        if not to:
            return {"error": "Missing 'to' parameter"}

        try:
            message = {
                "raw": base64.urlsafe_b64encode(
                    f"To: {to}\nSubject: {subject}\n\n{body}".encode()
                ).decode()
            }
            result = (
                service.users()
                .drafts()
                .create(userId="me", body={"message": message})
                .execute()
            )
            log.info(f"Created draft for {to}")
            return {"ok": True, "draft_id": result.get("id")}
        except Exception as e:
            log.error(f"Failed to create draft: {e}")
            return {"error": str(e)}
