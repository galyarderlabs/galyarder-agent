"""Tests for character profile persistence."""

from pathlib import Path

from g_agent.character.store import CharacterStore


def test_setup_default_profiles_does_not_overwrite_existing_profiles(tmp_path: Path):
    """Default owner/guest setup preserves local edits."""
    store = CharacterStore(tmp_path)
    owner, guest = store.setup_default_profiles()

    owner.voice = "Custom owner voice"
    guest.boundaries.append("Custom guest boundary.")
    store.save(owner)
    store.save(guest)

    owner_after, guest_after = store.setup_default_profiles()

    assert owner_after.voice == "Custom owner voice"
    assert "Custom guest boundary." in guest_after.boundaries
    assert owner_after.is_guest is False
    assert guest_after.is_guest is True
