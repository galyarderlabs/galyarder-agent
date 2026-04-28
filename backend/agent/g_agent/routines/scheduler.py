"""Routine scheduler for G-Agent."""

from pathlib import Path
from typing import Any

from loguru import logger
from g_agent.routines.store import RoutineStore
from g_agent.routines.runner import RoutineRunner
from g_agent.cron.service import CronService


class RoutineScheduler:
    """Bridges the CronService to G-Agent routines."""

    def __init__(self, workspace: Path, bus: Any, cron_service: CronService):
        self.workspace = workspace
        self.store = RoutineStore(workspace)
        self.runner = RoutineRunner(workspace, bus)
        self.cron = cron_service

    def sync(self):
        """Synchronize stored routines with the active cron service."""
        routines = self.store.list(enabled_only=True)
        cron_routines = [r for r in routines if r.trigger_type == "cron"]

        logger.info(f"Syncing {len(cron_routines)} routines with cron service")

        # Clear existing G-Agent routine jobs if the service supports it
        # (Assuming CronService has a way to identify routine-based jobs)

        for routine in cron_routines:
            self._schedule_routine(routine)

    def _schedule_routine(self, routine: Any):
        """Schedule a single routine in the cron service."""
        from g_agent.cron.types import CronSchedule

        logger.debug(f"Scheduling routine '{routine.name}' with schedule '{routine.schedule}'")

        # Map Routine schedule to CronSchedule
        # For now we assume routine.schedule is a cron expression
        schedule = CronSchedule(kind="cron", expr=routine.schedule)

        # We use a unique prefix to identify routine-based jobs in CronService
        job_name = f"routine:{routine.id}"

        # Check if job already exists to avoid duplicates
        existing = [j for j in self.cron.list_jobs(include_disabled=True) if j.name == job_name]
        if existing:
            # Update existing or skip? For now skip if enabled status matches
            # In a full implementation, we'd sync all fields.
            return

        self.cron.add_job(
            name=job_name,
            schedule=schedule,
            message=routine.content_prompt,
            kind="agent_turn",
            deliver=True,  # Routines usually want to deliver output
            channel=routine.destination_channel,
            to=routine.destination_chat_id,
        )
