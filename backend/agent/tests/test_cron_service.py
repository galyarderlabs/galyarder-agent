from pathlib import Path

from g_agent.cron.service import CronService
from g_agent.cron.types import CronSchedule


def test_add_job_preserves_payload_kind(tmp_path: Path):
    service = CronService(tmp_path / "jobs.json")
    job = service.add_job(
        name="calendar-watch",
        schedule=CronSchedule(kind="every", every_ms=60000),
        message="calendar_watch",
        kind="system_event",
        deliver=True,
        channel="telegram",
        to="123",
    )
    assert job.payload.kind == "system_event"
    assert job.payload.message == "calendar_watch"

    jobs = service.list_jobs(include_disabled=True)
    assert jobs and jobs[0].payload.kind == "system_event"
