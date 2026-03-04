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


_EXPECTED_SEED_NAMES = {"pd-daily-memory", "pd-weekly-memory", "pd-monthly-memory"}


def test_seed_default_jobs_creates_three_jobs(tmp_path: Path):
    """seed_default_jobs must register exactly 3 memory jobs on a fresh store."""
    service = CronService(tmp_path / "jobs.json")
    service.seed_default_jobs()

    jobs = service.list_jobs(include_disabled=True)
    names = {j.name for j in jobs}
    assert names == _EXPECTED_SEED_NAMES

    for job in jobs:
        assert job.payload.kind == "agent_turn"
        assert job.payload.deliver is False
        assert job.schedule.kind == "cron"
        assert job.schedule.expr is not None
        assert job.enabled is True


def test_seed_default_jobs_is_idempotent(tmp_path: Path):
    """Calling seed_default_jobs twice must not duplicate jobs."""
    service = CronService(tmp_path / "jobs.json")
    service.seed_default_jobs()
    service.seed_default_jobs()

    jobs = service.list_jobs(include_disabled=True)
    assert len(jobs) == 3
    assert {j.name for j in jobs} == _EXPECTED_SEED_NAMES


def test_seed_default_jobs_preserves_existing(tmp_path: Path):
    """seed_default_jobs must not overwrite a user-created job with the same name."""
    service = CronService(tmp_path / "jobs.json")

    # Pre-create one of the default jobs with custom message
    service.add_job(
        name="pd-daily-memory",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        message="custom user message",
    )

    service.seed_default_jobs()

    jobs = service.list_jobs(include_disabled=True)
    daily = [j for j in jobs if j.name == "pd-daily-memory"]
    assert len(daily) == 1
    assert daily[0].payload.message == "custom user message"
    assert len(jobs) == 3  # original + 2 newly seeded
