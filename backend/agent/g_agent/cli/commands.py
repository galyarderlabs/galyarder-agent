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

from g_agent import __version__, __logo__, __brand__

app = typer.Typer(
    name="g-agent",
    help=f"{__logo__} {__brand__} - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} {__brand__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """g-agent - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize g-agent configuration and workspace."""
    from g_agent.config.loader import get_config_path, save_config
    from g_agent.config.schema import Config
    from g_agent.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()
    
    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} {__brand__} is ready!")
    console.print("\nNext steps:")
    console.print(f"  1. Add your API key to [cyan]{config_path}[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]g-agent agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See the README Chat Apps section.[/dim]")




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
    
    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
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
):
    """Start the g-agent gateway."""
    from g_agent.config.loader import load_config, get_config_path, get_data_dir
    from g_agent.bus.queue import MessageBus
    from g_agent.bus.events import OutboundMessage
    from g_agent.providers.litellm_provider import LiteLLMProvider
    from g_agent.agent.loop import AgentLoop
    from g_agent.agent.tools.google_workspace import GoogleWorkspaceClient
    from g_agent.channels.manager import ChannelManager
    from g_agent.cron.service import CronService
    from g_agent.cron.types import CronJob
    from g_agent.heartbeat.service import HeartbeatService
    from g_agent.observability.metrics import MetricsStore
    from g_agent.proactive.engine import (
        ProactiveStateStore,
        compute_due_calendar_reminders,
        is_quiet_hours_now,
        resolve_timezone,
    )
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    console.print(f"{__logo__} Starting {__brand__} gateway on port {port}...")
    
    config = load_config()
    
    # Create components
    bus = MessageBus()
    
    # Create provider (supports OpenRouter, Anthropic, OpenAI, Bedrock)
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    model = config.agents.defaults.model
    is_bedrock = model.startswith("bedrock/")

    if not api_key and not is_bedrock:
        console.print("[red]Error: No API key configured.[/red]")
        console.print(f"Set one in {get_config_path()} under providers.openrouter.apiKey")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
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
                await bus.publish_outbound(OutboundMessage(
                    channel=job.payload.channel or "cli",
                    chat_id=job.payload.to,
                    content=response or "",
                    metadata={
                        "idempotency_key": (
                            f"cron:{job.id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
                        )
                    },
                ))
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
        enabled=True
    )
    
    # Create channel manager
    channels = ChannelManager(config, bus)
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")
    
    console.print("[green]✓[/green] Heartbeat: every 30m")
    
    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
    
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
    from g_agent.config.loader import load_config
    from g_agent.bus.queue import MessageBus
    from g_agent.providers.litellm_provider import LiteLLMProvider
    from g_agent.agent.loop import AgentLoop
    
    config = load_config()
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    model = config.agents.defaults.model
    is_bedrock = model.startswith("bedrock/")

    if not api_key and not is_bedrock:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)

    bus = MessageBus()
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
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
    )
    
    if message:
        # Single message mode
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            console.print(f"\n{__logo__} {response}")
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        console.print(f"{__logo__} Interactive mode (Ctrl+C to exit)\n")
        
        async def run_interactive():
            while True:
                try:
                    user_input = console.input("[bold blue]You:[/bold blue] ")
                    if not user_input.strip():
                        continue
                    
                    response = await agent_loop.process_direct(user_input, session_id)
                    console.print(f"\n{__logo__} {response}\n")
                except KeyboardInterrupt:
                    console.print("\nGoodbye!")
                    break
        
        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


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
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )
    
    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    console.print(table)


def _get_bridge_dir(force_rebuild: bool = False) -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess
    from g_agent.config.loader import get_data_dir
    
    # User's bridge location
    user_bridge = get_data_dir() / "bridge"
    
    # Check if already built
    if not force_rebuild and (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
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
        
        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login(
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Force rebuild local WhatsApp bridge before login",
    )
):
    """Link device via QR code."""
    import subprocess
    
    bridge_dir = _get_bridge_dir(force_rebuild=rebuild)
    
    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    console.print("[dim]Tip: keep this process running after connected.[/dim]")
    console.print("[dim]Run `g-agent gateway` in another terminal.[/dim]\n")
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Google Workspace Commands
# ============================================================================


google_app = typer.Typer(help="Manage Google Workspace integration")
app.add_typer(google_app, name="google")


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
    console.print(f"- Client credentials: {'[green]✓[/green]' if has_client else '[yellow]missing[/yellow]'}")
    console.print(f"- Refresh token: {'[green]✓[/green]' if has_refresh else '[yellow]missing[/yellow]'}")
    console.print(f"- Access token: {'[green]✓[/green]' if has_access else '[dim]not cached[/dim]'}")
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

    has_client = bool(config.integrations.google.client_id and config.integrations.google.client_secret)
    if has_client:
        console.print("[green]✓[/green] Google client credentials saved.")
    else:
        console.print("[yellow]Saved, but client credentials are still incomplete.[/yellow]")


@google_app.command("auth-url")
def google_auth_url(
    redirect_uri: str = typer.Option("http://localhost", "--redirect-uri", help="OAuth redirect URI"),
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
    from g_agent.config.loader import load_config, get_config_path

    config = load_config()
    google_cfg = config.integrations.google
    if not google_cfg.client_id:
        console.print("[red]Google client_id missing.[/red]")
        console.print(f"Set integrations.google.clientId in {get_config_path()}")
        raise typer.Exit(1)

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
    code: str = typer.Option(..., "--code", prompt=True, hide_input=False, help="OAuth authorization code"),
    redirect_uri: str = typer.Option("http://localhost", "--redirect-uri", help="OAuth redirect URI"),
):
    """Exchange OAuth code and save Google tokens into config."""
    import httpx
    from g_agent.config.loader import load_config, save_config

    config = load_config()
    google_cfg = config.integrations.google
    if not (google_cfg.client_id and google_cfg.client_secret):
        console.print("[red]Google client_id/client_secret missing.[/red]")
        console.print("Set integrations.google.clientId and integrations.google.clientSecret first.")
        raise typer.Exit(1)

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
        console.print(f"[red]Token exchange failed: {e}[/red]")
        raise typer.Exit(1)

    if response.status_code != 200:
        console.print(f"[red]Token exchange failed (HTTP {response.status_code}).[/red]")
        try:
            console.print(response.json())
        except Exception:
            console.print(response.text[:500])
        raise typer.Exit(1)

    data = response.json()
    access_token = data.get("access_token", "")
    refresh_token = data.get("refresh_token")
    if not access_token:
        console.print("[red]No access_token returned from Google.[/red]")
        raise typer.Exit(1)

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

    has_refresh_creds = bool(google_cfg.client_id and google_cfg.client_secret and google_cfg.refresh_token)
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
            console.print(f"[red]{refresh_error}[/red]")
            console.print("Run: g-agent google auth-url, then g-agent google exchange --code ...")
            raise typer.Exit(1)

    if not access_token:
        console.print("[red]Google auth not configured.[/red]")
        console.print("Run: g-agent google configure, then g-agent google auth-url + exchange")
        raise typer.Exit(1)

    try:
        with httpx.Client(timeout=timeout) as client:
            profile_resp = client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except Exception as e:
        console.print(f"[red]Google API request failed: {e}[/red]")
        raise typer.Exit(1)

    if profile_resp.status_code == 401 and has_refresh_creds:
        refreshed, refreshed_token, refresh_error = refresh_access_token()
        if not refreshed:
            console.print(f"[red]{refresh_error}[/red]")
            raise typer.Exit(1)
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
            console.print(f"[red]Google API request failed: {e}[/red]")
            raise typer.Exit(1)

    if profile_resp.status_code != 200:
        console.print(f"[red]Google verify failed (HTTP {profile_resp.status_code}).[/red]")
        try:
            console.print(profile_resp.json())
        except Exception:
            console.print(profile_resp.text)
        raise typer.Exit(1)

    profile = profile_resp.json()
    email_address = profile.get("emailAddress", "(unknown)")
    total_messages = profile.get("messagesTotal", "n/a")
    console.print(f"[green]✓[/green] Google auth verified for {email_address} (messages: {total_messages})")


@google_app.command("clear")
def google_clear(clear_client: bool = typer.Option(False, "--clear-client", help="Also clear client_id/client_secret")):
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
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
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
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from g_agent.config.loader import get_data_dir
    from g_agent.cron.service import CronService
    from g_agent.cron.types import CronSchedule
    
    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)
    
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
        console.print(f"[red]Job {job_id} not found[/red]")


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
        console.print(f"[red]Job {job_id} not found[/red]")


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
        console.print(f"[red]Failed to run job {job_id}[/red]")


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
    session_id: str = typer.Option("cli:digest", "--session", "-s", help="Session ID for digest generation"),
):
    """Generate a daily personal digest via the agent."""
    from g_agent.config.loader import load_config
    from g_agent.bus.queue import MessageBus
    from g_agent.providers.litellm_provider import LiteLLMProvider
    from g_agent.agent.loop import AgentLoop

    config = load_config()
    api_key = config.get_api_key()
    model = config.agents.defaults.model
    is_bedrock = model.startswith("bedrock/")
    if not api_key and not is_bedrock:
        console.print("[red]Error: No API key configured.[/red]")
        raise typer.Exit(1)

    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=config.get_api_base(),
        default_model=model,
    )
    bus = MessageBus()
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=model,
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
    weekly_cron: str = typer.Option("0 9 * * 1", "--weekly-cron", help="Cron for weekly lessons distillation"),
    include_calendar_watch: bool = typer.Option(True, "--calendar-watch/--no-calendar-watch", help="Enable calendar lookahead reminders"),
    calendar_every: int | None = typer.Option(None, "--calendar-every", help="Calendar watch interval in minutes"),
    calendar_horizon: int | None = typer.Option(None, "--calendar-horizon", help="Calendar lookahead window in minutes"),
    calendar_leads: str | None = typer.Option(None, "--calendar-leads", help="Lead reminders in minutes, comma-separated (e.g. 30,10)"),
    deliver: bool = typer.Option(False, "--deliver", help="Deliver output to a channel target"),
    channel: str = typer.Option(None, "--channel", help="Target channel for delivery (telegram/whatsapp)"),
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
    preset: str = typer.Argument(..., help="Preset name: personal_full|guest_limited|guest_readonly"),
    channel: str = typer.Option("", "--channel", help="Optional channel scope (telegram/whatsapp/...)"),
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
    console.print(
        f"Rules: {result['applied_rules']} applied ({result['changed_rules']} changed)"
    )
    console.print(f"Approval mode: {config.tools.approval_mode}")
    console.print(
        "Security (restrictToWorkspace): "
        + ("[green]enabled[/green]" if config.tools.restrict_to_workspace else "[yellow]disabled[/yellow]")
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
    from g_agent.config.loader import load_config
    from g_agent.agent.memory import MemoryStore

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
):
    """Show runtime observability metrics snapshot."""
    from g_agent.config.loader import load_config
    from g_agent.observability.metrics import MetricsStore

    config = load_config()
    store = MetricsStore(config.workspace_path / "state" / "metrics" / "events.jsonl")
    snapshot = store.snapshot(hours=hours)

    export_result: dict[str, Any] | None = None
    if export.strip():
        export_result = store.export_snapshot(
            Path(export.strip()),
            hours=hours,
            output_format=export_format,
        )
        if not export_result.get("ok"):
            console.print(f"[red]Metrics export failed:[/red] {export_result.get('error', 'unknown')}")
            raise typer.Exit(1)

    if dashboard_json:
        console.print(
            json.dumps(
                store.dashboard_summary(hours=hours),
                indent=2,
                ensure_ascii=False,
            )
        )
    elif as_json:
        console.print(json.dumps(snapshot, indent=2, ensure_ascii=False))
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
        top_tools = tools.get("top_tools", [])
        if top_tools:
            console.print("Top tools:")
            for item in top_tools[:8]:
                console.print(f"  - {item['tool']}: {item['calls']} call(s), {item['errors']} error(s)")

    if export_result:
        console.print(
            f"[green]✓[/green] Metrics exported: {export_result['path']} "
            f"({export_result['format']}, {export_result['bytes']} bytes)"
        )


@app.command()
def status():
    """Show g-agent status."""
    from datetime import datetime
    from g_agent.config.loader import load_config, get_config_path, get_data_dir

    data_dir = get_data_dir()
    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} {__brand__} Status\n")

    console.print(f"Data dir: {data_dir} {'[green]✓[/green]' if data_dir.exists() else '[red]✗[/red]'}")
    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        console.print(f"Model: {config.agents.defaults.model}")
        
        # Check API keys
        has_openrouter = bool(config.providers.openrouter.api_key)
        has_anthropic = bool(config.providers.anthropic.api_key)
        has_openai = bool(config.providers.openai.api_key)
        has_gemini = bool(config.providers.gemini.api_key)
        has_vllm = bool(config.providers.vllm.api_base)
        has_brave = bool(config.tools.web.search.api_key)
        
        console.print(f"OpenRouter API: {'[green]✓[/green]' if has_openrouter else '[dim]not set[/dim]'}")
        console.print(f"Anthropic API: {'[green]✓[/green]' if has_anthropic else '[dim]not set[/dim]'}")
        console.print(f"OpenAI API: {'[green]✓[/green]' if has_openai else '[dim]not set[/dim]'}")
        console.print(f"Gemini API: {'[green]✓[/green]' if has_gemini else '[dim]not set[/dim]'}")
        vllm_status = f"[green]✓ {config.providers.vllm.api_base}[/green]" if has_vllm else "[dim]not set[/dim]"
        console.print(f"vLLM/Local: {vllm_status}")
        console.print(f"Brave Search API: {'[green]✓[/green]' if has_brave else '[dim]not set[/dim]'}")
        console.print(f"Security (restrictToWorkspace): {'[green]✓ enabled[/green]' if config.tools.restrict_to_workspace else '[yellow]disabled[/yellow]'}")
        console.print(f"Reasoning reflection: {'[green]✓ enabled[/green]' if config.agents.defaults.enable_reflection else '[dim]disabled[/dim]'}")
        console.print(f"Session summary interval: {config.agents.defaults.summary_interval} turns")

        tg = config.channels.telegram
        wa = config.channels.whatsapp
        console.print(f"Telegram channel: {'[green]✓ enabled[/green]' if tg.enabled else '[dim]disabled[/dim]'} (allowFrom: {len(tg.allow_from)})")
        console.print(f"WhatsApp channel: {'[green]✓ enabled[/green]' if wa.enabled else '[dim]disabled[/dim]'} (allowFrom: {len(wa.allow_from)})")

        console.print(f"Slack webhook: {'[green]✓[/green]' if config.integrations.slack.webhook_url else '[dim]not set[/dim]'}")
        has_smtp = bool(config.integrations.smtp.host)
        console.print(f"SMTP integration: {'[green]✓[/green]' if has_smtp else '[dim]not set[/dim]'}")
        has_google = bool(
            config.integrations.google.access_token
            or (
                config.integrations.google.client_id
                and config.integrations.google.client_secret
                and config.integrations.google.refresh_token
            )
        )
        console.print(f"Google Workspace: {'[green]✓[/green]' if has_google else '[dim]not set[/dim]'}")
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
            if quiet_cfg.enabled else "disabled"
        )
        console.print(f"Quiet hours: {quiet_desc}")
        try:
            from g_agent.cron.service import CronService
            proactive_names = {"daily-digest", "weekly-lessons-distill", "calendar-watch"}
            cron_service = CronService(get_data_dir() / "cron" / "jobs.json")
            proactive_count = sum(
                1 for job in cron_service.list_jobs(include_disabled=True) if job.name in proactive_names
            )
            console.print(f"Proactive jobs: {proactive_count}")
        except Exception:
            console.print("Proactive jobs: [dim]unknown[/dim]")
        try:
            from g_agent.observability.metrics import MetricsStore

            metrics_store = MetricsStore(workspace / "state" / "metrics" / "events.jsonl")
            metrics_snapshot = metrics_store.snapshot(hours=24)
            console.print(
                "Metrics (24h): "
                f"events={metrics_snapshot['totals']['events']}, "
                f"llm={metrics_snapshot['llm']['calls']}, "
                f"tools={metrics_snapshot['tools']['calls']}, "
                f"recall-hit={metrics_snapshot['recall']['hit_rate']}%"
            )
        except Exception:
            console.print("Metrics (24h): [dim]unknown[/dim]")

        memory_file = workspace / "memory" / "MEMORY.md"
        facts_file = workspace / "memory" / "FACTS.md"
        lessons_file = workspace / "memory" / "LESSONS.md"
        profile_file = workspace / "memory" / "PROFILE.md"
        relationships_file = workspace / "memory" / "RELATIONSHIPS.md"
        projects_file = workspace / "memory" / "PROJECTS.md"
        today_file = workspace / "memory" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
        console.print(f"Long-term memory: {'[green]✓[/green]' if memory_file.exists() else '[yellow]missing[/yellow]'} ({memory_file})")
        console.print(f"Fact index memory: {'[green]✓[/green]' if facts_file.exists() else '[dim]not created yet[/dim]'} ({facts_file})")
        console.print(f"Lessons memory: {'[green]✓[/green]' if lessons_file.exists() else '[dim]not created yet[/dim]'} ({lessons_file})")
        console.print(f"Profile memory: {'[green]✓[/green]' if profile_file.exists() else '[dim]not created yet[/dim]'} ({profile_file})")
        console.print(f"Relationships memory: {'[green]✓[/green]' if relationships_file.exists() else '[dim]not created yet[/dim]'} ({relationships_file})")
        console.print(f"Projects memory: {'[green]✓[/green]' if projects_file.exists() else '[dim]not created yet[/dim]'} ({projects_file})")
        console.print(f"Today memory note: {'[green]✓[/green]' if today_file.exists() else '[dim]not created yet[/dim]'}")


@app.command()
def doctor(
    network: bool = typer.Option(True, "--network/--no-network", help="Run external network checks"),
    timeout: float = typer.Option(6.0, "--timeout", help="Per-check timeout in seconds"),
    strict: bool = typer.Option(False, "--strict", help="Exit with code 1 if any check fails"),
):
    """Run diagnostics for model, channels, memory, and tool configuration."""
    import httpx
    import socket
    from datetime import datetime
    from urllib.parse import urlparse
    from g_agent.config.loader import load_config, get_config_path, get_data_dir

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
        "" if config.tools.restrict_to_workspace else f"Set true in {config_path} (tools.restrictToWorkspace)",
    )

    model = config.agents.defaults.model
    model_key = config.get_api_key(model)
    model_base = config.get_api_base(model)
    is_bedrock = model.startswith("bedrock/")
    if is_bedrock or model_key:
        provider_detail = "bedrock" if is_bedrock else "api key configured"
        if model_base:
            provider_detail += f", base={model_base}"
        add("Model routing", "pass", f"model={model} ({provider_detail})")
    else:
        add(
            "Model routing",
            "fail",
            f"model={model} (no API key)",
            f"Set provider API key in {config_path} (or providers.vllm.apiKey for local proxy)",
        )

    add(
        "Reasoning reflection",
        "pass" if config.agents.defaults.enable_reflection else "warn",
        f"enableReflection={str(config.agents.defaults.enable_reflection).lower()}",
        "" if config.agents.defaults.enable_reflection else "Set agents.defaults.enableReflection=true",
    )
    add(
        "Session summaries",
        "pass" if config.agents.defaults.summary_interval >= 2 else "warn",
        f"summaryInterval={config.agents.defaults.summary_interval}",
        "" if config.agents.defaults.summary_interval >= 2 else "Set agents.defaults.summaryInterval to >= 2",
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
        add("SMTP integration", "pass", f"{config.integrations.smtp.host}:{config.integrations.smtp.port}")
    else:
        add(
            "SMTP integration",
            "warn",
            "SMTP not configured",
            "Set integrations.smtp.* or env G_AGENT_SMTP_* values",
        )

    google_cfg = config.integrations.google
    has_google_token = bool(google_cfg.access_token)
    has_google_refresh = bool(google_cfg.client_id and google_cfg.client_secret and google_cfg.refresh_token)
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
        "" if config.tools.approval_mode in {"off", "confirm"} else "Use tools.approvalMode = off|confirm",
    )
    add(
        "Tool policy rules",
        "pass" if config.tools.policy else "warn",
        f"{len(config.tools.policy)} rule(s)",
        "" if config.tools.policy else "Set tools.policy (e.g. {\"exec\":\"ask\",\"send_email\":\"deny\"})",
    )
    scoped_policy_count = sum(1 for key in config.tools.policy if ":" in key)
    add(
        "Scoped policy rules",
        "pass" if scoped_policy_count > 0 else "warn",
        f"{scoped_policy_count} scoped rule(s)",
        "" if scoped_policy_count > 0 else "Use `g-agent policy apply ... --channel ... --sender ...` for guest boundaries",
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
        "" if memory_file.exists() else f"Run: mkdir -p {workspace / 'memory'} && printf '# Long-term Memory\\n' > {memory_file}",
    )
    add(
        "Fact index",
        "pass" if facts_file.exists() else "warn",
        str(facts_file),
        "" if facts_file.exists() else "Create by using remember tool once (or run g-agent onboard)",
    )
    add(
        "Profile memory",
        "pass" if profile_file.exists() else "warn",
        str(profile_file),
        "" if profile_file.exists() else "Create with: g-agent onboard (or create memory/PROFILE.md)",
    )
    add(
        "Relationships memory",
        "pass" if relationships_file.exists() else "warn",
        str(relationships_file),
        "" if relationships_file.exists() else "Create with: g-agent onboard (or create memory/RELATIONSHIPS.md)",
    )
    add(
        "Projects memory",
        "pass" if projects_file.exists() else "warn",
        str(projects_file),
        "" if projects_file.exists() else "Create with: g-agent onboard (or create memory/PROJECTS.md)",
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
        "" if lessons_file.exists() else "Create with: g-agent feedback \"<lesson>\"",
    )

    metrics_file = workspace / "state" / "metrics" / "events.jsonl"
    if metrics_file.exists():
        try:
            from g_agent.observability.metrics import MetricsStore

            metrics_snapshot = MetricsStore(metrics_file).snapshot(hours=24)
            add(
                "Observability metrics",
                "pass",
                f"{metrics_file} ({metrics_snapshot['totals']['events']} events /24h)",
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
            add("Brave Search API", "warn", "key set, skipped (--no-network)", "Run again with --network")
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
    console.print(f"Summary: [green]{pass_count} pass[/green], [yellow]{warn_count} warn[/yellow], [red]{fail_count} fail[/red]")

    if strict and fail_count > 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
