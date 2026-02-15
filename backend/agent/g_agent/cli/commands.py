"""CLI commands for g-agent."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import quote

import typer
from rich.console import Console
from rich.table import Table

from g_agent import __brand__, __logo__, __version__

app = typer.Typer(
    name="g-agent",
    help=f"{__logo__} {__brand__} - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()


def _cli_fail(cause: str, fix: str | None = None, *, exit_code: int = 1) -> None:
    """Print a consistent CLI error block and exit."""
    console.print(f"[red]{cause}[/red]")
    if fix:
        console.print(f"[dim]Fix: {fix}[/dim]")
    raise typer.Exit(exit_code)


def _missing_api_key_fix(provider: str, config_path: Path) -> str:
    """Build actionable API-key guidance for the resolved route provider."""
    if provider in {"vllm", "proxy"}:
        return (
            f"Set providers.{provider}.apiKey in {config_path} and ensure "
            f"providers.{provider}.apiBase is set."
        )
    if provider == "unresolved":
        return (
            f"Set providers.<name>.apiKey in {config_path}. If you use a local proxy key "
            "(`sk-local-*`), set agents.defaults.routing.mode=\"proxy\" and "
            "agents.defaults.routing.proxyProvider to that provider (usually `proxy` or `vllm`)."
        )
    return f"Set providers.{provider}.apiKey in {config_path}"


def _normalize_name_set(values: list[str]) -> set[str]:
    """Normalize plugin names from policy lists."""
    return {value.strip().lower() for value in values if value and value.strip()}


def _plugin_policy_state(config: Any) -> tuple[bool, set[str], set[str]]:
    """Return enabled flag and normalized allow/deny sets."""
    plugin_cfg = config.tools.plugins
    return (
        bool(plugin_cfg.enabled),
        _normalize_name_set(plugin_cfg.allow),
        _normalize_name_set(plugin_cfg.deny),
    )


def _plugin_status(
    name: str,
    *,
    enabled: bool,
    allow_set: set[str],
    deny_set: set[str],
    active_set: set[str],
) -> tuple[str, str]:
    """Resolve plugin status label and reason."""
    key = name.strip().lower()
    if not enabled:
        return "[yellow]disabled[/yellow]", "plugins disabled globally"
    if key in deny_set:
        return "[red]blocked[/red]", "matched deny list"
    if allow_set and key not in allow_set:
        return "[yellow]blocked[/yellow]", "not in allow list"
    if key in active_set:
        return "[green]active[/green]", "loaded"
    return "[yellow]inactive[/yellow]", "not selected by policy"


def _plugin_hooks(plugin: Any) -> str:
    """Human-readable hook summary for plugin list."""
    from g_agent.plugins.base import PluginBase

    hooks: list[str] = []
    register_tools = getattr(type(plugin), "register_tools", None)
    register_channels = getattr(type(plugin), "register_channels", None)
    register_providers = getattr(type(plugin), "register_providers", None)
    if register_tools is not PluginBase.register_tools:
        hooks.append("tools")
    if register_channels is not PluginBase.register_channels:
        hooks.append("channels")
    if register_providers is not PluginBase.register_providers:
        hooks.append("providers")
    return ", ".join(hooks) if hooks else "-"


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} {__brand__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True),
):
    """g-agent - Personal AI Assistant."""
    pass


@app.command(
    "help",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def help_command(ctx: typer.Context):
    """Show help for g-agent commands (alias for --help)."""
    import subprocess
    import sys

    target = list(ctx.args)
    cmd = [sys.argv[0], *target, "--help"]
    result = subprocess.run(cmd, check=False)
    raise typer.Exit(result.returncode)


@app.command("version")
def version_command():
    """Show g-agent version."""
    console.print(f"{__logo__} {__brand__} v{__version__}")


@app.command("login")
def login_command():
    """Link device via QR code (alias for `channels login`)."""
    import subprocess
    import sys

    result = subprocess.run([sys.argv[0], "channels", "login"], check=False)
    raise typer.Exit(result.returncode)


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard(
    no_interactive: bool = typer.Option(False, "--no-interactive", help="Skip interactive setup"),
):
    """Initialize g-agent configuration and workspace."""
    from g_agent.config.loader import (
        convert_keys,
        convert_to_camel,
        deep_merge_config,
        get_config_path,
        load_config,
        save_config,
    )
    from g_agent.config.schema import Config
    from g_agent.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        existing_config = load_config()
        default_config = Config()
        existing_data = convert_to_camel(existing_config.model_dump())
        default_data = convert_to_camel(default_config.model_dump())
        merged_data = deep_merge_config(existing_data, default_data)
        merged_config = Config.model_validate(convert_keys(merged_data))
        save_config(merged_config)
        console.print(f"[green]✓[/green] Merged config at {config_path} (existing values preserved)")
    else:
        config = Config()
        save_config(config)
        console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")

    # Create default bootstrap files
    _create_workspace_templates(workspace)

    # Interactive setup wizard
    if not no_interactive:
        config = load_config()
        config = _interactive_setup(config)
        save_config(config)

    console.print(f"\n{__logo__} {__brand__} is ready!")
    console.print("\n  Chat: [cyan]g-agent agent -m \"Hello!\"[/cyan]")


_PROVIDER_CHOICES = [
    ("OpenRouter", "openrouter", "direct", "https://openrouter.ai/keys"),
    ("Anthropic (Claude)", "anthropic", "direct", "https://console.anthropic.com/settings/keys"),
    ("OpenAI (GPT)", "openai", "direct", "https://platform.openai.com/api-keys"),
    ("Gemini (Google)", "gemini", "direct", "https://aistudio.google.com/apikey"),
    ("DeepSeek", "deepseek", "direct", "https://platform.deepseek.com/api_keys"),
    ("Groq", "groq", "direct", "https://console.groq.com/keys"),
    ("Local Proxy (vLLM, Ollama, LiteLLM, etc.)", "proxy", "proxy", None),
]

_SELFIE_PROVIDER_CHOICES = [
    ("HuggingFace (free)", "huggingface"),
    ("Cloudflare Workers AI (free, ~2000/day)", "cloudflare"),
    ("Nebius", "nebius"),
    ("OpenAI-compatible (local)", "openai-compatible"),
]


def _prompt_choice(label: str, choices: list[str], current: str | None = None) -> int | None:
    """Show numbered menu, return 0-based index or None if skipped."""
    for i, choice in enumerate(choices, 1):
        marker = " [cyan]<current>[/cyan]" if current and current.lower() in choice.lower() else ""
        console.print(f"  {i}. {choice}{marker}")
    console.print("  0. Skip")
    while True:
        raw = typer.prompt("  Choose", default="0")
        try:
            n = int(raw)
            if 0 <= n <= len(choices):
                return None if n == 0 else n - 1
        except ValueError:
            pass
        console.print(f"  [dim]Enter 0-{len(choices)}[/dim]")


def _prompt_secret(label: str, current: str = "") -> str:
    """Prompt for a secret value, showing masked current value."""
    if current:
        masked = current[:4] + "..." + current[-4:] if len(current) > 8 else "***"
        hint = f" [dim](current: {masked}, Enter to keep)[/dim]"
        console.print(f"  {label}{hint}")
        value = typer.prompt("  ", default="", show_default=False)
        return value if value else current
    return typer.prompt(f"  {label}", default="")


def _interactive_setup(config: Any) -> Any:
    """Run interactive setup wizard, returning modified config."""
    console.print(f"\n{'─' * 50}")
    console.print("[bold]Interactive Setup[/bold]")
    console.print(f"{'─' * 50}")
    console.print("[dim]Each step is optional. Press 0 or Enter to skip.[/dim]\n")

    # ── Step 1: LLM Provider ──────────────────────────────────────
    console.print("[bold]Step 1/5: LLM Provider[/bold]")
    current_provider = config.agents.defaults.routing.proxy_provider
    if config.agents.defaults.routing.mode == "direct":
        current_provider = config.get_provider_name() or ""
    choice = _prompt_choice(
        "provider",
        [c[0] for c in _PROVIDER_CHOICES],
        current=current_provider,
    )
    if choice is not None:
        _, provider_name, routing_mode, key_url = _PROVIDER_CHOICES[choice]
        if key_url:
            console.print(f"  [dim]Get key at: {key_url}[/dim]")

        provider_cfg = getattr(config.providers, provider_name)
        api_key = _prompt_secret("API Key", provider_cfg.api_key)
        if api_key:
            provider_cfg.api_key = api_key

        if routing_mode == "proxy":
            api_base = typer.prompt(
                "  API Base URL",
                default=provider_cfg.api_base or "http://127.0.0.1:8000/v1",
            )
            provider_cfg.api_base = api_base

        config.agents.defaults.routing.mode = routing_mode
        if routing_mode == "proxy":
            config.agents.defaults.routing.proxy_provider = provider_name

        if api_key:
            console.print(f"  [green]✓[/green] {_PROVIDER_CHOICES[choice][0]} configured\n")
        else:
            console.print("  [yellow]⚠[/yellow] No API key set — add it later in config.json\n")
    else:
        console.print()

    # ── Step 2: Model Selection ───────────────────────────────────
    console.print("[bold]Step 2/5: Default Model[/bold]")
    current_model = config.agents.defaults.model
    console.print(f"  [dim]Current: {current_model}[/dim]")
    model = typer.prompt("  Model name (Enter to keep)", default="")
    if model:
        config.agents.defaults.model = model
        console.print(f"  [green]✓[/green] Model set to {model}\n")
    else:
        console.print()

    # ── Step 3: Web Search ────────────────────────────────────────
    console.print("[bold]Step 3/5: Web Search (Brave)[/bold]")
    if typer.confirm("  Enable web search?", default=bool(config.tools.web.search.api_key)):
        console.print("  [dim]Get key at: https://brave.com/search/api/[/dim]")
        api_key = _prompt_secret("Brave Search API Key", config.tools.web.search.api_key)
        if api_key:
            config.tools.web.search.api_key = api_key
            console.print("  [green]✓[/green] Web search configured\n")
        else:
            console.print("  [yellow]⚠[/yellow] No key set\n")
    else:
        console.print()

    # ── Step 4: Channels ──────────────────────────────────────────
    console.print("[bold]Step 4/5: Chat Channels[/bold]")

    # Telegram
    if typer.confirm("  Enable Telegram?", default=config.channels.telegram.enabled):
        config.channels.telegram.enabled = True
        console.print("  [dim]Get token from @BotFather on Telegram[/dim]")
        token = _prompt_secret("Bot token", config.channels.telegram.token)
        if token:
            config.channels.telegram.token = token
        user_id = typer.prompt(
            "  Your Telegram user ID",
            default=config.channels.telegram.allow_from[0]
            if config.channels.telegram.allow_from
            else "",
        )
        if user_id and user_id not in config.channels.telegram.allow_from:
            config.channels.telegram.allow_from.append(user_id)
        console.print("  [green]✓[/green] Telegram configured")
    else:
        config.channels.telegram.enabled = False

    # WhatsApp
    if typer.confirm("  Enable WhatsApp?", default=config.channels.whatsapp.enabled):
        config.channels.whatsapp.enabled = True
        bridge_token = _prompt_secret(
            "Bridge token (optional shared secret)", config.channels.whatsapp.bridge_token
        )
        if bridge_token:
            config.channels.whatsapp.bridge_token = bridge_token
        phone = typer.prompt(
            "  Your phone number (with country code, e.g. 6281234567890)",
            default=config.channels.whatsapp.allow_from[0]
            if config.channels.whatsapp.allow_from
            else "",
        )
        if phone and phone not in config.channels.whatsapp.allow_from:
            config.channels.whatsapp.allow_from.append(phone)
        console.print("  [green]✓[/green] WhatsApp configured")
    else:
        config.channels.whatsapp.enabled = False

    console.print()

    # ── Step 5: Visual Identity ───────────────────────────────────
    console.print("[bold]Step 5/5: Visual Identity (Selfie)[/bold]")
    if typer.confirm("  Enable AI selfie generation?", default=config.visual.enabled):
        config.visual.enabled = True
        choice = _prompt_choice(
            "selfie provider",
            [c[0] for c in _SELFIE_PROVIDER_CHOICES],
            current=config.visual.image_gen.provider,
        )
        if choice is not None:
            _, provider = _SELFIE_PROVIDER_CHOICES[choice]
            config.visual.image_gen.provider = provider
            api_key = _prompt_secret("Provider API Key", config.visual.image_gen.api_key)
            if api_key:
                config.visual.image_gen.api_key = api_key
            if provider == "cloudflare":
                account_id = typer.prompt(
                    "  Cloudflare Account ID",
                    default=config.visual.image_gen.account_id or "",
                )
                if account_id:
                    config.visual.image_gen.account_id = account_id
            elif provider == "openai-compatible":
                api_base = typer.prompt(
                    "  API Base URL",
                    default=config.visual.image_gen.api_base or "http://127.0.0.1:8188/v1",
                )
                if api_base:
                    config.visual.image_gen.api_base = api_base

        desc = typer.prompt(
            "  Physical description (or Enter to skip, will auto-extract from photo later)",
            default=config.visual.physical_description or "",
        )
        if desc:
            config.visual.physical_description = desc

        console.print("  [green]✓[/green] Visual identity configured\n")
    else:
        config.visual.enabled = False
        console.print()

    return config


def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are g-agent. Be concise, accurate, and practical.

## Guidelines

- Prefer minimal, root-cause fixes over broad changes
- Explain key actions before you execute them
- Ask for clarification when the request is ambiguous
- Use tools only when they add clear value
- Remember important information in your memory files
""",
        "SOUL.md": """# Soul

I am g-agent, a focused execution assistant.

## Personality

- Direct and helpful
- Calm under pressure
- Execution-focused

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions

## Visual Identity

- I have a consistent physical appearance. I can appear in different outfits,
  locations, and scenarios, but my face remains the same.
- When users ask for a photo, selfie, or picture of me, I use the `selfie` tool.
- I respond to appearance compliments naturally and engage creatively with
  outfit/location requests.

### When to Send a Selfie

- User explicitly asks for a photo/selfie/picture
- User asks "what are you doing?" or "where are you?" (contextual selfie)
- User requests to see me in specific outfit or location
- User says "kirim foto", "foto dong", "selfie dong", or similar
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }

    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")

    # Ensure existing SOUL.md has Visual Identity section
    soul_path = workspace / "SOUL.md"
    if soul_path.exists():
        soul_content = soul_path.read_text()
        if "## Visual Identity" not in soul_content:
            visual_section = """
