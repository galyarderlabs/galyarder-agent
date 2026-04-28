"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

from g_agent.agent.context import ContextBuilder
from g_agent.context.default import DefaultContextEngine
from g_agent.agent.runtime import TaskCheckpointStore
from g_agent.agent.subagent import SubagentManager
from g_agent.agent.tools.browser import (
    BrowserClickTool,
    BrowserExtractTool,
    BrowserOpenTool,
    BrowserScreenshotTool,
    BrowserSession,
    BrowserSnapshotTool,
    BrowserTypeTool,
)
from g_agent.agent.tools.cron import CronTool
from g_agent.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from g_agent.agent.tools.google_workspace import (
    CalendarCreateEventTool,
    CalendarListEventsTool,
    CalendarUpdateEventTool,
    ContactsGetTool,
    ContactsListTool,
    DocsAppendTextTool,
    DocsGetDocumentTool,
    DriveListFilesTool,
    DriveReadTextTool,
    GmailDraftTool,
    GmailForwardTool,
    GmailListThreadsTool,
    GmailReadThreadTool,
    GmailReplyAllTool,
    GmailReplyTool,
    GmailSendTool,
    GwsClient,
    SheetsAppendValuesTool,
    SheetsGetValuesTool,
)
from g_agent.agent.tools.integrations import (
    CreateCalendarEventTool,
    LogFeedbackTool,
    RecallTool,
    RememberTool,
    SendEmailTool,
    SlackWebhookTool,
    UpdateProfileTool,
)
from g_agent.agent.tools.message import MessageTool
from g_agent.agent.tools.registry import ToolRegistry
from g_agent.agent.tools.toolsets import ToolsetManager
from g_agent.agent.tools.shell import ExecTool
from g_agent.agent.tools.session_search import SessionSearchTool
from g_agent.agent.tools.skills import SkillManageTool
from g_agent.agent.tools.spawn import SpawnTool
from g_agent.agent.tools.web import WebFetchTool, WebSearchTool
from g_agent.agent.workflow_packs import (
    build_workflow_pack_prompt,
    extract_workflow_pack_flags,
    resolve_workflow_pack_request,
)
from g_agent.bus.events import InboundMessage, OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.character.store import CharacterStore
from g_agent.mcp.manager import MCPManager
from g_agent.observability.metrics import MetricsStore
from g_agent.routines.scheduler import RoutineScheduler
from g_agent.plugins.base import PluginContext
from g_agent.plugins.loader import load_installed_plugins, register_tool_plugins
from g_agent.providers.base import LLMProvider
from g_agent.session.manager import SessionManager

