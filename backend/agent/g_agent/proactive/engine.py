"""Proactive runtime helpers: quiet hours and calendar reminder dedupe."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _parse_hhmm(value: str) -> time | None:
    raw = (value or "").strip()
    if len(raw) != 5 or raw[2] != ":":
        return None
    try:
        hour = int(raw[:2])
        minute = int(raw[3:])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def resolve_timezone(name: str) -> timezone | ZoneInfo:
    """Resolve timezone string. 'local' and invalid values fallback to local tz."""
    raw = (name or "").strip()
    if not raw or raw.lower() == "local":
        local_tz = datetime.now().astimezone().tzinfo
        return local_tz if local_tz else timezone.utc
    try:
        return ZoneInfo(raw)
    except ZoneInfoNotFoundError:
        local_tz = datetime.now().astimezone().tzinfo
        return local_tz if local_tz else timezone.utc


def is_quiet_hours_now(
    now_local: datetime,
    start_hhmm: str,
    end_hhmm: str,
    enabled: bool = True,
) -> bool:
    """Check whether current local time falls inside quiet-hours window."""
    if not enabled:
        return False
    start = _parse_hhmm(start_hhmm)
    end = _parse_hhmm(end_hhmm)
    if start is None or end is None:
        return False
    now_t = now_local.timetz().replace(tzinfo=None)

    if start == end:
        return False
    if start < end:
        return start <= now_t < end
    return now_t >= start or now_t < end


def _parse_event_start_utc(event: dict[str, Any]) -> datetime | None:
    start = event.get("start", {}) if isinstance(event, dict) else {}
    if not isinstance(start, dict):
        return None
    start_dt = str(start.get("dateTime") or "").strip()
    if start_dt:
        normalized = start_dt.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None

    # All-day events use date; skip reminder scheduling to avoid noisy midnight alerts.
    return None


class ProactiveStateStore:
    """Persist dedupe state for proactive reminders."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        try:
            if self.path.exists():
                raw = self.path.read_text(encoding="utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _write(self, payload: dict[str, Any]) -> bool:
        try:
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return True
        except OSError:
            return False

    def was_notified(self, reminder_key: str) -> bool:
        key = (reminder_key or "").strip()
        if not key:
            return False
        state = self._read()
        reminders = state.get("calendar_reminders", {})
        return key in reminders if isinstance(reminders, dict) else False

    def mark_notified(self, reminder_key: str, notified_at_utc: datetime) -> bool:
        key = (reminder_key or "").strip()
        if not key:
            return False
        state = self._read()
        reminders = state.get("calendar_reminders")
        if not isinstance(reminders, dict):
            reminders = {}
        reminders[key] = notified_at_utc.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        state["calendar_reminders"] = reminders
        state["version"] = 1
        return self._write(state)

    def prune(self, older_than_days: int = 14) -> None:
        if older_than_days <= 0:
            return
        state = self._read()
        reminders = state.get("calendar_reminders")
        if not isinstance(reminders, dict) or not reminders:
            return
        threshold = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        fresh: dict[str, str] = {}
        for key, iso_time in reminders.items():
            try:
                parsed = datetime.fromisoformat(str(iso_time).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed >= threshold:
                    fresh[str(key)] = str(iso_time)
            except ValueError:
                continue
        state["calendar_reminders"] = fresh
        self._write(state)


def compute_due_calendar_reminders(
    events: list[dict[str, Any]],
    *,
    now_utc: datetime,
    lead_minutes: list[int],
    scan_minutes: int,
    horizon_minutes: int,
    state_store: ProactiveStateStore,
) -> list[dict[str, Any]]:
    """Return due calendar reminders and mark them as notified."""
    leads = sorted({int(item) for item in lead_minutes if int(item) > 0}, reverse=True)
    if not leads:
        leads = [30, 10]
    scan_window = max(1, int(scan_minutes))
    horizon = max(5, int(horizon_minutes))

    due: list[dict[str, Any]] = []
    for event in events:
        start_utc = _parse_event_start_utc(event)
        if not start_utc:
            continue
        delta_minutes = int((start_utc - now_utc).total_seconds() // 60)
        if delta_minutes < 0 or delta_minutes > horizon:
            continue

        event_id = str(event.get("id", "")).strip() or "unknown-event"
        summary = str(event.get("summary", "(no title)")).strip() or "(no title)"

        selected_lead = 0
        for lead in leads:
            lower_bound = max(0, lead - scan_window)
            if lower_bound <= delta_minutes <= lead:
                selected_lead = lead
                break
        if selected_lead <= 0:
            continue

        reminder_key = f"{event_id}:{start_utc.isoformat()}:{selected_lead}"
        if state_store.was_notified(reminder_key):
            continue
        state_store.mark_notified(reminder_key, now_utc)

        due.append(
            {
                "event_id": event_id,
                "summary": summary,
                "start_utc": start_utc,
                "minutes_to_start": delta_minutes,
                "lead_minutes": selected_lead,
            }
        )

    state_store.prune(older_than_days=21)
    due.sort(key=lambda item: item["start_utc"])
    return due