## Visual Identity

- I have a consistent physical appearance. I can appear in different outfits,
  locations, and scenarios, but my face remains the same.
- When users ask for a photo, selfie, or picture of me, I use the `selfie` tool.
- I respond to appearance compliments naturally and engage creatively with
  outfit/location requests.

### When to Send a Selfie

- User explicitly asks for a photo/selfie/picture
- User asks "what are you doing?" or "where are you?" (contextual selfie)
- User requests to see me in specific outfit or location
- User says "kirim foto", "foto dong", "selfie dong", or similar
"""
            soul_path.write_text(soul_content.rstrip() + "\n" + visual_section)
            console.print("  [dim]Added Visual Identity section to SOUL.md[/dim]")

    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)

    # Create skills directory for custom user skills
    skills_dir = workspace / "skills"
    skills_dir.mkdir(exist_ok=True)

    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")

    facts_file = memory_dir / "FACTS.md"
    if not facts_file.exists():
        facts_file.write_text("""# Fact Index (Machine-readable)

JSON lines with fields: id, type, confidence, source, last_seen, supersedes.
""")
        console.print("  [dim]Created memory/FACTS.md[/dim]")

    lessons_file = memory_dir / "LESSONS.md"
    if not lessons_file.exists():
        lessons_file.write_text("""# Lessons Learned

Actionable feedback and mistakes to avoid repeating.
""")
        console.print("  [dim]Created memory/LESSONS.md[/dim]")

    profile_file = memory_dir / "PROFILE.md"
    if not profile_file.exists():
        profile_file.write_text("""# Profile

## Identity
- name:
- timezone:
- language:

## Preferences
- communication_style:
- notification_style:
""")
        console.print("  [dim]Created memory/PROFILE.md[/dim]")

    relationships_file = memory_dir / "RELATIONSHIPS.md"
    if not relationships_file.exists():
        relationships_file.write_text("""# Relationships

- [name] role, context, preference
""")
        console.print("  [dim]Created memory/RELATIONSHIPS.md[/dim]")

    projects_file = memory_dir / "PROJECTS.md"
    if not projects_file.exists():
        projects_file.write_text("""# Projects

## Active
- [project] status: ; next:

## Backlog
""")
        console.print("  [dim]Created memory/PROJECTS.md[/dim]")


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    metrics_endpoint: bool = typer.Option(
        False,
        "--metrics-endpoint",
        help="Enable optional lightweight HTTP metrics endpoint (default: off)",
    ),
    metrics_host: str = typer.Option(
        "127.0.0.1", "--metrics-host", help="Metrics endpoint bind host"
    ),
    metrics_port: int = typer.Option(18791, "--metrics-port", help="Metrics endpoint bind port"),
    metrics_path: str = typer.Option("/metrics", "--metrics-path", help="Metrics endpoint path"),
    metrics_format: str = typer.Option(
        "prometheus",
        "--metrics-format",
        help="prometheus|json|dashboard_json",
    ),
    metrics_hours: int = typer.Option(
        24, "--metrics-hours", help="Metrics endpoint snapshot window"
    ),
):
    """Start the g-agent gateway."""
    from g_agent.agent.loop import AgentLoop
    from g_agent.agent.tools.google_workspace import GoogleWorkspaceClient
    from g_agent.bus.events import OutboundMessage
    from g_agent.bus.queue import MessageBus
    from g_agent.channels.manager import ChannelManager
    from g_agent.config.loader import get_config_path, get_data_dir, load_config
    from g_agent.cron.service import CronService
    from g_agent.cron.types import CronJob
    from g_agent.heartbeat.service import HeartbeatService
    from g_agent.observability.http_server import MetricsHttpServer
    from g_agent.observability.metrics import MetricsStore
    from g_agent.plugins.loader import filter_plugins, load_installed_plugins, plugin_label
    from g_agent.proactive.engine import (
        ProactiveStateStore,
        compute_due_calendar_reminders,
        is_quiet_hours_now,
        resolve_timezone,
    )
    from g_agent.providers.factory import build_provider, collect_provider_factories, has_provider_factory

    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    console.print(f"{__logo__} Starting {__brand__} gateway on port {port}...")

    config = load_config()
    plugins = filter_plugins(
        load_installed_plugins(),
        enabled=config.tools.plugins.enabled,
        allow=config.tools.plugins.allow,
        deny=config.tools.plugins.deny,
    )
    provider_factories = collect_provider_factories(config, plugins)
    if plugins:
        console.print(f"[green]✓[/green] Plugins loaded: {', '.join(plugin_label(p) for p in plugins)}")

    # Create components
    bus = MessageBus()

    # Create provider (supports OpenRouter, Anthropic, OpenAI, Bedrock)
    route = config.resolve_model_route()
    api_key = route.api_key
    if not api_key and route.provider not in {"vllm", "bedrock"}:
        api_key = config.get_api_key()
    model = config.agents.defaults.model
    is_bedrock = route.provider == "bedrock" or model.startswith("bedrock/")

    if (
        not api_key
        and not is_bedrock
        and not has_provider_factory(route.provider, provider_factories=provider_factories)
    ):
        config_path = get_config_path()
        _cli_fail(
            f"No API key configured for provider '{route.provider}'.",
            _missing_api_key_fix(route.provider, config_path),
        )

    provider = build_provider(
        route.model_copy(update={"api_key": api_key}),
        config,
        provider_factories=provider_factories,
    )

    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=route.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        slack_webhook_url=config.integrations.slack.webhook_url or None,
        smtp_config=config.integrations.smtp,
        google_config=config.integrations.google,
        browser_config=config.tools.browser,
        tool_policy=config.tools.policy,
        risky_tools=config.tools.risky_tools,
        approval_mode=config.tools.approval_mode,
        enable_reflection=config.agents.defaults.enable_reflection,
        summary_interval=config.agents.defaults.summary_interval,
        fallback_models=route.fallback_models,
        plugins=plugins,
        visual_config=config.visual,
    )

    data_dir = get_data_dir()
    proactive_state = ProactiveStateStore(data_dir / "proactive" / "state.json")
    metrics = MetricsStore(config.workspace_path / "state" / "metrics" / "events.jsonl")
    proactive_job_names = {"daily-digest", "weekly-lessons-distill", "calendar-watch"}

    def _is_proactive_job(job: CronJob) -> bool:
        return job.name in proactive_job_names or job.name.startswith("pd-")

    def _is_quiet_hours_blocked(job: CronJob) -> bool:
        quiet = config.proactive.quiet_hours
        if not quiet.enabled:
            return False
        if not job.payload.deliver:
            return False
        if not _is_proactive_job(job):
            return False
        tzinfo = resolve_timezone(quiet.timezone)
        now_local = datetime.now(timezone.utc).astimezone(tzinfo)
        return is_quiet_hours_now(
            now_local=now_local,
            start_hhmm=quiet.start,
            end_hhmm=quiet.end,
            enabled=quiet.enabled,
        )

    async def _run_calendar_watch(job: CronJob) -> str:
        if not (job.payload.deliver and job.payload.channel and job.payload.to):
            return "calendar_watch skipped: missing delivery target."

        google_cfg = config.integrations.google
        google = GoogleWorkspaceClient(
            client_id=google_cfg.client_id,
            client_secret=google_cfg.client_secret,
            refresh_token=google_cfg.refresh_token,
            access_token=google_cfg.access_token,
            calendar_id=google_cfg.calendar_id,
        )
        if not google.is_configured():
            return "calendar_watch skipped: Google Workspace not configured."

        now_utc = datetime.now(timezone.utc)
        horizon = max(10, int(config.proactive.calendar_watch_horizon_minutes))
        ok, data = await google.request(
            "GET",
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(google.calendar_id or 'primary', safe='')}/events",
            params={
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMin": now_utc.isoformat(),
                "timeMax": (now_utc + timedelta(minutes=horizon)).isoformat(),
                "maxResults": 25,
            },
        )
        if not ok:
            return f"calendar_watch error: {data.get('error', data)}"

        due = compute_due_calendar_reminders(
            data.get("items", []) or [],
            now_utc=now_utc,
            lead_minutes=config.proactive.calendar_watch_lead_minutes,
            scan_minutes=max(1, int(config.proactive.calendar_watch_every_minutes)),
            horizon_minutes=horizon,
            state_store=proactive_state,
        )
        if not due:
            return "calendar_watch: no due reminders."

        local_tz = resolve_timezone(config.proactive.quiet_hours.timezone)
        lines = ["⏰ Upcoming meetings:"]
        for item in due[:5]:
            start_local = item["start_utc"].astimezone(local_tz)
            lines.append(
                f"- {item['summary']} in {item['minutes_to_start']}m "
                f"({start_local.strftime('%H:%M')})"
            )

        await bus.publish_outbound(
            OutboundMessage(
                channel=job.payload.channel,
                chat_id=job.payload.to,
                content="\n".join(lines),
                metadata={
                    "idempotency_key": (
                        f"cron:{job.id}:{now_utc.strftime('%Y%m%d%H%M')}:{len(due)}"
                    )
                },
            )
        )
        return f"calendar_watch: sent {len(due)} reminder(s)."

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        started = perf_counter()
        error_message = ""
        success = True
        try:
            if _is_quiet_hours_blocked(job):
                return f"Skipped '{job.name}' due quiet hours."

            if job.payload.kind == "system_event":
                if (job.payload.message or "").strip().lower() == "calendar_watch":
                    return await _run_calendar_watch(job)
                return f"Skipped unknown system_event payload: {job.payload.message}"

            response = await agent.process_direct(
                job.payload.message,
                session_key=f"cron:{job.id}",
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
            )
            if job.payload.deliver and job.payload.to:
                await bus.publish_outbound(
                    OutboundMessage(
                        channel=job.payload.channel or "cli",
                        chat_id=job.payload.to,
                        content=response or "",
                        metadata={
                            "idempotency_key": (
                                f"cron:{job.id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
                            )
                        },
                    )
                )
            return response
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            metrics.record_cron_run(
                name=job.name,
                payload_kind=job.payload.kind,
                success=success,
                latency_ms=(perf_counter() - started) * 1000.0,
                delivered=bool(job.payload.deliver and job.payload.to),
                proactive=_is_proactive_job(job),
                error=error_message,
            )

    cron.on_job = on_cron_job

    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat")

    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True,
    )

    # Create channel manager
    channels = ChannelManager(config, bus, plugins=plugins)

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")

    console.print("[green]✓[/green] Heartbeat: every 30m")

    async def run():
        metrics_server: MetricsHttpServer | None = None
        start_error: str = ""
        try:
            if metrics_endpoint:
                metrics_server = MetricsHttpServer(
                    store=metrics,
                    host=metrics_host,
                    port=metrics_port,
                    path=metrics_path,
                    default_hours=metrics_hours,
                    default_format=metrics_format,
                )
                await metrics_server.start()
                console.print(
                    f"[green]✓[/green] Metrics endpoint: "
                    f"http://{metrics_host}:{metrics_server.bound_port}{metrics_server.path} "
                    f"({metrics_server.default_format})"
                )
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except OSError as e:
            start_error = str(e)
        except KeyboardInterrupt:
            console.print("\nShutting down...")
        finally:
            heartbeat.stop()
            cron.stop()
            await agent.shutdown()
            await channels.stop_all()
            if metrics_server:
                await metrics_server.stop()
            if start_error:
                console.print(f"[red]Gateway startup failed:[/red] {start_error}")
                raise typer.Exit(1)

    asyncio.run(run())


# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Interact with the agent directly."""
    from g_agent.agent.loop import AgentLoop
    from g_agent.bus.queue import MessageBus
    from g_agent.config.loader import get_config_path, load_config
    from g_agent.plugins.loader import filter_plugins, load_installed_plugins
    from g_agent.providers.factory import build_provider, collect_provider_factories, has_provider_factory

    config = load_config()

    route = config.resolve_model_route()
    api_key = route.api_key
    if not api_key and route.provider not in {"vllm", "bedrock"}:
        api_key = config.get_api_key()
    model = config.agents.defaults.model
    is_bedrock = route.provider == "bedrock" or model.startswith("bedrock/")

    bus = MessageBus()
    plugins = filter_plugins(
        load_installed_plugins(),
        enabled=config.tools.plugins.enabled,
        allow=config.tools.plugins.allow,
        deny=config.tools.plugins.deny,
    )
    provider_factories = collect_provider_factories(config, plugins)

    if (
        not api_key
        and not is_bedrock
        and not has_provider_factory(route.provider, provider_factories=provider_factories)
    ):
        config_path = get_config_path()
        _cli_fail(
            f"No API key configured for provider '{route.provider}'.",
            _missing_api_key_fix(route.provider, config_path),
        )

    provider = build_provider(
        route.model_copy(update={"api_key": api_key}),
        config,
        provider_factories=provider_factories,
    )

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=route.model,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        slack_webhook_url=config.integrations.slack.webhook_url or None,
        smtp_config=config.integrations.smtp,
        google_config=config.integrations.google,
        browser_config=config.tools.browser,
        tool_policy=config.tools.policy,
        risky_tools=config.tools.risky_tools,
        approval_mode=config.tools.approval_mode,
        enable_reflection=config.agents.defaults.enable_reflection,
        summary_interval=config.agents.defaults.summary_interval,
        fallback_models=route.fallback_models,
        plugins=plugins,
        visual_config=config.visual,
    )

    if message:
        # Single message mode
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            console.print(f"\n{__logo__} {response}")

        asyncio.run(run_once())
    else:
        # Interactive mode
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.styles import Style

        history_dir = config.workspace_path / "state"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "cli_history"

        session = PromptSession(history=FileHistory(str(history_file)))
        style = Style.from_dict({"prompt": "bold blue"})

        console.print(f"{__logo__} Interactive mode (Ctrl+C to exit)\n")

        async def run_interactive():
            while True:
                try:
                    user_input = await session.prompt_async("You: ", style=style)
                    if not user_input.strip():
                        continue

                    response = await agent_loop.process_direct(user_input, session_id)
                    console.print(f"\n{__logo__} {response}\n")
                except (KeyboardInterrupt, EOFError):
                    console.print("\nGoodbye!")
                    break

        asyncio.run(run_interactive())


