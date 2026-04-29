"""Routine model for G-Agent."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


TriggerType = Literal["cron", "webhook", "api_event", "file_change"]


class RoutineQuietHours(BaseModel):
    """Quiet hours configuration for a routine."""

    enabled: bool = False
    start_time: str = "22:00"  # HH:MM
    end_time: str = "08:00"  # HH:MM
    timezone: str = "UTC"


class RoutineScript(BaseModel):
    """Optional pre-turn script whose stdout becomes routine context."""

    enabled: bool = False
    command: list[str] = Field(default_factory=list)
    cwd: str | None = None
    timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    max_output_chars: int = Field(default=4000, gt=0, le=50000)


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
    target_character: str | None = None  # Character profile ID
    destination_channel: str
    destination_chat_id: str

    # Execution
    content_prompt: str  # The prompt or instruction to execute
    allowed_tools: list[str] = Field(default_factory=list)
    approval_policy: Literal["always", "never", "risky_only"] = "risky_only"
    script: RoutineScript = Field(default_factory=RoutineScript)

    # Proactive configuration
    quiet_hours: RoutineQuietHours = Field(default_factory=RoutineQuietHours)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    last_run_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
