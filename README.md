# Galyarder Agent — Landing Site

Landing website for **Galyarder Agent** at `agent.galyarderlabs.app`.

This repo is intentionally lean and focused on one job: a fast marketing site + waitlist API.

## Stack

- Next.js 15 (App Router)
- TypeScript + Tailwind CSS
- Radix UI + Framer Motion
- Upstash KV + Upstash Ratelimit
- Vercel Analytics + Speed Insights

## Project Structure

```text
.
├── app/                    # App Router pages + API routes
│   └── api/waitlist/       # Waitlist endpoint
├── components/             # Landing sections + UI primitives
├── lib/                    # Copy, schemas, utilities, motion config
├── public/                 # Static assets (robots, sitemap, icons)
├── vercel.json             # Deployment/security headers
└── package.json
```

## Quick Start

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment Variables

Create `.env.local`:

```bash
KV_REST_API_URL=your_upstash_redis_url
KV_REST_API_TOKEN=your_upstash_token
KV_REST_API_READ_ONLY_TOKEN=your_upstash_readonly_token
```

Without these, the waitlist API will not work in production.

## NPM Scripts

```bash
npm run dev             # local dev
npm run build           # production build
npm run start           # serve production build
npm run lint            # eslint
npm run typecheck       # tsc --noEmit
```

## Deploy

Primary deployment target:

- `agent.galyarderlabs.app`

Use:

```bash
vercel --prod
```

## Content Updates

All core landing copy is centralized in:

- `lib/copy.ts`

Update copy there, then rebuild/redeploy.

## API

### `POST /api/waitlist`

Stores waitlist entries in Upstash KV with:

- input validation (Zod)
- anti-spam honeypot
- duplicate-email prevention
- per-IP rate limiting

## Security Notes

- Security headers configured in `vercel.json`
- API input validated with Zod
- Rate limiting enabled in waitlist route
- No client-side secret exposure

## Contact

- `founders@galyarderlabs.app`
