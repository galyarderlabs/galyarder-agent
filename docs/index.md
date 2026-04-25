<section class="gagent-cover">
  <img src="assets/header.webp" alt="Galyarder Agent interface preview">
  <div class="gagent-cover-copy">
    <p class="gagent-kicker">Galyarder Agent Docs</p>
    <h1>Agentic digital identity for what should not disappear.</h1>
    <p>
      Build yourself, someone you love, a companion, an operator, or an
      imagined person as an agentic character with memory, values, visual
      presence, tools, and continuity across WhatsApp, Telegram, Discord,
      Email, and CLI.
    </p>
    <div class="gagent-actions">
      <a href="getting-started/">Get started</a>
      <a href="persona/">Shape identity</a>
      <a href="operations/">Operate services</a>
    </div>
  </div>
</section>

## What You Get

<div class="gagent-grid">
  <a class="gagent-card" href="channels/">
    <strong>Presence</strong>
    <span>Give the same digital identity a home in WhatsApp, Telegram, Discord, Email, CLI, and future channel plugins.</span>
  </a>
  <a class="gagent-card" href="configuration/#provider-registry">
    <strong>Continuity</strong>
    <span>Carry memory, values, preferences, relationships, and projects across sessions instead of starting over.</span>
  </a>
  <a class="gagent-card" href="configuration/#visual-identity--selfies">
    <strong>Visual Identity</strong>
    <span>Generate contextual selfies and mirror shots through Hugging Face, Cloudflare, or OpenAI-compatible image proxies.</span>
  </a>
  <a class="gagent-card" href="operations/">
    <strong>Action</strong>
    <span>Let the character use scoped tools for files, shell, Gmail, Calendar, Drive, schedules, media, and workflow packs.</span>
  </a>
</div>

## Start Here

1. [Getting Started](getting-started.md)
2. [Configuration](configuration.md)
3. [Channels](channels.md)
4. [Operations](operations.md)
5. [Troubleshooting](troubleshooting.md)
6. [Security](security.md)

## Runtime Map

- Backend runtime: `backend/agent`
- Docs source: `docs/`
- Release notes: `docs/release-notes/`

## Architecture

![g-agent architecture](assets/architecture.webp)

<p class="gagent-note"><i>Execution path: channel input -> identity and memory context -> agent loop -> tools/scheduler -> response and learning loop.</i></p>
