# Galyarder Agent Landingpages

Next.js landing site for Galyarder Agent.

## Run

```bash
npm install
npm run dev
```

## Build

```bash
npm run lint
npm run typecheck
npm run build
```

## Environment

Create `.env.local`:

```bash
KV_REST_API_URL=your_upstash_redis_url
KV_REST_API_TOKEN=your_upstash_token
KV_REST_API_READ_ONLY_TOKEN=your_upstash_readonly_token
```

## Notes

- Main landing copy is in `lib/copy.ts`.
- Waitlist endpoint is `app/api/waitlist/route.ts`.
