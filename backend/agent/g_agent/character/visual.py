"""Visual identity mapping for character profiles."""

from typing import Any, Dict
from g_agent.character.profile import CharacterProfile


def get_visual_config(profile: CharacterProfile) -> Dict[str, Any]:
    """
    Map character profile visual settings to a flat config dict
    suitable for the selfie tool.
    """
    cfg = profile.visual_identity
    return {
        "base_description": cfg.base_description,
        "lora_trigger": cfg.lora_trigger,
        "reference_images": cfg.reference_images,
        "outfit_presets": cfg.outfit_presets,
        "scene_presets": cfg.scene_presets,
        "character_name": profile.name,
    }
