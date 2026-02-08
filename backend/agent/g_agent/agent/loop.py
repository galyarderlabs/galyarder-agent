"""Agent loop: the core processing engine."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from g_agent.bus.events import InboundMessage, OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.providers.base import LLMProvider
from g_agent.agent.context import ContextBuilder
from g_agent.agent.tools.registry import ToolRegistry
from g_agent.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from g_agent.agent.tools.shell import ExecTool
from g_agent.agent.tools.web import WebSearchTool, WebFetchTool
from g_agent.agent.tools.message import MessageTool
from g_agent.agent.tools.spawn import SpawnTool
from g_agent.agent.tools.cron import CronTool
from g_agent.agent.tools.integrations import (
    RememberTool,
    RecallTool,
    UpdateProfileTool,
    LogFeedbackTool,
    SlackWebhookTool,
    SendEmailTool,
    CreateCalendarEventTool,
)
from g_agent.agent.tools.browser import (
    BrowserSession,
    BrowserOpenTool,
    BrowserSnapshotTool,
    BrowserClickTool,
    BrowserTypeTool,
    BrowserExtractTool,
    BrowserScreenshotTool,
)
from g_agent.agent.tools.google_workspace import (
    GoogleWorkspaceClient,
    GmailListThreadsTool,
    GmailReadThreadTool,
    GmailSendTool,
    GmailDraftTool,
    CalendarListEventsTool,
    CalendarCreateEventTool,
    CalendarUpdateEventTool,
    DriveListFilesTool,
    DriveReadTextTool,
    DocsGetDocumentTool,
    DocsAppendTextTool,
    SheetsGetValuesTool,
    SheetsAppendValuesTool,
    ContactsListTool,
    ContactsGetTool,
)
from g_agent.agent.subagent import SubagentManager
from g_agent.session.manager import SessionManager

if TYPE_CHECKING:
    from g_agent.config.schema import (
        BrowserToolsConfig,
        ExecToolConfig,
        GoogleWorkspaceConfig,
        SMTPConfig,
    )
    from g_agent.cron.service import CronService
    from g_agent.session.manager import Session


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        slack_webhook_url: str | None = None,
        smtp_config: SMTPConfig | None = None,
        google_config: GoogleWorkspaceConfig | None = None,
        browser_config: BrowserToolsConfig | None = None,
        tool_policy: dict[str, str] | None = None,
        risky_tools: list[str] | None = None,
        approval_mode: str = "off",
        enable_reflection: bool = True,
        summary_interval: int = 6,
    ):
        from g_agent.config.schema import (
            ExecToolConfig,
            SMTPConfig,
            GoogleWorkspaceConfig,
            BrowserToolsConfig,
        )
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.slack_webhook_url = slack_webhook_url
        self.smtp_config = smtp_config or SMTPConfig()
        self.google_config = google_config or GoogleWorkspaceConfig()
        self.browser_config = browser_config or BrowserToolsConfig()
        self.tool_policy = {
            (k or "").strip(): (v or "").strip().lower()
            for k, v in (tool_policy or {}).items()
            if (k or "").strip() and (v or "").strip().lower() in {"allow", "ask", "deny"}
        }
        default_risky = {"exec", "send_email", "slack_webhook_send", "message", "gmail_send"}
        source_risky = risky_tools if risky_tools is not None else list(default_risky)
        self.risky_tools = {name.strip() for name in source_risky if name and name.strip()}
        self.approval_mode = (approval_mode or "off").strip().lower()
        if self.approval_mode not in {"off", "confirm"}:
            self.approval_mode = "off"
        self.enable_reflection = enable_reflection
        self.summary_interval = max(2, summary_interval)
        self.browser = BrowserSession(
            workspace=workspace,
            allow_domains=list(self.browser_config.allow_domains),
            deny_domains=list(self.browser_config.deny_domains),
            request_timeout=float(self.browser_config.timeout_seconds),
            max_html_chars=max(20000, int(self.browser_config.max_html_chars)),
        )
        
        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )
        
        self._running = False
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools (restrict to workspace if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(allowed_dir=allowed_dir))
        
        # Shell tool
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
        ))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        
        # Browser tools (stateful)
        self.tools.register(BrowserOpenTool(self.browser))
        self.tools.register(BrowserSnapshotTool(self.browser))
        self.tools.register(BrowserClickTool(self.browser))
        self.tools.register(BrowserTypeTool(self.browser))
        self.tools.register(BrowserExtractTool(self.browser))
        self.tools.register(BrowserScreenshotTool(self.browser))

        # Memory + integrations
        self.tools.register(RememberTool(workspace=self.workspace))
        self.tools.register(RecallTool(workspace=self.workspace))
        self.tools.register(UpdateProfileTool(workspace=self.workspace))
        self.tools.register(LogFeedbackTool(workspace=self.workspace))
        self.tools.register(SlackWebhookTool(webhook_url=self.slack_webhook_url))
        self.tools.register(SendEmailTool(
            host=self.smtp_config.host,
            port=self.smtp_config.port,
            username=self.smtp_config.username,
            password=self.smtp_config.password,
            from_email=self.smtp_config.from_email,
            use_tls=self.smtp_config.use_tls,
        ))
        self.tools.register(CreateCalendarEventTool(workspace=self.workspace))

        # Google Workspace tools
        google = GoogleWorkspaceClient(
            client_id=self.google_config.client_id,
            client_secret=self.google_config.client_secret,
            refresh_token=self.google_config.refresh_token,
            access_token=self.google_config.access_token,
            calendar_id=self.google_config.calendar_id,
        )
        self.tools.register(GmailListThreadsTool(google))
        self.tools.register(GmailReadThreadTool(google))
        self.tools.register(GmailSendTool(google))
        self.tools.register(GmailDraftTool(google))
        self.tools.register(CalendarListEventsTool(google))
        self.tools.register(CalendarCreateEventTool(google))
        self.tools.register(CalendarUpdateEventTool(google))
        self.tools.register(DriveListFilesTool(google))
        self.tools.register(DriveReadTextTool(google))
        self.tools.register(DocsGetDocumentTool(google))
        self.tools.register(DocsAppendTextTool(google))
        self.tools.register(SheetsGetValuesTool(google))
        self.tools.register(SheetsAppendValuesTool(google))
        self.tools.register(ContactsListTool(google))
        self.tools.register(ContactsGetTool(google))
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")
        self._log_user_message_to_daily_memory(msg)
        
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)
        
        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            metadata=msg.metadata if msg.metadata else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )
        
        # Agent loop
        iteration = 0
        final_content = None
        used_tools = False
        executed_tools: list[str] = []
        executed_tool_results: list[tuple[str, str]] = []
        approved_tools, approve_all = self._extract_approval_intent(msg.content)
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            # Handle tool calls
            if response.has_tool_calls:
                used_tools = True
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self._execute_tool_with_policy(
                        tool_name=tool_call.name,
                        tool_args=tool_call.arguments,
                        channel=msg.channel,
                        sender_id=msg.sender_id,
                        approved_tools=approved_tools,
                        approve_all=approve_all,
                    )
                    executed_tools.append(tool_call.name)
                    executed_tool_results.append((tool_call.name, str(result)))
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        if self._should_reflect(msg.content, used_tools, final_content):
            final_content = await self._reflect_response(msg.content, final_content)
        final_content = self._enforce_memory_truth(final_content)
        auto_memory_result = await self._auto_remember_if_requested(msg.content, executed_tools)
        if auto_memory_result:
            final_content = f"{final_content.rstrip()}\n\n{auto_memory_result}"
        final_content = self._align_memory_claims(final_content, executed_tool_results)
        self._log_assistant_message_to_daily_memory(msg.channel, msg.chat_id, final_content)
        
        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        self._maybe_write_session_summary(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )

    def _log_user_message_to_daily_memory(self, msg: InboundMessage) -> None:
        """Append inbound user message to today's memory notes."""
        self._append_daily_memory_entry(msg.channel, msg.sender_id, msg.content)

    def _log_assistant_message_to_daily_memory(self, channel: str, chat_id: str, content: str) -> None:
        """Append assistant reply to today's memory notes."""
        self._append_daily_memory_entry(channel, f"assistant@{chat_id}", content)

    def _append_daily_memory_entry(self, channel: str, actor: str, content: str) -> None:
        """Append a compact entry to today's memory notes."""
        text = (content or "").strip()
        if not text:
            return

        compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if len(compact) > 1200:
            compact = compact[:1200] + "..."

        timestamp = datetime.now().strftime("%H:%M")
        entry = f"## {timestamp}\n- [{channel}] {actor}: {compact}"

        try:
            self.context.memory.append_today(entry)
        except Exception as e:
            logger.warning(f"Failed to append daily memory: {e}")
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            metadata=msg.metadata if msg.metadata else None,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        used_tools = False
        approved_tools: set[str] = set()
        approve_all = False
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            if response.has_tool_calls:
                used_tools = True
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self._execute_tool_with_policy(
                        tool_name=tool_call.name,
                        tool_args=tool_call.arguments,
                        channel=origin_channel,
                        sender_id=msg.sender_id,
                        approved_tools=approved_tools,
                        approve_all=approve_all,
                    )
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."

        if self._should_reflect(msg.content, used_tools, final_content):
            final_content = await self._reflect_response(msg.content, final_content)
        final_content = self._enforce_memory_truth(final_content)
        self._log_assistant_message_to_daily_memory(origin_channel, origin_chat_id, final_content)
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        self._maybe_write_session_summary(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""

    def _enforce_memory_truth(self, content: str | None) -> str:
        """Prevent incorrect claims that the agent has no persistent memory."""
        text = (content or "").strip()
        if not text:
            return text
        lowered = text.lower()
        denial_markers = (
            "i don't have long-term memory",
            "i do not have long-term memory",
            "i don't have persistent memory",
            "i do not have persistent memory",
            "only remember this conversation",
            "only within this conversation",
            "saya tidak punya memory jangka panjang",
            "saya tidak memiliki memory jangka panjang",
            "hanya bisa mengingat percakapan ini",
        )
        if not any(marker in lowered for marker in denial_markers):
            return text

        workspace_path = str(self.workspace.expanduser().resolve())
        return (
            "Saya punya memori persisten lintas sesi.\n"
            "Penyimpanan memori ada di:\n"
            f"- {workspace_path}/memory/MEMORY.md\n"
            f"- {workspace_path}/memory/PROFILE.md\n"
            f"- {workspace_path}/memory/RELATIONSHIPS.md\n"
            f"- {workspace_path}/memory/PROJECTS.md\n"
            f"- {workspace_path}/memory/LESSONS.md\n"
            f"- {workspace_path}/memory/YYYY-MM-DD.md"
        )

    def _is_explicit_remember_request(self, content: str) -> bool:
        """Detect explicit requests to save durable memory."""
        text = (content or "").strip().lower()
        if not text:
            return False
        if any(
            marker in text
            for marker in ("jangan ingat", "jgn ingat", "jangan simpan", "do not remember", "don't remember")
        ):
            return False

        patterns = (
            r"^\s*(tolong|please)?\s*(ingat(?:in)?|catat|simpan)\b",
            r"\b(ingat(?:in)?|catat|simpan)\s+(bahwa|ini|ya|dong)\b",
            r"\bingat\s+ya\b",
            r"^\s*(please\s+)?(remember|save|note)\b",
            r"\bremember\s+that\b",
            r"\bsave\s+this\b",
            r"\bnote\s+this\b",
        )
        return any(re.search(pattern, text) for pattern in patterns)

    def _extract_remember_fact(self, content: str) -> str | None:
        """Extract the durable fact payload from a remember-style request."""
        fact = (content or "").strip()
        if not fact:
            return None
        fact = re.sub(r"^\s*(tolong|please)\s+", "", fact, flags=re.IGNORECASE)
        fact = re.sub(
            r"^\s*(ingat(?:in)?|catat|simpan)\s*(bahwa|ini|ya|dong|:)?\s*",
            "",
            fact,
            flags=re.IGNORECASE,
        )
        fact = re.sub(
            r"^\s*(remember|save|note)\s*(that|this|:)?\s*",
            "",
            fact,
            flags=re.IGNORECASE,
        )
        fact = fact.strip(" \n\t\"'`")
        if len(fact) < 4:
            return None
        if len(fact) > 500:
            return fact[:500].rstrip() + "..."
        return fact

    async def _auto_remember_if_requested(self, user_content: str, executed_tools: list[str]) -> str | None:
        """Auto-save memory for explicit remember requests when model skipped memory tools."""
        if "remember" in executed_tools or "update_profile" in executed_tools:
            return None
        if not self._is_explicit_remember_request(user_content):
            return None

        fact = self._extract_remember_fact(user_content)
        if not fact:
            return None

        try:
            result = await self.tools.execute("remember", {"fact": fact, "category": "user"})
            if not isinstance(result, str):
                return None
            if "saved to long-term memory" in result.lower() or "long-term memory" in result.lower():
                logger.info("Auto-remember saved durable fact from explicit user request")
                return f"✅ {result}"
            return None
        except Exception as e:
            logger.warning(f"Auto remember failed: {e}")
            return None

    def _align_memory_claims(self, content: str | None, tool_results: list[tuple[str, str]]) -> str:
        """Correct memory-location claims when they do not match executed tools."""
        text = (content or "").strip()
        if not text:
            return text

        lowered = text.lower()
        claims_profile = any(
            marker in lowered
            for marker in (
                "saved to profile",
                "saved in profile",
                "simpan di profile",
                "tersimpan di profile",
                "user profile",
                "profile.md",
            )
        )
        if not claims_profile:
            return text

        profile_saved = any(
            name == "update_profile" and ("updated profile" in result.lower() or "profile." in result.lower())
            for name, result in tool_results
        )
        memory_saved = any(
            name == "remember" and "long-term memory" in result.lower()
            for name, result in tool_results
        )

        if profile_saved:
            return text

        workspace_path = str(self.workspace.expanduser().resolve())
        if memory_saved:
            return (
                f"{text.rstrip()}\n\n"
                f"Catatan: fakta ini tersimpan di `{workspace_path}/memory/MEMORY.md`, "
                "bukan di PROFILE.md."
            )
        return (
            f"{text.rstrip()}\n\n"
            "Catatan: penyimpanan profil belum terkonfirmasi; "
            "gunakan perintah eksplisit update profile (mis. nama/timezone/preference)."
        )

    def _extract_approval_intent(self, text: str) -> tuple[set[str], bool]:
        """Parse explicit approval flags from user text."""
        content = (text or "").strip().lower()
        if not content:
            return set(), False
        if re.search(r"\bapprove\s*[:=]?\s*all\b", content):
            return set(), True

        match = re.search(r"\bapprove\s*[:=]?\s*([a-z0-9_\-, ]+)", content)
        if not match:
            return set(), False

        raw = match.group(1)
        chunks = re.split(r"[,\s]+", raw)
        skip = {"tool", "tools", "and", "please", "pls"}
        names = {item.strip() for item in chunks if item.strip() and item.strip() not in skip}
        return names, False

    def _resolve_tool_policy(
        self,
        tool_name: str,
        channel: str,
        sender_id: str,
    ) -> str:
        """Resolve tool policy in order: specific -> wildcard -> default."""
        default = "allow"
        if self.approval_mode == "confirm" and tool_name in self.risky_tools:
            default = "ask"

        keys = [
            f"{channel}:{sender_id}:{tool_name}",
            f"{channel}:*:{tool_name}",
            f"{channel}:{tool_name}",
            tool_name,
            "*",
        ]
        for key in keys:
            decision = self.tool_policy.get(key)
            if decision in {"allow", "ask", "deny"}:
                return decision
        return default

    async def _execute_tool_with_policy(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        channel: str,
        sender_id: str,
        approved_tools: set[str],
        approve_all: bool,
    ) -> str:
        """Execute a tool call after policy/approval checks."""
        if not isinstance(tool_args, dict):
            tool_args = {}
        decision = self._resolve_tool_policy(tool_name, channel, sender_id)
        if decision == "deny":
            return f"Error: tool '{tool_name}' blocked by policy."
        if decision == "ask" and not (approve_all or tool_name in approved_tools):
            return (
                f"Approval required for tool '{tool_name}'. "
                f"Resend your request with `approve {tool_name}` (or `approve all`)."
            )
        return await self.tools.execute(tool_name, tool_args)

    def _should_reflect(self, user_content: str, used_tools: bool, draft: str | None) -> bool:
        """Decide whether to run a reflection pass."""
        if not self.enable_reflection:
            return False
        if not draft or not draft.strip():
            return False

        text = (user_content or "").lower()
        complex_keywords = (
            "plan", "roadmap", "step", "debug", "error", "fix", "why",
            "compare", "analyze", "implement", "design",
        )
        is_complex = len(text) >= 120 or any(k in text for k in complex_keywords)
        return used_tools or is_complex

    async def _reflect_response(self, user_content: str, draft: str) -> str:
        """Run a lightweight reflection pass and return improved answer if any."""
        review_prompt = (
            "You are a response reviewer. Improve the draft answer for correctness, clarity, "
            "and directness. Keep it concise. If the draft is already good, return exactly KEEP."
        )
        review_input = (
            f"User message:\n{user_content}\n\n"
            f"Draft answer:\n{draft}\n\n"
            "Output either KEEP or a revised final answer."
        )
        try:
            review = await self.provider.chat(
                messages=[
                    {"role": "system", "content": review_prompt},
                    {"role": "user", "content": review_input},
                ],
                tools=None,
                model=self.model,
                max_tokens=min(1200, max(256, len(draft) // 2 + 200)),
                temperature=0.2,
            )
            reviewed = (review.content or "").strip()
            if not reviewed or reviewed.upper() == "KEEP":
                return draft
            return reviewed
        except Exception:
            return draft

    def _maybe_write_session_summary(self, session: Session) -> None:
        """Periodically write compact session summaries to memory."""
        assistant_turns = sum(1 for m in session.messages if m.get("role") == "assistant")
        if assistant_turns < self.summary_interval:
            return

        last_summary_turn = int(session.metadata.get("last_summary_turn", 0) or 0)
        if (assistant_turns - last_summary_turn) < self.summary_interval:
            return

        summary = self._build_session_summary(session)
        if not summary:
            return

        if self.context.memory.append_session_summary(session.key, summary):
            session.metadata["last_summary_turn"] = assistant_turns
            self.sessions.save(session)

    def _build_session_summary(self, session: Session, max_pairs: int = 4) -> str:
        """Build a compact heuristic summary from recent session turns."""
        recent = session.messages[-max_pairs * 2:]
        user_items: list[str] = []
        assistant_items: list[str] = []

        def _compact(text: str, limit: int = 180) -> str:
            compact = " ".join((text or "").split())
            if len(compact) > limit:
                compact = compact[:limit] + "..."
            return compact

        for msg in recent:
            role = msg.get("role")
            content = _compact(msg.get("content", ""))
            if not content:
                continue
            if role == "user":
                if content not in user_items:
                    user_items.append(content)
            elif role == "assistant":
                if content not in assistant_items:
                    assistant_items.append(content)

        if not user_items and not assistant_items:
            return ""

        user_preview = " | ".join(user_items[-2:]) if user_items else ""
        assistant_preview = " | ".join(assistant_items[-2:]) if assistant_items else ""
        summary_parts = []
        if user_preview:
            summary_parts.append(f"user: {user_preview}")
        if assistant_preview:
            summary_parts.append(f"assistant: {assistant_preview}")
        return " || ".join(summary_parts)
