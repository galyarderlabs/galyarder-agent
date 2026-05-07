# DESIGN.md — Galyarder Agent Design

## Status

This is the product-specific design guide for **Galyarder Agent**.

For Labs-level canon, read:

- [`docs/galyarder-labs/DESIGN.md`](./docs/galyarder-labs/DESIGN.md)
- [`docs/galyarder-labs/BRAND.md`](./docs/galyarder-labs/BRAND.md)

This file governs Agent docs, UI concepts, identity surfaces, memory/profile screens, visual presence, channel setup, and local runtime UX.

---

## Design Role

Galyarder Agent is the **Continuity Layer**.

It can feel more human and dreamlike than Ledger, HQ, or Framework, but it must remain controlled, local-first, and inspectable.

It should feel:

- personal,
- memorable,
- local-first,
- intimate but bounded,
- identity-rich,
- useful,
- technically trustworthy.

It should not feel:

- generic chatbot,
- toy companion,
- manipulative romance app,
- cloud-locked avatar app,
- fake consciousness product.

---

## Required Surfaces

Agent design must preserve:

- memory profile,
- local profile files,
- values,
- voice,
- visual identity,
- channel presence,
- scheduled jobs,
- recurring routines,
- continuity records,
- tool policy,
- workspace boundaries,
- approval states,
- media/selfie workflows.

---

## Visual System

Use Labs Dream layer for identity/character presentation:

- warmth,
- memory,
- visual continuity,
- human-scale atmosphere,
- soft threshold light.

Use Machine layer for runtime/admin/config:

- config clarity,
- logs,
- allowlists,
- paths,
- service status,
- channel state,
- security policy.

Agent should bridge Dream and Machine more than other products.

---

## Color Rules

Violet/gold may appear in identity moments, onboarding, profile, visual presence, and channel setup.

Runtime/config/security screens must use semantic status colors for:

- connected,
- disconnected,
- blocked,
- approval required,
- restricted,
- failed,
- scheduled,
- running.

Do not use brand colors to hide security state.

---

## Typography

Use clear sans-serif for docs and runtime UI.

Use mono only for:

- paths,
- commands,
- config keys,
- logs,
- IDs,
- model/provider names.

Identity/character presentation may use softer editorial display moments, but not inside dense config screens.

---

## Quality Gate

Before shipping Agent UI/docs visuals, verify:

- Galyarder Agent is not confused with Ledger G-Agents,
- memory and identity are visible,
- channel presence is visible,
- local control is clear,
- tool policy and safety boundaries are inspectable,
- emotional language does not imply fake immortality or human replacement,
- the product remains useful beyond chat bubbles.
