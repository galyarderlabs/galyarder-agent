"""Lightweight browser-style tools with session state."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx

from g_agent.agent.tools.base import Tool


SENSITIVE_QUERY_KEYS = {
    "token",
    "api_key",
    "apikey",
    "access_token",
    "auth",
    "authorization",
    "password",
    "passwd",
    "secret",
    "session",
}


@dataclass
class BrowserSession:
    """Shared browser session state across browser tools."""

    workspace: Path
    current_url: str = ""
    current_html: str = ""
    current_title: str = ""
    last_status: int = 0
    links: list[dict[str, str]] = field(default_factory=list)
    form_values: dict[str, str] = field(default_factory=dict)
    allow_domains: list[str] = field(default_factory=list)
    deny_domains: list[str] = field(default_factory=list)
    request_timeout: float = 20.0
    max_html_chars: int = 250000

    @staticmethod
    def _host_matches(host: str, domain_rule: str) -> bool:
        host_l = host.lower().strip(".")
        rule_l = domain_rule.lower().strip().strip(".")
        if not host_l or not rule_l:
            return False
        return host_l == rule_l or host_l.endswith(f".{rule_l}")

    def _is_domain_allowed(self, url: str) -> tuple[bool, str]:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return False, "URL host is missing."

        for denied in self.deny_domains:
            if self._host_matches(host, denied):
                return False, f"Domain blocked by deny list: {denied}"

        if self.allow_domains:
            for allowed in self.allow_domains:
                if self._host_matches(host, allowed):
                    return True, ""
            return False, "Domain not in allow list."

        return True, ""

    @staticmethod
    def redact_url(url: str) -> str:
        try:
            parsed = urlparse(url)
            query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
            if not query_pairs:
                return url
            redacted_pairs: list[tuple[str, str]] = []
            for key, value in query_pairs:
                if key.lower() in SENSITIVE_QUERY_KEYS:
                    redacted_pairs.append((key, "***"))
                else:
                    redacted_pairs.append((key, value))
            return urlunparse(parsed._replace(query=urlencode(redacted_pairs)))
        except Exception:
            return url

    async def open_url(
        self,
        url: str,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Open URL and update browser state."""
        method_upper = method.upper().strip()
        if method_upper not in {"GET", "POST"}:
            return {"ok": False, "error": f"Unsupported method: {method}"}
        allowed, reason = self._is_domain_allowed(url)
        if not allowed:
            return {"ok": False, "error": reason, "url": self.redact_url(url)}

        request_timeout = timeout if timeout and timeout > 0 else self.request_timeout

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=request_timeout) as client:
                if method_upper == "GET":
                    response = await client.get(url, params=data or None)
                else:
                    response = await client.post(url, data=data or None)
        except Exception as e:
            return {"ok": False, "error": str(e), "url": self.redact_url(url)}

        final_url = str(response.url)
        allowed_final, reason_final = self._is_domain_allowed(final_url)
        if not allowed_final:
            return {"ok": False, "error": reason_final, "url": self.redact_url(final_url)}

        html = response.text or ""
        title = self._extract_title(html)
        self.current_url = final_url
        self.current_html = html[: self.max_html_chars]
        self.current_title = title
        self.last_status = response.status_code
        self.links = self._extract_links(html, self.current_url)

        return {
            "ok": True,
            "url": self.redact_url(self.current_url),
            "status": response.status_code,
            "title": title,
            "links": len(self.links),
        }

    @staticmethod
    def _extract_title(html: str) -> str:
        lower = html.lower()
        start = lower.find("<title>")
        end = lower.find("</title>")
        if start == -1 or end == -1 or end <= start:
            return ""
        return html[start + 7:end].strip()

    @staticmethod
    def _extract_links(html: str, base_url: str, max_links: int = 200) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        seen: set[str] = set()
        idx = 0
        lower = html.lower()
        pos = 0

        while len(links) < max_links:
            a_idx = lower.find("<a", pos)
            if a_idx == -1:
                break
            end_tag = lower.find(">", a_idx)
            if end_tag == -1:
                break
            chunk = html[a_idx:end_tag + 1]

            href = ""
            for quote in ("\"", "'"):
                marker = f"href={quote}"
                marker_pos = chunk.lower().find(marker)
                if marker_pos != -1:
                    start = marker_pos + len(marker)
                    stop = chunk.find(quote, start)
                    if stop != -1:
                        href = chunk[start:stop].strip()
                        break

            text_end = lower.find("</a>", end_tag)
            text = ""
            if text_end != -1:
                text = html[end_tag + 1:text_end].strip()

            pos = end_tag + 1 if text_end == -1 else text_end + 4

            if not href:
                continue
            absolute = urljoin(base_url, href)
            key = absolute.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            idx += 1
            links.append({"id": str(idx), "url": absolute, "text": text[:140]})

        return links