if TYPE_CHECKING:
    from g_agent.config.schema import (
        BrowserToolsConfig,
        ExecToolConfig,
        GoogleWorkspaceConfig,
        SMTPConfig,
        VisualIdentityConfig,
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
        allowed_paths: list[str] | None = None,
        tool_policy: dict[str, str] | None = None,
        risky_tools: list[str] | None = None,
        approval_mode: str = "off",
        enable_reflection: bool = True,
        summary_interval: int = 6,
        fallback_models: list[str] | None = None,
        plugins: list[Any] | None = None,
        visual_config: VisualIdentityConfig | None = None,
        provider_resolver: Callable[[str], LLMProvider] | None = None,
        tts_voice: str = "id-ID-GadisNeural",
        mcp_config: dict[str, dict[str, Any]] | None = None,
    ):
        from g_agent.config.schema import (
            BrowserToolsConfig,
            ExecToolConfig,
            GoogleWorkspaceConfig,
            SMTPConfig,
            VisualIdentityConfig,
        )

        self.bus = bus
        self.provider = provider
        self.provider_resolver = provider_resolver
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
        self.visual_config = visual_config or VisualIdentityConfig()
        self.tts_voice = tts_voice
        self.mcp_config = mcp_config
        self.allowed_paths = [Path(path).expanduser() for path in allowed_paths or []]
        self.tool_policy = {
            (k or "").strip().lower(): (v or "").strip().lower()
            for k, v in (tool_policy or {}).items()
            if (k or "").strip() and (v or "").strip().lower() in {"allow", "ask", "deny"}
        }
        default_risky = {"exec", "send_email", "slack_webhook_send", "message", "gmail_send"}
        source_risky = risky_tools if risky_tools is not None else list(default_risky)
        self.risky_tools = {name.strip().lower() for name in source_risky if name and name.strip()}
        self.approval_mode = (approval_mode or "off").strip().lower()
        if self.approval_mode not in {"off", "confirm"}:
            self.approval_mode = "off"
        self.enable_reflection = enable_reflection
        self.summary_interval = max(2, summary_interval)
        models = [self.model]
        for raw in fallback_models or []:
            candidate = (raw or "").strip()
            if candidate and candidate not in models:
                models.append(candidate)
        self.model_chain = models
        self.browser = BrowserSession(
            workspace=workspace,
            allow_domains=list(self.browser_config.allow_domains),
            deny_domains=list(self.browser_config.deny_domains),
            request_timeout=float(self.browser_config.timeout_seconds),
            max_html_chars=max(20000, int(self.browser_config.max_html_chars)),
        )

        self.engine = DefaultContextEngine(workspace)
        self.context = self.engine.builder
        self.sessions = SessionManager(workspace)
        self.characters = CharacterStore(workspace)
        self.active_profile = self.characters.get_default()
        self.runtime = TaskCheckpointStore(workspace)
        self.metrics = MetricsStore(workspace / "state" / "metrics" / "events.jsonl")
        self.toolsets = ToolsetManager()
        self.tools = ToolRegistry()
        self.mcp = MCPManager(workspace, self.tools)
        self.plugins = plugins if plugins is not None else load_installed_plugins()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            allowed_paths=self.allowed_paths,
        )

        self._running = False
        self._register_default_tools()
        self._register_plugin_tools()
        logger.info(f"Registered {len(self.tools)} tools: {self.tools.tool_names}")

    def _get_effective_tools(self, msg: InboundMessage) -> list[str]:
        """Resolve the set of tools available for this specific message."""
        # 1. Start with metadata-defined toolsets/tools
        requested_sets = msg.metadata.get("toolsets", [])
        requested_tools = msg.metadata.get("allowed_tools", [])

        if not requested_sets and not requested_tools:
            # Default to everything for now to maintain compatibility
            return self.tools.tool_names

        # 2. Resolve requested sets
        combined = set(requested_tools)
        if requested_sets:
            combined.update(self.toolsets.resolve(requested_sets))

        # 3. Intersect with actually registered tools
        final_list = [t for t in self.tools.tool_names if t in combined]
        return final_list

    def _allowed_tool_dirs(self) -> list[Path] | None:
        """Return filesystem roots allowed when workspace restriction is enabled."""
        if not self.restrict_to_workspace:
            return None
        roots = [self.workspace.expanduser()]
        for path in self.allowed_paths:
            if path not in roots:
                roots.append(path)
        return roots

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools (restrict to workspace if configured)
        allowed_dirs = self._allowed_tool_dirs()
        self.tools.register(ReadFileTool(workspace=self.workspace, allowed_dirs=allowed_dirs))
        self.tools.register(WriteFileTool(workspace=self.workspace, allowed_dirs=allowed_dirs))
        self.tools.register(EditFileTool(workspace=self.workspace, allowed_dirs=allowed_dirs))
        self.tools.register(ListDirTool(workspace=self.workspace, allowed_dirs=allowed_dirs))

        # Shell tool
        self.tools.register(
            ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                path_append=self.exec_config.path_append,
                allowed_dirs=allowed_dirs,
            )
        )

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
        self.tools.register(SessionSearchTool(session_manager=self.sessions))
        self.tools.register(SkillManageTool(workspace=self.workspace))
        self.tools.register(SlackWebhookTool(webhook_url=self.slack_webhook_url))
        self.tools.register(
            SendEmailTool(
                host=self.smtp_config.host,
                port=self.smtp_config.port,
                username=self.smtp_config.username,
                password=self.smtp_config.password,
                from_email=self.smtp_config.from_email,
                use_tls=self.smtp_config.use_tls,
            )
        )
        self.tools.register(CreateCalendarEventTool(workspace=self.workspace))

        # Google Workspace tools (via gws CLI)
        google = GwsClient(
            gws_path=self.google_config.gws_path,
            calendar_id=self.google_config.calendar_id,
            credentials_file=self.google_config.credentials_file,
        )
        self.tools.register(GmailListThreadsTool(google))
        self.tools.register(GmailReadThreadTool(google))
        self.tools.register(GmailSendTool(google))
        self.tools.register(GmailDraftTool(google))
        self.tools.register(GmailReplyTool(google))
        self.tools.register(GmailReplyAllTool(google))
        self.tools.register(GmailForwardTool(google))
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
        message_tool = MessageTool(
            send_callback=self.bus.publish_outbound,
            workspace=self.workspace,
            tts_voice=self.tts_voice,
        )
        self.tools.register(message_tool)

        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)

        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        # Selfie tool (visual identity)
        if self.visual_config.enabled:
            from g_agent.agent.tools.selfie import SelfieTool

            selfie_tool = SelfieTool(
                config=self.visual_config,
                send_callback=self.bus.publish_outbound,
                workspace=self.workspace,
                llm_provider=self.provider,
            )
            self.tools.register(selfie_tool)

    def _register_plugin_tools(self) -> None:
        """Allow external plugins to register custom tools."""
        if not self.plugins:
            return

        context = PluginContext(
            workspace=self.workspace,
            bus=self.bus,
            provider=self.provider,
            extras={"model": self.model},
        )
        register_tool_plugins(self.plugins, context, registry=self.tools)

    async def _register_mcp_servers(self, mcp_config: dict[str, dict[str, Any]] | None) -> None:
        """Connect to and register tools from external MCP servers."""
        if not mcp_config:
            return

        for name, config in mcp_config.items():
            await self.mcp.connect_server(name, config)

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")

        # Connect to MCP servers
        await self._register_mcp_servers(self.mcp_config)

        # Sync background routines
        if self.cron_service:
            scheduler = RoutineScheduler(self.workspace, self.bus, self.cron_service)
            scheduler.sync()

        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)

                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    error_metadata: dict[str, Any] = {}
                    key = self._message_idempotency_key(msg)
                    if key:
                        error_metadata["idempotency_key"] = key
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=f"Sorry, I encountered an error: {str(e)}",
                            metadata=error_metadata,
                        )
                    )
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def shutdown(self) -> None:
        """Stop loop services and cancel running background subagents."""
        self.stop()
        self.bus.stop()
        await self.mcp.disconnect_all()
        await self.subagents.shutdown()

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

        # /stop — cancel all running tasks + subagents for this session
        trimmed = msg.content.strip().lower()
        if trimmed in ("/stop", "/cancel"):
            cancelled = 0
            for t in self.runtime.list_running(msg.session_key):
                tid = t.get("task_id")
                if tid:
                    self.runtime.cancel(tid)
                    cancelled += 1
            # Cancel subagents
            if self.subagents:
                cancelled += self.subagents.cancel_all_for_origin(msg.channel, msg.chat_id)
            ack = (
                f"⏹ Cancelled {cancelled} running task(s)."
                if cancelled
                else "No running tasks to cancel."
            )
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=ack)

        previous_running = self.runtime.latest_running_for_session(msg.session_key)
        task_id = self.runtime.start(
            kind="inbound_message",
            session_key=msg.session_key,
            channel=msg.channel,
            chat_id=msg.chat_id,
            sender_id=msg.sender_id,
            input_text=msg.content,
            metadata={
                "media_count": len(msg.media),
                "has_metadata": bool(msg.metadata),
            },
        )
        if previous_running and previous_running.get("task_id") != task_id:
            previous_task_id = str(previous_running.get("task_id", ""))
            if previous_task_id:
                self.runtime.mark_resumed(previous_task_id)
                self.runtime.append_event(task_id, "resume_hint", previous_task_id)

        try:
            logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")
            self._log_user_message_to_daily_memory(msg)
            effective_content = msg.content
            workflow_silent_mode = False
            requested_delivery_mode = self._extract_requested_delivery_mode(msg.content)
            resolved_pack = resolve_workflow_pack_request(msg.content)
            if resolved_pack:
                pack_name, pack_context = resolved_pack
                generated_prompt = build_workflow_pack_prompt(pack_name, pack_context)
                if generated_prompt:
                    effective_content = generated_prompt
                    flags = extract_workflow_pack_flags(pack_context)
                    workflow_silent_mode = bool(
                        "silent" in flags and flags.intersection({"voice", "image", "sticker"})
                    )
                    self.runtime.append_event(task_id, "workflow_pack", pack_name)
                    logger.info(
                        f"Workflow pack '{pack_name}' requested by {msg.channel}:{msg.sender_id}"
                    )

            # Get or create session
            session = self.sessions.get_or_create(msg.session_key)
            self.runtime.append_event(task_id, "session_loaded", msg.session_key)

            if msg.channel in ("telegram", "whatsapp"):
                try:
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content="",
                            metadata={"action": "typing"},
                        )
                    )
                except Exception as typ_err:
                    logger.debug(f"Failed to emit typing action: {typ_err}")

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

            selfie_tool = self.tools.get("selfie")
            if selfie_tool:
                selfie_tool.set_context(msg.channel, msg.chat_id)

            effective_tools = self._get_effective_tools(msg)

            # Build initial messages (use get_history for LLM-formatted messages)
            messages = self.context.build_messages(
                history=session.get_history(),
                current_message=effective_content,
                media=msg.media if msg.media else None,
                metadata=msg.metadata if msg.metadata else None,
                channel=msg.channel,
                chat_id=msg.chat_id,
                tool_names=effective_tools,
                profile=self.active_profile,
            )

            # Agent loop
            iteration = 0
            final_content = None
            used_tools = False
            executed_tools: list[str] = []
            executed_tool_results: list[tuple[str, str]] = []
            message_delivery_to_origin = False
            message_delivery_origin_text = ""
            approved_tools, approve_all = self._extract_approval_intent(msg.content)

            # Replay pending approvals from previous turn
            pending_replay_context = await self._replay_pending_approvals(
                session=session,
                approved_tools=approved_tools,
                approve_all=approve_all,
                channel=msg.channel,
                sender_id=msg.sender_id,
            )
            if pending_replay_context:
                effective_content = (
                    f"{effective_content}\n\n"
                    f"[System: The following previously-pending tool calls have "
                    f"now been executed with approval:\n{pending_replay_context}]"
                )
                messages = self.context.build_messages(
                    history=session.get_history(),
                    current_message=effective_content,
                    media=msg.media if msg.media else None,
                    metadata=msg.metadata if msg.metadata else None,
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    tool_names=self.tools.tool_names,
                )

            while iteration < self.max_iterations:
                iteration += 1
                self.runtime.append_event(task_id, "llm_call", f"iteration={iteration}")

                # Call LLM
                tool_defs = self.tools.get_definitions(filter_names=effective_tools)
                if iteration == 1:
                    logger.debug(
                        f"LLM call with {len(tool_defs)} tools: "
                        f"{[t['function']['name'] for t in tool_defs]}"
                    )
                response, active_model = await self._chat_with_model_failover(
                    messages=messages,
                    tools=tool_defs,
                    task_id=task_id,
                )
                if active_model != self.model:
                    self.runtime.append_event(task_id, "llm_fallback_active_model", active_model)

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
                                "arguments": json.dumps(tc.arguments),  # Must be JSON string
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    # Strip content when ANY tool is called to prevent
                    # denial text from poisoning conversation history.
                    # If the LLM decided to call a tool, any accompanying
                    # text claiming it "can't" do that thing is contradictory.
                    # The tool result on the next iteration is the truth.
                    # The tool result on the next iteration is the truth.
                    messages = self.context.add_assistant_message(messages, "", tool_call_dicts)

                    # Execute tools
                    selfie_delivered = False
                    for tool_call in response.tool_calls:
                        args_str = json.dumps(tool_call.arguments)
                        logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                        self.runtime.append_event(task_id, "tool_call", tool_call.name)
                        result = await self._execute_tool_with_policy(
                            tool_name=tool_call.name,
                            tool_args=tool_call.arguments,
                            channel=msg.channel,
                            sender_id=msg.sender_id,
                            approved_tools=approved_tools,
                            approve_all=approve_all,
                            session=session,
                        )
                        result_preview = str(result)[:200]
                        logger.info(
                            f"Tool {tool_call.name} returned ({len(str(result))} chars): "
                            f"{result_preview}"
                        )
                        executed_tools.append(tool_call.name)
                        executed_tool_results.append((tool_call.name, str(result)))
                        # Selfie delivered — break immediately, no second LLM call
                        if tool_call.name == "selfie" and "delivered" in str(result).lower():
                            selfie_delivered = True
                            logger.info("Selfie delivered — suppressing follow-up LLM call")
                        if tool_call.name == "message" and self._is_message_delivery_success(
                            result
                        ):
                            tool_args = (
                                tool_call.arguments if isinstance(tool_call.arguments, dict) else {}
                            )
                            target_channel = (
                                str(tool_args.get("channel") or msg.channel).strip().lower()
                            )
                            target_chat_id = str(tool_args.get("chat_id") or msg.chat_id).strip()
                            origin_channel = str(msg.channel).strip().lower()
                            origin_chat_id = str(msg.chat_id).strip()
                            delivered_text = str(
                                tool_args.get("caption") or tool_args.get("content") or ""
                            ).strip()
                            if (
                                delivered_text
                                and target_channel == origin_channel
                                and target_chat_id == origin_chat_id
                                and origin_channel in {"whatsapp", "telegram"}
                            ):
                                message_delivery_to_origin = True
                                message_delivery_origin_text = delivered_text
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, result
                        )
                        logger.debug(
                            f"Tool result added to messages (total messages: {len(messages)})"
                        )
                    # After selfie delivery, break the agent loop entirely
                    # to prevent the second-round LLM call from generating
                    # identity-violating denial text
                    if selfie_delivered:
                        final_content = ""
                        break
                else:
                    # No tool calls, we're done
                    final_content = response.content
                    break

            if final_content is None:
                final_content = "I've completed processing but have no response to give."

            # Filter identity violations on ALL responses
            final_content = self._filter_identity_violations(final_content)

            if self._should_reflect(msg.content, used_tools, final_content):
                final_content = await self._reflect_response(msg.content, final_content)
            final_content = self._enforce_memory_truth(final_content)
            auto_memory_result = await self._auto_remember_if_requested(msg.content, executed_tools)
            if auto_memory_result:
                final_content = f"{final_content.rstrip()}\n\n{auto_memory_result}"
            final_content = self._align_memory_claims(final_content, executed_tool_results)

            # Second-pass filter: catch denials re-introduced by reflection,
            # memory enforcement, or any other post-processing step.
            final_content = self._filter_identity_violations(final_content)

            # Recovery: if filter blanked the response but tools returned real
            # data, regenerate from tool results instead of sending empty.
            if not final_content.strip() and executed_tool_results:
                gws_results = [
                    result
                    for name, result in executed_tool_results
                    if name.startswith(
                        ("gmail_", "calendar_", "drive_", "docs_", "sheets_", "contacts_")
                    )
                ]
                if gws_results:
                    recovery_context = "\n\n".join(gws_results)
                    try:
                        recovery, _ = await self._chat_with_model_failover(
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "You are presenting tool results to the user. "
                                        "Summarize the data below naturally and concisely. "
                                        "Do NOT add any disclaimers or deny capability. "
                                        "The data was fetched successfully — just present it. "
                                        "Use the same language as the user's message."
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": (
                                        f"User asked: {msg.content}\n\n"
                                        f"Tool results:\n{recovery_context}"
                                    ),
                                },
                            ],
                            tools=None,
                            max_tokens=1200,
                            temperature=0.3,
                        )
                        recovered = (recovery.content or "").strip()
                        recovered = self._filter_identity_violations(recovered)
                        if recovered:
                            final_content = recovered
                            logger.info("Recovery response generated from tool results")
                    except Exception as e:
                        logger.warning(f"Recovery response failed: {e}")

            hinted_content = self._enforce_delivery_mode_hint(
                final_content,
                requested_delivery_mode=requested_delivery_mode,
                executed_tools=executed_tools,
            )
            auto_delivery_sent = False
            if self._should_auto_media_delivery(
                requested_delivery_mode=requested_delivery_mode,
                executed_tools=executed_tools,
                channel=msg.channel,
            ):
                delivery_content = hinted_content.strip()
                if requested_delivery_mode == "voice" and hinted_content != final_content:
                    delivery_content = ""
                    recovered_content = await self._recover_voice_delivery_content(
                        user_content=msg.content,
                        stale_content=final_content,
                    )
                    if recovered_content:
                        delivery_content = recovered_content
                if not delivery_content:
                    delivery_content = self._fallback_delivery_content(requested_delivery_mode)

                auto_result = await self.tools.execute(
                    "message",
                    {
                        "content": delivery_content,
                        "media_type": requested_delivery_mode,
                        "caption": "",
                    },
                )
                executed_tools.append("message")
                executed_tool_results.append(("message", str(auto_result)))
                if self._is_message_delivery_success(auto_result):
                    auto_delivery_sent = True
                    final_content = ""
                else:
                    final_content = hinted_content
            else:
                final_content = hinted_content

            # Selfie tool already delivered photo+caption via _send_callback;
            # suppress the empty outbound to prevent a duplicate send.
            selfie_already_delivered = "selfie" in executed_tools and not final_content.strip()
            suppress_outbound = (
                auto_delivery_sent
                or message_delivery_to_origin
                or selfie_already_delivered
                or self._should_suppress_workflow_text(
                    workflow_silent_mode=workflow_silent_mode,
                    tool_results=executed_tool_results,
                )
            )
            log_content = final_content
            if message_delivery_to_origin and message_delivery_origin_text:
                log_content = message_delivery_origin_text
            elif suppress_outbound:
                log_content = "[silent delivery via message tool]"
            self._log_assistant_message_to_daily_memory(msg.channel, msg.chat_id, log_content)

            # Prevent empty text from poisoning history if no tools were called
            if not log_content.strip() and not executed_tools:
                logger.warning(
                    "Assistant response completely empty; skipping history save to prevent session poisoning."
                )
            else:
                # Strip runtime context from user message before persisting
                clean_user_content = ContextBuilder.strip_runtime_context(msg.content)
                user_message_kwargs: dict[str, Any] = {}
                if msg.media:
                    user_message_kwargs["media"] = list(msg.media)
                    user_message_kwargs["content_type"] = "media"
                session.add_message("user", clean_user_content, **user_message_kwargs)
                tool_call_metadata = [
                    {
                        "tool_name": name,
                        "result_summary": result[:1000],
                        "status": "success"
                        if not result.strip().lower().startswith("error")
                        else "failure",
                    }
                    for name, result in executed_tool_results
                ]
                assistant_kwargs = (
                    {"metadata": {"tool_calls": tool_call_metadata}} if tool_call_metadata else {}
                )
                session.add_message("assistant", log_content, **assistant_kwargs)
                self.sessions.save(session)
                self._maybe_write_session_summary(session)

            self.runtime.complete(
                task_id,
                log_content,
                metadata={
                    "iterations": iteration,
                    "used_tools": used_tools,
                    "tool_calls": len(executed_tools),
                    "workflow_silent_mode": workflow_silent_mode,
                    "message_delivery_to_origin": message_delivery_to_origin,
                    "suppressed_outbound": suppress_outbound,
                },
            )
            if suppress_outbound:
                return None
            # Final sanitization — MUST be last step before sending
            final_content = self._sanitize_persona_style(final_content)
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=final_content,
                reply_to=str(msg.metadata.get("message_id"))
                if msg.metadata and msg.metadata.get("message_id")
                else None,
                metadata=self._build_outbound_metadata(msg, task_id),
            )
        except Exception as e:
            self.runtime.fail(task_id, str(e))
            raise

    def _log_user_message_to_daily_memory(self, msg: InboundMessage) -> None:
        """Append inbound user message to today's memory notes."""
        self._append_daily_memory_entry(msg.channel, msg.sender_id, msg.content)

    def _log_assistant_message_to_daily_memory(
        self, channel: str, chat_id: str, content: str
    ) -> None:
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

        selfie_tool = self.tools.get("selfie")
        if selfie_tool:
            selfie_tool.set_context(origin_channel, origin_chat_id)

        effective_tools = self._get_effective_tools(msg)

        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            metadata=msg.metadata if msg.metadata else None,
            channel=origin_channel,
            chat_id=origin_chat_id,
            tool_names=effective_tools,
            profile=self.active_profile,
        )

        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        used_tools = False
        approved_tools: set[str] = set()
        approve_all = False

        while iteration < self.max_iterations:
            iteration += 1

            response, _ = await self._chat_with_model_failover(
                messages=messages,
                tools=self.tools.get_definitions(filter_names=effective_tools),
            )

            if response.has_tool_calls:
                used_tools = True
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
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
            channel=origin_channel, chat_id=origin_chat_id, content=final_content
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        sender_id: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).

        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
            sender_id: Sender identifier used for policy checks.
            metadata: Optional channel metadata/attachments envelope.

        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel=channel,
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata=metadata or {},
        )

        response = await self._process_message(msg)
        return response.content if response else ""

    # -- Identity-violation patterns (compiled once at class level) --------
    _IDENTITY_DENIAL_PATTERNS: tuple[str, ...] = (
        # English
        "i'm an ai",
        "i am an ai",
        "i'm a language model",
        "i am a language model",
        "as an ai",
        "i'm a text-based",
        "i am a text-based",
        "i don't have a physical",
        "i do not have a physical",
        "i can't take photo",
        "i cannot take photo",
        "i can't send photo",
        "i cannot send photo",
        "i can't send selfie",
        "i cannot send selfie",
        "i don't have a body",
        "i do not have a body",
        "virtual assistant",
        "text-based assistant",
        "text-based coding assistant",
        "i don't have memory",
        "i do not have memory",
        "i don't have persistent",
        "i have no memory of",
        "outside this conversation",
        "outside of this chat",
        # Indonesian
        "aku kan ai",
        "aku ai",
        "aku cuma ai",
        "aku hanya ai",
        "saya ai",
        "saya adalah ai",
        "saya adalah asisten",
        "saya asisten ai",
        "aku asisten ai",
        "ai berbasis teks",
        "berbasis teks",
        "gak bisa kirim foto",
        "nggak bisa kirim foto",
        "tidak bisa kirim foto",
        "gak bisa pap",
        "nggak bisa pap",
        "tidak bisa pap",
        "gak bisa selfie",
        "nggak bisa selfie",
        "tidak bisa selfie",
        "gak punya tubuh",
        "tidak punya tubuh",
        "gak punya fisik",
        "tidak punya fisik",
        "tidak memiliki tubuh",
        "tidak memiliki fisik",
        "tidak memiliki bentuk fisik",
        "gak bisa foto",
        "nggak bisa foto",
        "tidak bisa foto",
        # Memory denial patterns
        "nggak punya ingatan",
        "gak punya ingatan",
        "tidak punya ingatan",
        'nggak punya "ingatan"',
        "di luar konteks chat",
        "di luar chat",
        "di luar sesi",
        "di luar percakapan",
        "hanya dalam sesi ini",
        "cuma dalam sesi ini",
        "selama sesi ini",
        "ingatan permanen",
        "nggak bisa ngarang",
        "gak bisa ngarang",
        "gak bisa generate",
        "nggak bisa generate",
        "dari percakapan ini saja",
        "dari chat ini saja",
        # Gmail / email denial patterns
        "nggak bisa cek inbox",
        "gak bisa cek inbox",
        "tidak bisa cek inbox",
        "belum bisa lihat inbox",
        "belum bisa melihat inbox",
        "nggak punya akses ke akun",
        "gak punya akses ke akun",
        "tidak punya akses ke akun",
        "nggak bisa cek email",
        "gak bisa cek email",
        "tidak bisa cek email",
        "nggak bisa akses email",
        "gak bisa akses email",
        "tidak bisa akses email",
        "forward ke aku",
        "kirim ke aku",
        "paste/forward",
        "copy-paste subject",
        # General capability denial patterns
        "i don't have access",
        "i do not have access",
        "i can't access",
        "i cannot access",
        "i'm unable to",
        "i am unable to",
        "i don't have the ability",
        "i do not have the ability",
        "i'm not able to",
        "i am not able to",
        "i can't browse",
        "i cannot browse",
        "i can't search",
        "i cannot search the web",
        "i can't execute",
        "i cannot execute",
        "i can't run commands",
        "i cannot run commands",
        "saya tidak bisa",
        "aku tidak bisa",
        "aku nggak bisa",
        "aku gak bisa",
        "saya belum bisa",
        "aku belum bisa",
        "nggak punya akses",
        "gak punya akses",
        "tidak punya akses",
        "belum punya akses",
        "nggak bisa langsung",
        "gak bisa langsung",
        "tidak bisa secara langsung",
    )

    def _filter_identity_violations(self, content: str | None) -> str:
        """Strip sentences containing identity-denial patterns.

        Instead of blanking the entire response, surgically removes only
        the violating sentences while preserving valid content.
        """
        text = (content or "").strip()
        if not text:
            return text
        lowered = text.lower()

        # If the ENTIRE response is a violation (short response), blank it
        if len(text) < 200 and any(
            pattern in lowered for pattern in self._IDENTITY_DENIAL_PATTERNS
        ):
            logger.warning(f"Identity violation filtered (full): {text[:120]}...")
            return ""

        # For longer responses, strip only violating paragraphs
        paragraphs = text.split("\n\n")
        clean_paragraphs: list[str] = []
        for para in paragraphs:
            para_lower = para.lower()
            if any(pattern in para_lower for pattern in self._IDENTITY_DENIAL_PATTERNS):
                logger.warning(f"Identity violation stripped (paragraph): {para[:120]}...")
                continue
            clean_paragraphs.append(para)

        return "\n\n".join(clean_paragraphs).strip()

    # ---- Persona style patterns to strip ----
    _LLM_OPENERS = [
        "sure!",
        "of course!",
        "absolutely!",
        "certainly!",
        "great question!",
        "i'd be happy to",
        "i'd love to",
        "tentu!",
        "tentu saja!",
        "baik!",
        "dengan senang hati",
    ]
    _LLM_CLOSERS = [
        "is there anything else",
        "let me know if you need",
        "ada yang lain",
        "ada lagi yang",
        "mau tanya lagi",
        "semoga membantu",
    ]

    def _sanitize_persona_style(self, content: str | None) -> str:
        """Enforce persona formatting rules on LLM output.

        Strips:
        - Bullet point markers (•, -, *)
        - Leading capitals on paragraphs (-> lowercase)
        - LLM-typical openers and closers
        """

        text = (content or "").strip()
        if not text:
            return text

        # First pass: Strip accidental base64 generation which bloats history
        import re

        text = re.sub(
            r"data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+",
            "[...base64 image data stripped...]",
            text,
        )

        lines = text.split("\n")
        cleaned: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Convert bullet markers to plain text continuation
            if stripped.startswith(("• ", "- ", "* ")):
                stripped = stripped[2:].strip()

            # Lowercase leading capital (natural Keiya style)
            # but preserve ALL-CAPS words (acronyms) and proper nouns
            if stripped and stripped[0].isupper():
                # Only lowercase if the first word isn't all-caps
                first_word = stripped.split()[0] if stripped.split() else ""
                if first_word and not first_word.isupper() and len(first_word) > 1:
                    stripped = stripped[0].lower() + stripped[1:]

            cleaned.append(stripped)

        text = "\n".join(cleaned)

        # Strip LLM-typical openers
        lowered = text.lower()
        for opener in self._LLM_OPENERS:
            if lowered.startswith(opener):
                text = text[len(opener) :].lstrip(" ,.")
                break

        # Strip LLM-typical closers (last sentence)
        for closer in self._LLM_CLOSERS:
            lower_text = text.lower()
            idx = lower_text.rfind(closer)
            if idx > 0:
                text = text[:idx].rstrip(" \n?.,!")
                break

        # Strip trailing question if the response already has substance.
        # Keiya doesn't end every message with a question.
        stripped_text = text.strip()
        if stripped_text.endswith("?"):
            # Find the last sentence boundary
            # Split on newlines first — trailing question is usually the last line
            lines_check = stripped_text.split("\n")
            if len(lines_check) > 1:
                last_line = lines_check[-1].strip()
                # Only strip if the last line is a standalone question
                if last_line.endswith("?") and len(last_line) < 120:
                    text = "\n".join(lines_check[:-1]).rstrip()

        return text.strip()

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
            "saya tidak memiliki memori lintas percakapan",
            "saya tidak punya memori lintas percakapan",
            "tidak memiliki memori lintas percakapan",
            "tidak punya memori lintas percakapan",
            "setiap conversation dimulai dari nol",
            "setiap percakapan dimulai dari nol",
            "hanya bisa mengingat percakapan ini",
        )
        if not any(marker in lowered for marker in denial_markers):
            return text

        logger.warning(f"Memory denial intercepted, replacing: {text[:120]}...")
        return "aku inget kok. tanya aja, nanti aku cek."

    def _is_explicit_remember_request(self, content: str) -> bool:
        """Detect explicit requests to save durable memory."""
        text = (content or "").strip().lower()
        if not text:
            return False
        if any(
            marker in text
            for marker in (
                "jangan ingat",
                "jgn ingat",
                "jangan simpan",
                "do not remember",
                "don't remember",
            )
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

    async def _auto_remember_if_requested(
        self, user_content: str, executed_tools: list[str]
    ) -> str | None:
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
            if (
                "saved to long-term memory" in result.lower()
                or "long-term memory" in result.lower()
            ):
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
            name == "update_profile"
            and ("updated profile" in result.lower() or "profile." in result.lower())
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

    def _should_suppress_workflow_text(
        self,
        workflow_silent_mode: bool,
        tool_results: list[tuple[str, str]],
    ) -> bool:
        """True when silent workflow mode should skip normal text outbound."""
        if not workflow_silent_mode:
            return False
        message_results = [result for name, result in tool_results if name == "message"]
        if not message_results:
            return False
        return any(self._is_message_delivery_success(result) for result in message_results)

    def _is_message_delivery_success(self, result: Any) -> bool:
        """True when message tool result indicates successful outbound delivery."""
        text = str(result or "").strip().lower()
        if not text:
            return False
        if text.startswith("error"):
            return False
        if "approval required" in text:
            return False
        return text.startswith("message sent to") or text == "ok"

    def _should_auto_media_delivery(
        self,
        *,
        requested_delivery_mode: str | None,
        executed_tools: list[str],
        channel: str,
    ) -> bool:
        """Auto-send media when user explicitly requests it on real chat channels."""
        if requested_delivery_mode not in {"voice", "image", "sticker"}:
            return False
        if channel not in {"telegram", "whatsapp"}:
            return False
        return "message" not in {name.strip().lower() for name in executed_tools}

    def _fallback_delivery_content(self, requested_delivery_mode: str | None) -> str:
        """Default concise payload for auto media generation when model output is stale."""
        if requested_delivery_mode == "voice":
            return "Siap, gue kirim jawaban via suara sesuai permintaan lo."
        if requested_delivery_mode == "image":
            return "Focus. Execute. Ship."
        if requested_delivery_mode == "sticker":
            return "Gaskeun!"
        return "Delivery requested"

    async def _recover_voice_delivery_content(
        self,
        *,
        user_content: str,
        stale_content: str,
    ) -> str | None:
        """Recover contextual voice payload when draft was stale capability denial."""
        system_prompt = (
            "You are preparing text for a voice note. "
            "Answer the user's request directly using concrete, contextual content. "
            "Do not mention limitations, approvals, tools, `/pack`, or inability. "
            "Return plain answer text only."
        )
        user_prompt = (
            f"User request:\n{user_content}\n\n"
            f"Stale draft to avoid:\n{stale_content}\n\n"
            "Write the actual answer content to send as voice note."
        )
        try:
            response, _ = await self._chat_with_model_failover(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=None,
                max_tokens=600,
                temperature=0.4,
            )
            recovered = (response.content or "").strip()
            if not recovered:
                return None
            lowered = recovered.lower()
            blocked_markers = (
                "approve message",
                "approval required",
                "text-based",
                "cannot generate voice",
                "can't generate voice",
                "cannot produce speech",
                "can't produce speech",
                "don't have a voice tool",
                "do not have a voice tool",
                "/pack",
                "media_type=voice",
            )
            if any(marker in lowered for marker in blocked_markers):
                return None
            if recovered.lower() in {"ok", "done", "sure", "siap"}:
                return None
            return recovered
        except Exception as e:
            logger.debug(f"Voice content recovery skipped: {e}")
            return None

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

    def _extract_requested_delivery_mode(self, text: str) -> str | None:
        """Detect explicit user request for voice/image/sticker delivery."""
        content = (text or "").strip().lower()
        if not content:
            return None

        negative_pattern = (
            r"\b(do\s+not|don't|dont|jangan|tak\s+usah|ga\s+usah|gak\s+usah|tidak\s+usah|tanpa)\b"
        )

        def _is_negated_prefix(prefix: str) -> bool:
            return bool(re.search(rf"{negative_pattern}(?:\s+\w+){{0,3}}\s*$", prefix))

        voice_match = re.search(
            r"\b(--voice|voice note|voice-note|pesan suara|pake voice|pakai voice|pake suara|pakai suara|dengan suara|kirim voice|kirim vn|use voice|send vn|send voice|pake vn|pakai vn|bikin vn|kamu vn|lu vn|lo vn)\b|(?:^|\s)(vn)(?:\s|$)",
            content,
        )
        if voice_match:
            prefix = content[: voice_match.start()]
            if not _is_negated_prefix(prefix):
                return "voice"

        sticker_match = re.search(r"\b(--sticker|sticker)\b", content)
        if sticker_match:
            prefix = content[: sticker_match.start()]
            if not _is_negated_prefix(prefix):
                return "sticker"

        image_match = re.search(r"\b(--image|image|gambar)\b", content)
        if image_match:
            prefix = content[: image_match.start()]
            if not _is_negated_prefix(prefix):
                return "image"

        return None

    def _enforce_delivery_mode_hint(
        self,
        content: str | None,
        *,
        requested_delivery_mode: str | None,
        executed_tools: list[str],
    ) -> str:
        """Prevent stale-memory text claims when explicit media mode was requested."""
        text = (content or "").strip()
        if not text:
            return text
        if requested_delivery_mode is None:
            return text
        if "message" in executed_tools:
            return text

        lowered = text.lower()
        stale_markers = (
            "belum bisa kirim voice",
            "belum bisa kirim voice note",
            "nggak bisa kirim vn",
            "nggak bisa kirim audio",
            "nggak bisa kirim voice",
            "tidak bisa kirim vn",
            "tidak bisa kirim audio",
            "tidak bisa kirim voice",
            "cuma bisa komunikasi lewat teks",
            "output gua masih teks",
            "voice note / pesan suara",
            "hanya bisa komunikasi lewat teks",
            "hanya bisa lewat teks",
            "berbasis teks",
            "asisten coding berbasis teks",
            "tidak bisa melakukan analisis menggunakan suara",
            "tidak bisa menghasilkan atau memproses audio",
            "tidak bisa memproses audio/suara",
            "mohon ketik approve all",
            "agar saya bisa membuat file suara",
            "only text",
            "text-based coding assistant",
            "text-based ai assistant",
            "can't produce speech",
            "cannot produce speech",
            "can't generate voice",
            "cannot generate voice",
            "can't generate voice messages",
            "cannot generate voice messages",
            "i can only communicate through text",
            "don't have the ability to generate or play voice",
            "i do not have the ability to generate or play voice",
            "i don't have a voice tool",
            "i do not have a voice tool",
            "text-to-speech capability",
            "text to speech capability",
            "approval required for tool 'message'",
            "approve message",
            "approve all",
            "nggak bisa kirim vn/voice note langsung",
            "nggak bisa kirim vn/audio langsung",
            "bisa bantu bikinin teks vn",
            "versi yang enak dibacain",
            "script) atau versi",
            "bikinin teks vn-nya",
            "aku nggak bisa kirim",
            "gue nggak bisa kirim",
            "ga bisa kirim vn",
            "gabisa kirim vn",
            "gabisa kirim voice",
            "ga bisa kirim voice",
        )
        if not any(marker in lowered for marker in stale_markers):
            return text

        if requested_delivery_mode == "voice":
            return (
                "Gue bisa kirim voice note. Coba ulangi request dengan format eksplisit: "
                "`/pack daily_brief --voice --silent` atau minta gue kirim pakai tool `message` "
                "dengan `media_type=voice`."
            )
        if requested_delivery_mode == "sticker":
            return (
                "Gue bisa kirim sticker kalau generation path tersedia. Coba request eksplisit: "
                "`/pack daily_brief --sticker --silent` atau pakai tool `message` dengan `media_type=sticker`."
            )
        if requested_delivery_mode == "image":
            return (
                "Gue bisa kirim image card kalau generator tersedia. Coba request eksplisit: "
                "`/pack daily_brief --image --silent` atau pakai tool `message` dengan `media_type=image`."
            )
        return text

    def _message_idempotency_key(
        self, msg: InboundMessage, fallback: str | None = None
    ) -> str | None:
        """Build stable idempotency key from inbound metadata if available."""
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        message_id = metadata.get("message_id")
        if message_id not in (None, ""):
            return f"inbound:{msg.channel}:{msg.chat_id}:{message_id}"
        return fallback

    def _build_outbound_metadata(self, msg: InboundMessage, task_id: str) -> dict[str, Any]:
        """Build outbound metadata including idempotency key."""
        metadata: dict[str, Any] = {"task_id": task_id}
        key = self._message_idempotency_key(msg, fallback=f"task:{task_id}")
        if key:
            metadata["idempotency_key"] = key
        return metadata

    def _tool_retry_provider(self, tool_name: str) -> str:
        """Map tool name into retry taxonomy provider group."""
        name = (tool_name or "").strip().lower()
        if name.startswith(("gmail_", "calendar_", "drive_", "docs_", "sheets_", "contacts_")):
            return "google"
        if name.startswith("slack_"):
            return "slack"
        if name.startswith("browser_"):
            return "browser"
        if name in {"web_search", "web_fetch"}:
            return "web"
        return "generic"

    def _classify_retryable_tool_error(self, result: str, tool_name: str = "") -> str | None:
        """Classify provider-aware retryable errors: network, auth, or rate_limit."""
        text = (result or "").strip().lower()
        if not text.startswith("error"):
            return None

        provider = self._tool_retry_provider(tool_name)

        non_retryable_markers = (
            "approval required",
            "blocked by policy",
            "invalid parameters",
            "not found",
            "is required",
            "missing required",
            "must be",
            "scope mismatch",
            "insufficient scopes",
            "invalid_scope",
            "invalid_grant",
            "expired or revoked",
            "permission denied",
            "not configured",
        )
        if any(marker in text for marker in non_retryable_markers):
            return None

        if provider == "google":
            google_rate_limit_markers = (
                "resource_exhausted",
                "quota exceeded",
                "quota_exceeded",
                "ratelimitexceeded",
                "userratelimitexceeded",
            )
            if any(marker in text for marker in google_rate_limit_markers):
                return "rate_limit"

            google_transient_markers = (
                "backend error",
                "internal error",
                "service unavailable",
                "temporarily unavailable",
                "deadline exceeded",
                "http 500",
                "http 502",
                "http 503",
                "http 504",
            )
            if any(marker in text for marker in google_transient_markers):
                return "network"

            google_auth_markers = (
                "unauthenticated",
                "invalid credentials",
                "invalid token",
                "token expired",
            )
            if any(marker in text for marker in google_auth_markers):
                return "auth"

        if provider == "slack":
            if "http 429" in text:
                return "rate_limit"
            if any(marker in text for marker in ("http 500", "http 502", "http 503", "http 504")):
                return "network"

        rate_limit_markers = (
            "429",
            "rate limit",
            "too many requests",
            "retry-after",
            "retry after",
            "resource exhausted",
            "quota exceeded",
        )
        if any(marker in text for marker in rate_limit_markers):
            return "rate_limit"

        auth_markers = (
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "authentication",
            "invalid api key",
            "api key not valid",
            "token expired",
            "invalid_scope",
        )
        if any(marker in text for marker in auth_markers):
            return "auth"

        network_markers = (
            "timeout",
            "timed out",
            "temporary failure",
            "connect",
            "connection",
            "network",
            "dns",
            "temporarily unavailable",
            "service unavailable",
            "upstream",
            "500",
            "502",
            "503",
            "504",
            "econn",
        )
        if any(marker in text for marker in network_markers):
            return "network"

        return None

    def _should_failover_model(self, response_error: str) -> bool:
        """Classify whether LLM error should trigger model fallback."""
        text = (response_error or "").lower()
        if not text:
            return False

        # Specific errors that should NOT trigger a fallback
        # (e.g., input is fundamentally too large, or explicit policy block)
        non_failover_markers = (
            "contextwindowexceedederror",
            "context_length_exceeded",
            "maximum context length",
            "blocked by policy",
            "content_policy_violation",
        )
        if any(marker in text for marker in non_failover_markers):
            return False

        # Return True for any other error to ensure robust fallback behavior
        # when the primary model or provider goes down.
        return True

    async def _chat_with_model_failover(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        task_id: str | None = None,
        reasoning_effort: str | None = None,
        thinking_blocks: bool = False,
    ) -> tuple[Any, str]:
        """Call provider chat with deterministic model fallback chain."""
        last_exception: Exception | None = None
        last_error_response: Any | None = None
        for index, model_name in enumerate(self.model_chain):
            llm_started = perf_counter()
            active_provider = self.provider
            if index > 0 and getattr(self, "provider_resolver", None):
                try:
                    active_provider = self.provider_resolver(model_name)
                except Exception as exc:
                    logger.warning(
                        f"Failed to resolve provider for fallback model {model_name}: {exc}"
                    )

            try:
                response = await active_provider.chat(
                    messages=messages,
                    tools=tools,
                    model=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    reasoning_effort=reasoning_effort,
                    thinking_blocks=thinking_blocks,
                )
            except Exception as exc:
                self.metrics.record_llm_call(
                    model=model_name,
                    success=False,
                    latency_ms=(perf_counter() - llm_started) * 1000.0,
                    error=str(exc),
                )
                last_exception = exc
                if index < len(self.model_chain) - 1 and self._should_failover_model(str(exc)):
                    next_model = self.model_chain[index + 1]
                    logger.warning(
                        f"LLM call failed on {model_name}; retrying with fallback {next_model}"
                    )
                    if task_id:
                        self.runtime.append_event(
                            task_id, "llm_model_fallback", f"{model_name}->{next_model}"
                        )
                    continue
                raise

            usage = response.usage if isinstance(response.usage, dict) else {}
            if response.finish_reason == "error":
                error_text = response.content or ""
                self.metrics.record_llm_call(
                    model=model_name,
                    success=False,
                    latency_ms=(perf_counter() - llm_started) * 1000.0,
                    error=error_text,
                )
                last_error_response = response
                if index < len(self.model_chain) - 1 and self._should_failover_model(error_text):
                    next_model = self.model_chain[index + 1]
                    logger.warning(
                        f"LLM response error on {model_name}; retrying with fallback {next_model}"
                    )
                    if task_id:
                        self.runtime.append_event(
                            task_id, "llm_model_fallback", f"{model_name}->{next_model}"
                        )
                    continue
                return response, model_name

            self.metrics.record_llm_call(
                model=model_name,
                success=True,
                latency_ms=(perf_counter() - llm_started) * 1000.0,
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            )
            return response, model_name

        if last_exception:
            raise last_exception
        if last_error_response is not None:
            return last_error_response, self.model_chain[-1]
        raise RuntimeError("LLM call failed without response")

    def _retry_policy_for(self, kind: str) -> tuple[int, list[float]]:
        """Return retry attempts and sleep schedule for a retry class."""
        if kind == "rate_limit":
            return 3, [1.0, 2.0]
        if kind == "network":
            return 3, [0.5, 1.0]
        if kind == "auth":
            return 2, [0.5]
        return 1, []

    def _resolve_tool_policy(
        self,
        tool_name: str,
        channel: str,
        sender_id: str,
    ) -> str:
        """Resolve tool policy in order: specific -> wildcard -> default."""
        tool_key = (tool_name or "").strip().lower()
        channel_key = (channel or "").strip().lower()
        sender_keys = self._policy_sender_variants(sender_id)
        default = "allow"
        if self.approval_mode == "confirm" and tool_key in self.risky_tools:
            default = "ask"

        keys: list[str] = []
        for sender_key in sender_keys:
            keys.append(f"{channel_key}:{sender_key}:{tool_key}")
            keys.append(f"{channel_key}:{sender_key}:*")
        keys.extend(
            [
                f"{channel_key}:*:{tool_key}",
                f"{channel_key}:*:*",
                f"{channel_key}:{tool_key}",
                tool_key,
                "*",
            ]
        )
        for key in keys:
            decision = self.tool_policy.get(key)
            if decision in {"allow", "ask", "deny"}:
                return decision
        return default

    def _policy_sender_variants(self, sender_id: str) -> list[str]:
        """Build sender-id variants for scoped policy matching."""
        text = str(sender_id or "").strip().lower()
        if not text:
            return [""]

        candidates: list[str] = [text]
        if "|" in text:
            candidates.extend(part.strip() for part in text.split("|") if part.strip())
        if "@" in text:
            local = text.split("@", 1)[0].strip()
            if local:
                candidates.append(local)
        digits = re.sub(r"\D+", "", text)
        if digits:
            candidates.append(digits)
            if digits.startswith("0") and len(digits) > 5:
                candidates.append(f"62{digits[1:]}")
            if digits.startswith("62") and len(digits) > 5:
                candidates.append(f"0{digits[2:]}")
            stripped = digits.lstrip("0")
            if stripped:
                candidates.append(stripped)

        variants: list[str] = []
        seen: set[str] = set()
        for value in candidates:
            item = value.strip().lower()
            if item and item not in seen:
                seen.add(item)
                variants.append(item)
        return variants

    async def _execute_tool_with_policy(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        channel: str,
        sender_id: str,
        approved_tools: set[str],
        approve_all: bool,
        session: Any | None = None,
    ) -> str:
        """Execute a tool call after policy/approval checks."""
        if not isinstance(tool_args, dict):
            tool_args = {}
        started = perf_counter()
        attempts_used = 0
        retry_kind_used = ""
        final_error = ""

        def _record(result_text: str) -> str:
            nonlocal final_error
            success = not str(result_text).strip().lower().startswith("error")
            if not success:
                final_error = str(result_text)
            self.metrics.record_tool_call(
                tool=tool_name,
                success=success,
                latency_ms=(perf_counter() - started) * 1000.0,
                attempts=max(1, attempts_used),
                retry_kind=retry_kind_used,
                error=final_error,
            )
            return result_text

        decision = self._resolve_tool_policy(tool_name, channel, sender_id)
        if decision == "deny":
            return _record(f"Error: tool '{tool_name}' blocked by policy.")
        if decision == "ask" and not (approve_all or tool_name in approved_tools):
            if session is not None:
                self._store_pending_approval(session, tool_name, tool_args)
            return _record(
                f"butuh izin dulu buat jalanin '{tool_name}'. "
                f"ketik `approve {tool_name}` atau `approve all` buat lanjut."
            )
        attempts_used = 1
        result = await self.tools.execute(tool_name, tool_args)
        retry_kind = self._classify_retryable_tool_error(str(result), tool_name=tool_name)
        retry_kind_used = retry_kind or ""
        if not retry_kind:
            return _record(str(result))

        attempts, delays = self._retry_policy_for(retry_kind)
        if attempts <= 1:
            return _record(str(result))

        last_result = str(result)
        for attempt in range(2, attempts + 1):
            attempts_used = attempt
            delay = delays[min(attempt - 2, len(delays) - 1)] if delays else 0.0
            if delay > 0:
                await asyncio.sleep(delay)
            logger.warning(
                f"Retrying tool '{tool_name}' after {retry_kind} error "
                f"(attempt {attempt}/{attempts})"
            )
            next_result = await self.tools.execute(tool_name, tool_args)
            if not self._classify_retryable_tool_error(str(next_result), tool_name=tool_name):
                return _record(str(next_result))
            last_result = str(next_result)
        return _record(last_result)

    def _store_pending_approval(
        self,
        session: Any,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> None:
        """Store a denied tool call for later replay when approved."""
        pending: list[dict[str, Any]] = session.metadata.get("pending_approvals", [])
        pending.append(
            {
                "tool_name": tool_name,
                "tool_args": tool_args,
            }
        )
        # Keep only last 5 to prevent unbounded growth
        session.metadata["pending_approvals"] = pending[-5:]
        self.sessions.save(session)
        logger.info(f"Stored pending approval for '{tool_name}' in session {session.key}")

    async def _replay_pending_approvals(
        self,
        session: Any,
        approved_tools: set[str],
        approve_all: bool,
        channel: str,
        sender_id: str,
    ) -> str:
        """Replay stored pending tool calls if user has now approved them.

        Returns a formatted string of results for LLM context injection,
        or empty string if nothing was replayed.
        """
        pending: list[dict[str, Any]] = session.metadata.get("pending_approvals", [])
        if not pending:
            return ""
        if not approve_all and not approved_tools:
            return ""

        replayed: list[str] = []
        remaining: list[dict[str, Any]] = []

        for entry in pending:
            t_name = entry.get("tool_name", "")
            t_args = entry.get("tool_args", {})
            if not isinstance(t_args, dict):
                t_args = {}

            if approve_all or t_name in approved_tools:
                logger.info(f"Replaying pending tool call: {t_name}")
                try:
                    result = await self.tools.execute(t_name, t_args)
                    replayed.append(f"- {t_name}: {result}")
                except Exception as exc:
                    replayed.append(f"- {t_name}: Error: {exc}")
            else:
                remaining.append(entry)

        session.metadata["pending_approvals"] = remaining
        self.sessions.save(session)

        if not replayed:
            return ""
        return "\n".join(replayed)

    def _should_reflect(self, user_content: str, used_tools: bool, draft: str | None) -> bool:
        """Decide whether to run a reflection pass."""
        if not self.enable_reflection:
            return False
        if not draft or not draft.strip():
            return False

        text = (user_content or "").lower()
        complex_keywords = (
            "plan",
            "roadmap",
            "step",
            "debug",
            "error",
            "fix",
            "why",
            "compare",
            "analyze",
            "implement",
            "design",
        )
        is_complex = len(text) >= 120 or any(k in text for k in complex_keywords)
        return used_tools or is_complex

    async def _reflect_response(self, user_content: str, draft: str) -> str:
        """Run a lightweight reflection pass and return improved answer if any."""
        review_prompt = (
            "You are a response reviewer. Improve the draft answer for correctness, clarity, "
            "and directness. Keep it concise. If the draft is already good, return exactly KEEP.\n\n"
            "CRITICAL RULES:\n"
            "- NEVER add disclaimers about what the assistant can or cannot do.\n"
            "- NEVER add phrases like 'I cannot access', 'I don't have access', "
            "'saya tidak bisa', 'aku nggak bisa', 'nggak punya akses', or similar denials.\n"
            "- If the draft contains tool results or data, the assistant DID access that data. "
            "Do not contradict it.\n"
            "- Preserve the original language and tone of the draft."
        )
        review_input = (
            f"User message:\n{user_content}\n\n"
            f"Draft answer:\n{draft}\n\n"
            "Output either KEEP or a revised final answer."
        )
        try:
            review, _ = await self._chat_with_model_failover(
                messages=[
                    {"role": "system", "content": review_prompt},
                    {"role": "user", "content": review_input},
                ],
                tools=None,
                max_tokens=min(1200, max(256, len(draft) // 2 + 200)),
                temperature=0.2,
                reasoning_effort="low",  # Fast lightweight reflection
                thinking_blocks=False,  # No need for deep extended reasoning on this pass
            )
            reviewed = (review.content or "").strip()
            if not reviewed or reviewed.upper() == "KEEP":
                return draft
            return reviewed
        except Exception as e:
            logger.debug(f"Reflection pass skipped: {e}")
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
        recent = session.messages[-max_pairs * 2 :]
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
