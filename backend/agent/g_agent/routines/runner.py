"""Routine runner for G-Agent."""

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from g_agent.bus.events import InboundMessage
from g_agent.routines.model import Routine
from g_agent.routines.script import RoutineScriptPreprocessor, append_script_context


class RoutineRunner:
    """Converts routine triggers into active agent tasks."""

    def __init__(self, workspace: Path, bus: Any):
        self.workspace = workspace
        self.bus = bus
        self.script_preprocessor = RoutineScriptPreprocessor(workspace)

    async def run(self, routine: Routine) -> None:
        """Execute a routine by injecting an inbound message into the bus."""
        logger.info(f"Running routine: {routine.name} ({routine.id})")
        script_result = await self.script_preprocessor.run(routine)
        content = append_script_context(routine.content_prompt, script_result)

        # Build the inbound message that will trigger the agent loop
        msg = InboundMessage(
            content=content,
            channel=routine.destination_channel,
            chat_id=routine.destination_chat_id,
            sender_id="system-routine",
            metadata={
                "routine_id": routine.id,
                "sender_name": "System Routine",
                "target_character": routine.target_character,
                "toolsets": routine.metadata.get("toolsets", []),
                "allowed_tools": routine.allowed_tools,
                "approval_policy": routine.approval_policy,
                "is_proactive": True,
                "script": script_result.to_metadata(),
            },
        )

        # Inject into the bus
        await self.bus.publish_inbound(msg)

        # Update routine last run timestamp (calling code should handle saving)
        routine.last_run_at = datetime.now()
