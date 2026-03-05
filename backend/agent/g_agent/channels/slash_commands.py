"""Native slash command dispatcher for channel-level interception.

Commands are handled instantly without LLM involvement.
Each handler calls real subsystem APIs and returns structured text.
"""

from __future__ import annotations

import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    ) -> None:
        self.workspace = workspace
        self.model_name = model_name or "unknown"
        self.brave_api_key = brave_api_key or os.environ.get("BRAVE_API_KEY", "")
        self.cron_service = cron_service
        self.tool_names = tool_names or []
        self._boot_time = time.monotonic()

        # Ordered command registry: (command, aliases, description, usage)
        self._registry: list[tuple[str, list[str], str, str]] = [
            # Session
            ("start", [], "Start conversation", ""),
            ("new", [], "New session (alias /reset)", ""),
            ("reset", [], "Clear context & start fresh", ""),
            ("compact", [], "Summarize current session", ""),
            ("context", [], "Current session info", ""),
            # Info
            ("status", [], "System diagnostics", ""),
            ("whoami", [], "Your profile from memory", ""),
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
    ) -> str | None:
        """Try to handle text as a slash command.

        Returns response string if handled, None if not a command.
        """
        stripped = text.strip()
        if not stripped.startswith("/"):
            return None

        parts = stripped.split(maxsplit=1)
        raw_cmd = parts[0][1:].lower()  # Remove leading /
        args = parts[1].strip() if len(parts) > 1 else ""

        canonical = self._handlers.get(raw_cmd)
        if canonical is None:
            return None

        dispatch = {
            "start": lambda: self._cmd_start(),
            "new": lambda: self._cmd_reset(session_key),
            "reset": lambda: self._cmd_reset(session_key),
            "compact": lambda: self._cmd_compact(session_key),
            "context": lambda: self._cmd_context(session_key, channel, chat_id),
            "status": lambda: self._cmd_status(session_key),
            "whoami": lambda: self._cmd_whoami(),
            "memory": lambda: self._cmd_memory(args),
            "model": lambda: self._cmd_model(),
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

    def _cmd_start(self) -> str:
        return "👋 yo. send me a message, I'm listening."

    def _cmd_reset(self, session_key: str) -> str:
        from g_agent.session.manager import SessionManager

        sessions = SessionManager(self.workspace)
        session = sessions.get_or_create(session_key)
        msg_count = len(session.messages)

        if msg_count > 0:
            sessions.archive(session_key)
            return (
                f"🔄 Session Reset\n\n"
                f"Archived {msg_count} messages → session cleared.\n"
                f"Starting fresh. Send a message anytime."
            )
        return "🔄 Session already empty. Send a message to start."

    def _cmd_compact(self, session_key: str) -> str:
        from g_agent.session.manager import SessionManager

        sessions = SessionManager(self.workspace)
        session = sessions.get_or_create(session_key)
        msg_count = len(session.messages)

        if msg_count == 0:
            return "📦 Session empty, nothing to compact."

        # Count by role
        user_msgs = sum(1 for m in session.messages if m.get("role") == "user")
        assistant_msgs = sum(1 for m in session.messages if m.get("role") == "assistant")
        tool_msgs = msg_count - user_msgs - assistant_msgs

        # Calculate rough token estimate (1 token ≈ 4 chars)
        total_chars = sum(len(str(m.get("content", ""))) for m in session.messages)
        est_tokens = total_chars // 4

        lines = ["📦 Session Summary\n"]
        lines.append(f"Messages : {msg_count} ({user_msgs} user, {assistant_msgs} assistant, {tool_msgs} system)")
        lines.append(f"Est tokens: ~{est_tokens:,}")
        lines.append(f"Created  : {session.created_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Updated  : {session.updated_at.strftime('%Y-%m-%d %H:%M')}")

        if session.messages:
            first_content = str(session.messages[0].get("content", ""))[:100]
            last_content = str(session.messages[-1].get("content", ""))[:100]
            lines.append(f"\nFirst    : {first_content}")
            lines.append(f"Last     : {last_content}")

        lines.append(f"\n💡 Use /reset to clear & start fresh.")

        return "\n".join(lines)

    def _cmd_context(self, session_key: str, channel: str, chat_id: str) -> str:
        from g_agent.session.manager import SessionManager

        lines = ["📋 Session Context\n"]

        lines.append(f"Channel  : {channel}")
        lines.append(f"Chat ID  : {chat_id}")
        lines.append(f"Session  : {session_key}")

        try:
            sessions = SessionManager(self.workspace)
            session = sessions.get_or_create(session_key)
            lines.append(f"Messages : {len(session.messages)}")

            if session.messages:
                last_msg = session.messages[-1]
                role = last_msg.get("role", "?")
                content_preview = str(last_msg.get("content", ""))[:80]
                lines.append(f"Last     : [{role}] {content_preview}")

            lines.append(f"Created  : {session.created_at.strftime('%Y-%m-%d %H:%M')}")
            lines.append(f"Updated  : {session.updated_at.strftime('%Y-%m-%d %H:%M')}")
        except Exception as e:
            lines.append(f"Error    : {e}")

        return "\n".join(lines)

    # -- Info Commands -----------------------------------------------------

    def _cmd_status(self, session_key: str) -> str:
        from g_agent.session.manager import SessionManager

        lines = ["📊 System Status\n"]

        # Model
        lines.append(f"Model    : {self.model_name}")

        # Uptime
        uptime_s = time.monotonic() - self._boot_time
        hours = int(uptime_s // 3600)
        minutes = int((uptime_s % 3600) // 60)
        lines.append(f"Uptime   : {hours}h {minutes}m")

        # Cron
        if self.cron_service:
            try:
                cron_status = self.cron_service.status()
                job_count = cron_status.get("jobs", 0)
                enabled = "active" if cron_status.get("enabled") else "stopped"
                lines.append(f"Cron     : {job_count} jobs ({enabled})")
            except Exception:
                lines.append("Cron     : unavailable")
        else:
            lines.append("Cron     : not configured")

        # Session
        try:
            sessions = SessionManager(self.workspace)
            session = sessions.get_or_create(session_key)
            lines.append(f"Session  : {len(session.messages)} messages")
        except Exception:
            pass

        # Memory facts
        try:
            from g_agent.agent.memory import MemoryStore

            memory = MemoryStore(self.workspace)
            facts = memory._load_fact_index()
            lines.append(f"Memory   : {len(facts)} facts stored")
        except Exception:
            lines.append("Memory   : unavailable")

        # Tools
        lines.append(f"Tools    : {len(self.tool_names)} registered")

        # Packs
        try:
            from g_agent.agent.workflow_packs import list_workflow_packs

            packs = list_workflow_packs()
            lines.append(f"Packs    : {len(packs)} available")
        except Exception:
            pass

        # Timestamp
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"\nTimestamp : {now}")

        return "\n".join(lines)

    def _cmd_whoami(self) -> str:
        from g_agent.agent.memory import MemoryStore

        memory = MemoryStore(self.workspace)
        profile = memory.read_profile().strip()

        if not profile:
            return "👤 No profile stored yet."

        preview = profile[:800]
        if len(profile) > 800:
            preview += "\n..."

        return f"👤 Profile\n\n{preview}"

    def _cmd_memory(self, query: str) -> str:
        from g_agent.agent.memory import MemoryStore

        memory = MemoryStore(self.workspace)
        sections: list[str] = []

        # Profile summary
        profile = memory.read_profile().strip()
        if profile:
            preview = profile[:500]
            if len(profile) > 500:
                preview += "..."
            sections.append(f"👤 Profile\n{preview}")

        # Today's notes
        today = memory.read_today().strip()
        if today:
            preview = today[-500:]
            if len(today) > 500:
                preview = "..." + preview
            sections.append(f"📅 Today\n{preview}")

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
                        f"🧠 Memory (matching '{query}')\n" + "\n".join(matches[:10])
                    )
                else:
                    sections.append(f"🧠 No memories matching '{query}'")
            else:
                preview = long_term[:500]
                if len(long_term) > 500:
                    preview += "..."
                sections.append(f"🧠 Long-term Memory\n{preview}")

        # Fact count
        try:
            facts = memory._load_fact_index()
            sections.append(f"\n📊 Total: {len(facts)} facts stored")
        except Exception:
            pass

        if not sections:
            return "🧠 Memory empty. Nothing stored yet."

        return "\n\n".join(sections)

    def _cmd_model(self) -> str:
        return f"🤖 Model: {self.model_name}"

    # -- Tools & Integrations Commands -------------------------------------

    def _cmd_tools(self) -> str:
        if not self.tool_names:
            return "🔧 No tools registered."

        lines = [f"🔧 Tools ({len(self.tool_names)} registered)\n"]
        for name in sorted(self.tool_names):
            lines.append(f"  • {name}")
        return "\n".join(lines)

    def _cmd_cron(self) -> str:
        if not self.cron_service:
            return "⏰ Cron service not configured."

        try:
            jobs = self.cron_service.list_jobs(include_disabled=True)
        except Exception as e:
            return f"⚠️ Error loading cron jobs: {e}"

        if not jobs:
            return "⏰ No cron jobs scheduled."

        lines = [f"⏰ Cron Jobs ({len(jobs)})\n"]
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

            lines.append(f"  {status} {job.name} [{sched_str}]")

        return "\n".join(lines)

    def _cmd_packs(self) -> str:
        try:
            from g_agent.agent.workflow_packs import PACK_ALIASES, PACK_SPEC

            if not PACK_SPEC:
                return "📦 No workflow packs configured."

            lines = [f"📦 Workflow Packs ({len(PACK_SPEC)})\n"]
            for name, spec in sorted(PACK_SPEC.items()):
                objective = spec.get("objective", "")[:80]
                # Find aliases for this pack
                aliases = [a for a, target in PACK_ALIASES.items() if target == name]
                alias_str = f" (alias: {', '.join(aliases)})" if aliases else ""
                lines.append(f"  • {name}{alias_str}")
                lines.append(f"    {objective}")
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

    def _cmd_help(self) -> str:
        lines = ["ℹ️ Commands\n"]

        lines.append("Session")
        lines.append("  /start      — Start conversation")
        lines.append("  /new        — New session (= /reset)")
        lines.append("  /reset      — Clear context & start fresh")
        lines.append("  /compact    — Summarize current session")
        lines.append("  /context    — Current session info")

        lines.append("\nInfo")
        lines.append("  /status     — System diagnostics")
        lines.append("  /whoami     — Your profile")
        lines.append("  /memory     — Stored memories")
        lines.append("  /model      — Active model")

        lines.append("\nTools & Integrations")
        lines.append("  /tools      — Active tools")
        lines.append("  /cron       — Scheduled jobs")
        lines.append("  /packs      — Workflow packs")

        lines.append("\nUtility")
        lines.append("  /search <q> — Web search")
        lines.append("  /help       — This page")
        lines.append("  /commands   — Full list")

        return "\n".join(lines)

    def _cmd_commands(self, args: str) -> str:
        # Pagination
        page = 1
        if args:
            try:
                page = max(1, int(args))
            except ValueError:
                pass

        total = len(self._registry)
        total_pages = math.ceil(total / _COMMANDS_PAGE_SIZE)
        page = min(page, total_pages)

        start = (page - 1) * _COMMANDS_PAGE_SIZE
        end = start + _COMMANDS_PAGE_SIZE
        page_items = self._registry[start:end]

        lines = [f"ℹ️ Commands ({page}/{total_pages})\n"]

        current_section = ""
        section_map = {
            "start": "Session", "new": "Session", "reset": "Session",
            "compact": "Session", "context": "Session",
            "status": "Info", "whoami": "Info", "memory": "Info", "model": "Info",
            "tools": "Tools & Integrations", "cron": "Tools & Integrations",
            "packs": "Tools & Integrations",
            "search": "Utility", "help": "Utility", "commands": "Utility",
        }

        for cmd, aliases, desc, usage in page_items:
            section = section_map.get(cmd, "")
            if section != current_section:
                if current_section:
                    lines.append("")
                lines.append(section)
                current_section = section

            alias_str = f" (/{', /'.join(aliases)})" if aliases else ""
            usage_str = f" {usage}" if usage else ""
            lines.append(f"  /{cmd}{usage_str}{alias_str} — {desc}")

        if page < total_pages:
            lines.append(f"\nNext: /commands {page + 1}")

        return "\n".join(lines)
