"""Google Workspace tools (Gmail/Calendar/Drive/Docs/Sheets/Contacts) via REST API."""

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from g_agent.agent.tools.base import Tool


def _env(name: str, default: str = "") -> str:
    """Read env var with G_AGENT_ prefix."""
    key = name.strip().upper()
    return os.environ.get(f"G_AGENT_{key}", default)


def _extract_google_error_reason(payload: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Extract message/status/reasons from Google error payload."""
    error_obj = payload.get("error")
    if isinstance(error_obj, str):
        return error_obj.strip(), "", []
    if not isinstance(error_obj, dict):
        return "", "", []

    message = str(error_obj.get("message", "")).strip()
    status = str(error_obj.get("status", "")).strip()
    reasons: list[str] = []
    details = error_obj.get("details", [])
    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason", "")).strip()
            if reason:
                reasons.append(reason)
    return message, status, reasons


def _is_scope_error(status_code: int, payload: dict[str, Any]) -> bool:
    """Return True when Google response indicates OAuth scope mismatch."""
    if status_code != 403:
        return False
    message, status, reasons = _extract_google_error_reason(payload)
    combined = " ".join([message, status, *reasons]).lower()
    scope_markers = [
        "access_token_scope_insufficient",
        "insufficient authentication scopes",
        "insufficientpermissions",
    ]
    if any(marker in combined for marker in scope_markers):
        return True
    return "scope" in combined and "insufficient" in combined


def _format_refresh_error(response: httpx.Response) -> str:
    """Build actionable token refresh error message."""
    payload: dict[str, Any] = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            payload = parsed
    except (json.JSONDecodeError, ValueError):
        payload = {}

    error = str(payload.get("error", "")).strip().lower()
    description = str(payload.get("error_description", "")).strip()
    if error == "invalid_grant":
        return (
            "Token refresh failed: refresh token expired or revoked (invalid_grant). "
            "Run `g-agent google auth-url` then `g-agent google exchange --code ...`."
        )

    detail = description or str(payload.get("error", "")).strip()
    if detail:
        return f"Token refresh failed (HTTP {response.status_code}): {detail}"
    return f"Token refresh failed (HTTP {response.status_code})"


def _format_google_api_error(status_code: int, payload: dict[str, Any]) -> str:
    """Build readable error text from Google API payload."""
    if _is_scope_error(status_code, payload):
        return (
            "Google API scope mismatch (insufficient scopes). "
            "Run `g-agent google auth-url` with required scopes and "
            "`g-agent google exchange --code ...`."
        )

    message, _, _ = _extract_google_error_reason(payload)
    if message:
        return f"Google API error (HTTP {status_code}): {message}"

    raw_error = payload.get("error")
    if isinstance(raw_error, str) and raw_error.strip():
        return f"Google API error (HTTP {status_code}): {raw_error.strip()}"
    return f"HTTP {status_code}"


class GoogleWorkspaceClient:
    """Minimal Google Workspace REST client with token refresh."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        refresh_token: str = "",
        access_token: str = "",
        calendar_id: str = "primary",
    ):
        self.client_id = client_id or _env("GOOGLE_CLIENT_ID", "")
        self.client_secret = client_secret or _env("GOOGLE_CLIENT_SECRET", "")
        self.refresh_token = refresh_token or _env("GOOGLE_REFRESH_TOKEN", "")
        self.access_token = access_token or _env("GOOGLE_ACCESS_TOKEN", "")
        self.calendar_id = calendar_id or _env("GOOGLE_CALENDAR_ID", "primary")

        self._cached_token = self.access_token
        if self._can_refresh():
            # Access token from config/env may be stale; force refresh on first use.
            self._token_expiry = datetime.now(timezone.utc)
        elif self.access_token:
            self._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        else:
            self._token_expiry = None

    def is_configured(self) -> bool:
        """Return True if at least one workable auth path exists."""
        if self._cached_token:
            return True
        return self._can_refresh()

    def _can_refresh(self) -> bool:
        """Return True when refresh token credentials are complete."""
        return bool(self.client_id and self.client_secret and self.refresh_token)

    async def _ensure_token(self, force_refresh: bool = False) -> tuple[bool, str]:
        """Ensure a valid access token is available."""
        now = datetime.now(timezone.utc)
        if (
            not force_refresh
            and self._cached_token
            and self._token_expiry
            and self._token_expiry > now + timedelta(seconds=30)
        ):
            return True, self._cached_token

        if not self._can_refresh():
            if self._cached_token:
                return True, self._cached_token
            return False, "Google credentials not configured."

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": self.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
            if response.status_code != 200:
                return False, _format_refresh_error(response)
            data = response.json()
            token = data.get("access_token", "")
            if not token:
                return False, "Token refresh failed: no access_token"
            expires_in = int(data.get("expires_in", 3600))
            self._cached_token = token
            self._token_expiry = now + timedelta(seconds=max(60, expires_in - 30))
            return True, token
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
            return False, str(e)

    async def request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Perform authenticated request to Google APIs."""
        ok, token_or_error = await self._ensure_token()
        if not ok:
            return False, {"error": token_or_error}
        token = token_or_error

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                for attempt in range(2):
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        params=params,
                        json=json_body,
                        headers={"Authorization": f"Bearer {token}"},
                    )

                    payload = {}
                    try:
                        payload = response.json()
                    except json.JSONDecodeError:
                        payload = {"raw": response.text}

                    if response.status_code == 401 and attempt == 0 and self._can_refresh():
                        refreshed, refreshed_or_error = await self._ensure_token(force_refresh=True)
                        if not refreshed:
                            return False, {"error": refreshed_or_error}
                        token = refreshed_or_error
                        continue

                    if response.status_code >= 400:
                        if isinstance(payload.get("error"), dict):
                            payload["google_error"] = payload.get("error")
                        payload["error"] = _format_google_api_error(response.status_code, payload)
                        return False, payload

                    return True, payload

            return False, {"error": "Google API request failed without response."}
        except httpx.HTTPError as e:
            return False, {"error": str(e)}


class GmailListThreadsTool(Tool):
    """List Gmail threads."""

    name = "gmail_list_threads"
    description = "List Gmail threads (optional search query)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Gmail search query"},
            "maxResults": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "required": [],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(self, query: str = "", maxResults: int = 20, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."
        ok, data = await self.client.request(
            "GET",
            "https://gmail.googleapis.com/gmail/v1/users/me/threads",
            params={"q": query, "maxResults": maxResults},
        )
        if not ok:
            return f"Error: {data.get('error', data)}"
        threads = data.get("threads", []) or []
        if not threads:
            return "No Gmail threads found."
        lines = [f"Found {len(threads)} threads:"]
        for item in threads[:maxResults]:
            lines.append(f"- {item.get('id')}")
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

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(self, threadId: str | None = None, **kwargs: Any) -> str:
        thread_id = (threadId or "").strip()
        if not thread_id:
            return "Error: threadId is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."
        ok, data = await self.client.request(
            "GET",
            f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}",
            params={"format": "metadata"},
        )
        if not ok:
            return f"Error: {data.get('error', data)}"

        messages = data.get("messages", []) or []
        lines = [f"Thread {thread_id} ({len(messages)} messages):"]
        for msg in messages[:20]:
            headers = msg.get("payload", {}).get("headers", []) or []
            hdr = {h.get("name", "").lower(): h.get("value", "") for h in headers}
            lines.append(
                f"- {hdr.get('date', '')} | from: {hdr.get('from', '')} | subject: {hdr.get('subject', '')}"
            )
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
            "body": {"type": "string", "description": "Email plain text body"},
        },
        "required": ["to", "subject", "body"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(
        self,
        to: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        **kwargs: Any,
    ) -> str:
        to_addr = (to or "").strip()
        subject_text = (subject or "").strip()
        if not to_addr:
            return "Error: to is required."
        if not subject_text:
            return "Error: subject is required."
        if body is None:
            return "Error: body is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        raw = f"To: {to_addr}\r\nSubject: {subject_text}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
        raw_b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8").rstrip("=")
        ok, data = await self.client.request(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            json_body={"raw": raw_b64},
        )
        if not ok:
            return f"Error: {data.get('error', data)}"
        return f"Gmail message sent (id: {data.get('id', 'unknown')})"


class GmailDraftTool(Tool):
    """Create Gmail draft message."""

    name = "gmail_draft"
    description = "Create a Gmail draft via Gmail API."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email plain text body"},
        },
        "required": ["to", "subject", "body"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(
        self,
        to: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        **kwargs: Any,
    ) -> str:
        to_addr = (to or "").strip()
        subject_text = (subject or "").strip()
        if not to_addr:
            return "Error: to is required."
        if not subject_text:
            return "Error: subject is required."
        if body is None:
            return "Error: body is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        raw = f"To: {to_addr}\r\nSubject: {subject_text}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
        raw_b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8").rstrip("=")
        ok, data = await self.client.request(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            json_body={"message": {"raw": raw_b64}},
        )
        if not ok:
            return f"Error: {data.get('error', data)}"
        draft_id = (data.get("id") or data.get("draft", {}).get("id") or "unknown")
        return f"Gmail draft created (id: {draft_id})"


class CalendarListEventsTool(Tool):
    """List Google Calendar events."""

    name = "calendar_list_events"
    description = "List upcoming Google Calendar events."
    parameters = {
        "type": "object",
        "properties": {
            "calendarId": {"type": "string", "description": "Calendar ID (default primary)"},
            "timeMin": {"type": "string", "description": "ISO start time"},
            "timeMax": {"type": "string", "description": "ISO end time"},
            "maxResults": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "required": [],
    }

    def __init__(self, client: GoogleWorkspaceClient):
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
            return "Error: Google Workspace not configured."

        cal_id = calendarId or self.client.calendar_id or "primary"
        now_iso = datetime.now(timezone.utc).isoformat()
        params = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": timeMin or now_iso,
            "maxResults": maxResults,
        }
        if timeMax:
            params["timeMax"] = timeMax

        ok, data = await self.client.request(
            "GET",
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(cal_id, safe='')}/events",
            params=params,
        )
        if not ok:
            return f"Error: {data.get('error', data)}"

        items = data.get("items", []) or []
        if not items:
            return "No calendar events found."

        lines = [f"Upcoming events ({len(items)}):"]
        for event in items[:maxResults]:
            start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")
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
            "start": {"type": "string", "description": "Start datetime ISO"},
            "end": {"type": "string", "description": "End datetime ISO"},
            "timeZone": {"type": "string", "description": "Timezone", "default": "UTC"},
            "description": {"type": "string", "description": "Event description"},
            "location": {"type": "string", "description": "Event location"},
            "calendarId": {"type": "string", "description": "Calendar ID (default primary)"},
        },
        "required": ["summary", "start", "end"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
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
        summary_text = (summary or "").strip()
        start_text = (start or "").strip()
        end_text = (end or "").strip()
        if not summary_text:
            return "Error: summary is required."
        if not start_text:
            return "Error: start is required."
        if not end_text:
            return "Error: end is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        cal_id = calendarId or self.client.calendar_id or "primary"
        body = {
            "summary": summary_text,
            "description": description,
            "location": location,
            "start": {"dateTime": start_text, "timeZone": timeZone},
            "end": {"dateTime": end_text, "timeZone": timeZone},
        }
        ok, data = await self.client.request(
            "POST",
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(cal_id, safe='')}/events",
            json_body=body,
        )
        if not ok:
            return f"Error: {data.get('error', data)}"
        return json.dumps(
            {
                "ok": True,
                "id": data.get("id"),
                "htmlLink": data.get("htmlLink"),
                "summary": data.get("summary"),
            }
        )


class CalendarUpdateEventTool(Tool):
    """Update Google Calendar event."""

    name = "calendar_update_event"
    description = "Update an existing Google Calendar event."
    parameters = {
        "type": "object",
        "properties": {
            "eventId": {"type": "string", "description": "Event ID"},
            "calendarId": {"type": "string", "description": "Calendar ID (default primary)"},
            "summary": {"type": "string", "description": "Event title"},
            "start": {"type": "string", "description": "Start datetime ISO"},
            "end": {"type": "string", "description": "End datetime ISO"},
            "timeZone": {"type": "string", "description": "Timezone", "default": "UTC"},
            "description": {"type": "string", "description": "Event description"},
            "location": {"type": "string", "description": "Event location"},
        },
        "required": ["eventId"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
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
        event_id = (eventId or "").strip()
        if not event_id:
            return "Error: eventId is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        body: dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location
        if start:
            body["start"] = {"dateTime": start, "timeZone": timeZone}
        if end:
            body["end"] = {"dateTime": end, "timeZone": timeZone}
        if not body:
            return "Error: no update fields provided."

        cal_id = calendarId or self.client.calendar_id or "primary"
        ok, data = await self.client.request(
            "PATCH",
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(cal_id, safe='')}/events/{quote(event_id, safe='')}",
            json_body=body,
        )
        if not ok:
            return f"Error: {data.get('error', data)}"
        return json.dumps(
            {
                "ok": True,
                "id": data.get("id"),
                "htmlLink": data.get("htmlLink"),
                "summary": data.get("summary"),
            }
        )


class DriveListFilesTool(Tool):
    """List Google Drive files."""

    name = "drive_list_files"
    description = "List files in Google Drive (optional search query)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Drive search query (q param)"},
            "pageSize": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "required": [],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(self, query: str = "", pageSize: int = 20, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        params = {
            "pageSize": pageSize,
            "q": query or None,
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink)",
            "orderBy": "modifiedTime desc",
        }
        ok, data = await self.client.request(
            "GET",
            "https://www.googleapis.com/drive/v3/files",
            params=params,
        )
        if not ok:
            return f"Error: {data.get('error', data)}"

        files = data.get("files", []) or []
        if not files:
            return "No Drive files found."
        lines = [f"Drive files ({len(files)}):"]
        for item in files[:pageSize]:
            lines.append(
                f"- {item.get('name', '(no name)')} | id: {item.get('id')} | mime: {item.get('mimeType', '')}"
            )
        return "\n".join(lines)


class DriveReadTextTool(Tool):
    """Read text content from a Google Drive file."""

    name = "drive_read_text"
    description = "Read text content from a Drive file by file ID."
    parameters = {
        "type": "object",
        "properties": {
            "fileId": {"type": "string", "description": "Google Drive file ID"},
            "maxChars": {"type": "integer", "minimum": 100, "maximum": 50000, "default": 8000},
        },
        "required": ["fileId"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(self, fileId: str | None = None, maxChars: int = 8000, **kwargs: Any) -> str:
        file_id = (fileId or "").strip()
        if not file_id:
            return "Error: fileId is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        ok_meta, meta = await self.client.request(
            "GET",
            f"https://www.googleapis.com/drive/v3/files/{quote(file_id, safe='')}",
            params={"fields": "id,name,mimeType,webViewLink"},
        )
        if not ok_meta:
            return f"Error: {meta.get('error', meta)}"

        mime = str(meta.get("mimeType", ""))
        file_name = str(meta.get("name", "(unknown)"))
        token_ok, token_or_err = await self.client._ensure_token()
        if not token_ok:
            return f"Error: {token_or_err}"
        token = token_or_err

        if mime == "application/vnd.google-apps.document":
            url = (
                f"https://www.googleapis.com/drive/v3/files/{quote(file_id, safe='')}/export"
                "?mimeType=text/plain"
            )
        else:
            url = f"https://www.googleapis.com/drive/v3/files/{quote(file_id, safe='')}?alt=media"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            if response.status_code >= 400:
                return f"Error: HTTP {response.status_code} while reading file."
            text = response.text or ""
            compact = text[:maxChars]
            if len(text) > maxChars:
                compact += "\n...[truncated]..."
            return f"File: {file_name}\nMime: {mime}\n\n{compact}"
        except httpx.HTTPError as e:
            return f"Error: {e}"


def _extract_doc_text(data: dict[str, Any], max_chars: int = 8000) -> str:
    """Extract plain text from Google Docs API structure."""
    body = data.get("body", {}) if isinstance(data, dict) else {}
    content = body.get("content", []) if isinstance(body, dict) else []
    pieces: list[str] = []
    for node in content:
        para = node.get("paragraph") if isinstance(node, dict) else None
        if not para:
            continue
        elements = para.get("elements", []) if isinstance(para, dict) else []
        for element in elements:
            text_run = element.get("textRun") if isinstance(element, dict) else None
            if not text_run:
                continue
            text = str(text_run.get("content", ""))
            if text:
                pieces.append(text)
    joined = "".join(pieces).strip()
    if len(joined) > max_chars:
        return joined[:max_chars] + "\n...[truncated]..."
    return joined


class DocsGetDocumentTool(Tool):
    """Read a Google Docs document by ID."""

    name = "docs_get_document"
    description = "Get text content from Google Docs by document ID."
    parameters = {
        "type": "object",
        "properties": {
            "documentId": {"type": "string", "description": "Google Docs document ID"},
            "maxChars": {"type": "integer", "minimum": 100, "maximum": 50000, "default": 8000},
        },
        "required": ["documentId"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(self, documentId: str | None = None, maxChars: int = 8000, **kwargs: Any) -> str:
        document_id = (documentId or "").strip()
        if not document_id:
            return "Error: documentId is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        ok, data = await self.client.request(
            "GET",
            f"https://docs.googleapis.com/v1/documents/{quote(document_id, safe='')}",
        )
        if not ok:
            return f"Error: {data.get('error', data)}"
        title = str(data.get("title", "(untitled)"))
        text = _extract_doc_text(data, max_chars=maxChars)
        if not text:
            text = "(No readable text content found.)"
        return f"Document: {title}\n\n{text}"


class SheetsGetValuesTool(Tool):
    """Read values from Google Sheets range."""

    name = "sheets_get_values"
    description = "Get values from a Google Sheets range."
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheetId": {"type": "string", "description": "Google Sheets spreadsheet ID"},
            "rangeA1": {"type": "string", "description": "A1 notation range (e.g. Sheet1!A1:C20)"},
        },
        "required": ["spreadsheetId", "rangeA1"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(
        self,
        spreadsheetId: str | None = None,
        rangeA1: str | None = None,
        **kwargs: Any,
    ) -> str:
        spreadsheet_id = (spreadsheetId or "").strip()
        range_a1 = (rangeA1 or "").strip()
        if not spreadsheet_id:
            return "Error: spreadsheetId is required."
        if not range_a1:
            return "Error: rangeA1 is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        ok, data = await self.client.request(
            "GET",
            f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{quote(range_a1, safe='')}",
        )
        if not ok:
            return f"Error: {data.get('error', data)}"

        values = data.get("values", []) or []
        if not values:
            return "No values found."
        rows = ["\t".join(str(cell) for cell in row) for row in values]
        preview = "\n".join(rows[:200])
        return f"Range: {data.get('range', range_a1)}\nRows: {len(values)}\n\n{preview}"


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
                "description": "Append newline before text when needed",
                "default": True,
            },
        },
        "required": ["documentId", "text"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(
        self,
        documentId: str | None = None,
        text: str | None = None,
        ensureNewline: bool = True,
        **kwargs: Any,
    ) -> str:
        document_id = (documentId or "").strip()
        if not document_id:
            return "Error: documentId is required."
        if text is None:
            return "Error: text is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        append_text = text
        if ensureNewline and append_text and not append_text.startswith("\n"):
            append_text = "\n" + append_text

        body = {
            "requests": [
                {
                    "insertText": {
                        "endOfSegmentLocation": {},
                        "text": append_text,
                    }
                }
            ]
        }
        ok, data = await self.client.request(
            "POST",
            f"https://docs.googleapis.com/v1/documents/{quote(document_id, safe='')}:batchUpdate",
            json_body=body,
        )
        if not ok:
            return f"Error: {data.get('error', data)}"
        return json.dumps(
            {
                "ok": True,
                "documentId": document_id,
                "replyCount": len(data.get("replies", []) or []),
            }
        )


class SheetsAppendValuesTool(Tool):
    """Append rows to Google Sheets."""

    name = "sheets_append_values"
    description = "Append rows to a Google Sheets range."
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheetId": {"type": "string", "description": "Google Sheets spreadsheet ID"},
            "rangeA1": {"type": "string", "description": "A1 notation range (e.g. Sheet1!A:C)"},
            "rows": {
                "type": "array",
                "description": "Rows to append",
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "valueInputOption": {
                "type": "string",
                "enum": ["RAW", "USER_ENTERED"],
                "default": "USER_ENTERED",
            },
        },
        "required": ["spreadsheetId", "rangeA1", "rows"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(
        self,
        spreadsheetId: str | None = None,
        rangeA1: str | None = None,
        rows: list[list[str]] | None = None,
        valueInputOption: str = "USER_ENTERED",
        **kwargs: Any,
    ) -> str:
        spreadsheet_id = (spreadsheetId or "").strip()
        range_a1 = (rangeA1 or "").strip()
        if not spreadsheet_id:
            return "Error: spreadsheetId is required."
        if not range_a1:
            return "Error: rangeA1 is required."
        if rows is None:
            return "Error: rows is required."
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."
        if not rows:
            return "Error: rows cannot be empty."

        normalized_rows = [[str(cell) for cell in row] for row in rows]
        ok, data = await self.client.request(
            "POST",
            f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/{quote(range_a1, safe='')}:append",
            params={
                "valueInputOption": valueInputOption,
                "insertDataOption": "INSERT_ROWS",
            },
            json_body={"values": normalized_rows},
        )
        if not ok:
            return f"Error: {data.get('error', data)}"

        updates = data.get("updates", {}) if isinstance(data, dict) else {}
        return json.dumps(
            {
                "ok": True,
                "updatedRange": updates.get("updatedRange"),
                "updatedRows": updates.get("updatedRows"),
                "updatedCells": updates.get("updatedCells"),
            }
        )


def _format_person_line(person: dict[str, Any]) -> str:
    """Format People API person object into compact text."""
    names = person.get("names", []) or []
    emails = person.get("emailAddresses", []) or []
    phones = person.get("phoneNumbers", []) or []

    display_name = "(no name)"
    if names and isinstance(names[0], dict):
        display_name = str(
            names[0].get("displayName")
            or names[0].get("unstructuredName")
            or "(no name)"
        )

    email = ""
    if emails and isinstance(emails[0], dict):
        email = str(emails[0].get("value") or "")

    phone = ""
    if phones and isinstance(phones[0], dict):
        phone = str(phones[0].get("value") or "")

    resource_name = str(person.get("resourceName") or "")
    parts = [display_name]
    if email:
        parts.append(f"email: {email}")
    if phone:
        parts.append(f"phone: {phone}")
    if resource_name:
        parts.append(f"id: {resource_name}")
    return " | ".join(parts)


class ContactsListTool(Tool):
    """List Google Contacts entries."""

    name = "contacts_list"
    description = "List Google contacts (optionally search by query)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "pageSize": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20},
        },
        "required": [],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(self, query: str = "", pageSize: int = 20, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        q = (query or "").strip()
        if q:
            ok, data = await self.client.request(
                "GET",
                "https://people.googleapis.com/v1/people:searchContacts",
                params={
                    "query": q,
                    "pageSize": pageSize,
                    "readMask": "names,emailAddresses,phoneNumbers",
                },
            )
            people = data.get("results", []) if isinstance(data, dict) else []
            rows: list[dict[str, Any]] = []
            for item in people or []:
                if isinstance(item, dict) and isinstance(item.get("person"), dict):
                    rows.append(item["person"])
        else:
            ok, data = await self.client.request(
                "GET",
                "https://people.googleapis.com/v1/people/me/connections",
                params={
                    "personFields": "names,emailAddresses,phoneNumbers",
                    "pageSize": pageSize,
                    "sortOrder": "LAST_MODIFIED_ASCENDING",
                },
            )
            rows = data.get("connections", []) if isinstance(data, dict) else []

        if not ok:
            return f"Error: {data.get('error', data)}"
        if not rows:
            return "No contacts found."

        lines = [f"Contacts ({len(rows)}):"]
        for person in rows[:pageSize]:
            if isinstance(person, dict):
                lines.append(f"- {_format_person_line(person)}")
        return "\n".join(lines)


class ContactsGetTool(Tool):
    """Get single Google contact details."""

    name = "contacts_get"
    description = "Get Google contact detail by resource name (e.g. people/c123)."
    parameters = {
        "type": "object",
        "properties": {
            "resourceName": {"type": "string", "description": "People API resource name"},
        },
        "required": ["resourceName"],
    }

    def __init__(self, client: GoogleWorkspaceClient):
        self.client = client

    async def execute(self, resourceName: str | None = None, **kwargs: Any) -> str:
        if not self.client.is_configured():
            return "Error: Google Workspace not configured."

        rn = (resourceName or "").strip()
        if not rn:
            return "Error: resourceName is required."

        ok, data = await self.client.request(
            "GET",
            f"https://people.googleapis.com/v1/{quote(rn, safe='/')}",
            params={"personFields": "names,emailAddresses,phoneNumbers,organizations,biographies"},
        )
        if not ok:
            return f"Error: {data.get('error', data)}"

        lines = [
            f"Contact: {_format_person_line(data)}",
        ]
        orgs = data.get("organizations", []) if isinstance(data, dict) else []
        if orgs and isinstance(orgs[0], dict):
            name = str(orgs[0].get("name") or "")
            title = str(orgs[0].get("title") or "")
            if name or title:
                lines.append(f"Organization: {title} @ {name}".strip())
        bios = data.get("biographies", []) if isinstance(data, dict) else []
        if bios and isinstance(bios[0], dict):
            bio = str(bios[0].get("value") or "").strip()
            if bio:
                lines.append(f"Bio: {bio[:500]}")
        return "\n".join(lines)
