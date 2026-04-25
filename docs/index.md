---
template: home.html
title: Galyarder Agent
subtitle: Agentic digital identity for what should not disappear. Build characters with memory, values, and visual presence.
hide:
  - navigation
  - toc
---

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

1. [**Getting Started**](getting-started.md) — Rapid deployment guide.
2. [**Configuration**](configuration.md) — Dial in your providers and tools.
3. [**Channels**](channels.md) — Connect to the world.
4. [**Operations**](operations.md) — Master the agent loop.

## Architecture

![g-agent architecture](assets/architecture.webp)

<p class="gagent-note"><i>Execution path: channel input -> identity and memory context -> agent loop -> tools/scheduler -> response and learning loop.</i></p>