class BrowserOpenTool(Tool):
    """Open a URL and set current browser state."""

    name = "browser_open"
    description = "Open a URL in browser session state."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target URL"},
            "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET"},
            "data": {"type": "object", "description": "Optional query/body params"},
        },
        "required": ["url"],
    }

    def __init__(self, session: BrowserSession):
        self.session = session

    async def execute(
        self,
        url: str | None = None,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        target_url = (url or "").strip()
        if not target_url:
            return "Error: url is required."
        result = await self.session.open_url(url=target_url, method=method, data=data)
        return json.dumps(result)


class BrowserSnapshotTool(Tool):
    """Return snapshot of current page state and links."""

    name = "browser_snapshot"
    description = "Get title, URL, status, and indexed links of current page."
    parameters = {
        "type": "object",
        "properties": {
            "maxLinks": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "required": [],
    }

    def __init__(self, session: BrowserSession):
        self.session = session

    async def execute(self, maxLinks: int = 20, **kwargs: Any) -> str:
        if not self.session.current_url:
            return "Error: no current page. Use browser_open first."
        links = self.session.links[:maxLinks]
        lines = [
            f"URL: {self.session.redact_url(self.session.current_url)}",
            f"Status: {self.session.last_status}",
            f"Title: {self.session.current_title}",
            "",
            "Links:",
        ]
        for item in links:
            lines.append(
                f"- [{item['id']}] {item['text'] or '(no text)'} -> {self.session.redact_url(item['url'])}"
            )
        return "\n".join(lines)


class BrowserClickTool(Tool):
    """Navigate by indexed link id from snapshot or explicit URL."""

    name = "browser_click"
    description = "Navigate to a link by linkId from browser_snapshot or open direct url."
    parameters = {
        "type": "object",
        "properties": {
            "linkId": {"type": "string", "description": "Link ID from browser_snapshot"},
            "url": {"type": "string", "description": "Direct URL override"},
        },
        "required": [],
    }

    def __init__(self, session: BrowserSession):
        self.session = session

    async def execute(self, linkId: str | None = None, url: str | None = None, **kwargs: Any) -> str:
        target = (url or "").strip()
        if not target and linkId:
            for item in self.session.links:
                if item.get("id") == str(linkId):
                    target = item.get("url", "")
                    break
        if not target:
            return "Error: provide url or valid linkId from browser_snapshot."
        result = await self.session.open_url(url=target, method="GET")
        return json.dumps(result)


class BrowserTypeTool(Tool):
    """Set field values and optionally submit to a URL."""

    name = "browser_type"
    description = "Set field values in session and optionally submit."
    parameters = {
        "type": "object",
        "properties": {
            "field": {"type": "string", "description": "Field name"},
            "value": {"type": "string", "description": "Field value"},
            "submitUrl": {"type": "string", "description": "Optional URL to submit values"},
            "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET"},
        },
        "required": ["field", "value"],
    }

    def __init__(self, session: BrowserSession):
        self.session = session

    async def execute(
        self,
        field: str | None = None,
        value: str | None = None,
        submitUrl: str | None = None,
        method: str = "GET",
        **kwargs: Any,
    ) -> str:
        key = (field or "").strip()
        if not key:
            return "Error: field is required."
        if value is None:
            return "Error: value is required."
        self.session.form_values[key] = value

        if not submitUrl:
            return f"Field set: {key}."

        result = await self.session.open_url(
            url=submitUrl,
            method=method,
            data=self.session.form_values,
        )
        return json.dumps({"submitted": True, "fields": self.session.form_values, "result": result})


class BrowserExtractTool(Tool):
    """Extract page text snippets based on simple selectors."""

    name = "browser_extract"
    description = "Extract content from current page by selector (xpath, #id, .class, tag)."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "Selector (xpath, #id, .class, tag)"},
            "maxItems": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            "maxChars": {"type": "integer", "minimum": 20, "maximum": 4000, "default": 400},
        },
        "required": ["selector"],
    }

    def __init__(self, session: BrowserSession):
        self.session = session

    async def execute(
        self,
        selector: str | None = None,
        maxItems: int = 20,
        maxChars: int = 400,
        **kwargs: Any,
    ) -> str:
        if not self.session.current_html:
            return "Error: no current page. Use browser_open first."

        try:
            from lxml import html as lxml_html

            tree = lxml_html.fromstring(self.session.current_html)
            selector = (selector or "").strip()
            if not selector:
                return "Error: selector is required."
            if selector.startswith("//"):
                nodes = tree.xpath(selector)
            elif selector.startswith("#"):
                nodes = tree.xpath(f"//*[@id='{selector[1:]}']")
            elif selector.startswith("."):
                class_name = selector[1:]
                nodes = tree.xpath(
                    f"//*[contains(concat(' ', normalize-space(@class), ' '), ' {class_name} ')]"
                )
            else:
                nodes = tree.xpath(f"//{selector}")

            items: list[str] = []
            for node in nodes[:maxItems]:
                text = ""
                try:
                    text = " ".join((node.text_content() or "").split())
                except Exception:
                    text = str(node)
                text = text[:maxChars].strip()
                if text:
                    items.append(text)

            if not items:
                return f"No matches for selector: {selector}"
            return "\n".join(f"- {item}" for item in items)
        except Exception as e:
            return f"Error extracting selector '{selector}': {e}"