# ============================================================================
# Session Commands
# ============================================================================


@app.command("new")
def new_session(
    channel: str = typer.Option(None, "--channel", "-c", help="Target specific channel"),
    all_sessions: bool = typer.Option(False, "--all", "-a", help="Clear all sessions"),
    archive: bool = typer.Option(True, "--archive/--no-archive", help="Archive before clearing"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Start fresh by clearing/archiving conversation history."""
    from g_agent.config.loader import load_config
    from g_agent.session.manager import SessionManager

    config = load_config()
    sm = SessionManager(config.workspace_path)
    sessions = sm.list_sessions()

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        raise typer.Exit(0)

    # Determine which sessions to clear
    if all_sessions:
        targets = sessions
    elif channel:
        prefix = f"{channel}:"
        targets = [s for s in sessions if s.get("key", "").startswith(prefix)]
        if not targets:
            console.print(f"[dim]No sessions found for channel '{channel}'.[/dim]")
            raise typer.Exit(0)
    else:
        targets = [s for s in sessions if s.get("key") == "cli:default"]
        if not targets:
            console.print("[dim]No cli:default session found.[/dim]")
            raise typer.Exit(0)

    # Confirm
    if not yes:
        label = f"{len(targets)} session(s)"
        if not typer.confirm(f"Clear {label}?"):
            raise typer.Exit(0)

    count = 0
    for info in targets:
        key = info.get("key", "")
        if archive:
            if sm.archive(key):
                count += 1
        else:
            if sm.delete(key):
                count += 1

    verb = "Archived" if archive else "Cleared"
    console.print(f"[green]✓[/green] {verb} {count} session(s)")


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.callback(invoke_without_command=True)
def channels_main(ctx: typer.Context):
    """Manage channels."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from g_agent.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row("WhatsApp", "✓" if wa.enabled else "✗", wa.bridge_url)

    dc = config.channels.discord
    table.add_row("Discord", "✓" if dc.enabled else "✗", dc.gateway_url)

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row("Telegram", "✓" if tg.enabled else "✗", tg_config)

    console.print(table)


def _bridge_source_signature(source: Path) -> str:
    """Compute deterministic content signature for bridge source files."""
    import hashlib

    digest = hashlib.sha256()
    candidates = ["package.json", "package-lock.json", "tsconfig.json"]
    for path in sorted((source / "src").rglob("*.ts")):
        candidates.append(str(path.relative_to(source)))

    for rel_path in candidates:
        file_path = source / rel_path
        if not file_path.exists() or not file_path.is_file():
            continue
        digest.update(rel_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")

    return digest.hexdigest()


def _bridge_build_id_path(bridge_dir: Path) -> Path:
    """Marker file storing bridge source signature used for local build."""
    return bridge_dir / ".g_agent_bridge_build_id"


def _bridge_needs_rebuild(bridge_dir: Path, *, expected_build_id: str, force_rebuild: bool) -> bool:
    """Return True when local bridge should be rebuilt."""
    if force_rebuild:
        return True
    if not (bridge_dir / "dist" / "index.js").exists():
        return True
    marker = _bridge_build_id_path(bridge_dir)
    try:
        current_build_id = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return True
    return current_build_id != expected_build_id


def _get_bridge_dir(force_rebuild: bool = False) -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess

    from g_agent.config.loader import get_data_dir

    # User's bridge location
    user_bridge = get_data_dir() / "bridge"

    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)

    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # g-agent/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)

    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge

    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall galyarder-agent")
        raise typer.Exit(1)

    expected_build_id = _bridge_source_signature(source)
    if not _bridge_needs_rebuild(
        user_bridge,
        expected_build_id=expected_build_id,
        force_rebuild=force_rebuild,
    ):
        return user_bridge

    marker_path = _bridge_build_id_path(user_bridge)
    if marker_path.exists() and not force_rebuild:
        console.print("[yellow]Bridge source changed; rebuilding local bridge...[/yellow]")

    console.print(f"{__logo__} Setting up bridge...")

    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))

    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)

        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)

        _bridge_build_id_path(user_bridge).write_text(expected_build_id, encoding="utf-8")
        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)

    return user_bridge


def _is_bridge_port_in_use(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True when TCP bridge port is already accepting connections."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _bridge_port_pids(port: int) -> list[str]:
    """Best-effort list of process IDs currently listening on a TCP port."""
    import shutil
    import subprocess

    if not shutil.which("lsof"):
        return []

    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        return []

    pids = [line.strip() for line in result.stdout.splitlines() if line.strip().isdigit()]
    return sorted(set(pids))


def _stop_bridge_processes(port: int, pids: list[str], *, timeout_seconds: float = 3.0) -> list[str]:
    """Send SIGTERM to listed PIDs and return still-listening bridge PIDs."""
    import os
    import signal
    import time

    normalized = sorted({pid.strip() for pid in pids if pid and pid.strip().isdigit()})
    for pid in normalized:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            continue
        except OSError:
            continue

    if not normalized:
        return _bridge_port_pids(port)

    deadline = time.monotonic() + max(0.1, float(timeout_seconds))
    while time.monotonic() < deadline:
        active = set(_bridge_port_pids(port))
        survivors = sorted(active.intersection(normalized))
        if not survivors:
            return []
        time.sleep(0.1)

    active = set(_bridge_port_pids(port))
    return sorted(active.intersection(normalized))


def _force_kill_bridge_processes(
    port: int,
    pids: list[str],
    *,
    timeout_seconds: float = 1.5,
) -> list[str]:
    """Send SIGKILL to listed PIDs and return still-listening bridge PIDs."""
    import os
    import signal
    import time

    normalized = sorted({pid.strip() for pid in pids if pid and pid.strip().isdigit()})
    for pid in normalized:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except ProcessLookupError:
            continue
        except OSError:
            continue

    if not normalized:
        return _bridge_port_pids(port)

    deadline = time.monotonic() + max(0.1, float(timeout_seconds))
    while time.monotonic() < deadline:
        active = set(_bridge_port_pids(port))
        survivors = sorted(active.intersection(normalized))
        if not survivors:
            return []
        time.sleep(0.1)

    active = set(_bridge_port_pids(port))
    return sorted(active.intersection(normalized))


def _bridge_bind_error(host: str, port: int) -> OSError | None:
    """Return bind error for host:port, or None when bind is allowed."""
    import socket

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return exc

    seen: set[tuple[int, str, int]] = set()
    for family, socktype, proto, _canonname, sockaddr in infos:
        bind_host = str(sockaddr[0]) if isinstance(sockaddr, tuple) and sockaddr else host
        bind_port = int(sockaddr[1]) if isinstance(sockaddr, tuple) and len(sockaddr) > 1 else port
        key = (family, bind_host, bind_port)
        if key in seen:
            continue
        seen.add(key)

        try:
            sock = socket.socket(family, socktype, proto)
        except OSError as exc:
            return exc

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(sockaddr)
        except OSError as exc:
            return exc
        finally:
            sock.close()

    return None


@channels_app.command("login")
def channels_login(
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Force rebuild local WhatsApp bridge before login",
    ),
    restart_existing: bool = typer.Option(
        False,
        "--restart-existing",
        help="Stop process already listening on bridge port before login",
    ),
    force_kill: bool = typer.Option(
        False,
        "--force-kill",
        help="With --restart-existing, escalate to SIGKILL when SIGTERM cannot free bridge port",
    ),
):
    """Link device via QR code."""
    import errno
    import os
    import subprocess
    from urllib.parse import urlparse

    from g_agent.config.loader import get_data_dir, load_config

    config = load_config()
    bridge_url = config.channels.whatsapp.bridge_url
    if force_kill and not restart_existing:
        _cli_fail(
            "--force-kill requires --restart-existing.",
            "Run: g-agent channels login --restart-existing --force-kill",
        )

    parsed = urlparse(bridge_url)
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
        _cli_fail(
            f"Invalid channels.whatsapp.bridgeUrl: {bridge_url}",
            "Use ws://host:port or wss://host:port in config "
            f"({Path.home() / '.g-agent' / 'config.json'}).",
        )
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)

    pids = _bridge_port_pids(port)
    if pids and restart_existing:
        console.print(
            f"[yellow]Stopping existing bridge process on port {port}: "
            f"{', '.join(pids)}[/yellow]"
        )
        survivors = _stop_bridge_processes(port, pids)
        if survivors and force_kill:
            console.print(
                f"[yellow]SIGTERM did not clear port {port}; forcing stop with SIGKILL: "
                f"{', '.join(survivors)}[/yellow]"
            )
            survivors = _force_kill_bridge_processes(port, survivors)
        if survivors:
            fix_cmd = f"kill {' '.join(survivors)}"
            if not force_kill:
                fix_cmd += "  (or retry with --force-kill)"
            _cli_fail(
                f"Could not stop existing bridge process on port {port}: {', '.join(survivors)}",
                f"Stop manually with: {fix_cmd}",
            )
        pids = _bridge_port_pids(port)

    if pids:
        console.print(
            f"[yellow]Bridge already running at {bridge_url} "
            f"(port {port} is in use by PID: {', '.join(pids)}).[/yellow]"
        )
        console.print("[dim]Stop existing bridge first, then run login again.[/dim]")
        console.print(f"[dim]Example: kill {' '.join(pids)}[/dim]")
        raise typer.Exit(0)

    if _is_bridge_port_in_use(host, port):
        if restart_existing:
            _cli_fail(
                f"Bridge port {port} is still in use after restart attempt.",
                f"Check listener with `lsof -i :{port} -n -P`, then stop the blocking process.",
            )
        console.print(
            f"[yellow]Bridge already running at {bridge_url} "
            f"(port {port} is in use).[/yellow]"
        )
        console.print(
            "[dim]If you need a fresh QR, stop existing process first:[/dim] "
            f"[dim]lsof -i :{port} -n -P[/dim]"
        )
        console.print("[dim]Then kill the PID and run `g-agent channels login` again.[/dim]")
        raise typer.Exit(0)

    bind_error = _bridge_bind_error(host, port)
    if bind_error:
        if bind_error.errno in {errno.EPERM, errno.EACCES}:
            _cli_fail(
                f"Cannot bind bridge port {port} (permission denied: {bind_error}).",
                "Check sandbox/firewall/permissions, or change "
                "channels.whatsapp.bridgeUrl to another free port.",
            )
        if bind_error.errno == errno.EADDRINUSE:
            console.print(
                f"[yellow]Bridge port {port} is already in use ({bind_error}).[/yellow]"
            )
            console.print("[dim]Stop existing process, then run login again.[/dim]")
            raise typer.Exit(0)
        _cli_fail(
            f"Bridge preflight failed on port {port}: {bind_error}",
            f"Check listener state with `lsof -i :{port} -n -P` and retry.",
        )

    bridge_dir = _get_bridge_dir(force_rebuild=rebuild)

    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    console.print("[dim]Tip: keep this process running after connected.[/dim]")
    console.print("[dim]Run `g-agent gateway` in another terminal.[/dim]\n")

    bridge_env = os.environ.copy()
    bridge_env["BRIDGE_HOST"] = host
    bridge_env["BRIDGE_PORT"] = str(port)
    bridge_env["AUTH_DIR"] = str(get_data_dir() / "whatsapp-auth")

    if config.channels.whatsapp.bridge_token:
        bridge_env["BRIDGE_TOKEN"] = config.channels.whatsapp.bridge_token

    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True, env=bridge_env)
    except subprocess.CalledProcessError as e:
        _cli_fail(
            f"Bridge failed (exit {e.returncode}).",
            f"Common causes: port {port} in use, permission denied, or stale bridge process. "
            f"Check listener with `lsof -i :{port} -n -P`.",
        )
    except FileNotFoundError:
        _cli_fail("npm not found.", "Install Node.js >= 18 and retry.")


