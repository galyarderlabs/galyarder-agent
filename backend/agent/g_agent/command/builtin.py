"""Built-in command handlers for G-Agent."""

import time
import re
import json
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
        pending = queue.list_pending()
        if not pending:
            return "🧠 <b>Learning Queue</b> is empty. No candidates for review."

        lines = [f"🧠 <b>Learning Queue ({len(pending)})</b>\n"]
        for c in pending:
            lines.append(f"• <code>{c.id}</code> — <b>{c.title}</b> (<i>{c.kind}</i>)")
        return "\n".join(lines)

    if subcmd in ["approve", "reject"] and len(args) > 1:
        candidate_id = args[1]
        c = queue.get(candidate_id)
        if not c:
            return f"❌ Candidate <code>{candidate_id}</code> not found."

        status = "approved" if subcmd == "approve" else "rejected"
        queue.update_status(candidate_id, status)

        # If it's a skill candidate and approved, activate it
        if status == "approved" and c.kind == "skill":
            from g_agent.skills.manager import SkillManager

            skills = SkillManager(ctx.workspace)
            skill_name = c.content.get("name")
            if skill_name:
                ok, errors = skills.activate_skill(skill_name)
                if ok:
                    return f"✅ Candidate <code>{candidate_id}</code> approved and skill <b>{skill_name}</b> activated."
                else:
                    return "⚠️ Candidate approved but skill activation failed:\n" + "\n".join(
                        f"- {e}" for e in errors
                    )

        return f"✅ Candidate <code>{candidate_id}</code> marked as <b>{status}</b>."

    if subcmd == "info" and len(args) > 1:
        candidate_id = args[1]
        c = queue.get(candidate_id)
        if not c:
            return f"❌ Candidate <code>{candidate_id}</code> not found."

        lines = [f"🧠 <b>Learning Candidate: {c.title}</b>\n"]
        lines.append(f"<code>Kind     : {c.kind}</code>")
        lines.append(f"<code>Rationale: {c.rationale}</code>")
        lines.append(f"<code>Session  : {c.source_session or 'n/a'}</code>")
        lines.append("\n<b>Proposed Change</b>")
        lines.append(f"<pre>{json.dumps(c.content, indent=2)}</pre>")
        return "\n".join(lines)

    return "⚠️ Usage: /learn [list|approve <id>|reject <id>|info <id>]"


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
        usage="[list|approve|reject <id>]",
    )
    router.register(
        "routines", cmd_routines, description="Manage background tasks", usage="[list|enable|disable <id>]"
    )