class BrowserScreenshotTool(Tool):
    """Take a screenshot of current URL using Playwright if available."""

    name = "browser_screenshot"
    description = "Take screenshot of current page (requires playwright installed)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Output path (relative to workspace)"},
            "fullPage": {"type": "boolean", "description": "Capture full page", "default": True},
        },
        "required": ["path"],
    }

    def __init__(self, session: BrowserSession):
        self.session = session

    async def execute(self, path: str | None = None, fullPage: bool = True, **kwargs: Any) -> str:
        if not self.session.current_url:
            return "Error: no current page. Use browser_open first."
        target_path = (path or "").strip()
        if not target_path:
            return "Error: path is required."
        out = Path(target_path)
        if not out.is_absolute():
            out = self.session.workspace / target_path
        else:
            try:
                resolved = out.resolve()
                if self.session.workspace.resolve() not in resolved.parents and resolved != self.session.workspace.resolve():
                    return "Error: absolute screenshot path must stay inside workspace."
            except Exception:
                return "Error: invalid output path."
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            from playwright.async_api import async_playwright
        except Exception:
            return "Error: playwright not installed. Install with: pip install playwright && playwright install chromium"

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(self.session.current_url, wait_until="networkidle", timeout=30000)
                await page.screenshot(path=str(out), full_page=bool(fullPage))
                await browser.close()
            return json.dumps({"ok": True, "path": str(out), "url": self.session.current_url})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
