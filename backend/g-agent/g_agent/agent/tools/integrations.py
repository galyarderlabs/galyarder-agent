"""Integration tools: Slack, email, calendar, and memory helpers."""

import json
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx

from g_agent.agent.memory import MemoryStore
from g_agent.agent.tools.base import Tool
from g_agent.utils.helpers import ensure_dir


def _env(name: str, default: str = "") -> str:
    """Read env var with G_AGENT_ prefix."""
    key = name.strip().upper()
    return os.environ.get(f"G_AGENT_{key}", default)


class RememberTool(Tool):
    """Persist durable facts to long-term memory."""

    name = "remember"
    description = "Save an important durable fact into long-term memory."
    parameters = {
        "type": "object",
        "properties": {
            "fact": {"type": "string", "description": "Durable fact to remember"},
            "category": {"type": "string", "description": "Fact category", "default": "general"},
        },
        "required": ["fact"],
    }

    def __init__(self, workspace: Path):
        self.memory = MemoryStore(workspace)

    async def execute(self, fact: str, category: str = "general", **kwargs: Any) -> str:
        ok = self.memory.append_long_term_fact(fact, category=category)
        if ok:
            return f"Saved to long-term memory ({category})."
        return "Fact already exists or was empty; no change."


class RecallTool(Tool):
    """Recall relevant memory snippets for a query."""

    name = "recall"
    description = "Recall relevant memory snippets based on a query."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to recall"},
            "maxItems": {"type": "integer", "description": "Maximum items", "minimum": 1, "maximum": 30},
            "lookbackDays": {"type": "integer", "description": "Daily-memory lookback window", "minimum": 1, "maximum": 365},
            "scopes": {
                "type": "array",
                "description": "Optional memory scopes",
                "items": {"type": "string"},
            },
        },
        "required": ["query"],
    }

    def __init__(self, workspace: Path):
        self.memory = MemoryStore(workspace)

    async def execute(
        self,
        query: str,
        maxItems: int = 12,
        lookbackDays: int = 30,
        scopes: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        items = self.memory.recall(
            query=query,
            max_items=maxItems,
            lookback_days=lookbackDays,
            scopes=scopes,
        )
        if not items:
            return f"No memory matches found for: {query}"

        lines = [f"Memory recall for: {query}"]
        for idx, item in enumerate(items, 1):
            lines.append(f"{idx}. [{item['source']}] {item['text']}")
        return "\n".join(lines)


class UpdateProfileTool(Tool):
    """Update structured profile fields."""

    name = "update_profile"
    description = "Update a key/value field in profile memory."
    parameters = {
        "type": "object",
        "properties": {
            "section": {"type": "string", "description": "Profile section (e.g. Identity, Preferences)"},
            "key": {"type": "string", "description": "Field name"},
            "value": {"type": "string", "description": "Field value"},
        },
        "required": ["key", "value"],
    }

    def __init__(self, workspace: Path):
        self.memory = MemoryStore(workspace)

    async def execute(
        self,
        key: str,
        value: str,
        section: str = "Preferences",
        **kwargs: Any,
    ) -> str:
        ok = self.memory.upsert_profile_field(section=section, key=key, value=value)
        if ok:
            return f"Updated profile: {section}.{key}"
        return "Failed to update profile (invalid input or file not writable)."


class LogFeedbackTool(Tool):
    """Save feedback/lessons for self-improvement."""

    name = "log_feedback"
    description = "Log user feedback or mistakes into lessons learned."
    parameters = {
        "type": "object",
        "properties": {
            "feedback": {"type": "string", "description": "Feedback or lesson text"},
            "source": {"type": "string", "description": "Source label", "default": "user"},
            "severity": {
                "type": "string",
                "description": "Impact level",
                "enum": ["low", "medium", "high"],
                "default": "medium",
            },
        },
        "required": ["feedback"],
    }

    def __init__(self, workspace: Path):
        self.memory = MemoryStore(workspace)

    async def execute(self, feedback: str, source: str = "user", severity: str = "medium", **kwargs: Any) -> str:
        ok = self.memory.append_lesson(feedback, source=source, severity=severity)
        if ok:
            return "Logged feedback to lessons learned."
        return "Feedback was empty; no change."


class SlackWebhookTool(Tool):
    """Send messages to Slack via Incoming Webhook."""

    name = "slack_webhook_send"
    description = "Send a message to Slack using an Incoming Webhook URL."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Message text"},
            "webhookUrl": {"type": "string", "description": "Slack webhook URL (optional if configured)"},
        },
        "required": ["text"],
    }

    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or _env("SLACK_WEBHOOK_URL", "")

    async def execute(self, text: str, webhookUrl: str | None = None, **kwargs: Any) -> str:
        url = webhookUrl or self.webhook_url
        if not url:
            return "Error: Slack webhook URL not configured."

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json={"text": text})
            if 200 <= response.status_code < 300:
                return "Slack message sent."
            return f"Error: Slack webhook returned HTTP {response.status_code}"
        except Exception as e:
            return f"Error: {e}"


