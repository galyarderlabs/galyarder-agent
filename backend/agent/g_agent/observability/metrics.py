"""Lightweight runtime metrics collector backed by JSONL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from g_agent.utils.helpers import ensure_dir


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _to_iso(ts: datetime | None = None) -> str:
    return (ts or _now_utc()).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    data = sorted(float(v) for v in values)
    index = int(0.95 * (len(data) - 1))
    return round(data[index], 2)


class MetricsStore:
    """Append-only metrics event store with aggregated snapshots."""

    def __init__(self, events_path: Path):
        self.events_path = events_path
        ensure_dir(events_path.parent)

    def _append(self, payload: dict[str, Any]) -> bool:
        record = dict(payload)
        record.setdefault("ts", _to_iso())
        line = json.dumps(record, ensure_ascii=False)
        try:
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            return True
        except OSError:
            return False

    def record_llm_call(
        self,
        *,
        model: str,
        success: bool,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: str = "",
    ) -> bool:
        return self._append(
            {
                "type": "llm_call",
                "model": (model or "").strip(),
                "success": bool(success),
                "latency_ms": round(float(latency_ms), 2),
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "error": (error or "").strip()[:500],
            }
        )

    def record_tool_call(
        self,
        *,
        tool: str,
        success: bool,
        latency_ms: float,
        attempts: int = 1,
        retry_kind: str = "",
        error: str = "",
    ) -> bool:
        return self._append(
            {
                "type": "tool_call",
                "tool": (tool or "").strip(),
                "success": bool(success),
                "latency_ms": round(float(latency_ms), 2),
                "attempts": max(1, int(attempts)),
                "retry_kind": (retry_kind or "").strip(),
                "error": (error or "").strip()[:500],
            }
        )

    def record_recall(self, *, query: str, hits: int, scopes: list[str] | None = None) -> bool:
        return self._append(
            {
                "type": "memory_recall",
                "query": (query or "").strip()[:500],
                "hits": max(0, int(hits)),
                "hit": int(hits) > 0,
                "scopes": [str(item).strip() for item in (scopes or []) if str(item).strip()],
            }
        )

    def record_cron_run(
        self,
        *,
        name: str,
        payload_kind: str,
        success: bool,
        latency_ms: float,
        delivered: bool = False,
        proactive: bool = False,
        error: str = "",
    ) -> bool:
        return self._append(
            {
                "type": "cron_run",
                "name": (name or "").strip(),
                "payload_kind": (payload_kind or "").strip(),
                "success": bool(success),
                "latency_ms": round(float(latency_ms), 2),
                "delivered": bool(delivered),
                "proactive": bool(proactive),
                "error": (error or "").strip()[:500],
            }
        )

    def _iter_events(self, since: datetime | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            if not self.events_path.exists():
                return []
            for raw_line in self.events_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if since is not None:
                    ts = _parse_iso(str(event.get("ts", "")))
                    if ts is None or ts < since:
                        continue
                items.append(event)
        except OSError:
            return []
        return items

    def snapshot(self, hours: int = 24) -> dict[str, Any]:
        """Build aggregated metrics snapshot for the given window."""
        window_hours = max(1, int(hours))
        since = _now_utc() - timedelta(hours=window_hours)
        events = self._iter_events(since=since)

        llm_events = [e for e in events if e.get("type") == "llm_call"]
        tool_events = [e for e in events if e.get("type") == "tool_call"]
        recall_events = [e for e in events if e.get("type") == "memory_recall"]
        cron_events = [e for e in events if e.get("type") == "cron_run"]

        llm_success = sum(1 for e in llm_events if bool(e.get("success")))
        tool_success = sum(1 for e in tool_events if bool(e.get("success")))
        cron_success = sum(1 for e in cron_events if bool(e.get("success")))
        recall_hit = sum(1 for e in recall_events if bool(e.get("hit")))

        tool_stats: dict[str, dict[str, int]] = {}
        for item in tool_events:
            name = str(item.get("tool", "")).strip() or "unknown"
            bucket = tool_stats.setdefault(name, {"calls": 0, "errors": 0})
            bucket["calls"] += 1
            if not bool(item.get("success")):
                bucket["errors"] += 1

        top_tools = [
            {"tool": tool, "calls": data["calls"], "errors": data["errors"]}
            for tool, data in sorted(
                tool_stats.items(),
                key=lambda pair: (pair[1]["calls"], -pair[1]["errors"], pair[0]),
                reverse=True,
            )[:10]
        ]

        llm_latencies = [float(e.get("latency_ms", 0.0) or 0.0) for e in llm_events]
        tool_latencies = [float(e.get("latency_ms", 0.0) or 0.0) for e in tool_events]
        cron_latencies = [float(e.get("latency_ms", 0.0) or 0.0) for e in cron_events]

        total_hits = sum(int(e.get("hits", 0) or 0) for e in recall_events)
        proactive_cron = sum(1 for e in cron_events if bool(e.get("proactive")))

        return {
            "window_hours": window_hours,
            "generated_at": _to_iso(),
            "events_file": str(self.events_path),
            "totals": {"events": len(events)},
            "llm": {
                "calls": len(llm_events),
                "success": llm_success,
                "errors": len(llm_events) - llm_success,
                "success_rate": _pct(llm_success, len(llm_events)),
                "latency_ms_p95": _p95(llm_latencies),
            },
            "tools": {
                "calls": len(tool_events),
                "success": tool_success,
                "errors": len(tool_events) - tool_success,
                "success_rate": _pct(tool_success, len(tool_events)),
                "latency_ms_p95": _p95(tool_latencies),
                "top_tools": top_tools,
            },
            "recall": {
                "queries": len(recall_events),
                "hit_queries": recall_hit,
                "hit_rate": _pct(recall_hit, len(recall_events)),
                "avg_hits": round(total_hits / len(recall_events), 2) if recall_events else 0.0,
            },
            "cron": {
                "runs": len(cron_events),
                "success": cron_success,
                "errors": len(cron_events) - cron_success,
                "success_rate": _pct(cron_success, len(cron_events)),
                "latency_ms_p95": _p95(cron_latencies),
                "proactive_runs": proactive_cron,
            },
        }
