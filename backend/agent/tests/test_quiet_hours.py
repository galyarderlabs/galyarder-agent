import pytest
from pathlib import Path
from g_agent.routines.model import Routine, RoutineQuietHours
from g_agent.routines.runner import RoutineRunner

class MockBus:
    def __init__(self):
        self.events = []
    async def publish_event(self, event):
        self.events.append(event)
    async def publish_inbound(self, msg):
        pass

@pytest.mark.asyncio
async def test_routine_quiet_hours_enforcement(tmp_path: Path, monkeypatch):
    """Test that routine.run() skips execution during quiet hours."""
    bus = MockBus()
    runner = RoutineRunner(tmp_path, bus)

    routine = Routine(
        id="test-routine",
        name="Test Routine",
        description="Testing quiet hours",
        schedule="0 * * * *",
        destination_channel="cli",
        destination_chat_id="direct",
        content_prompt="ping",
        quiet_hours=RoutineQuietHours(
            enabled=True,
            start_time="10:00",
            end_time="11:00",
            timezone="UTC"
        )
    )

    # Mock datetime to return 10:30 UTC (inside quiet hours)
    class FixedDateTime:
        @staticmethod
        def now(tz=None):
            from datetime import datetime as real_datetime
            dt = real_datetime.strptime("2026-01-01 10:30", "%Y-%m-%d %H:%M")
            if tz:
                return dt.replace(tzinfo=tz)
            return dt

    monkeypatch.setattr("g_agent.routines.runner.datetime", FixedDateTime)

    await runner.run(routine)

    # Should have published skipped event and not published inbound message
    assert len(bus.events) == 1
    assert bus.events[0].type == "agent:routine:skipped"
    assert bus.events[0].data["routine_id"] == "test-routine"
    assert bus.events[0].data["reason"] == "quiet_hours"

def test_is_quiet_hours_disabled():
    """Test that disabled quiet hours always returns False."""
    runner = RoutineRunner(Path("/tmp"), None)

    routine = Routine(
        id="r", name="n", description="d",
        schedule="0 * * * *",
        destination_channel="c", destination_chat_id="ch", content_prompt="p",
        quiet_hours=RoutineQuietHours(enabled=False, start_time="09:00", end_time="17:00")
    )

    assert runner._is_quiet_hours(routine) is False

# Let's actually implementation a better unit test for _is_quiet_hours
@pytest.mark.parametrize("current,start,end,expected", [
    ("10:00", "09:00", "17:00", True),
    ("08:00", "09:00", "17:00", False),
    ("17:00", "09:00", "17:00", True),
    ("23:00", "22:00", "06:00", True), # Overlap midnight
    ("01:00", "22:00", "06:00", True), # Overlap midnight
    ("12:00", "22:00", "06:00", False),
])
def test_quiet_hours_comparison_logic(current, start, end, expected, monkeypatch):
    runner = RoutineRunner(Path("/tmp"), None)
    routine = Routine(
        id="r", name="n", description="d",
        schedule="0 * * * *",
        destination_channel="c", destination_chat_id="ch", content_prompt="p",
        quiet_hours=RoutineQuietHours(enabled=True, start_time=start, end_time=end, timezone="UTC")
    )
    
    class FixedDateTime:
        @staticmethod
        def now(tz=None):
            from datetime import datetime as real_datetime
            dt = real_datetime.strptime(f"2026-01-01 {current}", "%Y-%m-%d %H:%M")
            if tz:
                return dt.replace(tzinfo=tz)
            return dt

    monkeypatch.setattr("g_agent.routines.runner.datetime", FixedDateTime)
    assert runner._is_quiet_hours(routine) == expected
