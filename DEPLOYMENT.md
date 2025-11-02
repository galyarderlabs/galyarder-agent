# Deployment Guide

## Vercel Deployment

### Domain Configuration

This project is designed to be deployed on Vercel with the following domain structure:

- **Main domain**: `galyarderlabs.app`
- **Project subdomain**: `agent.galyarderlabs.app`

### Prerequisites

- Vercel account
- Access to DNS settings for `galyarderlabs.app`
- Node.js 20+ installed locally

### Steps to Deploy

#### 1. Install Vercel CLI (if not already installed)

```bash
npm i -g vercel
```

#### 2. Login to Vercel

```bash
vercel login
```

#### 3. Initial Deployment

From the project root:

```bash
cd galyarderagent-landing
vercel
```

Follow the prompts:
- Set up and deploy? **Yes**
- Which scope? Select your team/account
- Link to existing project? **No** (first time)
- Project name? `galyarderagent-landing` (or customize)
- Directory? `.` (current directory)
- Override settings? **No**

#### 4. Deploy to Production

```bash
vercel --prod
```

#### 5. Configure Custom Domain

##### In Vercel Dashboard:

1. Go to your project: https://vercel.com/dashboard
2. Select `galyarderagent-landing` project
3. Navigate to **Settings** → **Domains**
4. Click **Add Domain**
5. Enter: `agent.galyarderlabs.app`
6. Click **Add**

Vercel will provide DNS configuration instructions.

##### In Your DNS Provider:

Add the following DNS record:

**CNAME Record:**
- **Type**: `CNAME`
- **Name**: `agent`
- **Value**: `cname.vercel-dns.com`
- **TTL**: Automatic (or 3600)

*Note: DNS propagation can take 24-48 hours, but usually completes within minutes.*

### Environment Variables

#### Required for Waitlist Functionality

Set these in Vercel Dashboard under **Settings** → **Environment Variables**:

```
KV_REST_API_URL=your_upstash_redis_url
KV_REST_API_TOKEN=your_upstash_token
KV_REST_API_READ_ONLY_TOKEN=your_upstash_readonly_token
```

#### How to Get Upstash Redis Credentials:

1. Go to https://upstash.com/
2. Create account or login
3. Create new Redis database
4. Copy the REST API credentials
5. Paste into Vercel environment variables
6. Redeploy: `vercel --prod`

### Analytics Configuration

Analytics are already configured in the project:

- ✅ Vercel Analytics (page views, vitals)
- ✅ Vercel Speed Insights (performance metrics)

No additional setup needed. View analytics in Vercel Dashboard → Analytics tab.

### Deployment Workflow

#### Automatic Deployments:

- **Production**: Push to `main` branch
- **Preview**: Push to any other branch or open PR

#### Manual Deployments:

```bash
# Preview deployment
vercel

# Production deployment
vercel --prod
```

### Build Configuration

The project uses:
- **Framework**: Next.js 15.5.3
- **Build Command**: `npm run build --turbopack`
- **Output Directory**: `.next`
- **Node Version**: 20.x (auto-detected)

### Monitoring & Logs

View deployment logs:

```bash
vercel logs [deployment-url]
```

Or visit: Vercel Dashboard → Deployments → Select deployment → View logs

### Troubleshooting

#### Build Fails

```bash
# Test build locally
npm run build

# Check for TypeScript errors
npm run lint
```

#### Domain Not Working

1. Verify DNS CNAME record is correct
2. Wait for DNS propagation (use https://dnschecker.org)
3. Check Vercel Dashboard → Domains for status
4. Ensure SSL certificate is issued (automatic, may take a few minutes)

#### Environment Variables Not Working

1. Check variables are set in Vercel Dashboard
2. Redeploy after adding variables: `vercel --prod`
3. Ensure variable names match exactly (case-sensitive)

### Performance Optimization

Already configured:
- ✅ Next.js Turbopack for faster builds
- ✅ Image optimization
- ✅ Font optimization (Inter, JetBrains Mono)
- ✅ CSS minification
- ✅ Automatic code splitting

### Security

- ✅ Rate limiting on API routes (via Upstash)
- ✅ HTTPS enforced automatically by Vercel
- ✅ Security headers configured
- ✅ CSP headers (Content Security Policy)

### Project URLs

After deployment:

- **Production**: https://agent.galyarderlabs.app
- **Vercel URL**: https://galyarderagent-landing.vercel.app (backup)
- **Preview**: https://galyarderagent-landing-{branch}.vercel.app

### Contact

For deployment issues, contact: founders@galyarderlabs.app

---

## Quick Reference

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy to preview
vercel

# Deploy to production
vercel --prod

# View logs
vercel logs

# Remove deployment
vercel remove [deployment-url]
```

---

**Last Updated**: January 2025