"""Predefined workflow packs for proactive, multi-tool task execution."""

from __future__ import annotations

import re

PACK_ALIASES = {
    "daily": "daily_brief",
    "brief": "daily_brief",
    "dailybrief": "daily_brief",
    "meeting": "meeting_prep",
    "prep": "meeting_prep",
    "inbox": "inbox_zero_batch",
    "inboxzero": "inbox_zero_batch",
    "inboxzerobatch": "inbox_zero_batch",
}

PACK_SPEC = {
    "daily_brief": {
        "objective": "Prepare a concise daily execution brief from calendar, inbox, and memory.",
        "instructions": [
            "Call `calendar_list_events` for today's schedule and key meetings.",
            "Call `gmail_list_threads` for unread/high-priority threads.",
            "Call `recall` for relevant priorities, blockers, and commitments.",
            "If needed, call `web_search` for one external context check.",
            "Output format: Top 3 priorities, schedule risks, inbox actions, next focus block.",
        ],
    },
    "meeting_prep": {
        "objective": "Assemble a focused meeting prep note with agenda, risks, and follow-ups.",
        "instructions": [
            "Call `calendar_list_events` and identify the target meeting from provided context.",
            "Call `gmail_list_threads` and `gmail_read_thread` for related discussion context.",
            "Call `recall` for prior decisions, relationship notes, and open commitments.",
            "Output format: Meeting goal, talking points, decisions needed, red flags, follow-up checklist.",
        ],
    },
    "inbox_zero_batch": {
        "objective": "Create a practical inbox-zero batch plan with reply priorities.",
        "instructions": [
            "Call `gmail_list_threads` for unread threads and cluster by urgency.",
            "Call `gmail_read_thread` only for top priority threads to reduce latency.",
            "Use `recall` for sender context and existing commitments before drafting actions.",
            "Optionally call `gmail_draft` for top 3 replies if user asks to proceed.",
            "Output format: Urgent-now, Today, Delegate/Later, Suggested reply drafts.",
        ],
    },
}


def list_workflow_packs() -> list[str]:
    """List supported workflow pack names."""
    return sorted(PACK_SPEC.keys())


def _normalize_pack_name(name: str) -> str:
    raw = (name or "").strip().lower()
    if not raw:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_")


def _canonical_pack_name(name: str) -> str | None:
    normalized = _normalize_pack_name(name)
    if not normalized:
        return None
    if normalized in PACK_SPEC:
        return normalized
    alias = PACK_ALIASES.get(normalized)
    if alias in PACK_SPEC:
        return alias
    return None


def resolve_workflow_pack_request(content: str) -> tuple[str, str] | None:
    """Parse explicit pack intents from user message."""
    text = (content or "").strip()
    if not text:
        return None

    patterns = (
        r"^/pack\s+([a-zA-Z0-9_\-]+)(?:\s+(.+))?$",
        r"^(?:run|jalankan|jalanin)\s+(?:workflow\s+)?pack\s+([a-zA-Z0-9_\-]+)(?:\s+(.+))?$",
        r"^workflow(?:\s+pack)?\s+([a-zA-Z0-9_\-]+)(?:\s+(.+))?$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        pack_name = _canonical_pack_name(match.group(1))
        if not pack_name:
            return None
        user_context = (match.group(2) or "").strip()
        return pack_name, user_context
    return None


def build_workflow_pack_prompt(pack_name: str, user_context: str = "") -> str:
    """Build execution prompt for a workflow pack."""
    canonical = _canonical_pack_name(pack_name)
    if not canonical:
        return ""
    spec = PACK_SPEC[canonical]
    cleaned_context, flags = _extract_pack_flags(user_context)
    lines = [
        f"Workflow Pack: {canonical}",
        f"Objective: {spec['objective']}",
        "",
        "Execution rules:",
        "- Use available tools directly; do not ask for permission unless policy blocks a tool.",
        "- If a required tool is unavailable, continue with best-effort fallback and state the gap.",
        "- Be concise and action-oriented.",
        "",
        "Steps:",
    ]
    lines.extend([f"- {instruction}" for instruction in spec["instructions"]])
    delivery_modes = _select_delivery_modes(flags)
    if delivery_modes:
        lines.extend(["", "Delivery mode:"])
        if len(delivery_modes) == 1:
            mode = delivery_modes[0]
            lines.append(f"- {_delivery_mode_label(mode)} requested.")
            lines.append("- After preparing the brief, call `message` tool exactly once with:")
            lines.append(f"  1) {_delivery_mode_instruction(mode)}")
        else:
            labels = ", ".join(f"`--{mode}`" for mode in delivery_modes)
            lines.append(f"- Multi mode requested ({labels}).")
            lines.append(
                f"- After preparing the brief, call `message` tool exactly {len(delivery_modes)} times:"
            )
            for index, mode in enumerate(delivery_modes, start=1):
                lines.append(f"  {index}) {_delivery_mode_instruction(mode)}")
        lines.append(
            "- If any media generation/policy block happens, return text fallback and explain which mode failed."
        )
        if "silent" in flags:
            lines.append(
                "- Silent mode requested (`--silent`): avoid extra narrative text once media delivery succeeds."
            )
    elif "silent" in flags:
        lines.extend([
            "",
            "Delivery mode:",
            "- `--silent` was requested without media mode; ignore silent mode and return normal text brief.",
        ])
    if cleaned_context:
        lines.extend(["", f"User context: {cleaned_context}"])
    lines.extend(["", "Return a final brief with clear next actions."])
    return "\n".join(lines)


def _extract_pack_flags(user_context: str) -> tuple[str, set[str]]:
    """Parse lightweight workflow flags from user context."""
    text = (user_context or "").strip()
    if not text:
        return "", set()

    flags: set[str] = set()
    tokens = []
    for token in text.split():
        normalized = token.strip().lower()
        if normalized == "--voice":
            flags.add("voice")
            continue
        if normalized == "--image":
            flags.add("image")
            continue
        if normalized == "--sticker":
            flags.add("sticker")
            continue
        if normalized == "--silent":
            flags.add("silent")
            continue
        tokens.append(token)

    cleaned = " ".join(tokens).strip()
    return cleaned, flags


def _select_delivery_modes(flags: set[str]) -> list[str]:
    """Select ordered delivery modes from parsed flags."""
    modes: list[str] = []
    for mode in ("sticker", "image", "voice"):
        if mode in flags:
            modes.append(mode)
    return modes


def _delivery_mode_label(mode: str) -> str:
    """Human-readable mode label."""
    if mode == "voice":
        return "Voice mode (`--voice`)"
    if mode == "image":
        return "Image mode (`--image`)"
    if mode == "sticker":
        return "Sticker mode (`--sticker`)"
    return f"Mode (`--{mode}`)"


def _delivery_mode_instruction(mode: str) -> str:
    """Instruction line for message tool call by mode."""
    if mode == "voice":
        return "`media_type`: `voice` with concise spoken summary (<= 120 words)."
    if mode == "image":
        return "`media_type`: `image` with short card text (headline + key bullets, <= 140 words)."
    if mode == "sticker":
        return "`media_type`: `sticker` with very short punchline (<= 16 words)."
    return f"`media_type`: `{mode}` with concise summary."


def extract_workflow_pack_flags(user_context: str) -> set[str]:
    """Public helper to inspect workflow pack flags."""
    _, flags = _extract_pack_flags(user_context)
    return set(flags)