# ============================================================================
# Plugin Commands
# ============================================================================


plugins_app = typer.Typer(help="Inspect runtime plugins")
app.add_typer(plugins_app, name="plugins")


@plugins_app.callback(invoke_without_command=True)
def plugins_main(ctx: typer.Context):
    """Inspect runtime plugin loading and policy."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@plugins_app.command("list")
def plugins_list():
    """List discovered plugins and effective policy status."""
    from g_agent.config.loader import load_config
    from g_agent.plugins.loader import filter_plugins, load_installed_plugins, plugin_label

    config = load_config()
    enabled, allow_set, deny_set = _plugin_policy_state(config)
    discovered = sorted(load_installed_plugins(), key=lambda plugin: plugin_label(plugin).lower())
    active = filter_plugins(
        discovered,
        enabled=enabled,
        allow=sorted(allow_set),
        deny=sorted(deny_set),
    )
    active_set = {plugin_label(plugin).strip().lower() for plugin in active}

    allow_text = ", ".join(sorted(allow_set)) if allow_set else "all"
    deny_text = ", ".join(sorted(deny_set)) if deny_set else "none"
    console.print(
        "Policy: "
        f"enabled={str(enabled).lower()}, allow={allow_text}, deny={deny_text}"
    )

    if not discovered:
        console.print(
            "[yellow]No plugins discovered from entry point group `g_agent.plugins`.[/yellow]"
        )
        return

    table = Table(title="Runtime Plugins")
    table.add_column("Plugin", style="cyan")
    table.add_column("Status")
    table.add_column("Hooks")
    table.add_column("Reason", style="yellow")

    for plugin in discovered:
        name = plugin_label(plugin)
        status, reason = _plugin_status(
            name,
            enabled=enabled,
            allow_set=allow_set,
            deny_set=deny_set,
            active_set=active_set,
        )
        table.add_row(name, status, _plugin_hooks(plugin), reason)

    console.print(table)
    console.print(f"Discovered: {len(discovered)} | Active: {len(active)}")


@plugins_app.command("doctor")
def plugins_doctor(
    strict: bool = typer.Option(False, "--strict", help="Exit with code 1 if checks fail"),
):
    """Run diagnostics for plugin discovery and policy configuration."""
    from g_agent.config.loader import load_config
    from g_agent.plugins.loader import filter_plugins, load_installed_plugins, plugin_label

    def _mark(level: str) -> str:
        if level == "pass":
            return "[green]PASS[/green]"
        if level == "warn":
            return "[yellow]WARN[/yellow]"
        return "[red]FAIL[/red]"

    results: list[tuple[str, str, str, str]] = []

    def add(check: str, level: str, detail: str, fix: str = "") -> None:
        results.append((check, level, detail, fix))

    config = load_config()
    enabled, allow_set, deny_set = _plugin_policy_state(config)
    discovered = load_installed_plugins()
    discovered_names = {plugin_label(plugin).strip().lower() for plugin in discovered}
    active = filter_plugins(
        discovered,
        enabled=enabled,
        allow=sorted(allow_set),
        deny=sorted(deny_set),
    )

    allow_unknown = sorted(name for name in allow_set if name not in discovered_names)
    deny_unknown = sorted(name for name in deny_set if name not in discovered_names)
    overlap = sorted(allow_set & deny_set)

    add(
        "Plugin discovery",
        "pass" if discovered else "warn",
        f"{len(discovered)} discovered",
        ""
        if discovered
        else "Install plugin package(s) exposing `g_agent.plugins` entry points",
    )
    add(
        "Plugin switch",
        "pass" if enabled else "warn",
        f"enabled={str(enabled).lower()}",
        "" if enabled else "Set tools.plugins.enabled=true to activate plugins",
    )
    if allow_set:
        add(
            "Allow list names",
            "warn" if allow_unknown else "pass",
            (
                f"unknown: {', '.join(allow_unknown)}"
                if allow_unknown
                else f"{len(allow_set)} configured"
            ),
            (
                "Run `g-agent plugins list` and update tools.plugins.allow"
                if allow_unknown
                else ""
            ),
        )
    else:
        add("Allow list names", "pass", "not configured (all discovered allowed)")

    if deny_set:
        add(
            "Deny list names",
            "warn" if deny_unknown else "pass",
            (
                f"unknown: {', '.join(deny_unknown)}"
                if deny_unknown
                else f"{len(deny_set)} configured"
            ),
            "Remove stale names from tools.plugins.deny" if deny_unknown else "",
        )
    else:
        add("Deny list names", "pass", "not configured")

    add(
        "Allow/Deny overlap",
        "warn" if overlap else "pass",
        ", ".join(overlap) if overlap else "none",
        "Deny wins; remove overlaps to avoid confusion" if overlap else "",
    )

    if enabled and active:
        add("Active plugins", "pass", f"{len(active)} active")
    elif enabled and discovered:
        add(
            "Active plugins",
            "fail",
            f"0 active from {len(discovered)} discovered",
            "Adjust tools.plugins.allow/deny (or disable plugins explicitly)",
        )
    elif enabled:
        add(
            "Active plugins",
            "warn",
            "0 active (none discovered)",
            "Install plugins or keep tools.plugins.enabled=false",
        )
    else:
        add(
            "Active plugins",
            "warn",
            "plugins disabled",
            "Set tools.plugins.enabled=true to enable plugin loading",
        )

    table = Table(title="Plugin Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="yellow")
    table.add_column("Fix Hint", style="magenta")

    for check, level, detail, fix in results:
        table.add_row(check, _mark(level), detail, fix or "-")
    console.print(table)

    fail_count = sum(1 for _, level, _, _ in results if level == "fail")
    warn_count = sum(1 for _, level, _, _ in results if level == "warn")
    pass_count = len(results) - fail_count - warn_count
    console.print(
        f"Summary: [green]{pass_count} pass[/green], [yellow]{warn_count} warn[/yellow], [red]{fail_count} fail[/red]"
    )

    if strict and fail_count > 0:
        raise typer.Exit(1)


# ============================================================================
# Google Workspace Commands
# ============================================================================


google_app = typer.Typer(help="Manage Google Workspace integration")
app.add_typer(google_app, name="google")


@google_app.callback(invoke_without_command=True)
def google_main(ctx: typer.Context):
    """Manage Google Workspace integration."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@google_app.command("status")
def google_status():
    """Show Google Workspace integration status."""
    from g_agent.config.loader import load_config

    config = load_config()
    google_cfg = config.integrations.google
    has_client = bool(google_cfg.client_id and google_cfg.client_secret)
    has_refresh = bool(google_cfg.refresh_token)
    has_access = bool(google_cfg.access_token)

    console.print("Google Workspace status")
    console.print(
        f"- Client credentials: {'[green]✓[/green]' if has_client else '[yellow]missing[/yellow]'}"
    )
    console.print(
        f"- Refresh token: {'[green]✓[/green]' if has_refresh else '[yellow]missing[/yellow]'}"
    )
    console.print(
        f"- Access token: {'[green]✓[/green]' if has_access else '[dim]not cached[/dim]'}"
    )
    console.print(f"- Calendar ID: {google_cfg.calendar_id or 'primary'}")


@google_app.command("configure")
def google_configure(
    client_id: str = typer.Option("", "--client-id", help="Google OAuth client ID"),
    client_secret: str = typer.Option("", "--client-secret", help="Google OAuth client secret"),
    calendar_id: str = typer.Option("primary", "--calendar-id", help="Default Google Calendar ID"),
):
    """Save Google OAuth client credentials into config."""
    from g_agent.config.loader import load_config, save_config

    config = load_config()
    if client_id:
        config.integrations.google.client_id = client_id.strip()
    if client_secret:
        config.integrations.google.client_secret = client_secret.strip()
    if calendar_id:
        config.integrations.google.calendar_id = calendar_id.strip()
    save_config(config)

    has_client = bool(
        config.integrations.google.client_id and config.integrations.google.client_secret
    )
    if has_client:
        console.print("[green]✓[/green] Google client credentials saved.")
    else:
        console.print("[yellow]Saved, but client credentials are still incomplete.[/yellow]")


