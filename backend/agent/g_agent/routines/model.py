"""Routine model for G-Agent."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


TriggerType = Literal["cron", "webhook", "api_event", "file_change"]


class RoutineQuietHours(BaseModel):
    """Quiet hours configuration for a routine."""

    enabled: bool = False
    start_time: str = "22:00"  # HH:MM
    end_time: str = "08:00"  # HH:MM
    timezone: str = "UTC"


class Routine(BaseModel):
    """
    A reusable background workflow triggered by time or events.
    """

    id: str
    name: str
    description: str
    enabled: bool = True

    # Trigger
    trigger_type: TriggerType = "cron"
    schedule: str  # Cron expression or event identifier

    # Identity & Destination
    target_character: Optional[str] = None  # Character profile ID
    destination_channel: str
    destination_chat_id: str

    # Execution
    content_prompt: str  # The prompt or instruction to execute
    allowed_tools: List[str] = Field(default_factory=list)
    approval_policy: Literal["always", "never", "risky_only"] = "risky_only"

    # Proactive configuration
    quiet_hours: RoutineQuietHours = Field(default_factory=RoutineQuietHours)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    last_run_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
