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

        async def _job_wrapper():
            await self.runner.run(routine)
            self.store.save(routine)  # Save updated last_run_at

        # We need to map Routine to CronJob in CronService
        # This depends on how CronService is implemented
        logger.debug(f"Scheduling routine '{routine.name}' with schedule '{routine.schedule}'")
        # self.cron.add_job(...)
