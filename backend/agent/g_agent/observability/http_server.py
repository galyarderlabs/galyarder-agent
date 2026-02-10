"""Lightweight optional HTTP server for metrics scraping."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import parse_qs, urlsplit

from g_agent.observability.metrics import MetricsStore


class MetricsHttpServer:
    """Serve metrics snapshots over a tiny HTTP endpoint."""

    def __init__(
        self,
        *,
        store: MetricsStore,
        host: str = "127.0.0.1",
        port: int = 18791,
        path: str = "/metrics",
        default_hours: int = 24,
        default_format: str = "prometheus",
    ):
        self.store = store
        self.host = str(host or "127.0.0.1").strip()
        self.port = max(0, int(port))
        raw_path = str(path or "/metrics").strip()
        self.path = raw_path if raw_path.startswith("/") else f"/{raw_path}"
        self.default_hours = max(1, int(default_hours))
        self.default_format = self._normalize_format(default_format)
        self._server: asyncio.AbstractServer | None = None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def bound_port(self) -> int:
        if not self._server or not self._server.sockets:
            return self.port
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        if self._server:
            return
        self._server = await asyncio.start_server(
            self._handle_client, host=self.host, port=self.port
        )

    async def stop(self) -> None:
        if not self._server:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    def _normalize_format(self, value: str | None) -> str:
        fmt = str(value or "").strip().lower()
        if fmt in {"prom", "prometheus", "text"}:
            return "prometheus"
        if fmt in {"dashboard", "dashboard_json", "flat"}:
            return "dashboard_json"
        if fmt == "json":
            return "json"
        return "prometheus"

    def _render_payload(self, *, hours: int, output_format: str) -> tuple[str, str]:
        if output_format == "prometheus":
            return self.store.prometheus_text(
                hours=hours
            ), "text/plain; version=0.0.4; charset=utf-8"
        if output_format == "dashboard_json":
            payload = self.store.dashboard_summary(hours=hours)
            return json.dumps(
                payload, ensure_ascii=False, indent=2
            ) + "\n", "application/json; charset=utf-8"
        payload = self.store.snapshot(hours=hours)
        return json.dumps(
            payload, ensure_ascii=False, indent=2
        ) + "\n", "application/json; charset=utf-8"

    def _http_response(
        self, status: int, body: str, content_type: str = "text/plain; charset=utf-8"
    ) -> bytes:
        reason = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            405: "Method Not Allowed",
            500: "Internal Server Error",
        }.get(status, "OK")
        data = body.encode("utf-8")
        headers = [
            f"HTTP/1.1 {status} {reason}",
            f"Content-Type: {content_type}",
            f"Content-Length: {len(data)}",
            "Connection: close",
            "",
            "",
        ]
        return "\r\n".join(headers).encode("utf-8") + data

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            raw = await reader.read(8192)
            request_text = raw.decode("utf-8", errors="ignore")
            line = request_text.splitlines()[0].strip() if request_text.splitlines() else ""
            parts = line.split()
            if len(parts) < 2:
                writer.write(self._http_response(400, "bad request\n"))
                await writer.drain()
                return

            method = parts[0].upper()
            target = parts[1]
            if method != "GET":
                writer.write(self._http_response(405, "method not allowed\n"))
                await writer.drain()
                return

            parsed = urlsplit(target)
            path = parsed.path or "/"
            if path == "/health":
                writer.write(self._http_response(200, "ok\n"))
                await writer.drain()
                return

            if path != self.path:
                writer.write(self._http_response(404, "not found\n"))
                await writer.drain()
                return

            query = parse_qs(parsed.query or "")
            hours = self.default_hours
            raw_hours = (query.get("hours") or [None])[0]
            if raw_hours:
                try:
                    hours = max(1, int(str(raw_hours).strip()))
                except (TypeError, ValueError):
                    hours = self.default_hours
            raw_format = (query.get("format") or [self.default_format])[0]
            output_format = self._normalize_format(str(raw_format))

            body, content_type = self._render_payload(hours=hours, output_format=output_format)
            writer.write(self._http_response(200, body, content_type=content_type))
            await writer.drain()
        except Exception:
            writer.write(self._http_response(500, "internal error\n"))
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
