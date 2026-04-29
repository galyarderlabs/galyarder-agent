"""Built-in command handlers for G-Agent."""

import html
import json
import re
import time
from typing import Any

from g_agent.command.context import CommandContext
from g_agent.session.manager import SessionManager


def _fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def _redact(text: str) -> str:
    """Redact obvious secret-like values before showing logs in chat."""
    redacted = text or ""
    redacted = re.sub(
        r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization)\s*[:=]\s*['\"]?[^'\"\s]+",
        lambda m: f"{m.group(1)}=<redacted>",
        redacted,
    )
    redacted = re.sub(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{12,}", "Bearer <redacted>", redacted)
    redacted = re.sub(r"\bsk-[a-zA-Z0-9]{16,}", "sk-<redacted>", redacted)
    return redacted


async def cmd_status(ctx: CommandContext) -> str:
    """System diagnostics."""
    lines = []
    lines.append("🤖 <b>G-Agent</b>")

    # Model
    model = ctx.metadata.get("model_name", "unknown")
    lines.append(f"🧠 Model: <code>{model}</code>")

    # Channel capability contract
    try:
        from g_agent.channels.manager import ChannelManager
        cm = ChannelManager(ctx.config, None) # Transient manager to check status
        # Better: if we had access to the live manager, but we don't here.
        # We'll use the capabilities helper for now as a fallback.
        from g_agent.channels.capabilities import capabilities_for_channel

        caps = capabilities_for_channel(ctx.channel)
        lines.append(f"📡 Channel: <code>{ctx.channel}</code> · {html.escape(caps.summary())}")
    except Exception:
        lines.append(f"📡 Channel: <code>{ctx.channel}</code>")

    # Session
    sessions = SessionManager(ctx.workspace)
    session = sessions.get_or_create(ctx.session_key)
    lines.append(f"🧵 Session: <code>{ctx.session_key}</code> · {len(session.messages)} msgs")

    # Memory
    try:
        from g_agent.agent.memory import MemoryStore

        memory = MemoryStore(ctx.workspace)
        facts = memory._load_fact_index()
        lines.append(f"🧠 Memory: {len(facts)} facts stored")
    except Exception:
        pass

    return "\n".join(lines)


async def cmd_diagnostics(ctx: CommandContext) -> str:
    """Detailed channel and system diagnostics."""
    lines = []
    lines.append("🔍 <b>System Diagnostics</b>")

    manager = ctx.metadata.get("live_manager")
    if not manager:
        return "⚠️ Live channel manager not available in this context."

    status_map = manager.get_status()
    for name, status in status_map.items():
        lines.append(f"\n📡 <b>{name.upper()}</b>")
        for key, value in status.items():
            if key == "name":
                continue
            lines.append(f"• {key}: <code>{value}</code>")

    return "\n".join(lines)


async def cmd_logs(ctx: CommandContext) -> str:
    """View recent task execution logs."""
    from g_agent.agent.runtime import TaskCheckpointStore

    store = TaskCheckpointStore(ctx.workspace)
    # Get all task files, sorted by newest first
    task_files = sorted(
        store.tasks_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    if not task_files:
        return "📄 No logs found."

    lines = ["📄 <b>Recent Activity</b>\n"]
    for path in task_files[:5]:  # Show last 5 tasks
        task = store._safe_read(path)
        if not task:
            continue

        status_emoji = (
            "✅" if task["status"] == "ok" else "❌" if task["status"] == "error" else "⏳"
        )
        created = task["created_at"].split("T")[-1][:5]  # Just HH:MM

        lines.append(
            f"{status_emoji} <code>{created}</code> {task['kind']} — <i>{task['status']}</i>"
        )
        if task.get("input_preview"):
            preview = _redact(str(task["input_preview"]))[:60]
            lines.append(f"   <pre>In: {preview}...</pre>")
        if task.get("error"):
            error = _redact(str(task["error"]))[:100]
            lines.append(f"   ⚠️ <code>{error}</code>")

    return "\n".join(lines)


async def cmd_history(ctx: CommandContext) -> str:
    """Search session history."""
    if not ctx.args:
        return "⚠️ Usage: /history <query>"

    sessions = SessionManager(ctx.workspace)
    results = sessions.sqlite_store.search_messages(ctx.args, limit=5)

    if not results:
        return f"🔍 No history found for: <code>{ctx.args}</code>"

    lines = [f"📜 <b>History: {ctx.args}</b>\n"]
    for res in results:
        role = res["role"].upper()
        content = res["content"][:150].replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"• [{res['channel']}] <b>{role}</b>: {content}")

    return "\n\n".join(lines)


async def cmd_sessions(ctx: CommandContext) -> str:
    """List recent sessions."""
    sessions = SessionManager(ctx.workspace)
    rows = sessions.sqlite_store.list_sessions(limit=10)

    if not rows:
        return "🧵 No sessions found."

    lines = ["🧵 <b>Recent Sessions</b>\n"]
    for row in rows:
        ts = _fmt_time(row["updated_at"])
        lines.append(f"• <code>{row['key']}</code> — <i>{ts} ({row['message_count']} msgs)</i>")

    return "\n".join(lines)


async def cmd_new(ctx: CommandContext) -> str:
    """Start a new session."""
    sessions = SessionManager(ctx.workspace)
    session = sessions.get_or_create(ctx.session_key)
    msg_count = len(session.messages)

    if msg_count > 0:
        sessions.archive(ctx.session_key)
        model = ctx.metadata.get("model_name", "unknown")
        return (
            f"✅ <b>New session started</b> · model: <code>{model}</code>\n"
            f"<i>Archived {msg_count} messages.</i>"
        )
    return "✅ <b>Session already empty.</b>"


async def cmd_insights(ctx: CommandContext) -> str:
    """Generate session usage and cost insights."""
    from g_agent.observability.insights import InsightsEngine

    sessions = SessionManager(ctx.workspace)
    engine = InsightsEngine(sessions.sqlite_store, workspace=ctx.workspace)

    days = 30
    if ctx.args:
        try:
            days = int(ctx.args.strip())
        except ValueError:
            pass

    report = engine.generate(days=days)
    return engine.format_gateway(report)


async def cmd_whoami(ctx: CommandContext) -> dict:
    """Current identity info."""
    lines = ["🧭 <b>Identity</b>\n"]
    lines.append(f"<code>Channel : {ctx.channel}</code>")
    lines.append(f"<code>User ID : {ctx.user_id or ctx.chat_id}</code>")
    if ctx.username:
        lines.append(f"<code>Username: @{ctx.username}</code>")
    lines.append(f"<code>Session : {ctx.session_key}</code>")

    return {
        "text": "\n".join(lines),
        "buttons": [
            [{"text": "📄 View Profile", "data": "/profile"}],
        ],
    }


async def cmd_profile(ctx: CommandContext) -> str:
    """Manage character profiles."""
    from g_agent.character.store import CharacterStore

    store = CharacterStore(ctx.workspace)

    args = ctx.args.strip().split()
    subcmd = args[0] if args else "view"

    if subcmd == "list":
        profiles = store.list()
        lines = ["🎭 <b>Available Profiles</b>\n"]
        for p in profiles:
            lines.append(f"• <code>{p.id}</code> — <b>{p.name}</b> (<i>{p.role}</i>)")
        return "\n".join(lines)

    if subcmd == "set" and len(args) > 1:
        profile_id = args[1]
        p = store.get(profile_id)
        if not p:
            return f"❌ Profile <code>{profile_id}</code> not found."

        # Note: Actual switching needs to be handled by the loop/gateway
        # For now we just confirm it exists. In a real scenario, we'd
        # update a 'current_profile' setting in config.
        return f"✅ Profile set to <b>{p.name}</b> (<code>{p.id}</code>).\n<i>Note: New settings will apply to the next message.</i>"

    # View current (this is tricky without loop reference in ctx,
    # but we can show default or first one)
    p = store.get_default()
    lines = [f"👤 <b>Active Profile: {p.name}</b>\n"]
    lines.append(f"<code>Role : {p.role}</code>")
    lines.append(f"<code>Voice: {p.voice}</code>")
    lines.append(f"<code>Tone : {p.tone}</code>")

    if p.boundaries:
        lines.append("\n<b>Boundaries</b>")
        for b in p.boundaries:
            lines.append(f"• {b}")

    return "\n".join(lines)


async def cmd_learn(ctx: CommandContext) -> str:
    """Manage the learning queue."""
    from g_agent.learning.queue import LearningQueue

    queue = LearningQueue(ctx.workspace)

    args = ctx.args.strip().split()
    subcmd = args[0] if args else "list"

    if subcmd == "list":
        status_filter = args[1] if len(args) > 1 else "pending"
        candidates = queue.list(status=status_filter if status_filter != "all" else None)
        if not candidates:
            return f"🧠 <b>Learning Queue</b> has no <code>{status_filter}</code> candidates."

        lines = [f"🧠 <b>Learning Queue ({len(candidates)} {status_filter})</b>\n"]
        for c in candidates:
            lines.append(
                f"• <code>{c.id}</code> — <b>{c.title}</b> "
                f"(<i>{c.kind}</i>, <code>{c.status}</code>)"
            )
        return "\n".join(lines)

    if subcmd in ["approve", "reject"] and len(args) > 1:
        candidate_id = args[1]
        c = queue.get(candidate_id)
        if not c:
            return f"❌ Candidate <code>{candidate_id}</code> not found."

        status = "approved" if subcmd == "approve" else "rejected"
        queue.update_status(candidate_id, status)
        return f"✅ Candidate <code>{candidate_id}</code> marked as <b>{status}</b>."

    if subcmd == "edit" and len(args) > 2:
        candidate_id = args[1]
        c = queue.get(candidate_id)
        if not c:
            return f"❌ Candidate <code>{candidate_id}</code> not found."

        raw_payload = ctx.args.split(maxsplit=2)[2]
        try:
            content = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            return f"❌ Invalid JSON payload: <code>{exc}</code>"
        if not isinstance(content, dict):
            return "❌ Edit payload must be a JSON object."
        if queue.update_content(candidate_id, content, diff_preview="Edited by owner command."):
            return f"✅ Candidate <code>{candidate_id}</code> updated."
        return f"❌ Candidate <code>{candidate_id}</code> could not be edited."

    if subcmd in {"apply", "rollback"} and len(args) > 1:
        from g_agent.skills.manager import SkillManager

        candidate_id = args[1]
        c = queue.get(candidate_id)
        if not c:
            return f"❌ Candidate <code>{candidate_id}</code> not found."
        if c.kind != "skill":
            return f"⚠️ <code>{subcmd}</code> currently supports skill candidates only."

        skill_name = c.content.get("name")
        if not isinstance(skill_name, str) or not skill_name.strip():
            return f"❌ Candidate <code>{candidate_id}</code> is missing skill <code>name</code>."

        skills = SkillManager(ctx.workspace)

        if subcmd == "rollback":
            if c.status != "applied":
                return f"⚠️ Candidate <code>{candidate_id}</code> is not applied."
            ok, errors = skills.rollback_activation(skill_name, activation_id=candidate_id)
            if not ok:
                return "⚠️ Skill rollback failed:\n" + "\n".join(f"- {e}" for e in errors)
            queue.update_status(candidate_id, "rolled_back")
            return (
                f"↩️ Candidate <code>{candidate_id}</code> rolled back and skill "
                f"<b>{skill_name}</b> restored."
            )

        from g_agent.learning.apply import apply_learning_candidate

        result = apply_learning_candidate(ctx.workspace, candidate_id)
        if not result.ok:
            if result.code == "invalid_status":
                return f"⚠️ Candidate <code>{candidate_id}</code> cannot be applied from {c.status}."
            if result.code == "draft_validation_failed":
                return "⚠️ Skill draft validation failed:\n" + "\n".join(
                    f"- {e}" for e in result.errors
                )
            if result.code == "activation_failed":
                return "⚠️ Skill activation failed:\n" + "\n".join(
                    f"- {e}" for e in result.errors
                )
            return f"⚠️ {result.message}"
        return (
            f"✅ Candidate <code>{candidate_id}</code> applied and skill "
            f"<b>{skill_name}</b> activated."
        )

    if subcmd == "info" and len(args) > 1:
        candidate_id = args[1]
        c = queue.get(candidate_id)
        if not c:
            return f"❌ Candidate <code>{candidate_id}</code> not found."

        lines = [f"🧠 <b>Learning Candidate: {c.title}</b>\n"]
        lines.append(f"<code>Kind     : {c.kind}</code>")
        lines.append(f"<code>Rationale: {c.rationale}</code>")
        lines.append(f"<code>Session  : {c.source_session or 'n/a'}</code>")
        if c.applied_at:
            lines.append(f"<code>Applied  : {c.applied_at.isoformat()}</code>")
        lines.append("\n<b>Proposed Change</b>")
        lines.append(f"<pre>{json.dumps(c.content, indent=2)}</pre>")
        if c.metadata:
            lines.append("\n<b>Metadata</b>")
            lines.append(f"<pre>{json.dumps(c.metadata, indent=2)}</pre>")
        return "\n".join(lines)

    return (
        "⚠️ Usage: /learn "
        "[list [pending|approved|rejected|applied|rolled_back|all]|info <id>|"
        "approve <id>|reject <id>|edit <id> <json>|apply <id>|rollback <id>]"
    )


async def cmd_skills(ctx: CommandContext) -> str:
    """Inspect and patch procedural skills."""
    from g_agent.skills.manager import SkillManager

    manager = SkillManager(ctx.workspace)
    args = ctx.args.strip().split()
    subcmd = args[0] if args else "list"

    if subcmd == "list":
        location = args[1] if len(args) > 1 else "all"
        groups = manager.list_all(include_drafts=True)
        if location != "all":
            key = "drafts" if location in {"draft", "drafts"} else location
            if key not in groups:
                return "⚠️ Usage: /skills list [all|builtin|custom|drafts]"
            groups = {key: groups.get(key, [])}

        lines = ["🧰 <b>Skills</b>\n"]
        for key in ("custom", "drafts", "builtin"):
            if key not in groups:
                continue
            names = groups.get(key) or []
            if names:
                lines.append(
                    f"<b>{key}</b>: "
                    + ", ".join(f"<code>{html.escape(name)}</code>" for name in names)
                )
            else:
                lines.append(f"<b>{key}</b>: <i>none</i>")
        return "\n".join(lines)

    if subcmd == "view" and len(args) > 1:
        name = args[1]
        location = args[2] if len(args) > 2 else "custom"
        if location == "drafts":
            location = "draft"
        path = manager.store.get_skill_path(name, location=location)
        display_name = html.escape(name)
        display_location = html.escape(location)
        if not path:
            return (
                f"❌ Skill <code>{display_name}</code> not found in "
                f"<code>{display_location}</code>."
            )
        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            return f"❌ Skill <code>{display_name}</code> has no SKILL.md."
        content = skill_md.read_text(encoding="utf-8")
        return (
            f"🧰 <b>Skill: {display_name}</b> (<code>{display_location}</code>)\n"
            f"<pre>{html.escape(content)}</pre>"
        )

    if subcmd == "patch-draft" and len(args) > 2:
        name = args[1]
        raw_payload = ctx.args.split(maxsplit=2)[2]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            return f"❌ Invalid JSON payload: <code>{exc}</code>"
        if not isinstance(payload, dict):
            return "❌ Patch payload must be a JSON object."

        find = payload.get("find")
        replace = payload.get("replace")
        relative_path = str(payload.get("path") or "SKILL.md")
        if not isinstance(find, str) or not isinstance(replace, str):
            return "❌ Patch payload requires string fields: find, replace."

        ok, errors = manager.patch_draft(name, find, replace, relative_path=relative_path)
        if ok:
            return f"✅ Draft skill <code>{html.escape(name)}</code> patched and validated."
        return "⚠️ Draft patch failed and was rolled back:\n" + "\n".join(
            f"- {error}" for error in errors
        )

    return "⚠️ Usage: /skills [list [all|builtin|custom|drafts]|view <name> [location]|patch-draft <name> <json>]"


async def cmd_routines(ctx: CommandContext) -> str:
    """Manage background routines."""
    from g_agent.routines.store import RoutineStore

    store = RoutineStore(ctx.workspace)

    args = ctx.args.strip().split()
    subcmd = args[0] if args else "list"

    if subcmd == "list":
        routines = store.list()
        if not routines:
            return "🕒 <b>Routines</b> list is empty."

        lines = [f"🕒 <b>Background Routines ({len(routines)})</b>\n"]
        for r in routines:
            status = "✅" if r.enabled else "❌"
            lines.append(f"{status} <code>{r.id}</code> — <b>{r.name}</b> (<i>{r.schedule}</i>)")
        return "\n".join(lines)

    if subcmd in ["enable", "disable"] and len(args) > 1:
        routine_id = args[1]
        r = store.get(routine_id)
        if not r:
            return f"❌ Routine <code>{routine_id}</code> not found."

        r.enabled = subcmd == "enable"
        store.save(r)
        return f"✅ Routine <code>{routine_id}</code> is now <b>{subcmd}d</b>."

    if subcmd == "info" and len(args) > 1:
        routine_id = args[1]
        r = store.get(routine_id)
        if not r:
            return f"❌ Routine <code>{routine_id}</code> not found."

        lines = [f"🕒 <b>Routine: {r.name}</b>\n"]
        lines.append(f"<code>ID       : {r.id}</code>")
        lines.append(f"<code>Schedule : {r.schedule}</code>")
        lines.append(f"<code>Channel  : {r.destination_channel}</code>")
        lines.append(f"<code>Character: {r.target_character or 'Default'}</code>")
        lines.append(f"<code>Enabled  : {r.enabled}</code>")
        lines.append(f"\n<b>Prompt</b>\n<i>{r.content_prompt}</i>")
        return "\n".join(lines)

    return "⚠️ Usage: /routines [list|enable <id>|disable <id>|info <id>]"


def register_builtin_commands(router: Any):
    """Register all built-in commands to a router."""
    router.register("status", cmd_status, description="System diagnostics")
    router.register("diagnostics", cmd_diagnostics, description="Detailed system diagnostics")
    router.register(
        "insights",
        cmd_insights,
        description="Generate session usage and cost insights",
        usage="[days]",
    )
    router.register("logs", cmd_logs, description="View recent activity logs")
    router.register(
        "history",
        cmd_history,
        aliases=["hists"],
        description="Search session history",
        usage="<query>",
    )
    router.register("sessions", cmd_sessions, description="List recent sessions")
    router.register("new", cmd_new, aliases=["reset"], description="Start fresh")
    router.register("whoami", cmd_whoami, description="Your profile info")
    router.register(
        "profile", cmd_profile, description="Manage character profiles", usage="[list|set <id>]"
    )
    router.register(
        "learn",
        cmd_learn,
        description="Review learning candidates",
        usage="[list|info|approve|reject|edit|apply|rollback]",
    )
    router.register(
        "skills",
        cmd_skills,
        description="Inspect and patch procedural skills",
        usage="[list|view|patch-draft]",
    )
    router.register(
        "routines",
        cmd_routines,
        description="Manage background tasks",
        usage="[list|enable|disable <id>]",
    )