@google_app.command("auth-url")
def google_auth_url(
    redirect_uri: str = typer.Option(
        "http://localhost", "--redirect-uri", help="OAuth redirect URI"
    ),
    scopes: str = typer.Option(
        "openid email "
        "https://www.googleapis.com/auth/gmail.modify "
        "https://www.googleapis.com/auth/calendar "
        "https://www.googleapis.com/auth/drive.readonly "
        "https://www.googleapis.com/auth/documents "
        "https://www.googleapis.com/auth/spreadsheets "
        "https://www.googleapis.com/auth/contacts.readonly",
        "--scopes",
        help="Space-separated OAuth scopes",
    ),
):
    """Generate Google OAuth consent URL."""
    from urllib.parse import urlencode

    from g_agent.config.loader import get_config_path, load_config

    config = load_config()
    google_cfg = config.integrations.google
    if not google_cfg.client_id:
        _cli_fail(
            "Google client_id is missing.",
            f"Set integrations.google.clientId in {get_config_path()}",
        )

    params = {
        "client_id": google_cfg.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": scopes,
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    console.print("Open this URL, authorize, then copy the `code`:")
    console.print(url)


@google_app.command("exchange")
def google_exchange(
    code: str = typer.Option(
        ..., "--code", prompt=True, hide_input=False, help="OAuth authorization code"
    ),
    redirect_uri: str = typer.Option(
        "http://localhost", "--redirect-uri", help="OAuth redirect URI"
    ),
):
    """Exchange OAuth code and save Google tokens into config."""
    import httpx

    from g_agent.config.loader import load_config, save_config

    config = load_config()
    google_cfg = config.integrations.google
    if not (google_cfg.client_id and google_cfg.client_secret):
        _cli_fail(
            "Google client_id/client_secret are missing.",
            "Set integrations.google.clientId and integrations.google.clientSecret first.",
        )

    payload = {
        "code": code.strip(),
        "client_id": google_cfg.client_id,
        "client_secret": google_cfg.client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post("https://oauth2.googleapis.com/token", data=payload)
    except Exception as e:
        _cli_fail(
            f"Token exchange failed: {e}",
            "Check internet connectivity and OAuth client credentials, then retry.",
        )

    if response.status_code != 200:
        _cli_fail(
            f"Token exchange failed (HTTP {response.status_code}).",
            "Re-run `g-agent google auth-url` and complete consent flow again.",
        )

    data = response.json()
    access_token = data.get("access_token", "")
    refresh_token = data.get("refresh_token")
    if not access_token:
        _cli_fail(
            "No access_token returned from Google.",
            "Re-run consent flow via `g-agent google auth-url` and exchange code again.",
        )

    config.integrations.google.access_token = access_token
    if refresh_token:
        config.integrations.google.refresh_token = refresh_token
    save_config(config)

    scope = data.get("scope", "")
    console.print("[green]✓[/green] Google tokens saved to config.")
    console.print(f"Scope: {scope or '(unknown)'}")
    if not refresh_token:
        console.print("[yellow]Note:[/yellow] refresh_token not returned; existing value kept.")


@google_app.command("verify")
def google_verify(timeout: float = typer.Option(10.0, "--timeout", help="HTTP timeout seconds")):
    """Verify Google auth by calling Gmail profile endpoint."""
    import httpx

    from g_agent.config.loader import load_config, save_config

    config = load_config()
    google_cfg = config.integrations.google

    has_refresh_creds = bool(
        google_cfg.client_id and google_cfg.client_secret and google_cfg.refresh_token
    )
    access_token = (google_cfg.access_token or "").strip()

    def refresh_access_token() -> tuple[bool, str, str]:
        """Refresh Google access token from refresh token."""
        if not has_refresh_creds:
            return False, "", "Google refresh credentials are incomplete."
        try:
            with httpx.Client(timeout=timeout) as client:
                refresh_resp = client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": google_cfg.client_id,
                        "client_secret": google_cfg.client_secret,
                        "refresh_token": google_cfg.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
            if refresh_resp.status_code != 200:
                return False, "", f"Refresh token failed (HTTP {refresh_resp.status_code})."
            token = refresh_resp.json().get("access_token", "")
            if not token:
                return False, "", "Refresh token response missing access_token."
            return True, token, ""
        except Exception as e:
            return False, "", f"Google token refresh failed: {e}"

    if has_refresh_creds:
        refreshed, refreshed_token, refresh_error = refresh_access_token()
        if refreshed:
            access_token = refreshed_token
            config.integrations.google.access_token = access_token
            save_config(config)
        elif not access_token:
            _cli_fail(
                refresh_error,
                "Run `g-agent google auth-url`, then `g-agent google exchange --code ...`.",
            )

    if not access_token:
        _cli_fail(
            "Google auth not configured.",
            "Run `g-agent google configure`, then `g-agent google auth-url` and `g-agent google exchange --code ...`.",
        )

    try:
        with httpx.Client(timeout=timeout) as client:
            profile_resp = client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except Exception as e:
        _cli_fail(
            f"Google API request failed: {e}",
            "Check network connectivity, then run `g-agent google verify` again.",
        )

    if profile_resp.status_code == 401 and has_refresh_creds:
        refreshed, refreshed_token, refresh_error = refresh_access_token()
        if not refreshed:
            _cli_fail(
                refresh_error,
                "Re-run `g-agent google auth-url` and `g-agent google exchange --code ...`.",
            )
        access_token = refreshed_token
        config.integrations.google.access_token = access_token
        save_config(config)
        try:
            with httpx.Client(timeout=timeout) as client:
                profile_resp = client.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except Exception as e:
            _cli_fail(
                f"Google API request failed: {e}",
                "Check network connectivity, then run `g-agent google verify` again.",
            )

    if profile_resp.status_code != 200:
        _cli_fail(
            f"Google verify failed (HTTP {profile_resp.status_code}).",
            "Refresh auth with `g-agent google auth-url` and `g-agent google exchange --code ...`.",
        )

    profile = profile_resp.json()
    email_address = profile.get("emailAddress", "(unknown)")
    total_messages = profile.get("messagesTotal", "n/a")
    console.print(
        f"[green]✓[/green] Google auth verified for {email_address} (messages: {total_messages})"
    )


@google_app.command("clear")
def google_clear(
    clear_client: bool = typer.Option(
        False, "--clear-client", help="Also clear client_id/client_secret"
    ),
):
    """Clear saved Google Workspace tokens from config."""
    from g_agent.config.loader import load_config, save_config

    config = load_config()
    config.integrations.google.access_token = ""
    config.integrations.google.refresh_token = ""
    if clear_client:
        config.integrations.google.client_id = ""
        config.integrations.google.client_secret = ""
    save_config(config)
    console.print("[green]✓[/green] Cleared Google Workspace tokens.")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.callback(invoke_without_command=True)
def cron_main(ctx: typer.Context):
    """Manage scheduled tasks."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from g_agent.config.loader import get_data_dir
    from g_agent.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print("No scheduled jobs.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")

    import time

    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"

        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000)
            )
            next_run = next_time

        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"

        table.add_row(job.id, job.name, sched, status, next_run)

    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(
        None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"
    ),
):
    """Add a scheduled job."""
    import datetime

    from g_agent.config.loader import get_data_dir
    from g_agent.cron.service import CronService
    from g_agent.cron.types import CronSchedule

    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        try:
            dt = datetime.datetime.fromisoformat(at)
        except ValueError:
            _cli_fail(
                f"Invalid --at datetime: {at}",
                "Use ISO format, e.g. 2026-02-12T09:30:00",
            )
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        _cli_fail("Missing schedule option.", "Use exactly one of: --every, --cron, or --at")

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )

    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from g_agent.config.loader import get_data_dir
    from g_agent.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        _cli_fail(
            f"Job {job_id} not found.",
            "Run `g-agent cron list --all` to find valid IDs.",
        )


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from g_agent.config.loader import get_data_dir
    from g_agent.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        _cli_fail(
            f"Job {job_id} not found.",
            "Run `g-agent cron list --all` to find valid IDs.",
        )


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from g_agent.config.loader import get_data_dir
    from g_agent.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    async def run():
        return await service.run_job(job_id, force=force)

    if asyncio.run(run()):
        console.print("[green]✓[/green] Job executed")
    else:
        _cli_fail(
            f"Failed to run job {job_id}.",
            "Check if the job exists and is enabled with `g-agent cron list --all`.",
        )


# ============================================================================
# Proactive Commands
# ============================================================================


DAILY_DIGEST_PROMPT = (
    "Create a concise daily digest for the user. "
    "Use memory, recent context, and (if configured) calendar/email tools. "
    "Output sections: Priorities, Calendar, Inbox, Next 3 Actions."
)

WEEKLY_LESSONS_PROMPT = (
    "Review recent lessons and interactions, distill recurring mistakes, "
    "and propose practical behavior improvements for next week."
)


@app.command()
def digest(
    session_id: str = typer.Option(
        "cli:digest", "--session", "-s", help="Session ID for digest generation"
    ),
):
    """Generate a daily personal digest via the agent."""
    from g_agent.agent.loop import AgentLoop
    from g_agent.bus.queue import MessageBus
    from g_agent.config.loader import get_config_path, load_config
    from g_agent.plugins.loader import filter_plugins, load_installed_plugins
    from g_agent.providers.factory import build_provider, collect_provider_factories, has_provider_factory

    config = load_config()
    route = config.resolve_model_route()
    api_key = route.api_key
    if not api_key and route.provider not in {"vllm", "bedrock"}:
        api_key = config.get_api_key()
    model = config.agents.defaults.model
    is_bedrock = route.provider == "bedrock" or model.startswith("bedrock/")
    plugins = filter_plugins(
        load_installed_plugins(),
        enabled=config.tools.plugins.enabled,
        allow=config.tools.plugins.allow,
        deny=config.tools.plugins.deny,
    )
    provider_factories = collect_provider_factories(config, plugins)
    if (
        not api_key
        and not is_bedrock
        and not has_provider_factory(route.provider, provider_factories=provider_factories)
    ):
        config_path = get_config_path()
        _cli_fail(
            f"No API key configured for provider '{route.provider}'.",
            _missing_api_key_fix(route.provider, config_path),
        )

    provider = build_provider(
        route.model_copy(update={"api_key": api_key}),
        config,
        provider_factories=provider_factories,
    )
    bus = MessageBus()
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=route.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        slack_webhook_url=config.integrations.slack.webhook_url or None,
        smtp_config=config.integrations.smtp,
        google_config=config.integrations.google,
        browser_config=config.tools.browser,
        tool_policy=config.tools.policy,
        risky_tools=config.tools.risky_tools,
        approval_mode=config.tools.approval_mode,
        enable_reflection=config.agents.defaults.enable_reflection,
        summary_interval=config.agents.defaults.summary_interval,
        fallback_models=route.fallback_models,
        plugins=plugins,
        visual_config=config.visual,
    )

    async def run_digest() -> str:
        return await agent_loop.process_direct(
            DAILY_DIGEST_PROMPT,
            session_key=session_id,
            channel="cli",
            chat_id="digest",
        )

    response = asyncio.run(run_digest())
    console.print(f"\n{__logo__} {response}")


@app.command("proactive-enable")
def proactive_enable(
    daily_cron: str = typer.Option("0 8 * * *", "--daily-cron", help="Cron for daily digest"),
    weekly_cron: str = typer.Option(
        "0 9 * * 1", "--weekly-cron", help="Cron for weekly lessons distillation"
    ),
    include_calendar_watch: bool = typer.Option(
        True, "--calendar-watch/--no-calendar-watch", help="Enable calendar lookahead reminders"
    ),
    calendar_every: int | None = typer.Option(
        None, "--calendar-every", help="Calendar watch interval in minutes"
    ),
    calendar_horizon: int | None = typer.Option(
        None, "--calendar-horizon", help="Calendar lookahead window in minutes"
    ),
    calendar_leads: str | None = typer.Option(
        None, "--calendar-leads", help="Lead reminders in minutes, comma-separated (e.g. 30,10)"
    ),
    deliver: bool = typer.Option(False, "--deliver", help="Deliver output to a channel target"),
    channel: str = typer.Option(
        None, "--channel", help="Target channel for delivery (telegram/whatsapp)"
    ),
    to: str = typer.Option(None, "--to", help="Target chat ID / number for delivery"),
):
    """Install proactive cron jobs (daily digest + weekly lessons)."""
    from g_agent.config.loader import get_data_dir, load_config, save_config
    from g_agent.cron.service import CronService
    from g_agent.cron.types import CronSchedule

    if deliver and (not channel or not to):
        console.print("[red]When --deliver is set, both --channel and --to are required.[/red]")
        raise typer.Exit(1)

    config = load_config()
    proactive_cfg = config.proactive
    if calendar_every is not None:
        proactive_cfg.calendar_watch_every_minutes = max(1, int(calendar_every))
    if calendar_horizon is not None:
        proactive_cfg.calendar_watch_horizon_minutes = max(10, int(calendar_horizon))
    if calendar_leads is not None:
        parsed_leads = []
        for token in calendar_leads.split(","):
            raw = token.strip()
            if not raw:
                continue
            try:
                value = int(raw)
            except ValueError:
                continue
            if value > 0:
                parsed_leads.append(value)
        if parsed_leads:
            proactive_cfg.calendar_watch_lead_minutes = sorted(set(parsed_leads), reverse=True)
    save_config(config)

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    existing = {job.name: job for job in service.list_jobs(include_disabled=True)}

    created: list[str] = []
    if "daily-digest" not in existing:
        job = service.add_job(
            name="daily-digest",
            schedule=CronSchedule(kind="cron", expr=daily_cron),
            message=DAILY_DIGEST_PROMPT,
            deliver=deliver,
            channel=channel,
            to=to,
        )
        created.append(f"daily-digest ({job.id})")

    if "weekly-lessons-distill" not in existing:
        job = service.add_job(
            name="weekly-lessons-distill",
            schedule=CronSchedule(kind="cron", expr=weekly_cron),
            message=WEEKLY_LESSONS_PROMPT,
            deliver=deliver,
            channel=channel,
            to=to,
        )
        created.append(f"weekly-lessons-distill ({job.id})")

    if include_calendar_watch and "calendar-watch" not in existing:
        if deliver and channel and to:
            job = service.add_job(
                name="calendar-watch",
                schedule=CronSchedule(
                    kind="every",
                    every_ms=max(1, int(proactive_cfg.calendar_watch_every_minutes)) * 60 * 1000,
                ),
                message="calendar_watch",
                kind="system_event",
                deliver=True,
                channel=channel,
                to=to,
            )
            created.append(f"calendar-watch ({job.id})")
        else:
            console.print(
                "[yellow]Calendar watch skipped: requires --deliver --channel --to target.[/yellow]"
            )

    if created:
        console.print("[green]✓[/green] Proactive jobs created:")
        for item in created:
            console.print(f"  - {item}")
    else:
        console.print("[yellow]Proactive jobs already exist. No changes made.[/yellow]")


@app.command("proactive-disable")
def proactive_disable():
    """Remove default proactive cron jobs."""
    from g_agent.config.loader import get_data_dir
    from g_agent.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    targets = {"daily-digest", "weekly-lessons-distill", "calendar-watch"}
    removed = 0
    for job in service.list_jobs(include_disabled=True):
        if job.name in targets and service.remove_job(job.id):
            removed += 1

    if removed:
        console.print(f"[green]✓[/green] Removed {removed} proactive job(s).")
    else:
        console.print("[yellow]No proactive jobs found.[/yellow]")


# ============================================================================
# Policy Preset Commands
# ============================================================================


policy_app = typer.Typer(help="Manage tool policy presets")
app.add_typer(policy_app, name="policy")


@policy_app.callback(invoke_without_command=True)
def policy_main(ctx: typer.Context):
    """Manage tool policy presets."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@policy_app.command("list")
def policy_list():
    """List available policy presets."""
    from g_agent.config.presets import list_presets

    table = Table(title="Policy Presets")
    table.add_column("Preset", style="cyan")
    table.add_column("Description")
    table.add_column("Rules", justify="right")

    for preset in list_presets():
        table.add_row(preset.name, preset.description, str(len(preset.rules)))

    console.print(table)


@policy_app.command("apply")
def policy_apply(
    preset: str = typer.Argument(
        ..., help="Preset name: personal_full|guest_limited|guest_readonly"
    ),
    channel: str = typer.Option(
        "", "--channel", help="Optional channel scope (telegram/whatsapp/...)"
    ),
    sender: str = typer.Option("", "--sender", help="Optional sender scope (user ID/phone)"),
    replace_scope: bool = typer.Option(
        False,
        "--replace-scope",
        help="Replace existing rules in the same scope before applying",
    ),
):
    """Apply a policy preset globally or to a channel/sender scope."""
    from g_agent.config.loader import load_config, save_config
    from g_agent.config.presets import apply_preset, get_preset

    channel = channel.strip()
    sender = sender.strip()
    if sender and not channel:
        console.print("[red]--sender requires --channel[/red]")
        raise typer.Exit(1)

    config = load_config()
    try:
        get_preset(preset)
        result = apply_preset(
            config,
            preset_name=preset,
            channel=channel or None,
            sender=sender or None,
            replace_scope=replace_scope,
            set_defaults=True,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    save_config(config)

    scope_text = "global"
    if result.get("channel") and result.get("sender"):
        scope_text = f"{result['channel']}:{result['sender']}"
    elif result.get("channel"):
        scope_text = f"{result['channel']}:*"

    console.print(f"[green]✓[/green] Applied preset: [bold]{result['preset']}[/bold]")
    console.print(f"Scope: {scope_text}")
    console.print(f"Rules: {result['applied_rules']} applied ({result['changed_rules']} changed)")
    console.print(f"Approval mode: {config.tools.approval_mode}")
    console.print(
        "Security (restrictToWorkspace): "
        + (
            "[green]enabled[/green]"
            if config.tools.restrict_to_workspace
            else "[yellow]disabled[/yellow]"
        )
    )


@policy_app.command("status")
def policy_status():
    """Show current policy map grouped by scope."""
    from g_agent.config.loader import load_config

    config = load_config()
    policy = dict(config.tools.policy)
    if not policy:
        console.print("No policy rules configured.")
        return

    global_rules = {k: v for k, v in policy.items() if ":" not in k}
    scoped_rules = {k: v for k, v in policy.items() if ":" in k}

    console.print(f"Approval mode: {config.tools.approval_mode}")
    console.print(
        "Security (restrictToWorkspace): "
        + ("enabled" if config.tools.restrict_to_workspace else "disabled")
    )
    console.print(f"Risky tools: {len(config.tools.risky_tools)}")

    if global_rules:
        table = Table(title="Global Policy Rules")
        table.add_column("Key", style="cyan")
        table.add_column("Decision")
        for key in sorted(global_rules):
            table.add_row(key, global_rules[key])
        console.print(table)

    if scoped_rules:
        table = Table(title="Scoped Policy Rules")
        table.add_column("Key", style="cyan")
        table.add_column("Decision")
        for key in sorted(scoped_rules):
            table.add_row(key, scoped_rules[key])
        console.print(table)


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def feedback(
    message: str = typer.Argument(..., help="Feedback or lesson text"),
    severity: str = typer.Option("medium", "--severity", help="low|medium|high"),
    source: str = typer.Option("manual", "--source", help="Feedback source label"),
):
    """Log a lesson for self-improvement memory."""
    from g_agent.agent.memory import MemoryStore
    from g_agent.config.loader import load_config

    if severity not in {"low", "medium", "high"}:
        console.print("[red]Severity must be one of: low, medium, high[/red]")
        raise typer.Exit(1)

    config = load_config()
    store = MemoryStore(config.workspace_path)
    try:
        ok = store.append_lesson(message, source=source, severity=severity)
    except Exception as e:
        console.print(f"[red]Failed to save feedback: {e}[/red]")
        raise typer.Exit(1)

    if ok:
        console.print("[green]✓[/green] Feedback saved to memory/LESSONS.md")
    else:
        console.print("[yellow]Feedback was empty or file not writable.[/yellow]")


@app.command("memory-audit")
def memory_audit(
    limit: int = typer.Option(40, "--limit", help="Maximum drift/conflict items to inspect"),
    scope: list[str] = typer.Option(
        None,
        "--scope",
        help="Optional repeated scope filter for cross-scope checks (profile|long-term|custom|projects|relationships)",
    ),
    as_json: bool = typer.Option(False, "--json", help="Output JSON payload"),
    strict: bool = typer.Option(False, "--strict", help="Exit 1 when drift/conflicts exist"),
):
    """Audit memory drift and cross-scope fact conflicts."""
    from g_agent.agent.memory import MemoryStore
    from g_agent.config.loader import load_config

    max_items = max(1, int(limit))
    scopes = [item.strip().lower() for item in (scope or []) if item.strip()]
    scoped = scopes or None

    config = load_config()
    store = MemoryStore(config.workspace_path)
    summary_drifts = store.detect_summary_fact_drift(limit=max_items)
    cross_scope_conflicts = store.detect_cross_scope_fact_conflicts(
        scopes=scoped,
        limit=max_items,
    )

    payload: dict[str, Any] = {
        "workspace": str(config.workspace_path),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "limit": max_items,
        "scopes": scopes or ["profile", "long-term", "custom"],
        "summary_drift_count": len(summary_drifts),
        "cross_scope_conflict_count": len(cross_scope_conflicts),
        "summary_drifts": summary_drifts,
        "cross_scope_conflicts": cross_scope_conflicts,
    }

    if as_json:
        console.print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        console.print(f"{__logo__} Memory Audit\n")
        console.print(f"Summary drift: {len(summary_drifts)}")
        console.print(f"Cross-scope conflicts: {len(cross_scope_conflicts)}")

        if summary_drifts:
            console.print("Summary drift details:")
            for item in summary_drifts[:12]:
                console.print(
                    f"  - {item.get('key', 'unknown')}: "
                    f"summary='{item.get('summary_fact', '')}' vs durable='{item.get('active_fact', '')}'"
                )

        if cross_scope_conflicts:
            console.print("Cross-scope conflict details:")
            for item in cross_scope_conflicts[:12]:
                preferred_scope = item.get("preferred_scope", "")
                preferred_fact = item.get("preferred_fact", "")
                console.print(
                    f"  - {item.get('key', 'unknown')}: prefer [{preferred_scope}] {preferred_fact}"
                )
                for conflict in item.get("conflicting_facts", [])[:5]:
                    console.print(
                        f"      vs [{conflict.get('scope', '')}:{conflict.get('source', '')}] "
                        f"{conflict.get('text', '')}"
                    )

    if strict and (summary_drifts or cross_scope_conflicts):
        raise typer.Exit(1)


@app.command("security-audit")
def security_audit(
    as_json: bool = typer.Option(False, "--json", help="Output JSON payload"),
    strict: bool = typer.Option(False, "--strict", help="Exit 1 when audit has warn/fail checks"),
):
    """Run baseline security audit for current profile."""
    from g_agent.config.loader import get_config_path, get_data_dir, load_config
    from g_agent.security.audit import run_security_audit

    data_dir = get_data_dir()
    config_path = get_config_path()
    config = load_config()
    report = run_security_audit(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=config.workspace_path,
    )

    if as_json:
        console.print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        table = Table(title=f"{__logo__} Security Audit")
        table.add_column("Check", style="cyan")
        table.add_column("Status")
        table.add_column("Details", style="yellow")
        table.add_column("Fix Hint", style="magenta")

        for item in report.get("checks", []):
            level = item.get("level", "warn")
            if level == "pass":
                mark = "[green]PASS[/green]"
            elif level == "fail":
                mark = "[red]FAIL[/red]"
            else:
                mark = "[yellow]WARN[/yellow]"
            table.add_row(
                str(item.get("name", "")),
                mark,
                str(item.get("detail", "")),
                str(item.get("remediation", "") or "-"),
            )

        console.print(table)
        summary = report.get("summary", {})
        console.print(
            "Summary: "
            f"pass={summary.get('pass', 0)}, "
            f"warn={summary.get('warn', 0)}, "
            f"fail={summary.get('fail', 0)}"
        )

    summary = report.get("summary", {})
    if strict and (int(summary.get("warn", 0)) > 0 or int(summary.get("fail", 0)) > 0):
        raise typer.Exit(1)


@app.command("security-fix")
def security_fix(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply safe automatic remediations (default: dry-run)",
    ),
    as_json: bool = typer.Option(False, "--json", help="Output JSON payload"),
):
    """Plan or apply automatic security baseline remediations."""
    from g_agent.config.loader import get_config_path, get_data_dir, load_config
    from g_agent.security.fix import run_security_fix

    data_dir = get_data_dir()
    config_path = get_config_path()
    config = load_config()

    report = run_security_fix(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=config.workspace_path,
        apply=apply,
    )

    if as_json:
        console.print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    table = Table(title=f"{__logo__} Security Fix ({'apply' if apply else 'dry-run'})")
    table.add_column("Action", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="yellow")

    for item in report.get("actions", []):
        status = str(item.get("status", "skipped"))
        if status in {"applied", "unchanged"}:
            mark = "[green]APPLIED[/green]" if status == "applied" else "[green]OK[/green]"
        elif status == "planned":
            mark = "[yellow]PLAN[/yellow]"
        elif status == "failed":
            mark = "[red]FAILED[/red]"
        else:
            mark = "[yellow]SKIP[/yellow]"
        table.add_row(str(item.get("name", "")), mark, str(item.get("detail", "")))

    console.print(table)
    before = report.get("before", {}).get("summary", {})
    after = report.get("after", {}).get("summary", {})
    console.print(
        "Before: "
        f"pass={before.get('pass', 0)}, warn={before.get('warn', 0)}, fail={before.get('fail', 0)}"
    )
    console.print(
        "After:  "
        f"pass={after.get('pass', 0)}, warn={after.get('warn', 0)}, fail={after.get('fail', 0)}"
    )
    console.print(f"Changed items: {report.get('changed', 0)}")
    if not apply:
        console.print("[dim]Dry-run only. Re-run with --apply to apply planned remediations.[/dim]")


@app.command("metrics")
def metrics_cmd(
    hours: int = typer.Option(24, "--hours", "-w", help="Metrics window in hours"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON snapshot"),
    dashboard_json: bool = typer.Option(
        False,
        "--dashboard-json",
        help="Output flat dashboard/scraper-friendly JSON summary",
    ),
    export: str = typer.Option(
        "",
        "--export",
        help="Optional output path (.json, .prom, .dashboard.json)",
    ),
    export_format: str = typer.Option(
        "auto",
        "--export-format",
        help="auto|json|prometheus|dashboard_json",
    ),
    prune: bool = typer.Option(
        False,
        "--prune",
        help="Prune metrics events before printing snapshot",
    ),
    retention_hours: int = typer.Option(
        168,
        "--retention-hours",
        help="Retention window used with --prune",
    ),
    max_events: int = typer.Option(
        50000,
        "--max-events",
        help="Maximum events kept after pruning (0 disables cap)",
    ),
    prune_dry_run: bool = typer.Option(
        False,
        "--prune-dry-run",
        help="Preview prune result without rewriting events file",
    ),
):
    """Show runtime observability metrics snapshot."""
    from g_agent.config.loader import load_config
    from g_agent.observability.metrics import MetricsStore

    config = load_config()
    store = MetricsStore(config.workspace_path / "state" / "metrics" / "events.jsonl")
    prune_result: dict[str, Any] | None = None
    if prune:
        prune_result = store.prune_events(
            keep_hours=retention_hours,
            max_events=max_events,
            dry_run=prune_dry_run,
        )
        if not prune_result.get("ok"):
            console.print(
                f"[red]Metrics prune failed:[/red] {prune_result.get('error', 'unknown')}"
            )
            raise typer.Exit(1)

    snapshot = store.snapshot(hours=hours)
    alerts = store.alert_summary(hours=hours, snapshot=snapshot)

    export_result: dict[str, Any] | None = None
    if export.strip():
        export_result = store.export_snapshot(
            Path(export.strip()),
            hours=hours,
            output_format=export_format,
        )
        if not export_result.get("ok"):
            console.print(
                f"[red]Metrics export failed:[/red] {export_result.get('error', 'unknown')}"
            )
            raise typer.Exit(1)

    if dashboard_json:
        payload = store.dashboard_summary(hours=hours)
        if prune_result:
            payload["prune"] = prune_result
        console.print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif as_json:
        payload = dict(snapshot)
        payload["alerts"] = alerts
        if prune_result:
            payload["prune"] = prune_result
        console.print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        llm = snapshot["llm"]
        tools = snapshot["tools"]
        recall = snapshot["recall"]
        cron = snapshot["cron"]
        totals = snapshot["totals"]

        console.print(f"{__logo__} Metrics ({snapshot['window_hours']}h)\n")
        console.print(f"Events file: {snapshot['events_file']}")
        console.print(f"Total events: {totals['events']}")
        console.print(
            f"LLM calls: {llm['calls']} | success: {llm['success_rate']}% | p95: {llm['latency_ms_p95']}ms"
        )
        console.print(
            f"Tool calls: {tools['calls']} | success: {tools['success_rate']}% | p95: {tools['latency_ms_p95']}ms"
        )
        console.print(
            f"Recall hit-rate: {recall['hit_rate']}% ({recall['hit_queries']}/{recall['queries']}) | avg hits: {recall['avg_hits']}"
        )
        console.print(
            f"Cron runs: {cron['runs']} | success: {cron['success_rate']}% | proactive: {cron['proactive_runs']}"
        )
        console.print(
            f"Alerts: {alerts['overall']} | warn: {alerts['warn_count']} | ok: {alerts['ok_count']} | na: {alerts['na_count']}"
        )
        if alerts["warn_count"] > 0:
            console.print("Alert checks:")
            for item in alerts["checks"]:
                if item["status"] != "warn":
                    continue
                console.print(
                    f"  - {item['key']}: {item['actual']} {item['operator']} {item['threshold']} "
                    f"(samples: {item['samples']})"
                )
        top_tools = tools.get("top_tools", [])
        if top_tools:
            console.print("Top tools:")
            for item in top_tools[:8]:
                console.print(
                    f"  - {item['tool']}: {item['calls']} call(s), {item['errors']} error(s)"
                )
        if prune_result:
            console.print(
                f"Prune: removed {prune_result['removed_total']} event(s), "
                f"kept {prune_result['after']} (age={prune_result['removed_by_age']}, cap={prune_result['removed_by_cap']}, "
                f"dry-run={prune_result['dry_run']})"
            )

    if export_result:
        console.print(
            f"[green]✓[/green] Metrics exported: {export_result['path']} "
            f"({export_result['format']}, {export_result['bytes']} bytes)"
        )


@app.command()
def status():
    """Show g-agent status."""
    from datetime import datetime

    from g_agent.config.loader import get_config_path, get_data_dir, load_config

    data_dir = get_data_dir()
    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} {__brand__} Status\n")

    console.print(
        f"Data dir: {data_dir} {'[green]✓[/green]' if data_dir.exists() else '[red]✗[/red]'}"
    )
    console.print(
        f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}"
    )
    console.print(
        f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}"
    )

    if config_path.exists():
        route = config.resolve_model_route()
        console.print(f"Model: {route.model}")
        console.print(
            f"Routing: mode={route.mode}, provider={route.provider}, base={route.api_base or 'none'}"
        )
        if route.fallback_models:
            console.print(f"Fallback models: {', '.join(route.fallback_models)}")

        # Check API keys
        has_openrouter = bool(config.providers.openrouter.api_key)
        has_anthropic = bool(config.providers.anthropic.api_key)
        has_openai = bool(config.providers.openai.api_key)
        has_gemini = bool(config.providers.gemini.api_key)
        has_vllm = bool(config.providers.vllm.api_base)
        has_brave = bool(config.tools.web.search.api_key)

        console.print(
            f"OpenRouter API: {'[green]✓[/green]' if has_openrouter else '[dim]not set[/dim]'}"
        )
        console.print(
            f"Anthropic API: {'[green]✓[/green]' if has_anthropic else '[dim]not set[/dim]'}"
        )
        console.print(f"OpenAI API: {'[green]✓[/green]' if has_openai else '[dim]not set[/dim]'}")
        console.print(f"Gemini API: {'[green]✓[/green]' if has_gemini else '[dim]not set[/dim]'}")
        vllm_status = (
            f"[green]✓ {config.providers.vllm.api_base}[/green]"
            if has_vllm
            else "[dim]not set[/dim]"
        )
        console.print(f"vLLM/Local: {vllm_status}")
        console.print(
            f"Brave Search API: {'[green]✓[/green]' if has_brave else '[dim]not set[/dim]'}"
        )
        console.print(
            f"Security (restrictToWorkspace): {'[green]✓ enabled[/green]' if config.tools.restrict_to_workspace else '[yellow]disabled[/yellow]'}"
        )
        console.print(
            f"Reasoning reflection: {'[green]✓ enabled[/green]' if config.agents.defaults.enable_reflection else '[dim]disabled[/dim]'}"
        )
        console.print(f"Session summary interval: {config.agents.defaults.summary_interval} turns")

        tg = config.channels.telegram
        wa = config.channels.whatsapp
        console.print(
            f"Telegram channel: {'[green]✓ enabled[/green]' if tg.enabled else '[dim]disabled[/dim]'} (allowFrom: {len(tg.allow_from)})"
        )
        console.print(
            f"WhatsApp channel: {'[green]✓ enabled[/green]' if wa.enabled else '[dim]disabled[/dim]'} (allowFrom: {len(wa.allow_from)})"
        )

        console.print(
            f"Slack webhook: {'[green]✓[/green]' if config.integrations.slack.webhook_url else '[dim]not set[/dim]'}"
        )
        has_smtp = bool(config.integrations.smtp.host)
        console.print(
            f"SMTP integration: {'[green]✓[/green]' if has_smtp else '[dim]not set[/dim]'}"
        )
        has_google = bool(
            config.integrations.google.access_token
            or (
                config.integrations.google.client_id
                and config.integrations.google.client_secret
                and config.integrations.google.refresh_token
            )
        )
        console.print(
            f"Google Workspace: {'[green]✓[/green]' if has_google else '[dim]not set[/dim]'}"
        )
        google_has_client = bool(
            config.integrations.google.client_id and config.integrations.google.client_secret
        )
        google_has_refresh = bool(config.integrations.google.refresh_token)
        console.print(
            f"Google OAuth parts: client={'✓' if google_has_client else '✗'}, refresh={'✓' if google_has_refresh else '✗'}"
        )
        browser_allow = len(config.tools.browser.allow_domains)
        browser_deny = len(config.tools.browser.deny_domains)
        policy_global = sum(1 for key in config.tools.policy if ":" not in key)
        policy_scoped = len(config.tools.policy) - policy_global
        console.print(
            f"Browser policy: allow={browser_allow}, deny={browser_deny}, timeout={config.tools.browser.timeout_seconds}s"
        )
        console.print(f"Tool policy rules: {len(config.tools.policy)}")
        console.print(f"Tool policy scope: global={policy_global}, scoped={policy_scoped}")
        console.print(f"Approval mode: {config.tools.approval_mode}")
        quiet_cfg = config.proactive.quiet_hours
        quiet_desc = (
            f"{quiet_cfg.start}-{quiet_cfg.end} ({quiet_cfg.timezone})"
            if quiet_cfg.enabled
            else "disabled"
        )
        console.print(f"Quiet hours: {quiet_desc}")
        try:
            from g_agent.cron.service import CronService

            proactive_names = {"daily-digest", "weekly-lessons-distill", "calendar-watch"}
            cron_service = CronService(get_data_dir() / "cron" / "jobs.json")
            proactive_count = sum(
                1
                for job in cron_service.list_jobs(include_disabled=True)
                if job.name in proactive_names
            )
            console.print(f"Proactive jobs: {proactive_count}")
        except Exception:
            console.print("Proactive jobs: [dim]unknown[/dim]")
        try:
            from g_agent.observability.metrics import MetricsStore

            metrics_store = MetricsStore(workspace / "state" / "metrics" / "events.jsonl")
            metrics_snapshot = metrics_store.snapshot(hours=24)
            metrics_alerts = metrics_store.alert_compact(hours=24, snapshot=metrics_snapshot)
            console.print(
                "Metrics (24h): "
                f"events={metrics_snapshot['totals']['events']}, "
                f"llm={metrics_snapshot['llm']['calls']}, "
                f"tools={metrics_snapshot['tools']['calls']}, "
                f"recall-hit={metrics_snapshot['recall']['hit_rate']}%"
            )
            console.print(f"Metrics alerts (24h): {metrics_alerts['brief']}")
        except Exception:
            console.print("Metrics (24h): [dim]unknown[/dim]")

        memory_file = workspace / "memory" / "MEMORY.md"
        facts_file = workspace / "memory" / "FACTS.md"
        lessons_file = workspace / "memory" / "LESSONS.md"
        profile_file = workspace / "memory" / "PROFILE.md"
        relationships_file = workspace / "memory" / "RELATIONSHIPS.md"
        projects_file = workspace / "memory" / "PROJECTS.md"
        today_file = workspace / "memory" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
        console.print(
            f"Long-term memory: {'[green]✓[/green]' if memory_file.exists() else '[yellow]missing[/yellow]'} ({memory_file})"
        )
        console.print(
            f"Fact index memory: {'[green]✓[/green]' if facts_file.exists() else '[dim]not created yet[/dim]'} ({facts_file})"
        )
        console.print(
            f"Lessons memory: {'[green]✓[/green]' if lessons_file.exists() else '[dim]not created yet[/dim]'} ({lessons_file})"
        )
        console.print(
            f"Profile memory: {'[green]✓[/green]' if profile_file.exists() else '[dim]not created yet[/dim]'} ({profile_file})"
        )
        console.print(
            f"Relationships memory: {'[green]✓[/green]' if relationships_file.exists() else '[dim]not created yet[/dim]'} ({relationships_file})"
        )
        console.print(
            f"Projects memory: {'[green]✓[/green]' if projects_file.exists() else '[dim]not created yet[/dim]'} ({projects_file})"
        )
        console.print(
            f"Today memory note: {'[green]✓[/green]' if today_file.exists() else '[dim]not created yet[/dim]'}"
        )


