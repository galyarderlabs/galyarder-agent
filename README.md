# Galyarder Agent Monorepo

One repo for:

- **Landing web** (Next.js) at repo root
- **Backend assistant** (`g-agent`) at `backend/g-agent`

This keeps branding, product site, and runtime agent in one place.

## Structure

```text
.
├── app/                      # Landing pages + waitlist API
├── components/               # Landing UI blocks
├── lib/                      # Landing copy/schema/utils
├── public/                   # Static assets
├── backend/g-agent/          # Python assistant backend
│   ├── g_agent/              # Core agent package
│   ├── bridge/               # WhatsApp bridge (Baileys)
│   ├── tests/                # Backend tests
│   └── pyproject.toml
└── package.json
```

## Run Landing (Web)

```bash
npm install
npm run dev
```

## Run Backend (`g-agent`)

```bash
cd backend/g-agent
pip install -e .
g-agent onboard
g-agent status
```

For channels runtime:

```bash
g-agent channels login
g-agent gateway
```

## Landing Env

Create `.env.local` for waitlist API:

```bash
KV_REST_API_URL=your_upstash_redis_url
KV_REST_API_TOKEN=your_upstash_token
KV_REST_API_READ_ONLY_TOKEN=your_upstash_readonly_token
```

## Acknowledgements

Built from practical learnings and inspiration from:

- `nanobot`
- `openclaw`
