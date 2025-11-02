# GalyarderAgent Landing Page

**Execution, Engineered.**

Landing page for GalyarderAgent — a protocol-driven, memory-aware AI agent framework for sovereign automation.

🔗 **Live Site**: [agent.galyarderlabs.app](https://agent.galyarderlabs.app)

---

## Overview

This is the official landing page for GalyarderAgent, built with Next.js 15 and deployed on Vercel. The site features:

- **Protocol-First Messaging**: Clear communication of GalyarderAgent's execution-over-chat philosophy
- **Waitlist System**: Upstash Redis-backed waitlist with rate limiting
- **Performance Optimized**: Vercel Analytics, Speed Insights, and Turbopack
- **Production Ready**: Security headers, SEO optimized, fully responsive

---

## Features

### Core Functionality
- ✅ Responsive landing page with smooth scroll navigation
- ✅ Waitlist form with validation (email + role selection)
- ✅ Rate-limited API endpoints (Upstash Redis)
- ✅ Dark mode optimized design
- ✅ Accessibility-first (WCAG 2.1 AA compliant)

### Analytics & Monitoring
- ✅ Vercel Analytics for traffic insights
- ✅ Vercel Speed Insights for performance tracking
- ✅ Server-side logging for waitlist signups

### SEO & Social
- ✅ Open Graph meta tags
- ✅ Twitter Card optimization
- ✅ Sitemap.xml for search engines
- ✅ Robots.txt configuration
- 📝 OG image template (see `OG_IMAGE_GUIDE.md`)

---

## Tech Stack

- **Framework**: [Next.js 15.5.3](https://nextjs.org/) (App Router)
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS 3.4 + CSS Variables
- **UI Components**: Radix UI primitives
- **Forms**: React Hook Form + Zod validation
- **Animations**: Framer Motion
- **Database**: Upstash Redis (KV store)
- **Deployment**: Vercel
- **Build Tool**: Turbopack

---

## Getting Started

### Prerequisites

- Node.js 20.x or higher
- npm or pnpm

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd galyarderagent-landing

# Install dependencies
npm install

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the site.

### Environment Variables

For waitlist functionality, create a `.env.local` file:

```bash
KV_REST_API_URL=your_upstash_redis_url
KV_REST_API_TOKEN=your_upstash_token
KV_REST_API_READ_ONLY_TOKEN=your_upstash_readonly_token
```

Get these from [Upstash Console](https://console.upstash.com/).

---

## Project Structure

```
galyarderagent-landing/
├── app/
│   ├── api/waitlist/       # Waitlist API route
│   ├── layout.tsx          # Root layout with analytics
│   ├── page.tsx            # Landing page
│   └── globals.css         # Global styles
├── components/
│   ├── ui/                 # Radix UI components
│   ├── WaitlistForm.tsx    # Waitlist form component
│   └── ...                 # Other components
├── lib/
│   ├── copy.ts             # All site copy/content
│   ├── schema.ts           # Zod schemas
│   └── utils.ts            # Utility functions
├── public/
│   ├── sitemap.xml         # SEO sitemap
│   ├── robots.txt          # Crawler instructions
│   └── og-image.png        # Social sharing image (add this)
├── vercel.json             # Vercel configuration
├── DEPLOYMENT.md           # Deployment guide
└── OG_IMAGE_GUIDE.md       # OG image creation guide
```

---

## Development

### Available Scripts

```bash
# Development with Turbopack
npm run dev

# Production build
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

### Code Quality

- **Linting**: ESLint + Prettier
- **Formatting**: Prettier with Tailwind plugin
- **Commits**: Commitlint (conventional commits)
- **Pre-commit**: Husky + lint-staged

---

## Deployment

This project is configured for Vercel deployment with the domain:

**Production URL**: `agent.galyarderlabs.app`

### Quick Deploy

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy to production
vercel --prod
```

For detailed deployment instructions, including DNS configuration and environment variables, see **[DEPLOYMENT.md](./DEPLOYMENT.md)**.

### Domain Configuration

- **Main Domain**: `galyarderlabs.app`
- **Project Subdomain**: `agent.galyarderlabs.app`

DNS CNAME record:
```
Name: agent
Value: cname.vercel-dns.com
```

---

## Content Management

All site copy is centralized in `lib/copy.ts` for easy updates:

```typescript
export const copy = {
  meta: { /* SEO metadata */ },
  hero: { /* Hero section */ },
  problem: { /* Problem statement */ },
  solution: { /* Solution overview */ },
  // ... etc
};
```

Update copy there, rebuild, and deploy.

---

## API Routes

### POST `/api/waitlist`

Add email to waitlist.

**Request Body:**
```json
{
  "email": "user@example.com",
  "role": "Builder",
  "consent": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Added to waitlist"
}
```

**Rate Limiting**: 5 requests per minute per IP

---

## Performance

Current metrics:
- **Lighthouse Score**: 95+ (Performance)
- **First Contentful Paint**: <1.5s
- **Time to Interactive**: <3s
- **Bundle Size**: Optimized with code splitting

---

## Security

- ✅ Security headers (X-Frame-Options, CSP, etc.)
- ✅ Rate limiting on API routes
- ✅ Input validation with Zod
- ✅ HTTPS enforced
- ✅ No client-side secrets

---

## Browser Support

- Chrome (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- Edge (last 2 versions)

---

## Contributing

This is a private project. For questions or issues, contact:

**Email**: founders@galyarderlabs.app

---

## License

© 2025 GalyarderLabs. All rights reserved.

---

## Related Projects

- **GalyarderOS**: [galyarderos.app](https://galyarderos.app) — Sovereign OS for operators
- **GalyarderCode**: [galyardercode.app](https://galyardercode.app) — Repo-aware code execution
- **GalyarderWallet**: [galyarderwallet.app](https://galyarderwallet.app) — Treasury automation
- **GalyarderID**: [galyarderid.app](https://galyarderid.app) — Identity & permissions

---

**Built with discipline. Deployed with confidence.**