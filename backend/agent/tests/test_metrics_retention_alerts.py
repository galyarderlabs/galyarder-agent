import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from g_agent.observability.metrics import MetricsStore


def _write_events(path: Path, events: list[dict[str, object]]) -> None:
    lines = [json.dumps(item, ensure_ascii=False) for item in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_prune_events_applies_retention_and_cap(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    store = MetricsStore(events_path)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    old_ts = (now - timedelta(hours=48)).isoformat()
    fresh_ts = (now - timedelta(hours=1)).isoformat()
    events = [
        {"type": "llm_call", "success": True, "latency_ms": 100, "ts": old_ts} for _ in range(5)
    ] + [
        {"type": "tool_call", "success": True, "latency_ms": 200, "ts": fresh_ts} for _ in range(5)
    ]
    _write_events(events_path, events)

    dry_result = store.prune_events(keep_hours=24, max_events=3, dry_run=True)
    assert dry_result["ok"] is True
    assert dry_result["before"] == 10
    assert dry_result["after"] == 3
    assert dry_result["removed_by_age"] == 5
    assert dry_result["removed_by_cap"] == 2
    assert len(events_path.read_text(encoding="utf-8").splitlines()) == 10

    result = store.prune_events(keep_hours=24, max_events=3, dry_run=False)
    assert result["ok"] is True
    assert result["removed_total"] == 7
    assert len(events_path.read_text(encoding="utf-8").splitlines()) == 3


def test_alert_summary_and_dashboard_alert_fields(tmp_path: Path):
    store = MetricsStore(tmp_path / "events.jsonl")
    store.record_llm_call(model="gemini", success=True, latency_ms=300)
    store.record_llm_call(model="gemini", success=False, latency_ms=900, error="timeout")
    store.record_tool_call(tool="web_search", success=True, latency_ms=400)
    store.record_cron_run(
        name="morning-brief",
        payload_kind="digest",
        success=False,
        latency_ms=12000,
        delivered=False,
        proactive=True,
        error="timeout",
    )
    store.record_recall(query="timezone", hits=0)

    alerts = store.alert_summary(
        hours=24,
        thresholds={
            "llm_success_rate_min": 90.0,
            "cron_success_rate_min": 80.0,
            "cron_latency_p95_max": 5000.0,
        },
    )
    assert alerts["overall"] == "warn"
    assert alerts["warn_count"] >= 2
    warned = {item["key"] for item in alerts["checks"] if item["status"] == "warn"}
    assert "llm_success_rate" in warned
    assert "cron_success_rate" in warned
    assert "cron_latency_p95_ms" in warned

    dashboard = store.dashboard_summary(hours=24)
    assert dashboard["alerts_overall"] in {"ok", "warn", "na"}
    assert isinstance(dashboard["alerts_warn_count"], int)
    assert isinstance(dashboard["alerts_triggered_checks"], list)
    assert isinstance(dashboard["alerts_top_warn_checks"], list)
    assert isinstance(dashboard["alerts_brief"], str)


def test_alert_summary_empty_window_is_na(tmp_path: Path):
    store = MetricsStore(tmp_path / "events.jsonl")
    alerts = store.alert_summary(hours=24)

    assert alerts["overall"] == "na"
    assert alerts["warn_count"] == 0
    assert alerts["ok_count"] == 0
    assert alerts["na_count"] > 0


def test_alert_compact_and_prometheus_expose_alert_gauges(tmp_path: Path):
    store = MetricsStore(tmp_path / "events.jsonl")
    store.record_llm_call(model="gemini", success=False, latency_ms=300, error="timeout")
    store.record_tool_call(tool="web_search", success=True, latency_ms=200)
    store.record_recall(query="timezone", hits=0)
    store.record_cron_run(
        name="calendar-watch",
        payload_kind="system_event",
        success=False,
        latency_ms=15000,
        delivered=False,
        proactive=True,
        error="timeout",
    )

    compact = store.alert_compact(hours=24)
    assert compact["overall"] == "warn"
    assert "warn" in compact["brief"]
    assert isinstance(compact["top_warn_checks"], list)
    assert compact["top_warn_checks"]

    text = store.prometheus_text(hours=24)
    assert "g_agent_alerts_warn_count" in text
    assert 'g_agent_alerts_overall{state="warn"} 1' in text
    assert 'g_agent_alert_check_warn{check="llm_success_rate"} 1' in text
