"""Routine runner for G-Agent."""

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from g_agent.bus.events import InboundMessage, LifecycleEvent
from g_agent.routines.model import Routine
from g_agent.routines.script import RoutineScriptPreprocessor, append_script_context


class RoutineRunner:
    """Converts routine triggers into active agent tasks."""

    def __init__(self, workspace: Path, bus: Any):
        self.workspace = workspace
        self.bus = bus
        self.script_preprocessor = RoutineScriptPreprocessor(workspace)

    async def run(self, routine: Routine, trigger_metadata: dict[str, Any] | None = None) -> None:
        """Execute a routine by injecting an inbound message into the bus."""
        if self._is_quiet_hours(routine):
            logger.info(f"Skipping routine {routine.id} (quiet hours)")
            await self.bus.publish_event(
                LifecycleEvent(
                    type="agent:routine:skipped",
                    chat_id=routine.destination_chat_id,
                    data={
                        "routine_id": routine.id,
                        "name": routine.name,
                        "reason": "quiet_hours",
                    },
                )
            )
            return

        logger.info(f"Running routine: {routine.name} ({routine.id})")

        # Build idempotency key for this run
        now = datetime.now()
        run_id = f"run-{routine.id}-{now.strftime('%Y%m%d%H%M')}"

        # Publish event
        await self.bus.publish_event(
            LifecycleEvent(
                type="agent:routine:started",
                chat_id=routine.destination_chat_id,
                data={
                    "routine_id": routine.id,
                    "run_id": run_id,
                    "name": routine.name,
                    "channel": routine.destination_channel,
                }
            )
        )

        try:
            script_result = await self.script_preprocessor.run(routine)
            if script_result.error:
                 await self.bus.publish_event(
                    LifecycleEvent(
                        type="agent:routine:script_failed",
                        chat_id=routine.destination_chat_id,
                        data={
                            "routine_id": routine.id,
                            "run_id": run_id,
                            "error": script_result.error,
                            "stderr": script_result.stderr,
                        }
                    )
                )

            content = append_script_context(routine.content_prompt, script_result)
        except Exception as e:
            logger.error(f"Routine runner failed to preprocess: {e}")
            await self.bus.publish_event(
                LifecycleEvent(
                    type="agent:routine:failed",
                    chat_id=routine.destination_chat_id,
                    data={
                        "routine_id": routine.id,
                        "run_id": run_id,
                        "error": str(e),
                    }
                )
            )
            return

        # Build metadata
        metadata = {
            "routine_id": routine.id,
            "run_id": run_id,
            "idempotency_key": f"routine:{run_id}",
            "sender_name": "System Routine",
            "target_character": routine.target_character,
            "toolsets": routine.metadata.get("toolsets", []),
            "allowed_tools": routine.allowed_tools,
            "approval_policy": routine.approval_policy,
            "is_proactive": True,
            "bypass_busy": True,
            "script": script_result.to_metadata(),
        }

        if routine.steps:
            metadata["routine_steps"] = [s.model_dump() for s in routine.steps]

        if trigger_metadata:
            metadata.update(trigger_metadata)

        # Build the inbound message that will trigger the agent loop
        msg = InboundMessage(
            content=content,
            channel=routine.destination_channel,
            chat_id=routine.destination_chat_id,
            sender_id="system-routine",
            metadata=metadata,
        )

        # Inject into the bus
        await self.bus.publish_inbound(msg)

        # Update routine last run timestamp (calling code should handle saving)
        routine.last_run_at = now

    def _is_quiet_hours(self, routine: Routine) -> bool:
        """Check if current time falls within routine's quiet hours."""
        qh = routine.quiet_hours
        if not qh.enabled:
            return False

        try:
            import zoneinfo

            tz = zoneinfo.ZoneInfo(qh.timezone)
            # Use current time in target timezone
            now_tz = datetime.now(tz)
            current_time = now_tz.strftime("%H:%M")

            start = qh.start_time
            end = qh.end_time

            if start <= end:
                return start <= current_time <= end
            else:
                # Overlap midnight
                return current_time >= start or current_time <= end
        except Exception as e:
            logger.warning(f"Quiet hours check failed for {routine.id}: {e}")
            return False
