# Persona & Identity

g-agent supports a persona system that gives the AI agent a consistent identity,
visual appearance, and voice across conversations.

## Workspace Files

All persona files live in `~/.g-agent/workspace/`:

| File | Purpose |
|------|---------|
| `SOUL.md` | Core identity: personality, values, visual identity rules |
| `AGENTS.md` | Agent instructions, guidelines, and behavior constraints |
| `USER.md` | User preferences (timezone, language, communication style) |
| `memory/PROFILE.md` | Agent's identity fields (name, timezone, language) |
| `memory/MEMORY.md` | Long-term facts persisted across sessions |

These files are created automatically by `g-agent onboard` with sensible defaults.
Edit them to customize the agent's persona.

## SOUL.md Structure

The soul file defines who the agent *is*. Key sections:

```markdown
# Soul

## Personality
- (traits)

## Values
- (values)

## Visual Identity
- Hard rules against denying physical existence
- When to send selfies (with `caption` parameter)
- When NOT to send selfies (identity questions, technical queries)
```

### Visual Identity

When `visual.enabled` is `true` in config, the agent can generate selfie photos
using the `selfie` tool.

**Selfie tool parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `context` | Yes | Scene description for image generation |
| `caption` | Yes | Short text sent WITH the photo |
| `mode` | No | `mirror`, `direct`, or `auto` |

The `caption` is the only text the user sees — no follow-up message is sent
after the photo.

## AGENTS.md

Agent-level instructions that control behavior. Defaults to:

```markdown
# Agent Instructions

You are g-agent. Be concise, accurate, and practical.
```

Override this to set a custom name, persona, and constraints.

## TTS (Text-to-Speech)

The `message` tool supports synthesizing voice notes using edge-tts
(Microsoft Neural TTS) with espeak-ng as a fallback.

### Configuration

Set the voice in `config.json`:

```json
{
  "tools": {
    "ttsVoice": "id-ID-GadisNeural"
  }
}
```

### Available voices

Run `edge-tts --list-voices` to see all available voices. Common options:

| Voice | Language | Gender |
|-------|----------|--------|
| `id-ID-GadisNeural` | Indonesian | Female |
| `id-ID-ArdiNeural` | Indonesian | Male |
| `en-US-JennyNeural` | English (US) | Female |
| `en-US-GuyNeural` | English (US) | Male |
| `en-GB-SoniaNeural` | English (UK) | Female |
| `ja-JP-NanamiNeural` | Japanese | Female |
| `ko-KR-SunHiNeural` | Korean | Female |

### Fallback

If edge-tts is not installed, the tool falls back to espeak-ng (robotic quality).
Install edge-tts for natural-sounding voice notes:

```bash
pip install edge-tts
```

## Privacy

Persona files (`SOUL.md`, `AGENTS.md`, `USER.md`, `memory/*`) are stored locally
in `~/.g-agent/workspace/` and are **never** committed to the project repository.
The repo only contains the default *templates* in the onboard CLI.
