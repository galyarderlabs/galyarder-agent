"""Configuration schema using Pydantic."""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from g_agent.utils.helpers import get_data_path


def _default_workspace() -> str:
    """Default workspace under active data directory."""
    return str(get_data_path() / "workspace")


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""

    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers
    bridge_token: str = ""  # Shared secret for bridge WebSocket auth


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = (
        None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    )


class FeishuConfig(BaseModel):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids


class DiscordConfig(BaseModel):
    """Discord channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT


class EmailConfig(BaseModel):
    """Email channel configuration (IMAP inbound + SMTP outbound)."""

    enabled: bool = False
    consent_granted: bool = False  # Explicit owner permission to access mailbox data

    # IMAP (receive)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    # SMTP (send)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""

    # Behavior
    auto_reply_enabled: bool = (
        True  # If false, inbound email is read but no automatic reply is sent
    )
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)  # Allowed sender email addresses


class SlackDMConfig(BaseModel):
    """Slack DM policy configuration."""

    enabled: bool = True
    policy: str = "open"  # "open" or "allowlist"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs


class SlackChannelConfig(BaseModel):
    """Slack channel configuration (Socket Mode — bidirectional channel, not webhook)."""

    enabled: bool = False
    mode: str = "socket"  # "socket" supported
    webhook_path: str = "/slack/events"
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-...
    user_token_read_only: bool = True
    group_policy: str = "mention"  # "mention", "open", "allowlist"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed channel IDs if allowlist
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""

    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack_channel: SlackChannelConfig = Field(default_factory=SlackChannelConfig)


class RoutingConfig(BaseModel):
    """Model routing policy."""

    mode: str = "auto"  # auto | proxy | direct
    proxy_provider: str = "vllm"  # provider slot used in proxy mode
    fallback_models: list[str] = Field(default_factory=list)


class LLMRoute(BaseModel):
    """Resolved route for model/provider selection."""

    model: str
    mode: str
    provider: str
    api_key: str | None = None
    api_base: str | None = None
    fallback_models: list[str] = Field(default_factory=list)


class AgentDefaults(BaseModel):
    """Default agent configuration."""

    workspace: str = Field(default_factory=_default_workspace)
    model: str = "claude-opus-4-6-thinking"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20
    enable_reflection: bool = True
    summary_interval: int = 6
    routing: "RoutingConfig" = Field(default_factory=RoutingConfig)


class AgentsConfig(BaseModel):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix)


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""

    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(
        default_factory=ProviderConfig
    )  # Alibaba Cloud Tongyi Qianwen
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway
    proxy: ProviderConfig = Field(default_factory=ProviderConfig)


class SlackConfig(BaseModel):
    """Slack integration via Incoming Webhook."""

    webhook_url: str = ""


class SMTPConfig(BaseModel):
    """SMTP integration config for email sending."""

    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    use_tls: bool = True


class GoogleWorkspaceConfig(BaseModel):
    """Google Workspace integration config."""

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    access_token: str = ""
    calendar_id: str = "primary"


class IntegrationsConfig(BaseModel):
    """Optional integrations configuration."""

    slack: SlackConfig = Field(default_factory=SlackConfig)
    smtp: SMTPConfig = Field(default_factory=SMTPConfig)
    google: GoogleWorkspaceConfig = Field(default_factory=GoogleWorkspaceConfig)


class QuietHoursConfig(BaseModel):
    """Quiet hours policy for proactive delivery."""

    enabled: bool = False
    start: str = "22:00"
    end: str = "06:00"
    timezone: str = "local"


class ProactiveConfig(BaseModel):
    """Proactive runtime behavior."""

    quiet_hours: QuietHoursConfig = Field(default_factory=QuietHoursConfig)
    calendar_watch_enabled: bool = True
    calendar_watch_every_minutes: int = 15
    calendar_watch_horizon_minutes: int = 120
    calendar_watch_lead_minutes: list[int] = Field(default_factory=lambda: [30, 10])


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""

    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""

    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class BrowserToolsConfig(BaseModel):
    """Browser tool safety configuration."""

    allow_domains: list[str] = Field(default_factory=list)
    deny_domains: list[str] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "169.254.169.254",
            "metadata.google.internal",
        ]
    )
    timeout_seconds: float = 20.0
    max_html_chars: int = 250000


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""

    timeout: int = 60


class PluginsConfig(BaseModel):
    """Plugin runtime policy."""

    enabled: bool = True
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class ToolsConfig(BaseModel):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    browser: BrowserToolsConfig = Field(default_factory=BrowserToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory
    policy: dict[str, str] = Field(default_factory=dict)  # tool_name -> allow|ask|deny
    risky_tools: list[str] = Field(
        default_factory=lambda: [
            "exec",
            "send_email",
            "gmail_send",
            "slack_webhook_send",
            "message",
        ]
    )
    approval_mode: str = "off"  # off|confirm


class Config(BaseSettings):
    """Root configuration for Galyarder Agent."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    proactive: ProactiveConfig = Field(default_factory=ProactiveConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()

    def _provider_map(self) -> dict[str, ProviderConfig]:
        """Map provider names to config objects."""
        return {
            "openrouter": self.providers.openrouter,
            "deepseek": self.providers.deepseek,
            "anthropic": self.providers.anthropic,
            "openai": self.providers.openai,
            "gemini": self.providers.gemini,
            "zhipu": self.providers.zhipu,
            "groq": self.providers.groq,
            "moonshot": self.providers.moonshot,
            "minimax": self.providers.minimax,
            "dashscope": self.providers.dashscope,
            "aihubmix": self.providers.aihubmix,
            "vllm": self.providers.vllm,
            "proxy": self.providers.proxy,
        }

    def _match_provider(
        self, model: str | None = None
    ) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name using ProviderSpec registry."""
        from g_agent.providers.registry import PROVIDERS

        model_lower = (model or self.agents.defaults.model).lower()

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(kw in model_lower for kw in spec.keywords) and p.api_key:
                return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers)."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider."""
        _, name = self._match_provider(model)
        return name

    def _routing_mode(self) -> str:
        """Normalize routing mode value."""
        mode = (self.agents.defaults.routing.mode or "auto").strip().lower()
        if mode not in {"auto", "proxy", "direct"}:
            return "auto"
        return mode

    def _model_provider_hints(self, model: str) -> tuple[str, ...]:
        """Provider hints extracted from model text."""
        lowered = model.lower()
        hints: list[str] = []
        if lowered.startswith(("openrouter/",)):
            hints.append("openrouter")
        if lowered.startswith(("deepseek/",)):
            hints.append("deepseek")
        if lowered.startswith(("anthropic/", "claude/")):
            hints.append("anthropic")
        if lowered.startswith(("openai/",)):
            hints.append("openai")
        if lowered.startswith(("gemini/",)):
            hints.append("gemini")
        if lowered.startswith(("zhipu/", "zai/")):
            hints.append("zhipu")
        if lowered.startswith(("groq/",)):
            hints.append("groq")
        if lowered.startswith(("moonshot/",)):
            hints.append("moonshot")
        if lowered.startswith(("minimax/",)):
            hints.append("minimax")
        if lowered.startswith(("dashscope/", "qwen/")):
            hints.append("dashscope")
        if lowered.startswith(("aihubmix/",)):
            hints.append("aihubmix")
        if lowered.startswith(("vllm/", "hosted_vllm/")):
            hints.append("vllm")

        keyword_hints = {
            "openrouter": "openrouter",
            "deepseek": "deepseek",
            "anthropic": "anthropic",
            "claude": "anthropic",
            "openai": "openai",
            "gpt": "openai",
            "gemini": "gemini",
            "zhipu": "zhipu",
            "glm": "zhipu",
            "zai": "zhipu",
            "groq": "groq",
            "moonshot": "moonshot",
            "kimi": "moonshot",
            "minimax": "minimax",
            "abab": "minimax",
            "dashscope": "dashscope",
            "qwen": "dashscope",
            "tongyi": "dashscope",
            "aihubmix": "aihubmix",
            "vllm": "vllm",
            "hosted_vllm": "vllm",
            "proxy": "proxy",
        }
        for keyword, provider_name in keyword_hints.items():
            if keyword in lowered and provider_name not in hints:
                hints.append(provider_name)
        return tuple(hints)

    def _explicit_provider_from_model(self, model: str) -> str | None:
        """Resolve provider only from explicit model prefix."""
        lowered = model.lower().strip()
        explicit_prefixes = (
            ("openrouter/", "openrouter"),
            ("deepseek/", "deepseek"),
            ("anthropic/", "anthropic"),
            ("claude/", "anthropic"),
            ("openai/", "openai"),
            ("gemini/", "gemini"),
            ("zhipu/", "zhipu"),
            ("zai/", "zhipu"),
            ("groq/", "groq"),
            ("moonshot/", "moonshot"),
            ("minimax/", "minimax"),
            ("dashscope/", "dashscope"),
            ("qwen/", "dashscope"),
            ("aihubmix/", "aihubmix"),
            ("vllm/", "vllm"),
            ("hosted_vllm/", "vllm"),
            ("proxy/", "proxy"),
        )
        for prefix, provider_name in explicit_prefixes:
            if lowered.startswith(prefix):
                return provider_name
        return None

    def _sanitize_fallback_models(self, primary_model: str) -> list[str]:
        """Return unique, normalized fallback model list."""
        seen: set[str] = {primary_model.strip().lower()}
        cleaned: list[str] = []
        for raw in self.agents.defaults.routing.fallback_models:
            model = (raw or "").strip()
            if not model:
                continue
            key = model.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(model)
        return cleaned

    def _proxy_provider_names(self) -> set[str]:
        """Provider names treated as proxy (not direct)."""
        configured = self.agents.defaults.routing.proxy_provider.strip().lower()
        return {"vllm", "proxy"} | ({configured} if configured else set())

    def _resolve_direct_provider(self, model: str | None = None) -> str | None:
        """Resolve direct provider from explicit hints and configured keys."""
        providers = self._provider_map()
        proxy_names = self._proxy_provider_names()
        direct_order = (
            "openrouter",
            "deepseek",
            "anthropic",
            "openai",
            "gemini",
            "zhipu",
            "moonshot",
            "minimax",
            "dashscope",
            "aihubmix",
            "groq",
        )
        hints = self._model_provider_hints(model) if model else ()
        for provider_name in hints:
            if provider_name in proxy_names:
                continue
            provider_cfg = providers.get(provider_name)
            if provider_cfg and provider_cfg.api_key:
                return provider_name
        for provider_name in direct_order:
            provider_cfg = providers[provider_name]
            if provider_cfg.api_key:
                return provider_name
        return None

    def _provider_base(self, provider_name: str, provider_cfg: ProviderConfig) -> str | None:
        """Resolve API base for provider."""
        if provider_name == "openrouter":
            return provider_cfg.api_base or "https://openrouter.ai/api/v1"
        return provider_cfg.api_base

    def _resolve_proxy_route(
        self,
        selected_model: str,
        fallback_models: list[str],
    ) -> LLMRoute:
        """Build LLMRoute for the configured proxy provider."""
        providers = self._provider_map()
        proxy_name = self.agents.defaults.routing.proxy_provider.strip().lower() or "vllm"
        proxy_cfg = providers.get(proxy_name, ProviderConfig())
        return LLMRoute(
            model=selected_model,
            mode="proxy",
            provider=proxy_name,
            api_key=proxy_cfg.api_key or None,
            api_base=proxy_cfg.api_base,
            fallback_models=fallback_models,
        )

    def resolve_model_route(self, model: str | None = None) -> LLMRoute:
        """Resolve model provider route using routing mode + provider availability."""
        selected_model = (model or self.agents.defaults.model).strip()
        lowered = selected_model.lower()
        mode = self._routing_mode()
        fallback_models = self._sanitize_fallback_models(selected_model)
        proxy_names = self._proxy_provider_names()

        if lowered.startswith("bedrock/"):
            return LLMRoute(
                model=selected_model,
                mode="direct",
                provider="bedrock",
                api_key=None,
                api_base=None,
                fallback_models=fallback_models,
            )

        providers = self._provider_map()

        # ── Explicit proxy mode ─────────────────────────────────────
        if mode == "proxy":
            return self._resolve_proxy_route(selected_model, fallback_models)

        # ── Explicit direct mode ────────────────────────────────────
        if mode == "direct":
            provider_name = self._resolve_direct_provider(selected_model) or "unresolved"
            provider_cfg = providers.get(provider_name, ProviderConfig())
            return LLMRoute(
                model=selected_model,
                mode="direct",
                provider=provider_name,
                api_key=provider_cfg.api_key or None,
                api_base=self._provider_base(provider_name, provider_cfg)
                if provider_name in providers
                else None,
                fallback_models=fallback_models,
            )

        # ── Auto mode ───────────────────────────────────────────────
        # 1. Explicit prefix pointing to a proxy provider?
        explicit_provider = self._explicit_provider_from_model(selected_model)
        if explicit_provider in proxy_names:
            proxy_cfg = providers.get(explicit_provider, ProviderConfig())
            return LLMRoute(
                model=selected_model,
                mode="proxy",
                provider=explicit_provider,
                api_key=proxy_cfg.api_key or None,
                api_base=proxy_cfg.api_base,
                fallback_models=fallback_models,
            )
        # 2. Explicit prefix pointing to a direct provider with key?
        if explicit_provider and providers[explicit_provider].api_key:
            provider_cfg = providers[explicit_provider]
            return LLMRoute(
                model=selected_model,
                mode="direct",
                provider=explicit_provider,
                api_key=provider_cfg.api_key or None,
                api_base=self._provider_base(explicit_provider, provider_cfg),
                fallback_models=fallback_models,
            )

        # 3. Configured proxy provider has api_base? Use it.
        proxy_name = self.agents.defaults.routing.proxy_provider.strip().lower() or "vllm"
        proxy_cfg = providers.get(proxy_name, ProviderConfig())
        if proxy_cfg.api_base:
            return LLMRoute(
                model=selected_model,
                mode="proxy",
                provider=proxy_name,
                api_key=proxy_cfg.api_key or None,
                api_base=proxy_cfg.api_base,
                fallback_models=fallback_models,
            )

        # 4. Fall back to any direct provider with a key.
        provider_name = self._resolve_direct_provider(selected_model) or "unresolved"
        provider_cfg = providers.get(provider_name, ProviderConfig())
        return LLMRoute(
            model=selected_model,
            mode="direct" if provider_name != "unresolved" else "auto",
            provider=provider_name,
            api_key=provider_cfg.api_key or None,
            api_base=self._provider_base(provider_name, provider_cfg)
            if provider_name in providers
            else None,
            fallback_models=fallback_models,
        )

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model (or default model). Falls back to first available key."""
        route = self.resolve_model_route(model)
        if route.api_key:
            return route.api_key
        # Fallback: return first available key
        for provider in [
            self.providers.openrouter,
            self.providers.deepseek,
            self.providers.anthropic,
            self.providers.openai,
            self.providers.gemini,
            self.providers.zhipu,
            self.providers.moonshot,
            self.providers.minimax,
            self.providers.vllm,
            self.providers.groq,
        ]:
            if provider.api_key:
                return provider.api_key
        return None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL based on model name."""
        route = self.resolve_model_route(model)
        return route.api_base

    model_config = SettingsConfigDict(
        env_prefix="G_AGENT_",
        env_nested_delimiter="__",
    )
