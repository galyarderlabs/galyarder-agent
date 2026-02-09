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


def _escape_label(value: str) -> str:
    text = str(value or "")
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


DEFAULT_ALERT_THRESHOLDS: dict[str, float] = {
    "llm_success_rate_min": 95.0,
    "tool_success_rate_min": 95.0,
    "cron_success_rate_min": 95.0,
    "recall_hit_rate_min": 20.0,
    "llm_latency_p95_max": 15000.0,
    "tool_latency_p95_max": 10000.0,
    "cron_latency_p95_max": 10000.0,
}


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

    def dashboard_summary(self, hours: int = 24, top_n_tools: int = 5) -> dict[str, Any]:
        """Flatten snapshot into dashboard/scraper-friendly fields."""
        snapshot = self.snapshot(hours=hours)
        llm = snapshot["llm"]
        tools = snapshot["tools"]
        recall = snapshot["recall"]
        cron = snapshot["cron"]
        totals = snapshot["totals"]
        summary: dict[str, Any] = {
            "generated_at": snapshot["generated_at"],
            "window_hours": snapshot["window_hours"],
            "events_file": snapshot["events_file"],
            "events_total": totals["events"],
            "llm_calls": llm["calls"],
            "llm_success": llm["success"],
            "llm_errors": llm["errors"],
            "llm_success_rate_pct": llm["success_rate"],
            "llm_latency_p95_ms": llm["latency_ms_p95"],
            "tool_calls": tools["calls"],
            "tool_success": tools["success"],
            "tool_errors": tools["errors"],
            "tool_success_rate_pct": tools["success_rate"],
            "tool_latency_p95_ms": tools["latency_ms_p95"],
            "recall_queries": recall["queries"],
            "recall_hit_queries": recall["hit_queries"],
            "recall_hit_rate_pct": recall["hit_rate"],
            "recall_avg_hits": recall["avg_hits"],
            "cron_runs": cron["runs"],
            "cron_success": cron["success"],
            "cron_errors": cron["errors"],
            "cron_success_rate_pct": cron["success_rate"],
            "cron_latency_p95_ms": cron["latency_ms_p95"],
            "cron_proactive_runs": cron["proactive_runs"],
        }
        for index, item in enumerate(tools.get("top_tools", [])[:max(0, int(top_n_tools))], start=1):
            summary[f"top_tool_{index}_name"] = item.get("tool", "")
            summary[f"top_tool_{index}_calls"] = int(item.get("calls", 0))
            summary[f"top_tool_{index}_errors"] = int(item.get("errors", 0))
        alerts = self.alert_summary(hours=hours, snapshot=snapshot)
        summary["alerts_overall"] = alerts["overall"]
        summary["alerts_warn_count"] = alerts["warn_count"]
        summary["alerts_ok_count"] = alerts["ok_count"]
        summary["alerts_na_count"] = alerts["na_count"]
        summary["alerts_triggered_checks"] = [
            item.get("key", "") for item in alerts.get("checks", []) if item.get("status") == "warn"
        ]
        return summary

    def prometheus_text(self, hours: int = 24) -> str:
        """Render snapshot as Prometheus text exposition format."""
        snapshot = self.snapshot(hours=hours)
        llm = snapshot["llm"]
        tools = snapshot["tools"]
        recall = snapshot["recall"]
        cron = snapshot["cron"]
        totals = snapshot["totals"]

        lines = [
            "# HELP g_agent_events_total Total recorded events in snapshot window",
            "# TYPE g_agent_events_total gauge",
            f"g_agent_events_total {totals['events']}",
            "# HELP g_agent_llm_calls_total LLM calls in snapshot window",
            "# TYPE g_agent_llm_calls_total gauge",
            f"g_agent_llm_calls_total {llm['calls']}",
            f"g_agent_llm_success_total {llm['success']}",
            f"g_agent_llm_errors_total {llm['errors']}",
            f"g_agent_llm_success_rate_pct {llm['success_rate']}",
            f"g_agent_llm_latency_p95_ms {llm['latency_ms_p95']}",
            "# HELP g_agent_tool_calls_total Tool calls in snapshot window",
            "# TYPE g_agent_tool_calls_total gauge",
            f"g_agent_tool_calls_total {tools['calls']}",
            f"g_agent_tool_success_total {tools['success']}",
            f"g_agent_tool_errors_total {tools['errors']}",
            f"g_agent_tool_success_rate_pct {tools['success_rate']}",
            f"g_agent_tool_latency_p95_ms {tools['latency_ms_p95']}",
            f"g_agent_recall_queries_total {recall['queries']}",
            f"g_agent_recall_hit_queries_total {recall['hit_queries']}",
            f"g_agent_recall_hit_rate_pct {recall['hit_rate']}",
            f"g_agent_recall_avg_hits {recall['avg_hits']}",
            f"g_agent_cron_runs_total {cron['runs']}",
            f"g_agent_cron_success_total {cron['success']}",
            f"g_agent_cron_errors_total {cron['errors']}",
            f"g_agent_cron_success_rate_pct {cron['success_rate']}",
            f"g_agent_cron_latency_p95_ms {cron['latency_ms_p95']}",
            f"g_agent_cron_proactive_runs_total {cron['proactive_runs']}",
        ]
        for item in tools.get("top_tools", []):
            tool = _escape_label(str(item.get("tool", "")))
            calls = int(item.get("calls", 0))
            errors = int(item.get("errors", 0))
            lines.append(f'g_agent_top_tool_calls{{tool="{tool}"}} {calls}')
            lines.append(f'g_agent_top_tool_errors{{tool="{tool}"}} {errors}')
        return "\n".join(lines).rstrip() + "\n"

    def alert_summary(
        self,
        *,
        hours: int = 24,
        snapshot: dict[str, Any] | None = None,
        thresholds: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Evaluate snapshot against uptime/SLO thresholds."""
        base_snapshot = snapshot or self.snapshot(hours=hours)
        merged_thresholds = dict(DEFAULT_ALERT_THRESHOLDS)
        for key, value in (thresholds or {}).items():
            try:
                merged_thresholds[str(key)] = float(value)
            except (TypeError, ValueError):
                continue

        llm = base_snapshot["llm"]
        tools = base_snapshot["tools"]
        recall = base_snapshot["recall"]
        cron = base_snapshot["cron"]
        checks_config = [
            (
                "llm_success_rate",
                "min",
                float(llm["success_rate"]),
                float(merged_thresholds["llm_success_rate_min"]),
                int(llm["calls"]),
            ),
            (
                "tool_success_rate",
                "min",
                float(tools["success_rate"]),
                float(merged_thresholds["tool_success_rate_min"]),
                int(tools["calls"]),
            ),
            (
                "cron_success_rate",
                "min",
                float(cron["success_rate"]),
                float(merged_thresholds["cron_success_rate_min"]),
                int(cron["runs"]),
            ),
            (
                "recall_hit_rate",
                "min",
                float(recall["hit_rate"]),
                float(merged_thresholds["recall_hit_rate_min"]),
                int(recall["queries"]),
            ),
            (
                "llm_latency_p95_ms",
                "max",
                float(llm["latency_ms_p95"]),
                float(merged_thresholds["llm_latency_p95_max"]),
                int(llm["calls"]),
            ),
            (
                "tool_latency_p95_ms",
                "max",
                float(tools["latency_ms_p95"]),
                float(merged_thresholds["tool_latency_p95_max"]),
                int(tools["calls"]),
            ),
            (
                "cron_latency_p95_ms",
                "max",
                float(cron["latency_ms_p95"]),
                float(merged_thresholds["cron_latency_p95_max"]),
                int(cron["runs"]),
            ),
        ]

        checks: list[dict[str, Any]] = []
        for key, comparator, actual, threshold_value, samples in checks_config:
            if samples <= 0:
                checks.append(
                    {
                        "key": key,
                        "status": "na",
                        "samples": samples,
                        "actual": round(actual, 2),
                        "threshold": round(threshold_value, 2),
                        "operator": ">=" if comparator == "min" else "<=",
                    }
                )
                continue
            if comparator == "min":
                passed = actual >= threshold_value
                operator = ">="
            else:
                passed = actual <= threshold_value
                operator = "<="
            checks.append(
                {
                    "key": key,
                    "status": "ok" if passed else "warn",
                    "samples": samples,
                    "actual": round(actual, 2),
                    "threshold": round(threshold_value, 2),
                    "operator": operator,
                }
            )

        warn_count = sum(1 for item in checks if item["status"] == "warn")
        ok_count = sum(1 for item in checks if item["status"] == "ok")
        na_count = sum(1 for item in checks if item["status"] == "na")
        if warn_count > 0:
            overall = "warn"
        elif ok_count > 0:
            overall = "ok"
        else:
            overall = "na"

        return {
            "window_hours": base_snapshot["window_hours"],
            "generated_at": base_snapshot["generated_at"],
            "overall": overall,
            "warn_count": warn_count,
            "ok_count": ok_count,
            "na_count": na_count,
            "checks": checks,
            "thresholds": merged_thresholds,
        }

    def prune_events(
        self,
        *,
        keep_hours: int = 168,
        max_events: int = 50000,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Prune stale metrics events to control file growth."""
        retention_hours = max(1, int(keep_hours))
        events_cap = max(0, int(max_events))
        cutoff = _now_utc() - timedelta(hours=retention_hours)
        result: dict[str, Any] = {
            "ok": True,
            "path": str(self.events_path),
            "retention_hours": retention_hours,
            "max_events": events_cap,
            "cutoff_utc": _to_iso(cutoff),
            "dry_run": bool(dry_run),
            "raw_lines": 0,
            "parse_errors": 0,
            "retained_without_ts": 0,
            "before": 0,
            "after": 0,
            "removed_by_age": 0,
            "removed_by_cap": 0,
            "removed_total": 0,
        }
        if not self.events_path.exists():
            return result

        parsed_events: list[dict[str, Any]] = []
        try:
            for raw_line in self.events_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                result["raw_lines"] += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    result["parse_errors"] += 1
                    continue
                if not isinstance(event, dict):
                    result["parse_errors"] += 1
                    continue
                parsed_events.append(event)
        except OSError as e:
            result["ok"] = False
            result["error"] = str(e)
            return result

        result["before"] = len(parsed_events)
        retained_events: list[dict[str, Any]] = []
        for event in parsed_events:
            ts = _parse_iso(str(event.get("ts", "")))
            if ts is not None and ts < cutoff:
                result["removed_by_age"] += 1
                continue
            if ts is None:
                result["retained_without_ts"] += 1
            retained_events.append(event)

        if events_cap > 0 and len(retained_events) > events_cap:
            result["removed_by_cap"] = len(retained_events) - events_cap
            retained_events = retained_events[-events_cap:]

        result["after"] = len(retained_events)
        result["removed_total"] = result["before"] - result["after"]
        if dry_run:
            return result

        serialized = "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in retained_events)
        tmp_path = self.events_path.with_name(f"{self.events_path.name}.tmp")
        try:
            tmp_path.write_text(serialized, encoding="utf-8")
            tmp_path.replace(self.events_path)
        except OSError as e:
            result["ok"] = False
            result["error"] = str(e)
            return result
        return result

    def export_snapshot(
        self,
        output_path: Path,
        *,
        hours: int = 24,
        output_format: str = "auto",
    ) -> dict[str, Any]:
        """Export metrics snapshot to a file for shipping/scraping."""
        path = Path(output_path).expanduser()
        ensure_dir(path.parent)

        fmt = (output_format or "auto").strip().lower()
        if fmt == "auto":
            suffix = path.suffix.lower()
            filename = path.name.lower()
            if suffix == ".prom":
                fmt = "prometheus"
            elif filename.endswith(".dashboard.json") or suffix == ".djson":
                fmt = "dashboard_json"
            else:
                fmt = "json"

        if fmt == "prometheus":
            content = self.prometheus_text(hours=hours)
        elif fmt == "dashboard_json":
            content = json.dumps(
                self.dashboard_summary(hours=hours),
                indent=2,
                ensure_ascii=False,
            ) + "\n"
        elif fmt == "json":
            content = json.dumps(
                self.snapshot(hours=hours),
                indent=2,
                ensure_ascii=False,
            ) + "\n"
        else:
            return {"ok": False, "error": f"Unknown output format: {output_format}"}

        try:
            path.write_text(content, encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": str(e)}

        return {
            "ok": True,
            "path": str(path),
            "format": fmt,
            "bytes": len(content.encode("utf-8")),
        }
