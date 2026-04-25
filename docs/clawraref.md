# Clawra Reference Archive

This page is kept only as a historical pointer to the old Clawra adoption
research. The previous long blueprint was removed from the active docs because
it still described stale provider assumptions and implementation steps that no
longer match the current Galyarder Agent direction.

Current source of truth:

- `README.md`: product identity, philosophy, and front-door overview
- [Persona](persona.md): agentic character model and identity layers
- [Configuration](configuration.md): current model, channel, Google Workspace, and visual identity setup
- [Channels](channels.md): current channel setup
- `ROADMAP.md`: active product direction
- [Hermes and Nanobot Reference Audit](reports/hermes-nanobot-reference-audit.md): current reference audit

What remains useful from the old Clawra research:

- Visual identity matters because a character should not be only text.
- Selfie and mirror-photo generation should be treated as an identity feature,
  not a novelty image command.
- Reference-photo, manual-description, and LoRA-trigger paths are different
  identity anchors with different consistency tradeoffs.
- Image generation providers should stay OpenAI-compatible where possible, so a
  local proxy can route to models such as `gpt-image-2`.

Superseded assumptions:

- Nebius-specific text-to-image setup is no longer documented as a current path.
- Provider comparisons from the old blueprint are stale.
- The old file list and test plan are replaced by the current runtime, docs, and
  roadmap.
