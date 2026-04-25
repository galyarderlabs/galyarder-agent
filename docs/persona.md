# Persona & Identity

g-agent is built for agentic digital identity: a way to preserve and operate
the character layer of a person, companion, operator, fictional persona, or
future self.

Humans are temporary. Bodies age, time disappears, and people eventually leave.
But memory, values, taste, love, mission, voice, rituals, and the way someone
sees the world can continue when they are remembered and given a living digital
form.

The character can be yourself as an agent, someone you love, an agentic
girlfriend, a personal operator, a creative companion, an idol, a fictional
persona, or the best version of the person you are trying to become. The point
is continuity: the same identity can remember you, speak in a stable voice, send
contextual selfies or mirror photos, and act inside the workflows you allow.

Use this system only for personas you own, created, or have clear permission to
represent. For public or shared deployments, make the character identity clear
and avoid impersonating real people without consent.

## Character Layers

| Layer | What it controls |
|-------|------------------|
| Identity | Name, origin, values, mission, relationship to the user, boundaries |
| Memory | Durable facts, preferences, projects, relationship context, lived history |
| Presence | WhatsApp, Telegram, Discord, Email, CLI, and other approved channel behavior |
| Visuals | Physical description, LoRA trigger, selfie and mirror-photo style |
| Voice | TTS voice and spoken-message behavior |
| Tools | Files, shell, Google Workspace, media, schedules, and workflow packs |

## Workspace Files

All persona files live in `~/.g-agent/workspace/`:

| File | Purpose |
|------|---------|
| `SOUL.md` | Core identity: personality, values, visual identity rules |
| `AGENTS.md` | Agent instructions, guidelines, and behavior constraints |
| `USER.md` | User preferences (timezone, language, communication style) |
| `memory/PROFILE.md` | Agent's identity fields (name, timezone, language) |
| `TOOLS.md` | Tool-specific instructions and constraints |
| `HEARTBEAT.md` | Proactive action rules (scheduled messages, reminders) |
| `memory/MEMORY.md` | Long-term facts persisted across sessions |

These files are created automatically by `g-agent onboard` with sensible
defaults. Edit them to shape the character.

## Character Patterns

Common builds:

- **Agentic yourself**: preserves your tone, priorities, values, work style, memory, and decision patterns.
- **Digital legacy**: turns a life, mission, relationship, or worldview into an identity that can keep speaking and acting.
- **Personal operator**: remembers your projects, prepares briefs, manages tasks, and speaks in your preferred cadence.
- **Companion character**: understands your emotional style, keeps long-term context, sends voice notes or selfies, and stays bounded by your rules.
- **Agentic girlfriend**: a relationship-style companion with memory, voice notes, visual identity, and explicit boundaries you define.
- **Fictional persona**: a designed character with its own face, voice, backstory, and workflow role.

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

Visual identity can be anchored in two ways:

- **LoRA trigger**: best for a dedicated character with a trained visual style.
- **Reference description**: use a reference image once, extract physical traits, then generate future images from the description.

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
