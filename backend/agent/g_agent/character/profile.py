"""Character profile model for G-Agent."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VisualIdentityConfig(BaseModel):
    """Configuration for character's visual identity."""
    reference_images: List[str] = Field(default_factory=list)
    base_description: str = ""
    lora_trigger: Optional[str] = None
    outfit_presets: Dict[str, str] = Field(default_factory=dict)
    scene_presets: Dict[str, str] = Field(default_factory=dict)


class CharacterProfile(BaseModel):
    """
    A character profile defines the agent's identity, voice, 
    and behavioral boundaries.
    """
    id: str
    name: str
    role: str
    kind: str = "agentic_identity"
    voice: str = "Direct and helpful"
    tone: str = "Professional yet approachable"
    boundaries: List[str] = Field(default_factory=list)
    relationship_model: str = "Owner and Agent"
    visual_identity: VisualIdentityConfig = Field(default_factory=VisualIdentityConfig)
    channel_behavior: Dict[str, Any] = Field(default_factory=dict)
    proactive_policy: str = "opt-in"
    tool_policy: str = "ask_for_risky"
    memory_policy: str = "remember_facts"
    metadata: Dict[str, Any] = Field(default_factory=dict)
