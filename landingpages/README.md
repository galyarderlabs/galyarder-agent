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
WAITLIST_STATS_TOKEN=strong_random_token_for_stats_endpoint
WAITLIST_IP_SALT=strong_random_salt_for_ip_hashing
```

## Notes

- Main landing copy is in `lib/copy.ts`.
- Waitlist endpoint is `app/api/waitlist/route.ts`.
- Waitlist stats endpoint requires `x-waitlist-stats-token` header.
- Raw IP is not persisted; only salted hash is stored when `WAITLIST_IP_SALT` is set.
