"""Pre-built agent templates for common automation tasks."""

from __future__ import annotations

from ..intent import AgentSpec


def _file_triage_spec() -> AgentSpec:
    """Watch Downloads folder, categorize files by type."""
    return AgentSpec(
        name="file-triage",
        summary="Automatically organize downloaded files into typed folders",
        trigger="every 1 hour",
        steps=[
            {
                "action": "list_files",
                "target": "~/Downloads",
                "args": {"filter": "*"},
            },
            {
                "action": "categorize",
                "target": "files",
                "args": {
                    "rules": [
                        {"pattern": "*.pdf", "dest": "~/Documents/PDFs"},
                        {"pattern": "*.docx", "dest": "~/Documents/Word"},
                        {"pattern": "*.xlsx", "dest": "~/Documents/Sheets"},
                        {"pattern": "*.jpg|*.png|*.gif", "dest": "~/Pictures/Downloads"},
                        {"pattern": "*.zip|*.tar|*.gz", "dest": "~/Downloads/Archives"},
                    ]
                },
            },
            {"action": "move_files", "target": "categorized", "args": {}},
        ],
        inputs=[
            {
                "name": "downloads_dir",
                "type": "string",
                "description": "Path to watch (default: ~/Downloads)",
            }
        ],
        notes="Runs hourly; skips files accessed in the last 5 minutes.",
    )


def _meeting_note_router_spec() -> AgentSpec:
    """After a meeting app closes, prompt to save notes, route to Notion."""
    return AgentSpec(
        name="meeting-note-router",
        summary="Capture meeting notes and route them to Notion",
        trigger="when Zoom/Meet/Teams closes",
        steps=[
            {
                "action": "prompt",
                "target": "user",
                "args": {"message": "Save meeting notes?", "type": "textarea"},
            },
            {
                "action": "extract_metadata",
                "target": "meeting",
                "args": {
                    "fields": ["title", "participants", "start_time", "end_time"]
                },
            },
            {
                "action": "api_call",
                "target": "notion",
                "args": {
                    "method": "POST",
                    "endpoint": "/pages",
                    "body": {
                        "parent": {"database_id": "{notion_db_id}"},
                        "properties": {
                            "Title": {"title": [{"text": {"content": "{meeting_title}"}}]},
                            "Notes": {"rich_text": [{"text": {"content": "{user_notes}"}}]},
                            "Date": {"date": {"start": "{start_time}"}},
                        },
                    },
                },
            },
        ],
        inputs=[
            {
                "name": "notion_db_id",
                "type": "string",
                "description": "Notion database ID for meeting notes",
            }
        ],
        notes="Requires Notion integration and API token.",
    )


def _daily_standup_prep_spec() -> AgentSpec:
    """Every weekday at 8:45am, gather git commits, Linear issues, Slack mentions."""
    return AgentSpec(
        name="daily-standup-prep",
        summary="Prepare daily standup summary with commits, issues, and messages",
        trigger="every weekday at 08:45",
        steps=[
            {
                "action": "api_call",
                "target": "git",
                "args": {
                    "method": "GET",
                    "endpoint": "log --oneline -10 --since=24h",
                },
            },
            {
                "action": "api_call",
                "target": "linear",
                "args": {
                    "method": "GET",
                    "endpoint": "/issues?filter=assignee:me AND state:\"In Progress\"",
                },
            },
            {
                "action": "api_call",
                "target": "slack",
                "args": {
                    "method": "GET",
                    "endpoint": "/users.list",
                    "params": {"mentions": True, "since": "-24h"},
                },
            },
            {
                "action": "compose",
                "target": "summary",
                "args": {
                    "template": "## Today's Standup\n\n### Done Yesterday\n{git_commits}\n\n### In Progress\n{linear_issues}\n\n### Mentions\n{slack_mentions}"
                },
            },
            {
                "action": "notify",
                "target": "user",
                "args": {"message": "{summary}", "type": "notification"},
            },
        ],
        inputs=[],
        notes="Requires git, Linear API token, and Slack token.",
    )


def _email_followup_spec() -> AgentSpec:
    """Detect unread or unreplied emails after 24h, surface reminder."""
    return AgentSpec(
        name="email-followup",
        summary="Remind you to reply to emails after 24 hours of no response",
        trigger="every 4 hours",
        steps=[
            {
                "action": "api_call",
                "target": "email",
                "args": {
                    "method": "GET",
                    "endpoint": "/messages?q=is:read -label:replied older_than:24h",
                },
            },
            {
                "action": "filter",
                "target": "messages",
                "args": {"exclude_senders": ["notifications@", "noreply@"]},
            },
            {
                "action": "notify",
                "target": "user",
                "args": {
                    "message": "You have {count} emails waiting for a reply",
                    "type": "toast",
                    "action": "open_email",
                },
            },
        ],
        inputs=[],
        notes="Works with Gmail and compatible email APIs.",
    )


def _tab_cleanup_spec() -> AgentSpec:
    """When browser tab count exceeds 20, suggest grouping/closing."""
    return AgentSpec(
        name="tab-cleanup",
        summary="Suggest tab cleanup when tab count gets excessive",
        trigger="when browser has >20 tabs",
        steps=[
            {
                "action": "list_tabs",
                "target": "browser",
                "args": {},
            },
            {
                "action": "prompt",
                "target": "user",
                "args": {
                    "message": "You have {tab_count} tabs. Group by topic?",
                    "type": "confirm",
                },
            },
            {
                "action": "api_call",
                "target": "browser",
                "args": {
                    "method": "POST",
                    "endpoint": "/tab-groups/create",
                    "body": {
                        "title": "{suggested_group}",
                        "tabs": "{tab_ids}",
                    },
                },
            },
        ],
        inputs=[],
        notes="Requires browser extension or automation API access.",
    )


def _expense_logger_spec() -> AgentSpec:
    """After visiting banking/finance sites, prompt to log the transaction."""
    return AgentSpec(
        name="expense-logger",
        summary="Prompt to log transactions after visiting banking/finance sites",
        trigger="when user closes a banking or finance app",
        steps=[
            {
                "action": "prompt",
                "target": "user",
                "args": {
                    "message": "Log this transaction?",
                    "type": "form",
                    "fields": [
                        {"name": "amount", "type": "number"},
                        {"name": "category", "type": "select", "options": [
                            "Food", "Transport", "Utilities", "Entertainment", "Other"
                        ]},
                        {"name": "notes", "type": "textarea"},
                    ],
                },
            },
            {
                "action": "api_call",
                "target": "spreadsheet",
                "args": {
                    "method": "POST",
                    "endpoint": "/sheets/{sheet_id}/append",
                    "body": {
                        "values": [
                            ["{date}", "{amount}", "{category}", "{notes}"]
                        ],
                    },
                },
            },
        ],
        inputs=[
            {
                "name": "sheet_id",
                "type": "string",
                "description": "Google Sheets ID for expense log",
            }
        ],
        notes="Works with Google Sheets; set up sheet manually before first run.",
    )


_TEMPLATES = [
    _file_triage_spec(),
    _meeting_note_router_spec(),
    _daily_standup_prep_spec(),
    _email_followup_spec(),
    _tab_cleanup_spec(),
    _expense_logger_spec(),
]


def get_all_templates() -> list[AgentSpec]:
    """Return all built-in agent templates."""
    return _TEMPLATES


def get_template_by_name(name: str) -> AgentSpec | None:
    """Get a template by its kebab-case name."""
    for spec in _TEMPLATES:
        if spec.name == name:
            return spec
    return None
