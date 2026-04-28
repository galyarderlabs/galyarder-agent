"""Routine runner for G-Agent."""

from pathlib import Path
from typing import Any

from loguru import logger
from g_agent.routines.model import Routine
from g_agent.bus.events import InboundMessage


class RoutineRunner:
    """Converts routine triggers into active agent tasks."""

    def __init__(self, workspace: Path, bus: Any):
        self.workspace = workspace
        self.bus = bus

    async def run(self, routine: Routine):
        """Execute a routine by injecting an inbound message into the bus."""
        logger.info(f"Running routine: {routine.name} ({routine.id})")

        # Build the inbound message that will trigger the agent loop
        msg = InboundMessage(
            content=routine.content_prompt,
            channel=routine.destination_channel,
            chat_id=routine.destination_chat_id,
            sender_id="system-routine",
            sender_name="System Routine",
            metadata={
                "routine_id": routine.id,
                "target_character": routine.target_character,
                "toolsets": routine.metadata.get("toolsets", []),
                "allowed_tools": routine.allowed_tools,
                "approval_policy": routine.approval_policy,
                "is_proactive": True,
            },
        )

        # Inject into the bus
        await self.bus.publish_inbound(msg)

        # Update routine last run timestamp (calling code should handle saving)
        from datetime import datetime

        routine.last_run_at = datetime.now()
