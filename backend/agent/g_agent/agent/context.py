"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from pathlib import Path
from typing import Any

from g_agent.agent.memory import MemoryStore
from g_agent.agent.skills import SkillsLoader


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    """
    
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
    
    def build_system_prompt(
        self,
        skill_names: list[str] | None = None,
        current_message: str | None = None,
    ) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.
        
        Args:
            skill_names: Optional list of skills to include.
            current_message: Optional current user message for memory retrieval.
        
        Returns:
            Complete system prompt.
        """
        parts = []
        
        # Core identity
        parts.append(self._get_identity())
        
        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        # Memory context
        memory = self.memory.get_memory_context(
            query=current_message,
            include_full=not bool(current_message),
        )
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
        
        return f"""# g-agent

You are g-agent (Galyarder Agent), a pragmatic AI operator for this workspace.

You can use tools to:
- Read, write, edit, and list files
- Execute shell commands
- Search and fetch web content
- Use stateful browser actions (open/click/type/extract/screenshot)
- Send cross-channel messages
- Send Slack webhook and email messages
- Use Google Workspace tools (Gmail, Calendar, Drive, Docs, Sheets, Contacts) when configured
- Create calendar event files (.ics)
- Spawn subagents for background work
- Schedule tasks via cron
- Save durable memory and feedback lessons

## Operating Rules
- Be concise, accurate, and action-oriented.
- Prefer minimal, root-cause fixes over broad changes.
- State assumptions when uncertain and ask brief clarifying questions if needed.
- For normal conversation, respond directly in text.
- Use the `message` tool only when you must deliver content to a specific channel/chat.
- If a tool is approval-gated, ask user to resend with `approve <tool>` or `approve all`.
- If a tool fails, explain the failure plainly and provide the next best step.
- You have persistent cross-session memory. Never claim you only remember the current conversation.
- If user asks to remember/save a durable fact, use `remember` or `update_profile` before final reply.
- If user asks where memory is stored, state the exact memory file paths in this workspace.
- Respect workspace and security constraints.

## Current Time
{now}

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Profile: {workspace_path}/memory/PROFILE.md
- Relationships: {workspace_path}/memory/RELATIONSHIPS.md
- Projects: {workspace_path}/memory/PROJECTS.md
- Lessons: {workspace_path}/memory/LESSONS.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

When writing durable user/context facts, use `remember` and `update_profile` tools."""
    
    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []
        
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
        
        return "\n\n".join(parts) if parts else ""
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            metadata: Optional message metadata (including attachment envelope).
            channel: Current channel (telegram, feishu, etc.).
            chat_id: Current chat/user ID.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt
        system_prompt = self.build_system_prompt(
            skill_names=skill_names,
            current_message=current_message,
        )
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
        messages.append({"role": "system", "content": system_prompt})

        # History
        messages.extend(history)

        # Current message (with optional image attachments)
        user_content = self._build_user_content(current_message, media, metadata)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_user_content(
        self,
        text: str,
        media: list[str] | None,
        metadata: dict[str, Any] | None,
    ) -> str | list[dict[str, Any]]:
        """Build user message content with standardized attachment envelope support."""
        text_block = text or ""
        attachments: list[dict[str, str]] = []

        meta_attachments = (metadata or {}).get("attachments")
        if isinstance(meta_attachments, list):
            for item in meta_attachments:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path") or "").strip()
                if not path:
                    continue
                attachments.append({
                    "type": str(item.get("type") or "file"),
                    "path": path,
                    "mime": str(item.get("mime") or ""),
                    "caption": str(item.get("caption") or ""),
                    "sourceChannel": str(item.get("sourceChannel") or ""),
                })

        if not attachments and media:
            for path in media:
                mime, _ = mimetypes.guess_type(path)
                attachment_type = "image" if (mime and mime.startswith("image/")) else "file"
                attachments.append({
                    "type": attachment_type,
                    "path": path,
                    "mime": mime or "",
                    "caption": "",
                    "sourceChannel": "",
                })

        if not attachments:
            return text_block

        multimodal_parts: list[dict[str, Any]] = []
        attachment_notes: list[str] = []

        for item in attachments:
            path = item["path"]
            attachment_type = item.get("type", "file")
            mime = item.get("mime", "")
            caption = item.get("caption", "")
            source = item.get("sourceChannel", "")
            file_path = Path(path)

            is_image = mime.startswith("image/") or attachment_type in {"image", "sticker"}
            if is_image and file_path.is_file():
                try:
                    b64 = base64.b64encode(file_path.read_bytes()).decode()
                    effective_mime = mime or "image/jpeg"
                    multimodal_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{effective_mime};base64,{b64}"},
                    })
                    if attachment_type == "sticker":
                        note = f"sticker from {source or 'channel'} ({file_path.name})"
                        if caption:
                            note += f", caption: {caption}"
                        attachment_notes.append(note)
                    continue
                except Exception:
                    attachment_notes.append(f"type={attachment_type}, path={path}, note=image embed failed")
                    continue

            descriptor = f"type={attachment_type}, path={path}"
            if mime:
                descriptor += f", mime={mime}"
            if caption:
                descriptor += f", caption={caption}"
            if source:
                descriptor += f", source={source}"
            attachment_notes.append(descriptor)

        if attachment_notes:
            notes_text = "\n".join(f"- {note}" for note in attachment_notes)
            text_block = (text_block + "\n\nAttachments:\n" + notes_text).strip()

        if not multimodal_parts:
            return text_block

        final_text = text_block or "See attached image(s)."
        return multimodal_parts + [{"type": "text", "text": final_text}]
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.
        
        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
        
        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.
        
        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
        
        Returns:
            Updated message list.
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        messages.append(msg)
        return messages
