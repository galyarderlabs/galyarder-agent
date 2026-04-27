"""Built-in command handlers for G-Agent."""

import time
import re
from typing import Any

from g_agent.command.context import CommandContext
from g_agent.session.manager import SessionManager


def _fmt_time(ts: float) -> str:
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))


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
    task_files = sorted(store.tasks_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not task_files:
        return "📄 No logs found."

    lines = ["📄 <b>Recent Activity</b>\n"]
    for path in task_files[:5]: # Show last 5 tasks
        task = store._safe_read(path)
        if not task:
            continue

        status_emoji = "✅" if task["status"] == "ok" else "❌" if task["status"] == "error" else "⏳"
        created = task["created_at"].split("T")[-1][:5] # Just HH:MM

        lines.append(f"{status_emoji} <code>{created}</code> {task['kind']} — <i>{task['status']}</i>")
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
        ts = _fmt_time(row['updated_at'])
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
            [{"text": "📄 View Profile", "data": "/memory"}],
        ],
    }


def register_builtin_commands(router: Any):
    """Register all built-in commands to a router."""
    router.register("status", cmd_status, description="System diagnostics")
    router.register("logs", cmd_logs, description="View recent activity logs")
    router.register("history", cmd_history, aliases=["hists"], description="Search session history", usage="<query>")
    router.register("sessions", cmd_sessions, description="List recent sessions")
    router.register("new", cmd_new, aliases=["reset"], description="Start fresh")
    router.register("whoami", cmd_whoami, description="Your profile info")
