from datetime import datetime, timezone
from pathlib import Path

from g_agent.proactive.engine import (
    ProactiveStateStore,
    compute_due_calendar_reminders,
    is_quiet_hours_now,
    resolve_timezone,
)


def test_is_quiet_hours_now_overnight_window():
    tzinfo = resolve_timezone("UTC")
    late = datetime(2026, 2, 8, 23, 10, tzinfo=tzinfo)
    early = datetime(2026, 2, 9, 5, 45, tzinfo=tzinfo)
    daytime = datetime(2026, 2, 9, 12, 0, tzinfo=tzinfo)

    assert is_quiet_hours_now(late, "22:00", "06:00", enabled=True)
    assert is_quiet_hours_now(early, "22:00", "06:00", enabled=True)
    assert not is_quiet_hours_now(daytime, "22:00", "06:00", enabled=True)


def test_compute_due_calendar_reminders_dedup(tmp_path: Path):
    now_utc = datetime(2026, 2, 8, 7, 0, tzinfo=timezone.utc)
    events = [
        {
            "id": "evt-1",
            "summary": "Investor Sync",
            "start": {"dateTime": "2026-02-08T07:10:00+00:00"},
        },
        {
            "id": "evt-2",
            "summary": "Deep Work",
            "start": {"dateTime": "2026-02-08T08:30:00+00:00"},
        },
    ]
    store = ProactiveStateStore(tmp_path / "proactive-state.json")

    first = compute_due_calendar_reminders(
        events,
        now_utc=now_utc,
        lead_minutes=[30, 10],
        scan_minutes=15,
        horizon_minutes=120,
        state_store=store,
    )
    assert len(first) == 1
    assert first[0]["event_id"] == "evt-1"
    assert first[0]["lead_minutes"] == 10

    second = compute_due_calendar_reminders(
        events,
        now_utc=now_utc,
        lead_minutes=[30, 10],
        scan_minutes=15,
        horizon_minutes=120,
        state_store=store,
    )
    assert second == []
