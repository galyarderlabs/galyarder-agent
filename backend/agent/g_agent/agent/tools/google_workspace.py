"""Google Workspace tools via `gws` CLI (https://github.com/googleworkspace/cli).

All auth is handled by gws itself (OS keyring, AES-256-GCM encrypted).
Run `gws auth setup` once to configure.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from loguru import logger

from g_agent.agent.tools.base import Tool


# ---------------------------------------------------------------------------
# GwsClient — thin async wrapper around the `gws` binary
# ---------------------------------------------------------------------------


def _find_gws_binary() -> str:
    """Locate gws binary, checking common install locations."""
    import os
    import subprocess
    from pathlib import Path

    # 1. Already on PATH
    found = shutil.which("gws")
    if found:
        return found

    # 2. Probe common install locations
    home = Path.home()
    candidates = [
        home / ".local" / "bin" / "gws",        # pipx-style
        Path("/usr/local/bin/gws"),              # manual install
    ]

    # 3. NVM / npm global bins
    nvm_dir = os.environ.get("NVM_DIR")
    if nvm_dir:
        versions_dir = Path(nvm_dir) / "versions" / "node"
        if versions_dir.exists():
            for v_dir in versions_dir.iterdir():
                if v_dir.is_dir():
                    candidates.append(v_dir / "bin" / "gws")

    npm_prefix = os.environ.get("NVM_BIN", "")
    if npm_prefix:
        candidates.append(Path(npm_prefix) / "gws")
        
    try:
        npm_global = subprocess.check_output(["npm", "prefix", "-g"], text=True).strip()
        if npm_global:
             candidates.append(Path(npm_global) / "bin" / "gws")
    except Exception:
        pass

    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)

    return "gws"  # fallback — will fail with FileNotFoundError at runtime


class GwsClient:
    """Helper client for executing gws CLI commands."""

    def __init__(
        self, *, gws_path: str = "", calendar_id: str = "primary", credentials_file: str = ""
    ) -> None:
        self._bin = gws_path or _find_gws_binary()
        self.calendar_id = calendar_id
        self._credentials_file = credentials_file

    def is_configured(self) -> bool:
        """Return True if the gws binary is reachable."""
        import os
        # Absolute path: check directly. Bare name: use which.
        if os.path.isabs(self._bin):
            return os.path.isfile(self._bin) and os.access(self._bin, os.X_OK)
        return shutil.which(self._bin) is not None

    def _build_env(self) -> dict[str, str] | None:
        """Build environment dict for gws subprocess, ensuring auth vars are forwarded."""
        import os

        env = os.environ.copy()
        if self._credentials_file and "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE" not in env:
            env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = self._credentials_file
        return env

    async def run(
        self,
        args: list[str],
        *,
        timeout_s: float = 30.0,
    ) -> tuple[bool, dict[str, Any] | str]:
        """Run a gws command and return (success, parsed_json_or_error_text)."""
        cmd = [self._bin, *args]
        logger.debug(f"gws exec: {' '.join(cmd)}")

        try:
            logger.debug("gws: spawning subprocess...")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
            )
            logger.debug(f"gws: subprocess spawned (pid={proc.pid}), waiting for output...")
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s
            )
            logger.debug(
                f"gws: subprocess completed (rc={proc.returncode}, "
                f"stdout={len(stdout_bytes)}b, stderr={len(stderr_bytes)}b)"
            )
        except asyncio.TimeoutError:
            logger.error(f"gws: TIMEOUT after {timeout_s}s")
            return False, f"gws timed out after {timeout_s}s"
        except FileNotFoundError:
            logger.error("gws: binary not found")
            return False, "gws binary not found. Install: npm i -g @googleworkspace/cli"
        except Exception as e:
            logger.error(f"gws: unexpected error during subprocess: {type(e).__name__}: {e}")
            return False, f"gws subprocess error: {e}"

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            error_msg = stderr or stdout or f"gws exited with code {proc.returncode}"
            logger.warning(f"gws error (rc={proc.returncode}): {error_msg[:300]}")
            return False, error_msg

        # gws outputs structured JSON on success
        if not stdout:
            logger.debug("gws: success with empty output")
            return True, {}

        try:
            parsed = json.loads(stdout)
            logger.debug(f"gws: success, parsed JSON ({len(stdout)} chars)")
            return True, parsed
        except json.JSONDecodeError:
            # Some commands return plain text (e.g. +send confirmation)
            logger.debug(f"gws: success, plain text ({len(stdout)} chars)")
            return True, {"text": stdout}

    async def run_text(
        self,
        args: list[str],
        *,
        timeout_s: float = 30.0,
    ) -> tuple[bool, str]:
        """Run a gws command and return (success, raw_text_output)."""
        cmd = [self._bin, *args]
        logger.debug(f"gws exec (text): {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s
            )
        except asyncio.TimeoutError:
            return False, f"gws timed out after {timeout_s}s"
        except FileNotFoundError:
            return False, "gws binary not found."

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            return False, stderr or stdout or f"exit code {proc.returncode}"
        return True, stdout


# ---------------------------------------------------------------------------
# Helper: build --params JSON flag
# ---------------------------------------------------------------------------


def _params_flag(params: dict[str, Any]) -> list[str]:
    """Build ['--params', '{"key":"val"}'] from dict, dropping None values."""
    clean = {k: v for k, v in params.items() if v is not None}
    if not clean:
        return []
    return ["--params", json.dumps(clean, separators=(",", ":"))]


def _json_flag(body: dict[str, Any]) -> list[str]:
    """Build ['--json', '{"key":"val"}'] from dict."""
    return ["--json", json.dumps(body, separators=(",", ":"))]


def _not_configured_error() -> str:
    return "Error: gws CLI not found. Install: npm i -g @googleworkspace/cli && gws auth setup"


# ===========================================================================
# Gmail Tools
# ===========================================================================


class GmailListThreadsTool(Tool):
    """List Gmail threads."""

    name = "gmail_list_threads"
    description = "List Gmail threads (optional search query)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Gmail search query"},
            "maxResults": {"type": "integer", "description": "Max threads to return"},
        },
        "required": [],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(self, query: str = "", maxResults: int = 20, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return _not_configured_error()

        params: dict[str, Any] = {"userId": "me", "maxResults": maxResults}
        if query:
            params["q"] = query

        ok, data = await self.client.run(
            ["gmail", "users", "threads", "list", *_params_flag(params)]
        )
        if not ok:
            return f"Error: {data}"

        if isinstance(data, str):
            return data

        threads = data.get("threads", []) or []
        if not threads:
            return "No Gmail threads found."

        lines = [f"Found {len(threads)} threads:"]
        for item in threads[:maxResults]:
            snippet = item.get("snippet", "")[:80]
            lines.append(f"- {item.get('id')} | {snippet}")
        return "\n".join(lines)


class GmailReadThreadTool(Tool):
    """Read a Gmail thread."""

    name = "gmail_read_thread"
    description = "Read a Gmail thread by thread ID."
    parameters = {
        "type": "object",
        "properties": {
            "threadId": {"type": "string", "description": "Gmail thread ID"},
        },
        "required": ["threadId"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(self, threadId: str | None = None, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not threadId:
            return "Error: threadId is required."

        ok, data = await self.client.run(
            ["gmail", "users", "threads", "get",
             *_params_flag({"userId": "me", "id": threadId})]
        )
        if not ok:
            return f"Error: {data}"

        if isinstance(data, str):
            return data

        messages = data.get("messages", []) or []
        if not messages:
            return f"Thread {threadId} has no messages."

        lines = [f"Thread {threadId} ({len(messages)} messages):"]
        for msg in messages:
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])
                       if h.get("name") in ("From", "Subject", "Date")}
            lines.append(f"\n--- {headers.get('Date', '?')} ---")
            lines.append(f"From: {headers.get('From', '?')}")
            lines.append(f"Subject: {headers.get('Subject', '?')}")
            # Extract plain text body
            snippet = msg.get("snippet", "")
            if snippet:
                lines.append(snippet[:500])
        return "\n".join(lines)


class GmailSendTool(Tool):
    """Send Gmail message."""

    name = "gmail_send"
    description = "Send email via Gmail API."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body"},
        },
        "required": ["to", "subject", "body"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        to: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not to or not subject or not body:
            return "Error: to, subject, and body are all required."

        ok, result = await self.client.run_text(
            ["gmail", "+send", "--to", to, "--subject", subject, "--body", body]
        )
        if not ok:
            return f"Error sending email: {result}"
        return f"Email sent to {to}. {result}"


class GmailDraftTool(Tool):
    """Create Gmail draft message."""

    name = "gmail_draft"
    description = "Create a Gmail draft via Gmail API."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body"},
        },
        "required": ["to", "subject", "body"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        to: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not to or not subject or not body:
            return "Error: to, subject, and body are all required."

        import base64
        from email.mime.text import MIMEText

        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

        ok, data = await self.client.run(
            ["gmail", "draft", "create", *_json_flag({"message": {"raw": raw}})]
        )
        if not ok:
            return f"Error creating draft: {data}"
        draft_id = data.get("id", "?") if isinstance(data, dict) else "?"
        return f"Draft created (id: {draft_id}). To send it later via web UI."


class GmailReplyTool(Tool):
    """Reply to a Gmail message."""

    name = "gmail_reply"
    description = "Reply to a Gmail message (automatic threading)."
    parameters = {
        "type": "object",
        "properties": {
            "messageId": {"type": "string", "description": "ID of message to reply to"},
            "body": {"type": "string", "description": "Reply content (plain text or html)"},
        },
        "required": ["messageId", "body"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self, messageId: str | None = None, body: str | None = None, **kwargs: Any
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not messageId or not body:
            return "Error: messageId and body are required."

        ok, data = await self.client.run(
            ["gmail", "+reply", "--id", messageId, *_json_flag({"body": body})]
        )
        if not ok:
            return f"Error sending reply: {data}"

        msg_id = data.get("id", "?") if isinstance(data, dict) else "?"
        return f"Reply sent successfully (id: {msg_id})."


class GmailReplyAllTool(Tool):
    """Reply-all to a Gmail message."""

    name = "gmail_reply_all"
    description = "Reply-all to a Gmail message."
    parameters = {
        "type": "object",
        "properties": {
            "messageId": {"type": "string", "description": "ID of message to reply to"},
            "body": {"type": "string", "description": "Reply content (plain text or html)"},
            "remove": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Email addresses to remove from CC",
            },
            "cc": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional email addresses to CC",
            },
        },
        "required": ["messageId", "body"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        messageId: str | None = None,
        body: str | None = None,
        remove: list[str] | None = None,
        cc: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not messageId or not body:
            return "Error: messageId and body are required."

        req_body: dict[str, Any] = {"body": body}
        if remove:
            req_body["remove"] = remove
        if cc:
            req_body["cc"] = cc

        ok, data = await self.client.run(
            ["gmail", "+reply-all", "--id", messageId, *_json_flag(req_body)]
        )
        if not ok:
            return f"Error sending reply-all: {data}"

        msg_id = data.get("id", "?") if isinstance(data, dict) else "?"
        return f"Reply-all sent successfully (id: {msg_id})."


class GmailForwardTool(Tool):
    """Forward a Gmail message."""

    name = "gmail_forward"
    description = "Forward a Gmail message to new recipients."
    parameters = {
        "type": "object",
        "properties": {
            "messageId": {"type": "string", "description": "ID of message to forward"},
            "to": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Forward recipients",
            },
            "body": {
                "type": "string",
                "description": "Optional message body to prepend to the forwarded content",
            },
        },
        "required": ["messageId", "to"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        messageId: str | None = None,
        to: list[str] | None = None,
        body: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not messageId or not to:
            return "Error: messageId and to are required."

        req_body: dict[str, Any] = {"to": to}
        if body:
            req_body["body"] = body

        ok, data = await self.client.run(
            ["gmail", "+forward", "--id", messageId, *_json_flag(req_body)]
        )
        if not ok:
            return f"Error forwarding message: {data}"

        msg_id = data.get("id", "?") if isinstance(data, dict) else "?"
        return f"Message forwarded successfully (id: {msg_id})."


# ===========================================================================
# Calendar Tools
# ===========================================================================


class CalendarListEventsTool(Tool):
    """List Google Calendar events."""

    name = "calendar_list_events"
    description = "List upcoming Google Calendar events."
    parameters = {
        "type": "object",
        "properties": {
            "calendarId": {"type": "string", "description": "Calendar ID (default: primary)"},
            "timeMin": {"type": "string", "description": "Filter: start >= ISO-8601 timestamp"},
            "timeMax": {"type": "string", "description": "Filter: start < ISO-8601 timestamp"},
            "maxResults": {"type": "integer", "description": "Max events"},
        },
        "required": [],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        calendarId: str | None = None,
        timeMin: str | None = None,
        timeMax: str | None = None,
        maxResults: int = 20,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()

        from datetime import datetime, timezone

        cal_id = calendarId or self.client.calendar_id or "primary"
        params: dict[str, Any] = {
            "calendarId": cal_id,
            "singleEvents": True,
            "orderBy": "startTime",
            "timeMin": timeMin or datetime.now(timezone.utc).isoformat(),
            "maxResults": maxResults,
        }
        if timeMax:
            params["timeMax"] = timeMax

        ok, data = await self.client.run(
            ["calendar", "events", "list", *_params_flag(params)]
        )
        if not ok:
            return f"Error: {data}"

        if isinstance(data, str):
            return data

        items = data.get("items", []) or []
        if not items:
            return "No calendar events found."

        lines = [f"Upcoming events ({len(items)}):"]
        for event in items[:maxResults]:
            start = (event.get("start", {}).get("dateTime")
                     or event.get("start", {}).get("date", ""))
            lines.append(f"- {start} | {event.get('summary', '(no title)')}")
        return "\n".join(lines)


class CalendarCreateEventTool(Tool):
    """Create Google Calendar event."""

    name = "calendar_create_event"
    description = "Create a Google Calendar event."
    parameters = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Event title"},
            "start": {"type": "string", "description": "Start datetime ISO-8601"},
            "end": {"type": "string", "description": "End datetime ISO-8601"},
            "timeZone": {"type": "string", "description": "Timezone (e.g. Asia/Jakarta)"},
            "description": {"type": "string", "description": "Event description"},
            "location": {"type": "string", "description": "Event location"},
            "calendarId": {"type": "string", "description": "Calendar ID"},
        },
        "required": ["summary", "start", "end"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        summary: str | None = None,
        start: str | None = None,
        end: str | None = None,
        timeZone: str = "UTC",
        description: str = "",
        location: str = "",
        calendarId: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not summary or not start or not end:
            return "Error: summary, start, and end are required."

        cal_id = calendarId or self.client.calendar_id or "primary"
        body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start, "timeZone": timeZone},
            "end": {"dateTime": end, "timeZone": timeZone},
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location

        ok, data = await self.client.run(
            ["calendar", "events", "insert",
             *_params_flag({"calendarId": cal_id}),
             *_json_flag(body)]
        )
        if not ok:
            return f"Error creating event: {data}"

        event_id = data.get("id", "?") if isinstance(data, dict) else "?"
        html_link = data.get("htmlLink", "") if isinstance(data, dict) else ""
        return f"Event created: {summary} (id: {event_id})\n{html_link}"


class CalendarUpdateEventTool(Tool):
    """Update Google Calendar event."""

    name = "calendar_update_event"
    description = "Update an existing Google Calendar event."
    parameters = {
        "type": "object",
        "properties": {
            "eventId": {"type": "string", "description": "Event ID to update"},
            "calendarId": {"type": "string", "description": "Calendar ID"},
            "summary": {"type": "string", "description": "New event title"},
            "start": {"type": "string", "description": "New start ISO-8601"},
            "end": {"type": "string", "description": "New end ISO-8601"},
            "timeZone": {"type": "string", "description": "Timezone"},
            "description": {"type": "string", "description": "New description"},
            "location": {"type": "string", "description": "New location"},
        },
        "required": ["eventId"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        eventId: str | None = None,
        calendarId: str | None = None,
        summary: str | None = None,
        start: str | None = None,
        end: str | None = None,
        timeZone: str = "UTC",
        description: str | None = None,
        location: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not eventId:
            return "Error: eventId is required."

        cal_id = calendarId or self.client.calendar_id or "primary"
        body: dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if start is not None:
            body["start"] = {"dateTime": start, "timeZone": timeZone}
        if end is not None:
            body["end"] = {"dateTime": end, "timeZone": timeZone}
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location

        if not body:
            return "Error: at least one field to update is required."

        ok, data = await self.client.run(
            ["calendar", "events", "patch",
             *_params_flag({"calendarId": cal_id, "eventId": eventId}),
             *_json_flag(body)]
        )
        if not ok:
            return f"Error updating event: {data}"
        return f"Event {eventId} updated."


# ===========================================================================
# Drive Tools
# ===========================================================================


class DriveListFilesTool(Tool):
    """List Google Drive files."""

    name = "drive_list_files"
    description = "List files in Google Drive (optional search query)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Drive search query"},
            "pageSize": {"type": "integer", "description": "Max files to return"},
        },
        "required": [],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(self, query: str = "", pageSize: int = 20, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return _not_configured_error()

        params: dict[str, Any] = {"pageSize": pageSize}
        if query:
            params["q"] = query

        ok, data = await self.client.run(
            ["drive", "files", "list", *_params_flag(params)]
        )
        if not ok:
            return f"Error: {data}"

        if isinstance(data, str):
            return data

        files = data.get("files", []) or []
        if not files:
            return "No Drive files found."

        lines = [f"Found {len(files)} files:"]
        for f in files[:pageSize]:
            lines.append(f"- {f.get('id')} | {f.get('name', '?')} ({f.get('mimeType', '?')})")
        return "\n".join(lines)


class DriveReadTextTool(Tool):
    """Read text content from a Google Drive file."""

    name = "drive_read_text"
    description = "Read text content from a Drive file by file ID."
    parameters = {
        "type": "object",
        "properties": {
            "fileId": {"type": "string", "description": "Drive file ID"},
            "maxChars": {"type": "integer", "description": "Max characters to return"},
        },
        "required": ["fileId"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(self, fileId: str | None = None, maxChars: int = 8000, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not fileId:
            return "Error: fileId is required."

        # First get file metadata to determine type
        ok, meta = await self.client.run(
            ["drive", "files", "get", *_params_flag({"fileId": fileId, "fields": "mimeType,name"})]
        )
        if not ok:
            return f"Error: {meta}"

        mime = meta.get("mimeType", "") if isinstance(meta, dict) else ""
        name = meta.get("name", fileId) if isinstance(meta, dict) else fileId

        # Google Docs types need export, others use direct download
        export_map = {
            "application/vnd.google-apps.document": "text/plain",
            "application/vnd.google-apps.spreadsheet": "text/csv",
            "application/vnd.google-apps.presentation": "text/plain",
        }

        if mime in export_map:
            ok, text = await self.client.run_text(
                ["drive", "files", "export",
                 *_params_flag({"fileId": fileId, "mimeType": export_map[mime]})]
            )
        else:
            # Direct download (text files)
            ok, text = await self.client.run_text(
                ["drive", "files", "get",
                 *_params_flag({"fileId": fileId, "alt": "media"})]
            )

        if not ok:
            return f"Error reading {name}: {text}"

        content = text[:maxChars]
        suffix = f"\n... (truncated, {len(text)} total chars)" if len(text) > maxChars else ""
        return f"Content of '{name}':\n{content}{suffix}"


# ===========================================================================
# Docs Tools
# ===========================================================================


class DocsGetDocumentTool(Tool):
    """Read a Google Docs document by ID."""

    name = "docs_get_document"
    description = "Get text content from Google Docs by document ID."
    parameters = {
        "type": "object",
        "properties": {
            "documentId": {"type": "string", "description": "Google Docs document ID"},
        },
        "required": ["documentId"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self, documentId: str | None = None, maxChars: int = 8000, **kwargs: Any
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not documentId:
            return "Error: documentId is required."

        ok, data = await self.client.run(
            ["docs", "documents", "get", *_params_flag({"documentId": documentId})]
        )
        if not ok:
            return f"Error: {data}"

        if isinstance(data, str):
            return data

        title = data.get("title", "Untitled")
        # Extract text from document body
        text = _extract_doc_text(data, maxChars)
        return f"Document: {title}\n\n{text}"


def _extract_doc_text(data: dict[str, Any], max_chars: int = 8000) -> str:
    """Extract plain text from Google Docs API structure."""
    body = data.get("body", {})
    content = body.get("content", [])
    parts: list[str] = []
    total = 0
    for element in content:
        para = element.get("paragraph", {})
        for elem in para.get("elements", []):
            text_run = elem.get("textRun", {})
            text = text_run.get("content", "")
            if text:
                remaining = max_chars - total
                if remaining <= 0:
                    break
                parts.append(text[:remaining])
                total += len(text)
        if total >= max_chars:
            break
    result = "".join(parts)
    if total > max_chars:
        result += "\n... (truncated)"
    return result


class DocsAppendTextTool(Tool):
    """Append text to a Google Docs document."""

    name = "docs_append_text"
    description = "Append text to the end of a Google Docs document."
    parameters = {
        "type": "object",
        "properties": {
            "documentId": {"type": "string", "description": "Google Docs document ID"},
            "text": {"type": "string", "description": "Text to append"},
            "ensureNewline": {
                "type": "boolean",
                "description": "Add newline before text if needed",
            },
        },
        "required": ["documentId", "text"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        documentId: str | None = None,
        text: str | None = None,
        ensureNewline: bool = True,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not documentId or not text:
            return "Error: documentId and text are required."

        # Get doc to find end index
        ok, doc = await self.client.run(
            ["docs", "documents", "get", *_params_flag({"documentId": documentId})]
        )
        if not ok:
            return f"Error fetching document: {doc}"

        if not isinstance(doc, dict):
            return f"Error: unexpected response: {doc}"

        body = doc.get("body", {})
        content = body.get("content", [])
        end_index = 1
        if content:
            last = content[-1]
            end_index = last.get("endIndex", 1) - 1
        end_index = max(end_index, 1)

        insert_text = f"\n{text}" if ensureNewline else text

        requests_body = {
            "requests": [
                {
                    "insertText": {
                        "location": {"index": end_index},
                        "text": insert_text,
                    }
                }
            ]
        }

        ok, result = await self.client.run(
            ["docs", "documents", "batchUpdate",
             *_params_flag({"documentId": documentId}),
             *_json_flag(requests_body)]
        )
        if not ok:
            return f"Error appending text: {result}"
        return f"Appended {len(text)} chars to document."


# ===========================================================================
# Sheets Tools
# ===========================================================================


class SheetsGetValuesTool(Tool):
    """Read values from Google Sheets range."""

    name = "sheets_get_values"
    description = "Get values from a Google Sheets range."
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheetId": {"type": "string", "description": "Spreadsheet ID"},
            "rangeA1": {"type": "string", "description": "A1 range notation (e.g. Sheet1!A1:D10)"},
        },
        "required": ["spreadsheetId", "rangeA1"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        spreadsheetId: str | None = None,
        rangeA1: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not spreadsheetId or not rangeA1:
            return "Error: spreadsheetId and rangeA1 are required."

        ok, data = await self.client.run(
            ["sheets", "spreadsheets.values", "get",
             *_params_flag({"spreadsheetId": spreadsheetId, "range": rangeA1})]
        )
        if not ok:
            return f"Error: {data}"

        if isinstance(data, str):
            return data

        values = data.get("values", [])
        if not values:
            return f"No values in {rangeA1}."

        lines = [f"Values from {rangeA1} ({len(values)} rows):"]
        for row in values[:50]:  # Cap at 50 rows for output
            lines.append(" | ".join(str(c) for c in row))
        if len(values) > 50:
            lines.append(f"... ({len(values) - 50} more rows)")
        return "\n".join(lines)


class SheetsAppendValuesTool(Tool):
    """Append rows to Google Sheets."""

    name = "sheets_append_values"
    description = "Append rows to a Google Sheets range."
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheetId": {"type": "string", "description": "Spreadsheet ID"},
            "rangeA1": {"type": "string", "description": "A1 range (e.g. Sheet1!A:D)"},
            "rows": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
                "description": "Rows to append (2D array)",
            },
            "valueInputOption": {
                "type": "string",
                "description": "How to interpret values: RAW or USER_ENTERED",
            },
        },
        "required": ["spreadsheetId", "rangeA1", "rows"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(
        self,
        spreadsheetId: str | None = None,
        rangeA1: str | None = None,
        rows: list[list[str]] | None = None,
        valueInputOption: str = "USER_ENTERED",
        **kwargs: Any,
    ) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not spreadsheetId or not rangeA1 or not rows:
            return "Error: spreadsheetId, rangeA1, and rows are required."

        ok, data = await self.client.run(
            ["sheets", "spreadsheets.values", "append",
             *_params_flag({
                 "spreadsheetId": spreadsheetId,
                 "range": rangeA1,
                 "valueInputOption": valueInputOption,
             }),
             *_json_flag({"values": rows})]
        )
        if not ok:
            return f"Error: {data}"

        updates = data.get("updates", {}) if isinstance(data, dict) else {}
        updated_rows = updates.get("updatedRows", len(rows))
        return f"Appended {updated_rows} rows to {rangeA1}."


# ===========================================================================
# Contacts Tools
# ===========================================================================


def _format_person_line(person: dict[str, Any]) -> str:
    """Format People API person object into compact text."""
    names = person.get("names", [])
    name = names[0].get("displayName", "?") if names else "?"

    emails = person.get("emailAddresses", [])
    email = emails[0].get("value", "") if emails else ""

    phones = person.get("phoneNumbers", [])
    phone = phones[0].get("value", "") if phones else ""

    resource = person.get("resourceName", "")

    parts = [name]
    if email:
        parts.append(f"<{email}>")
    if phone:
        parts.append(phone)
    parts.append(f"[{resource}]")
    return " | ".join(parts)


class ContactsListTool(Tool):
    """List Google Contacts entries."""

    name = "contacts_list"
    description = "List Google contacts (optionally search by query)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "pageSize": {"type": "integer", "description": "Max results"},
        },
        "required": [],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(self, query: str = "", pageSize: int = 20, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return _not_configured_error()

        if query:
            # Use searchContacts for query
            ok, data = await self.client.run(
                ["people", "people", "searchContacts",
                 *_params_flag({
                     "query": query,
                     "readMask": "names,emailAddresses,phoneNumbers",
                     "pageSize": pageSize,
                 })]
            )
            if not ok:
                return f"Error: {data}"
            results = data.get("results", []) if isinstance(data, dict) else []
            people = [r.get("person", {}) for r in results]
        else:
            ok, data = await self.client.run(
                ["people", "people.connections", "list",
                 *_params_flag({
                     "resourceName": "people/me",
                     "personFields": "names,emailAddresses,phoneNumbers",
                     "pageSize": pageSize,
                 })]
            )
            if not ok:
                return f"Error: {data}"
            people = data.get("connections", []) if isinstance(data, dict) else []

        if not people:
            return "No contacts found."

        lines = [f"Contacts ({len(people)}):"]
        for p in people[:pageSize]:
            lines.append(f"- {_format_person_line(p)}")
        return "\n".join(lines)


class ContactsGetTool(Tool):
    """Get single Google contact details."""

    name = "contacts_get"
    description = "Get Google contact detail by resource name (e.g. people/c123)."
    parameters = {
        "type": "object",
        "properties": {
            "resourceName": {"type": "string", "description": "people/cXXX resource name"},
        },
        "required": ["resourceName"],
    }

    def __init__(self, client: GwsClient):
        self.client = client

    async def execute(self, resourceName: str | None = None, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return _not_configured_error()
        if not resourceName:
            return "Error: resourceName is required."

        ok, data = await self.client.run(
            ["people", "people", "get",
             *_params_flag({
                 "resourceName": resourceName,
                 "personFields": "names,emailAddresses,phoneNumbers,organizations,biographies",
             })]
        )
        if not ok:
            return f"Error: {data}"

        if isinstance(data, str):
            return data

        lines = [_format_person_line(data)]

        orgs = data.get("organizations", [])
        if orgs:
            org = orgs[0]
            lines.append(f"Org: {org.get('name', '?')} — {org.get('title', '?')}")

        bios = data.get("biographies", [])
        if bios:
            lines.append(f"Bio: {bios[0].get('value', '')[:200]}")

        return "\n".join(lines)