class SendEmailTool(Tool):
    """Send email via SMTP."""

    name = "send_email"
    description = "Send an email using SMTP settings from config/env."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body"},
            "fromEmail": {"type": "string", "description": "Sender email override"},
        },
        "required": ["to", "subject", "body"],
    }

    def __init__(
        self,
        host: str = "",
        port: int = 587,
        username: str = "",
        password: str = "",
        from_email: str = "",
        use_tls: bool = True,
    ):
        self.host = host or _env("SMTP_HOST", "")
        self.port = int(_env("SMTP_PORT", str(port)))
        self.username = username or _env("SMTP_USERNAME", "")
        self.password = password or _env("SMTP_PASSWORD", "")
        self.from_email = from_email or _env("SMTP_FROM", "")
        self.use_tls = use_tls

    async def execute(self, to: str, subject: str, body: str, fromEmail: str | None = None, **kwargs: Any) -> str:
        if not self.host:
            return "Error: SMTP host not configured."

        sender = fromEmail or self.from_email or self.username
        if not sender:
            return "Error: sender email not configured."

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.send_message(msg)
            return f"Email sent to {to}."
        except Exception as e:
            return f"Error: {e}"


class CreateCalendarEventTool(Tool):
    """Create a local .ics calendar event file."""

    name = "create_calendar_event"
    description = "Create an ICS calendar event file in the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Event title"},
            "start": {"type": "string", "description": "Start datetime (ISO 8601)"},
            "end": {"type": "string", "description": "End datetime (ISO 8601)"},
            "description": {"type": "string", "description": "Event description"},
            "location": {"type": "string", "description": "Event location"},
            "outputFile": {"type": "string", "description": "Optional output file path"},
        },
        "required": ["title", "start", "end"],
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.calendar_dir = ensure_dir(workspace / "calendar")

    def _parse_iso(self, value: str) -> datetime:
        value = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _fmt_ics(self, dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%SZ")

    async def execute(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        outputFile: str | None = None,
        **kwargs: Any,
    ) -> str:
        try:
            start_dt = self._parse_iso(start)
            end_dt = self._parse_iso(end)
            if end_dt <= start_dt:
                return "Error: end must be after start."

            uid = f"{int(datetime.now(tz=timezone.utc).timestamp())}-{abs(hash(title))}@g-agent"
            stamp = self._fmt_ics(datetime.now(tz=timezone.utc))
            ics = "\n".join([
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//g-agent//EN",
                "CALSCALE:GREGORIAN",
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{self._fmt_ics(start_dt)}",
                f"DTEND:{self._fmt_ics(end_dt)}",
                f"SUMMARY:{title}",
                f"DESCRIPTION:{description}",
                f"LOCATION:{location}",
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ])

            if outputFile:
                out = Path(outputFile).expanduser()
                if not out.is_absolute():
                    out = self.workspace / outputFile
            else:
                safe_name = "".join(ch if ch.isalnum() else "-" for ch in title.lower()).strip("-") or "event"
                out = self.calendar_dir / f"{safe_name}-{start_dt.strftime('%Y%m%dT%H%M%SZ')}.ics"

            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(ics, encoding="utf-8")
            return json.dumps({"ok": True, "path": str(out), "title": title})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
