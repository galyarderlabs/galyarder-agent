export const copy = {
  meta: {
    title: 'GalyarderAgent — Execution, Engineered.',
    description:
      'GalyarderAgent is a protocol-driven, memory-aware agent framework for sovereign automation. Join early access.',
    ogTitle: 'GalyarderAgent — Execution, Engineered.',
    ogDescription:
      'GalyarderAgent is a protocol-driven, memory-aware agent framework for sovereign automation. Join early access.',
  },
  nav: [
    { label: 'How', href: '#how' },
    { label: 'Modes', href: '#modes' },
    { label: 'Integrations', href: '#integrations' },
    { label: 'Features', href: '#features' },
    { label: 'Security', href: '#security' },
    { label: 'Models', href: '#models' },
    { label: 'FAQ', href: '#faq' },
    { label: 'Access', href: '#access' },
  ],
  hero: {
    title: 'Execution, Engineered.',
    subtitle:
      'GalyarderAgent is a modular AI execution framework. Protocol-driven, memory-aware, and built for sovereign automation—without the noise.',
    ctaPrimary: 'Join the Early Access',
    ctaSecondary: 'See How It Works',
    kicker: 'Not prompts. Protocols.',
  },
  problem: {
    lead: 'AI today talks more than it executes. Context leaks, prompt spaghetti, platform lock-ins, and zero auditability.',
    bullets: [
      'Chat-first tools with no protocols or guarantees.',
      'Black-box platforms—vendor lock, usage opacity, runaway costs.',
      'Shallow automations that break on edge cases and context shifts.',
      'No audit trail, no guardrails, no deterministic paths to done.',
    ],
    close: "This isn't a UX gap. It's an execution architecture failure.",
  },
  solution: {
    title: 'What GalyarderAgent Is',
    body: 'A disciplined agent runtime that turns objectives into protocols, protocols into plans, and plans into signed actions. Memory, tools, approvals, and logs—under your control.',
    outcomes: [
      'Protocol over prompt: structured execution, repeatable results.',
      'Memory with boundaries: context that is scoped, versioned, and auditable.',
      'Sovereign deployment: BYOK models, local-first option, zero mandatory cloud.',
    ],
  },
  how: {
    title: 'How It Works',
    steps: [
      {
        title: 'Define',
        body: 'State the objective and constraints. Select modes, permissions, and success criteria. The system compiles a protocol.',
      },
      {
        title: 'Compose',
        body: 'Attach tools (filesystem, repo, HTTP, finance adapters), load scoped memory, and schedule triggers—on-demand or recurring.',
      },
      {
        title: 'Execute',
        body: 'The agent plans, requests approvals where required, and performs signed actions. Every step is logged, revertible, and reviewable.',
      },
    ],
  },
  modes: {
    title: 'Execution Modes',
    body: 'Different problems demand different agents. Switch modes without rewriting your world.',
    items: [
      {
        name: 'Prime',
        desc: 'General execution with approvals on sensitive steps. Balanced speed and control.',
      },
      {
        name: 'Architekt',
        desc: 'System design and refactor planning. Produces specs, plans, and diffs before any change.',
      },
      {
        name: 'Oracle',
        desc: 'Analysis and insight generation. Synthesizes data, produces decision briefs with references.',
      },
      {
        name: 'Sentinel',
        desc: 'Monitoring and safeguards. Watches metrics, triggers playbooks, escalates with evidence.',
      },
    ],
    note: 'Modes can chain. A Sentinel can trigger Prime; Prime can request Architekt specs; Oracle can verify outcomes.',
  },
  integrations: {
    title: 'Integrated with the Stack',
    note: 'The agent sits at the center of the sovereign stack—automating without owning your data.',
    systems: [
      {
        name: 'GalyarderOS',
        desc: 'Run rituals, weekly reviews, and project playbooks as protocols—no tab circus.',
        link: 'https://galyarderos.app',
      },
      {
        name: 'GalyarderCode',
        desc: 'Repo-aware execution: generate scaffolds, refactor modules, open PRs with diffs and tests.',
        link: 'https://galyardercode.app',
      },
      {
        name: 'GalyarderWallet',
        desc: 'Treasury checks, airdrop filters, allocation proposals—human-in-the-loop by default.',
        link: 'https://galyarderwallet.app',
      },
      {
        name: 'GalyarderID',
        desc: 'Scoped permissions per protocol. Every action signed against your identity.',
        link: 'https://galyarderid.app',
      },
    ],
  },
  features: {
    title: 'Built for Discipline',
    items: [
      {
        name: 'Protocol DSL',
        desc: 'From prompts to procedures. Objectives, constraints, approvals, and exit criteria as code.',
        icon: 'Code2',
      },
      {
        name: 'Memory Graph',
        desc: 'Structured, scoped context with versioned snapshots. Reusable without bleed-through.',
        icon: 'Database',
      },
      {
        name: 'Tool Adapters',
        desc: 'Filesystem, Git, HTTP, docs, and finance adapters. Extend with your own safely.',
        icon: 'Plug',
      },
      {
        name: 'Model Router',
        desc: 'BYOK. Route tasks across Claude/GPT/Gemini or local models. Cost and privacy aware.',
        icon: 'Route',
      },
      {
        name: 'Safety & Audit',
        desc: 'Human-in-the-loop checkpoints, signed actions, immutable logs, and dry-run previews.',
        icon: 'Shield',
      },
      {
        name: 'Schedulers & Triggers',
        desc: 'Cron, webhooks, and event-based activation. Sentinel rules for proactive action.',
        icon: 'Clock',
      },
    ],
  },
  security: {
    title: 'Security Model',
    bullets: [
      'Scoped permissions per protocol; least privilege by default.',
      'Local-first runtime option; secrets stored in your vault.',
      'Signed actions with tamper-evident logs and rollback points.',
      'No implicit network or file access—everything is explicit and auditable.',
    ],
  },
  models: {
    title: 'Models & Deployment',
    bullets: [
      'BYOK across vendors; swap models per task stage (plan, draft, verify).',
      'Local inference supported where feasible; hybrid routing allowed.',
      'Deterministic planning passes with temperature governance.',
      'Vendor isolation to prevent cross-context leakage.',
    ],
  },
  waitlist: {
    title: 'Join the Agent Early Access',
    body: 'We are onboarding operators who need execution—not chatter. Early access includes the protocol DSL, core adapters, and Sentinel rules.',
    cta: 'Join Early Access',
    emailLabel: 'Email',
    emailPlaceholder: 'you@example.com',
    roleLabel: 'Role (optional)',
    rolePlaceholder: 'Builder, Operator, or Researcher',
    consentLabel:
      'I agree to receive early access communications for GalyarderAgent and related modules.',
    success: "You're on the list! Check your inbox for next steps.",
    error: 'Something went wrong. Please try again or email founders@galyarderlabs.app',
    legal:
      'By joining, you agree to receive early access communications for GalyarderAgent and related modules.',
  },
  faq: {
    title: 'FAQ',
    items: [
      {
        q: 'How is this different from a chatbot?',
        a: "It's protocol-driven, not chat-driven. Objectives become procedures with tools, memory, approvals, and logs.",
      },
      {
        q: 'Which models are supported?',
        a: 'Bring your own—Claude, GPT, Gemini, and compatible local models. You control routing and cost.',
      },
      {
        q: 'Does it run locally?',
        a: 'Yes. A local-first runtime is supported. Cloud is optional—never mandatory.',
      },
      {
        q: 'How do you handle secrets and permissions?',
        a: 'Secrets live in your vault. Protocols declare explicit scopes. Every action is signed and auditable.',
      },
      {
        q: 'Can it modify code or finances?',
        a: 'Only within granted scopes and with approvals you configure. Sensitive operations require human-in-the-loop.',
      },
    ],
  },
  footer: {
    note: 'GalyarderAgent turns objectives into auditable execution—on your terms.',
    links: {
      docs: 'https://github.com/galyarderlabs/galyarder-agent',
      blog: 'https://github.com/galyarderlabs/galyarder-agent/releases',
      contact: 'mailto:founders@galyarderlabs.app',
    },
    copyright: '© 2025 GalyarderLabs. Systems for sovereign execution.',
  },
};