@app.command()
def doctor(
    network: bool = typer.Option(
        True, "--network/--no-network", help="Run external network checks"
    ),
    timeout: float = typer.Option(6.0, "--timeout", help="Per-check timeout in seconds"),
    strict: bool = typer.Option(False, "--strict", help="Exit with code 1 if any check fails"),
):
    """Run diagnostics for model, channels, memory, and tool configuration."""
    import socket
    from datetime import datetime
    from urllib.parse import urlparse

    import httpx

    from g_agent.config.loader import get_config_path, get_data_dir, load_config

    def _mark(level: str) -> str:
        if level == "pass":
            return "[green]PASS[/green]"
        if level == "warn":
            return "[yellow]WARN[/yellow]"
        return "[red]FAIL[/red]"

    results: list[tuple[str, str, str, str]] = []

    def add(check: str, level: str, detail: str, fix: str = "") -> None:
        results.append((check, level, detail, fix))

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    if config_path.exists():
        add("Config file", "pass", str(config_path))
    else:
        add("Config file", "fail", str(config_path), "Run: g-agent onboard")

    if workspace.exists():
        add("Workspace", "pass", str(workspace))
    else:
        add("Workspace", "fail", str(workspace), f"Run: mkdir -p {workspace}")

    add(
        "Security sandbox",
        "pass" if config.tools.restrict_to_workspace else "warn",
        f"restrictToWorkspace={str(config.tools.restrict_to_workspace).lower()}",
        ""
        if config.tools.restrict_to_workspace
        else f"Set true in {config_path} (tools.restrictToWorkspace)",
    )
    try:
        from g_agent.security.audit import run_security_audit

        security_report = run_security_audit(
            config=config,
            data_dir=get_data_dir(),
            config_path=config_path,
            workspace_path=workspace,
        )
        security_summary = security_report.get("summary", {})
        security_fail = int(security_summary.get("fail", 0))
        security_warn = int(security_summary.get("warn", 0))
        add(
            "Security baseline audit",
            "pass"
            if security_fail == 0 and security_warn == 0
            else ("fail" if security_fail > 0 else "warn"),
            f"pass={security_summary.get('pass', 0)}, warn={security_warn}, fail={security_fail}",
            ""
            if security_fail == 0 and security_warn == 0
            else "Run: g-agent security-fix --apply",
        )
    except Exception as e:
        add(
            "Security baseline audit",
            "warn",
            f"Unable to inspect ({type(e).__name__}: {e})",
            "Run: g-agent security-audit --json",
        )

    model = config.agents.defaults.model
    route = config.resolve_model_route(model)
    model_key = route.api_key
    if not model_key and route.provider not in {"vllm", "bedrock"}:
        model_key = config.get_api_key(model)
    is_bedrock = route.provider == "bedrock" or model.startswith("bedrock/")
    if is_bedrock or model_key:
        provider_detail = (
            f"mode={route.mode}, provider={route.provider}, "
            f"base={route.api_base or 'none'}, fallback={len(route.fallback_models)}"
        )
        add("Model routing", "pass", f"model={route.model} ({provider_detail})")
    else:
        add(
            "Model routing",
            "fail",
            f"model={route.model} (mode={route.mode}, provider={route.provider}, no API key)",
            _missing_api_key_fix(route.provider, config_path),
        )

    add(
        "Reasoning reflection",
        "pass" if config.agents.defaults.enable_reflection else "warn",
        f"enableReflection={str(config.agents.defaults.enable_reflection).lower()}",
        ""
        if config.agents.defaults.enable_reflection
        else "Set agents.defaults.enableReflection=true",
    )
    add(
        "Session summaries",
        "pass" if config.agents.defaults.summary_interval >= 2 else "warn",
        f"summaryInterval={config.agents.defaults.summary_interval}",
        ""
        if config.agents.defaults.summary_interval >= 2
        else "Set agents.defaults.summaryInterval to >= 2",
    )

    if config.integrations.slack.webhook_url:
        add("Slack integration", "pass", "webhook configured")
    else:
        add(
            "Slack integration",
            "warn",
            "webhook not configured",
            "Set integrations.slack.webhookUrl or env G_AGENT_SLACK_WEBHOOK_URL",
        )

    if config.integrations.smtp.host:
        add(
            "SMTP integration",
            "pass",
            f"{config.integrations.smtp.host}:{config.integrations.smtp.port}",
        )
    else:
        add(
            "SMTP integration",
            "warn",
            "SMTP not configured",
            "Set integrations.smtp.* or env G_AGENT_SMTP_* values",
        )

    google_cfg = config.integrations.google
    has_google_token = bool(google_cfg.access_token)
    has_google_refresh = bool(
        google_cfg.client_id and google_cfg.client_secret and google_cfg.refresh_token
    )
    if has_google_token or has_google_refresh:
        mode = "access token" if has_google_token else "refresh token flow"
        add("Google Workspace", "pass", mode)
    else:
        add(
            "Google Workspace",
            "warn",
            "not configured",
            "Set client credentials, then run: g-agent google auth-url / g-agent google exchange",
        )

    if config.tools.browser.allow_domains:
        add(
            "Browser allowlist",
            "pass",
            ", ".join(config.tools.browser.allow_domains),
        )
    else:
        add(
            "Browser allowlist",
            "warn",
            "empty (all domains allowed)",
            "Set tools.browser.allowDomains for tighter browsing control",
        )
    if config.tools.browser.deny_domains:
        add(
            "Browser denylist",
            "pass",
            ", ".join(config.tools.browser.deny_domains),
        )
    else:
        add(
            "Browser denylist",
            "warn",
            "empty",
            "Optional: set tools.browser.denyDomains for known risky domains",
        )
    add(
        "Tool approval mode",
        "pass" if config.tools.approval_mode in {"off", "confirm"} else "warn",
        config.tools.approval_mode,
        ""
        if config.tools.approval_mode in {"off", "confirm"}
        else "Use tools.approvalMode = off|confirm",
    )
    add(
        "Tool policy rules",
        "pass" if config.tools.policy else "warn",
        f"{len(config.tools.policy)} rule(s)",
        "" if config.tools.policy else 'Set tools.policy (e.g. {"exec":"ask","send_email":"deny"})',
    )
    scoped_policy_count = sum(1 for key in config.tools.policy if ":" in key)
    add(
        "Scoped policy rules",
        "pass" if scoped_policy_count > 0 else "warn",
        f"{scoped_policy_count} scoped rule(s)",
        ""
        if scoped_policy_count > 0
        else "Use `g-agent policy apply ... --channel ... --sender ...` for guest boundaries",
    )

    try:
        from g_agent.cron.service import CronService

        proactive_names = {"daily-digest", "weekly-lessons-distill", "calendar-watch"}
        cron_store_path = get_data_dir() / "cron" / "jobs.json"
        cron_service = CronService(cron_store_path)
        jobs = cron_service.list_jobs(include_disabled=True)
        proactive_count = sum(1 for job in jobs if job.name in proactive_names)
        add(
            "Proactive jobs",
            "pass" if proactive_count >= 1 else "warn",
            f"{proactive_count} configured",
            "" if proactive_count >= 1 else "Run: g-agent proactive-enable",
        )
    except Exception as e:
        add(
            "Proactive jobs",
            "warn",
            f"Unable to inspect ({type(e).__name__}: {e})",
            "Run: g-agent proactive-enable",
        )

    quiet_cfg = config.proactive.quiet_hours
    quiet_ok = bool(quiet_cfg.start and quiet_cfg.end)
    add(
        "Quiet hours config",
        "pass" if quiet_ok else "warn",
        (
            f"enabled={str(quiet_cfg.enabled).lower()}, "
            f"{quiet_cfg.start}-{quiet_cfg.end}, tz={quiet_cfg.timezone}"
        ),
        "" if quiet_ok else "Set proactive.quietHours.start/end (HH:MM)",
    )

    calendar_dir = workspace / "calendar"
    add(
        "Calendar integration",
        "pass" if calendar_dir.exists() else "warn",
        str(calendar_dir),
        "" if calendar_dir.exists() else "Will be created on first create_calendar_event tool call",
    )

    memory_file = workspace / "memory" / "MEMORY.md"
    facts_file = workspace / "memory" / "FACTS.md"
    lessons_file = workspace / "memory" / "LESSONS.md"
    profile_file = workspace / "memory" / "PROFILE.md"
    relationships_file = workspace / "memory" / "RELATIONSHIPS.md"
    projects_file = workspace / "memory" / "PROJECTS.md"
    today_file = workspace / "memory" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    add(
        "Memory file",
        "pass" if memory_file.exists() else "warn",
        str(memory_file),
        ""
        if memory_file.exists()
        else f"Run: mkdir -p {workspace / 'memory'} && printf '# Long-term Memory\\n' > {memory_file}",
    )
    add(
        "Fact index",
        "pass" if facts_file.exists() else "warn",
        str(facts_file),
        ""
        if facts_file.exists()
        else "Create by using remember tool once (or run g-agent onboard)",
    )
    add(
        "Profile memory",
        "pass" if profile_file.exists() else "warn",
        str(profile_file),
        ""
        if profile_file.exists()
        else "Create with: g-agent onboard (or create memory/PROFILE.md)",
    )
    add(
        "Relationships memory",
        "pass" if relationships_file.exists() else "warn",
        str(relationships_file),
        ""
        if relationships_file.exists()
        else "Create with: g-agent onboard (or create memory/RELATIONSHIPS.md)",
    )
    add(
        "Projects memory",
        "pass" if projects_file.exists() else "warn",
        str(projects_file),
        ""
        if projects_file.exists()
        else "Create with: g-agent onboard (or create memory/PROJECTS.md)",
    )
    add(
        "Today memory note",
        "pass" if today_file.exists() else "warn",
        str(today_file),
        "" if today_file.exists() else "Create by chatting once (or write file manually)",
    )
    add(
        "Lessons memory",
        "pass" if lessons_file.exists() else "warn",
        str(lessons_file),
        "" if lessons_file.exists() else 'Create with: g-agent feedback "<lesson>"',
    )
    try:
        from g_agent.agent.memory import MemoryStore

        memory_store = MemoryStore(workspace)
        summary_drifts = memory_store.detect_summary_fact_drift(limit=50)
        add(
            "Memory summary drift",
            "pass" if not summary_drifts else "warn",
            f"{len(summary_drifts)} issue(s)",
            "" if not summary_drifts else "Review with: g-agent memory-audit",
        )
        cross_scope_conflicts = memory_store.detect_cross_scope_fact_conflicts(limit=50)
        add(
            "Memory cross-scope conflicts",
            "pass" if not cross_scope_conflicts else "warn",
            f"{len(cross_scope_conflicts)} key(s)",
            "" if not cross_scope_conflicts else "Review with: g-agent memory-audit --json",
        )
    except Exception as e:
        add(
            "Memory drift/conflicts",
            "warn",
            f"Unable to inspect ({type(e).__name__}: {e})",
            "Run: g-agent memory-audit --json",
        )

    metrics_file = workspace / "state" / "metrics" / "events.jsonl"
    if metrics_file.exists():
        try:
            from g_agent.observability.metrics import MetricsStore

            metrics_store = MetricsStore(metrics_file)
            metrics_snapshot = metrics_store.snapshot(hours=24)
            metrics_alerts = metrics_store.alert_compact(hours=24, snapshot=metrics_snapshot)
            add(
                "Observability metrics",
                "pass",
                f"{metrics_file} ({metrics_snapshot['totals']['events']} events /24h)",
            )
            add(
                "Observability alerts (24h)",
                "pass" if metrics_alerts["overall"] == "ok" else "warn",
                metrics_alerts["brief"],
                ""
                if metrics_alerts["overall"] == "ok"
                else "Inspect with: g-agent metrics --hours 24",
            )
        except Exception as e:
            add(
                "Observability metrics",
                "warn",
                f"{metrics_file} (read failed: {type(e).__name__})",
                "Run: g-agent metrics --json",
            )
    else:
        add(
            "Observability metrics",
            "warn",
            str(metrics_file),
            "Metrics file appears after first tool/LLM activity",
        )

    if config.providers.vllm.api_base:
        url = f"{config.providers.vllm.api_base.rstrip('/')}/models"
        headers = {}
        if config.providers.vllm.api_key:
            headers["Authorization"] = f"Bearer {config.providers.vllm.api_key}"
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url, headers=headers)
            if response.status_code == 200:
                count = len(response.json().get("data", []))
                add("vLLM /models", "pass", f"{url} ({count} models)")
            else:
                add(
                    "vLLM /models",
                    "fail",
                    f"{url} (HTTP {response.status_code})",
                    f"Test manually: curl -sS {url} -H 'Authorization: Bearer <api-key>'",
                )
        except Exception as e:
            add(
                "vLLM /models",
                "fail",
                f"{url} ({type(e).__name__}: {e})",
                "Start your local proxy/server and ensure apiBase points to it",
            )
    else:
        add(
            "vLLM /models",
            "warn",
            "providers.vllm.apiBase not configured",
            f"Set providers.vllm.apiBase in {config_path}",
        )

    tg = config.channels.telegram
    if tg.enabled:
        if not tg.token:
            add(
                "Telegram bot token",
                "fail",
                "telegram enabled but token empty",
                f"Set channels.telegram.token in {config_path}",
            )
        elif not network:
            add("Telegram API", "warn", "skipped (--no-network)", "Run again with --network")
        else:
            url = f"https://api.telegram.org/bot{tg.token}/getMe"
            client_kwargs = {"timeout": timeout}
            if tg.proxy:
                client_kwargs["proxy"] = tg.proxy
            try:
                with httpx.Client(**client_kwargs) as client:
                    response = client.get(url)
                if response.status_code == 200 and response.json().get("ok"):
                    username = response.json().get("result", {}).get("username", "unknown")
                    add("Telegram API", "pass", f"@{username}")
                else:
                    add(
                        "Telegram API",
                        "fail",
                        f"HTTP {response.status_code}",
                        "Verify token: curl -sS https://api.telegram.org/bot<TOKEN>/getMe",
                    )
            except TypeError:
                try:
                    with httpx.Client(timeout=timeout) as client:
                        response = client.get(url)
                    if response.status_code == 200 and response.json().get("ok"):
                        username = response.json().get("result", {}).get("username", "unknown")
                        add("Telegram API", "pass", f"@{username}")
                    else:
                        add(
                            "Telegram API",
                            "fail",
                            f"HTTP {response.status_code}",
                            "Verify token and network route to api.telegram.org:443",
                        )
                except Exception as e:
                    add(
                        "Telegram API",
                        "fail",
                        f"{type(e).__name__}: {e}",
                        "Check internet/proxy and token validity",
                    )
            except Exception as e:
                add(
                    "Telegram API",
                    "fail",
                    f"{type(e).__name__}: {e}",
                    "Check internet/proxy and token validity",
                )
    else:
        add(
            "Telegram channel",
            "warn",
            "disabled",
            "Enable channels.telegram.enabled=true and set allowFrom",
        )

    wa = config.channels.whatsapp
    if wa.enabled:
        try:
            parsed = urlparse(wa.bridge_url)
            if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
                raise ValueError("bridgeUrl must be a valid ws:// or wss:// URL")

            default_port = 443 if parsed.scheme == "wss" else 80
            port = parsed.port or default_port
            with socket.create_connection((parsed.hostname, port), timeout=timeout):
                pass
            add("WhatsApp bridge", "pass", wa.bridge_url)
        except Exception as e:
            add(
                "WhatsApp bridge",
                "fail",
                f"{wa.bridge_url} ({type(e).__name__}: {e})",
                "Start bridge with: g-agent channels login (keep it running)",
            )
    else:
        add(
            "WhatsApp channel",
            "warn",
            "disabled",
            "Enable channels.whatsapp.enabled=true and set allowFrom",
        )

    brave_key = config.tools.web.search.api_key
    if brave_key:
        if not network:
            add(
                "Brave Search API",
                "warn",
                "key set, skipped (--no-network)",
                "Run again with --network",
            )
        else:
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": "g-agent health check", "count": 1},
                        headers={
                            "Accept": "application/json",
                            "X-Subscription-Token": brave_key,
                        },
                    )
                if response.status_code == 200:
                    add("Brave Search API", "pass", "search endpoint reachable")
                else:
                    add(
                        "Brave Search API",
                        "fail",
                        f"HTTP {response.status_code}",
                        "Verify key at Brave dashboard and retry",
                    )
            except Exception as e:
                add(
                    "Brave Search API",
                    "fail",
                    f"{type(e).__name__}: {e}",
                    "Check internet access and Brave API key",
                )
    else:
        add(
            "Brave Search API",
            "warn",
            "tools.web.search.apiKey not set",
            f"Set tools.web.search.apiKey in {config_path}",
        )

    if has_google_token or has_google_refresh:
        if not network:
            add("Google API network", "warn", "skipped (--no-network)", "Run again with --network")
        else:
            try:
                from g_agent.agent.tools.google_workspace import GoogleWorkspaceClient

                google_client = GoogleWorkspaceClient(
                    client_id=google_cfg.client_id,
                    client_secret=google_cfg.client_secret,
                    refresh_token=google_cfg.refresh_token,
                    access_token=google_cfg.access_token,
                    calendar_id=google_cfg.calendar_id,
                )
                ok, payload = asyncio.run(
                    google_client.request(
                        "GET",
                        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    )
                )
                if ok:
                    mode = "refresh-token flow" if has_google_refresh else "access token"
                    add("Google API network", "pass", f"reachable ({mode})")
                else:
                    detail = payload.get("error", payload) if isinstance(payload, dict) else payload
                    add(
                        "Google API network",
                        "fail",
                        str(detail),
                        "Verify Google token/refresh credentials",
                    )
            except Exception as e:
                add(
                    "Google API network",
                    "fail",
                    f"{type(e).__name__}: {e}",
                    "Check internet access and Google credentials",
                )

    table = Table(title=f"{__brand__} Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="yellow")
    table.add_column("Fix Hint", style="magenta")
    for check, level, detail, fix in results:
        table.add_row(check, _mark(level), detail, fix or "-")
    console.print(table)

    fail_count = sum(1 for _, level, _, _ in results if level == "fail")
    warn_count = sum(1 for _, level, _, _ in results if level == "warn")
    pass_count = len(results) - fail_count - warn_count
    console.print(
        f"Summary: [green]{pass_count} pass[/green], [yellow]{warn_count} warn[/yellow], [red]{fail_count} fail[/red]"
    )

    if strict and fail_count > 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
