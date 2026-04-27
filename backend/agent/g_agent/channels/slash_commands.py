"""Native slash command dispatcher for channel-level interception.

Commands are handled instantly without LLM involvement.
Each handler calls real subsystem APIs and returns structured text.
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from g_agent.cron.service import CronService

# Number of commands per page for /commands pagination
_COMMANDS_PAGE_SIZE = 8


class SlashCommandDispatcher:
    """Handle slash commands with instant, deterministic responses."""

    def __init__(
        self,
        workspace: Path,
        *,
        model_name: str = "",
        brave_api_key: str = "",
        cron_service: CronService | None = None,
        tool_names: list[str] | None = None,
        version: str = "",
    ) -> None:
        self.workspace = workspace
        self.model_name = model_name or "unknown"
        self.brave_api_key = brave_api_key or os.environ.get("BRAVE_API_KEY", "")
        self.cron_service = cron_service
        self.tool_names = tool_names or []
        self.version = version or "dev"
        self._boot_time = time.monotonic()
        self._command_router = self._build_command_router()

        # Ordered command registry: (command, aliases, description, usage)
        self._registry: list[tuple[str, list[str], str, str]] = [
            # Session
            ("start", [], "Start conversation", ""),
            ("new", [], "New session (alias /reset)", ""),
            ("reset", [], "Clear context & start fresh", ""),
            ("compact", [], "Summarize current session", ""),
            ("context", [], "Current session info", ""),
            ("history", ["hists"], "Search session history", "<query>"),
            ("sessions", [], "List recent sessions", ""),
            # Info
            ("status", [], "System diagnostics", ""),
            ("whoami", [], "Your profile from memory", ""),
            ("logs", [], "View recent activity logs", ""),
            ("deny", [], "Deny pending approval", "[tool|all]"),
            ("approve", [], "Approve pending tool call", "[tool|all]"),
            ("memory", ["mem"], "View stored memories", "[query]"),
            ("model", [], "Active model", ""),
            # Tools & Integrations
            ("tools", [], "List active tools", ""),
            ("cron", [], "View scheduled jobs", ""),
            ("packs", [], "View workflow packs", ""),
            # Utility
            ("search", ["s"], "Web search", "<query>"),
            ("help", ["h"], "Quick guide", ""),
            ("commands", ["cmds"], "Full command list", "[page]"),
        ]

        self._handlers: dict[str, str] = {}
        for cmd, aliases, _, _ in self._registry:
            self._handlers[cmd] = cmd
            for alias in aliases:
                self._handlers[alias] = cmd

    async def try_handle(
        self,
        text: str,
        session_key: str,
        channel: str,
        chat_id: str,
        *,
        sender_username: str = "",
        sender_id: str = "",
    ) -> str | dict | None:
        """Try to handle text as a slash command.

        Returns response string/dict if handled, None if not a command.
        Dict format: {"text": str, "buttons": [[{"text": str, "data": str}]]}
        """
        stripped = text.strip()
        if not stripped.startswith("/"):
            return None

        raw_cmd, args = self._command_router.parse(stripped)

        # Approval replay is implemented in AgentLoop so it can execute the
        # pending tool call with the live registry. Let /approve pass through.
        if raw_cmd == "approve":
            return None

        canonical = self._handlers.get(raw_cmd)
        if canonical is None:
            return "⚠️ Unknown command. Try /commands."

        dispatch = {
            "start": lambda: self._cmd_start(),
            "new": lambda: self._cmd_reset(session_key),
            "reset": lambda: self._cmd_reset(session_key),
            "compact": lambda: self._cmd_compact(session_key),
            "context": lambda: self._cmd_context(session_key, channel, chat_id),
            "history": lambda: self._cmd_history(args),
            "sessions": lambda: self._cmd_sessions(),
            "status": lambda: self._cmd_status(session_key),
            "whoami": lambda: self._cmd_whoami(
                channel=channel, chat_id=chat_id,
                username=sender_username, user_id=sender_id,
            ),
            "logs": lambda: self._cmd_router(
                text=text,
                session_key=session_key,
                channel=channel,
                chat_id=chat_id,
                sender_username=sender_username,
                sender_id=sender_id,
            ),
            "deny": lambda: self._cmd_deny(session_key, args),
            "memory": lambda: self._cmd_memory(args),
            "model": lambda: self._cmd_model(args),
            "tools": lambda: self._cmd_tools(),
            "cron": lambda: self._cmd_cron(),
            "packs": lambda: self._cmd_packs(),
            "search": lambda: self._cmd_search(args),
            "help": lambda: self._cmd_help(),
            "commands": lambda: self._cmd_commands(args),
        }

        handler = dispatch.get(canonical)
        if handler is None:
            return None

        try:
            result = handler()
            # Support async handlers (e.g., /search)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as e:
            logger.error(f"Slash command /{raw_cmd} failed: {e}")
            return f"⚠️ Error executing /{raw_cmd}: {e}"

    # -- Session Commands --------------------------------------------------

    @staticmethod
    def _build_command_router():
        from g_agent.command.builtin import register_builtin_commands
        from g_agent.command.router import CommandRouter

        router = CommandRouter()
        register_builtin_commands(router)
        return router

    async def _cmd_router(
        self,
        *,
        text: str,
        session_key: str,
        channel: str,
        chat_id: str,
        sender_username: str = "",
        sender_id: str = "",
    ) -> str | dict | None:
        from g_agent.command.context import CommandContext

        context = CommandContext(
            workspace=self.workspace,
            channel=channel,
            chat_id=chat_id,
            session_key=session_key,
            user_id=sender_id,
            username=sender_username,
            metadata={"model_name": self.model_name},
        )
        return await self._command_router.handle(text, context)

    def _cmd_start(self) -> str:
        return "👋 <b>yo.</b> send me a message, I'm listening."

    def _cmd_reset(self, session_key: str) -> str:
        from g_agent.session.manager import SessionManager

        sessions = SessionManager(self.workspace)
        session = sessions.get_or_create(session_key)
        msg_count = len(session.messages)

        if msg_count > 0:
            sessions.archive(session_key)
            return (
                f"✅ <b>New session started</b> · model: <code>{self.model_name}</code>\n"
                f"<i>Archived {msg_count} messages.</i>"
            )
        return f"✅ <b>Session already empty.</b> · model: <code>{self.model_name}</code>"

    def _cmd_compact(self, session_key: str) -> str:
        from g_agent.session.manager import SessionManager

        sessions = SessionManager(self.workspace)
        session = sessions.get_or_create(session_key)
        msg_count = len(session.messages)

        if msg_count <= 1:
            return "📦 Session too short, nothing to compact."

        # Calculate before stats
        total_chars_before = sum(len(str(m.get("content", ""))) for m in session.messages)
        est_tokens_before = total_chars_before // 4

        # Build digest and compress
        digest = sessions._build_digest(session, max_chars=4000)
        
        # Replace history with single summary message
        session.clear()
        session.add_message(
            role="system",
            content=f"[Session compacted. Previous context:]\n\n{digest}"
        )
        sessions.save(session)
        
        # Calculate after stats
        total_chars_after = len(session.messages[0].get("content", ""))
        est_tokens_after = total_chars_after // 4

        return (
            f"📦 <b>Session Compacted</b>\n"
            f"<i>Compressed {msg_count} messages into 1 summary.</i>\n"
            f"<code>Tokens: ~{est_tokens_before:,} → ~{est_tokens_after:,}</code>"
        )

    def _cmd_context(self, session_key: str, channel: str, chat_id: str) -> dict:
        from g_agent.session.manager import SessionManager

        lines = ["📋 <b>Session Context</b>\n"]

        lines.append(f"<code>Channel : {channel}</code>")
        lines.append(f"<code>Chat ID : {chat_id}</code>")
        lines.append(f"<code>Session : {session_key}</code>")

        try:
            sessions = SessionManager(self.workspace)
            session = sessions.get_or_create(session_key)
            lines.append(f"<code>Messages: {len(session.messages)}</code>")
            lines.append(f"<code>Created : {session.created_at.strftime('%Y-%m-%d %H:%M')}</code>")
            lines.append(f"<code>Updated : {session.updated_at.strftime('%Y-%m-%d %H:%M')}</code>")
        except Exception as e:
            lines.append(f"<code>Error   : {e}</code>")

        return {
            "text": "\n".join(lines),
            "buttons": [
                [
                    {"text": "📦 Compact", "data": "/compact"},
                    {"text": "🔄 Reset", "data": "/reset"},
                    {"text": "📊 Status", "data": "/status"},
                ],
            ],
        }

    def _cmd_history(self, query: str) -> str:
        if not query:
            return "⚠️ Usage: /history <query>\n\nExample: /history 'database schema'"

        from g_agent.session.manager import SessionManager
        sessions = SessionManager(self.workspace)
        results = sessions.sqlite_store.search_messages(query, limit=5)

        if not results:
            return f"🔍 No history found for: <code>{query}</code>"

        lines = [f"📜 <b>History: {query}</b>\n"]
        for res in results:
            role = res["role"].upper()
            content = res["content"][:150].replace("<", "&lt;").replace(">", "&gt;")
            if len(res["content"]) > 150:
                content += "..."
            lines.append(
                f"• [{res['channel']}] <b>{role}</b>: {content}\n"
                f"  <i>Session: {res['session_key']}</i>"
            )

        return "\n\n".join(lines)

    def _cmd_sessions(self) -> str:
        from g_agent.session.manager import SessionManager
        sessions = SessionManager(self.workspace)
        rows = sessions.sqlite_store.list_sessions(limit=10)

        if not rows:
            return "🧵 No sessions found."

        lines = ["🧵 <b>Recent Sessions</b>\n"]
        for row in rows:
            ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(row['updated_at']))
            lines.append(f"• <code>{row['key']}</code> — <i>{ts} ({row['message_count']} msgs)</i>")

        return "\n".join(lines)

    def _cmd_deny(self, session_key: str, args: str) -> str:
        from g_agent.session.manager import SessionManager

        sessions = SessionManager(self.workspace)
        session = sessions.get_or_create(session_key)
        pending: list[dict] = session.metadata.get("pending_approvals", [])
        if not pending:
            return "✅ No pending approvals."

        target = (args or "").strip().lower()
        if not target:
            denied = [pending[0]]
            remaining = pending[1:]
        elif target == "all":
            denied = pending
            remaining = []
        else:
            denied = [item for item in pending if item.get("tool_name", "").lower() == target]
            remaining = [
                item for item in pending if item.get("tool_name", "").lower() != target
            ]
            if not denied:
                return f"✅ No pending approval for <code>{target}</code>."

        session.metadata["pending_approvals"] = remaining
        sessions.save(session)
        names = ", ".join(item.get("tool_name", "unknown") for item in denied)
        return f"🚫 Denied pending approval: <code>{names}</code>."

    # -- Info Commands -----------------------------------------------------

    def _cmd_status(self, session_key: str) -> str:
        from g_agent.session.manager import SessionManager

        lines: list[str] = []

        # Header with version
        lines.append(f"🤖 <b>Keiya</b> {self.version}")

        # Model
        lines.append(f"🧠 Model: <code>{self.model_name}</code>")

        # Uptime + Cron on one line
        uptime_s = time.monotonic() - self._boot_time
        hours = int(uptime_s // 3600)
        minutes = int((uptime_s % 3600) // 60)
        uptime_str = f"{hours}h {minutes}m"

        cron_str = "n/a"
        if self.cron_service:
            try:
                cron_status = self.cron_service.status()
                job_count = cron_status.get("jobs", 0)
                enabled = "active" if cron_status.get("enabled") else "stopped"
                cron_str = f"{job_count} jobs ({enabled})"
            except Exception:
                cron_str = "err"
        lines.append(f"⏱️ Uptime: {uptime_str} · ⏰ Cron: {cron_str}")

        # Session
        try:
            sessions = SessionManager(self.workspace)
            session = sessions.get_or_create(session_key)
            msg_count = len(session.messages)
            lines.append(f"🧵 Session: <code>{session_key}</code> · {msg_count} msgs")
        except Exception:
            lines.append(f"🧵 Session: <code>{session_key}</code>")

        # Memory + Tools on one line
        mem_str = "n/a"
        try:
            from g_agent.agent.memory import MemoryStore
            memory = MemoryStore(self.workspace)
            facts = memory._load_fact_index()
            mem_str = f"{len(facts)} facts"
        except Exception:
            pass
        lines.append(f"🧠 Memory: {mem_str} · 🔧 Tools: {len(self.tool_names)} registered")

        return "\n".join(lines)

    def _cmd_whoami(
        self,
        *,
        channel: str = "",
        chat_id: str = "",
        username: str = "",
        user_id: str = "",
    ) -> dict:
        lines = ["🧭 <b>Identity</b>\n"]
        lines.append(f"<code>Channel : {channel or 'unknown'}</code>")
        # user_id may contain "id|username" format from telegram
        clean_id = user_id.split("|")[0] if user_id else chat_id
        lines.append(f"<code>User ID : {clean_id}</code>")
        if username:
            lines.append(f"<code>Username: @{username}</code>")
        lines.append(f"<code>Session : {channel}:{chat_id}</code>")

        return {
            "text": "\n".join(lines),
            "buttons": [
                [{"text": "📄 View Profile", "data": "/memory"}],
            ],
        }

    def _cmd_memory(self, query: str) -> str:
        from g_agent.agent.memory import MemoryStore

        memory = MemoryStore(self.workspace)
        sections: list[str] = []

        # Profile summary
        profile = memory.read_profile().strip()
        if profile:
            preview = profile[:500].replace("<", "&lt;").replace(">", "&gt;")
            if len(profile) > 500:
                preview += "..."
            sections.append(f"👤 <b>Profile</b>\n<pre>{preview}</pre>")

        # Today's notes
        today = memory.read_today().strip()
        if today:
            preview = today[-500:].replace("<", "&lt;").replace(">", "&gt;")
            if len(today) > 500:
                preview = "..." + preview
            sections.append(f"📅 <b>Today</b>\n<pre>{preview}</pre>")

        # Long-term memory
        long_term = memory.read_long_term().strip()
        if long_term:
            if query:
                matches = [
                    line
                    for line in long_term.splitlines()
                    if query.lower() in line.lower()
                ]
                if matches:
                    sections.append(
                        f"🧠 <b>Memory (matching '{query}')</b>\n<pre>" + "\n".join(matches[:10]).replace("<", "&lt;").replace(">", "&gt;") + "</pre>"
                    )
                else:
                    sections.append(f"🧠 <i>No memories matching '{query}'</i>")
            else:
                preview = long_term[:500].replace("<", "&lt;").replace(">", "&gt;")
                if len(long_term) > 500:
                    preview += "..."
                sections.append(f"🧠 <b>Long-term Memory</b>\n<pre>{preview}</pre>")

        # Fact count
        try:
            facts = memory._load_fact_index()
            sections.append(f"\n📊 <b>Total:</b> <code>{len(facts)} facts stored</code>")
        except Exception:
            pass

        if not sections:
            return "🧠 <i>Memory empty. Nothing stored yet.</i>"

        return "\n\n".join(sections)

    def _cmd_model(self, args: str = "") -> dict:
        import os
        from g_agent.providers.registry import PROVIDERS

        if args:
            # Example: "/model openai" shows provider info.
            # Example: "/model set openai/gpt-4o" sets the model name.
            if args.startswith("set "):
                new_model = args[4:].strip()
                if new_model:
                    self.model_name = new_model
                    return {"text": f"✅ Model set to <code>{new_model}</code>.", "buttons": []}

            for spec in PROVIDERS:
                if spec.name == args:
                    key_masked = "configured" if os.environ.get(spec.env_key) else "not set"
                    text = (
                        f"🧠 <b>{spec.label}</b>\n\n"
                        f"<code>Name   : {spec.name}</code>\n"
                        f"<code>Env    : {spec.env_key}</code>\n"
                        f"<code>Key    : {key_masked}</code>\n"
                        f"<code>Gateway: {'yes' if spec.is_gateway else 'no'}</code>"
                    )
                    return {
                        "text": text,
                        "buttons": [
                            [{"text": "⬅️ Back to Providers", "data": "/model"}],
                        ],
                    }
                    
            # Fallback: if user types `/model some-model-name` directly
            self.model_name = args.strip()
            return {"text": f"✅ Model set to <code>{self.model_name}</code>.", "buttons": []}

        # Show only configured providers
        configured_providers = [p for p in PROVIDERS if os.environ.get(p.env_key)]
        
        text = (
            f"🧠 <b>Model Selection</b>\n"
            f"Current: <code>{self.model_name}</code>\n\n"
            f"<i>Select a configured provider for details, or use <code>/model set &lt;model_id&gt;</code> to change models.</i>"
        )

        buttons: list[list[dict[str, str]]] = []
        row: list[dict[str, str]] = []
        for spec in configured_providers:
            row.append({"text": spec.label, "data": f"/model {spec.name}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        return {"text": text, "buttons": buttons}

    # -- Tools & Integrations Commands -------------------------------------

    def _cmd_tools(self) -> str:
        if not self.tool_names:
            return "🔧 <i>No tools registered.</i>"

        lines = [f"🔧 <b>Tools ({len(self.tool_names)})</b>\n"]
        for name in sorted(self.tool_names):
            lines.append(f"• <code>{name}</code>")
        return "\n".join(lines)

    def _cmd_cron(self) -> str:
        if not self.cron_service:
            return "⏰ <i>Cron service not configured.</i>"

        try:
            jobs = self.cron_service.list_jobs(include_disabled=True)
        except Exception as e:
            return f"⚠️ <b>Error loading cron jobs:</b> <code>{e}</code>"

        if not jobs:
            return "⏰ <i>No cron jobs scheduled.</i>"

        lines = [f"⏰ <b>Cron Jobs ({len(jobs)})</b>\n"]
        for job in jobs:
            status = "✅" if job.enabled else "⏸️"
            # Schedule display
            sched = job.schedule
            if sched.kind == "cron" and sched.expr:
                sched_str = sched.expr
            elif sched.kind == "every" and sched.every_ms:
                secs = sched.every_ms // 1000
                if secs >= 3600:
                    sched_str = f"every {secs // 3600}h"
                elif secs >= 60:
                    sched_str = f"every {secs // 60}m"
                else:
                    sched_str = f"every {secs}s"
            elif sched.kind == "at" and sched.at_ms:
                from datetime import datetime as _dt, timezone as _tz
                at_dt = _dt.fromtimestamp(sched.at_ms / 1000, tz=_tz.utc)
                sched_str = f"at {at_dt.strftime('%H:%M')}"
            else:
                sched_str = sched.kind

            lines.append(f"{status} <b>{job.name}</b> [<code>{sched_str}</code>]")

        return "\n".join(lines)

    def _cmd_packs(self) -> str:
        try:
            from g_agent.agent.workflow_packs import PACK_ALIASES, PACK_SPEC

            if not PACK_SPEC:
                return "📦 <i>No workflow packs configured.</i>"

            lines = [f"📦 <b>Workflow Packs ({len(PACK_SPEC)})</b>\n"]
            for name, spec in sorted(PACK_SPEC.items()):
                objective = spec.get("objective", "")[:80]
                aliases = [a for a, target in PACK_ALIASES.items() if target == name]
                alias_str = f" (<code>{', '.join(aliases)}</code>)" if aliases else ""
                lines.append(f"• <b>{name}</b>{alias_str}")
                if objective:
                    lines.append(f"  <i>{objective}</i>")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Error loading packs: {e}"

    # -- Utility Commands --------------------------------------------------

    async def _cmd_search(self, query: str) -> str:
        if not query:
            return "⚠️ Usage: /search <query>\n\nExample: /search docker deployment guide"

        if not self.brave_api_key:
            return "⚠️ Web search not configured (BRAVE_API_KEY missing)"

        from g_agent.agent.tools.web import WebSearchTool

        tool = WebSearchTool(api_key=self.brave_api_key, max_results=5)
        result = await tool.execute(query=query)

        return f"🔍 {result}"

    def _cmd_help(self) -> dict:
        text = (
            "ℹ️ <b>Help</b>\n\n"
            "<b>Session</b>\n"
            "/new  |  /reset  |  /compact  |  /context\n\n"
            "<b>Info</b>\n"
            "/status  |  /whoami  |  /memory  |  /model\n\n"
            "<b>Tools</b>\n"
            "/tools  |  /cron  |  /packs\n\n"
            "<b>Utility</b>\n"
            "/search &lt;query&gt;\n\n"
            "More: /commands for full list"
        )
        return {
            "text": text,
            "buttons": [
                [
                    {"text": "📊 Status", "data": "/status"},
                    {"text": "🧭 Who Am I", "data": "/whoami"},
                ],
                [
                    {"text": "🧠 Model", "data": "/model"},
                    {"text": "📋 Commands", "data": "/commands"},
                ],
            ],
        }

    def _cmd_commands(self, args: str) -> dict:
        page = 1
        if args:
            try:
                page = max(1, int(args))
            except ValueError:
                pass

        per_page = 8
        total = len(self._registry)
        total_pages = max(1, math.ceil(total / per_page))
        page = min(page, total_pages)

        start = (page - 1) * per_page
        end = start + per_page
        page_items = self._registry[start:end]

        lines = [f"ℹ️ <b>Commands ({page}/{total_pages})</b>\n"]

        for cmd, _, desc, usage in page_items:
            usage_str = f" {usage}" if usage else ""
            lines.append(f"<code>/{cmd}{usage_str}</code> — <i>{desc}</i>")

        # Buttons
        buttons = []
        nav_row = []
        if page > 1:
            nav_row.append({"text": "⬅️ Prev", "data": f"/commands {page - 1}"})
        if page < total_pages:
            nav_row.append({"text": "Next ➡️", "data": f"/commands {page + 1}"})
        
        if nav_row:
            buttons.append(nav_row)

        return {
            "text": "\n".join(lines),
            "buttons": buttons
        }
