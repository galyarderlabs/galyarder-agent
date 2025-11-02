# Pre-Launch Checklist

## 🚀 Deployment Readiness

Use this checklist before deploying to production at `agent.galyarderlabs.app`.

---

## 📋 Technical Setup

### Environment & Configuration

- [ ] `@vercel/kv` package installed
- [ ] All npm dependencies up to date (`npm audit` clean)
- [ ] Environment variables configured in Vercel Dashboard:
  - [ ] `KV_REST_API_URL`
  - [ ] `KV_REST_API_TOKEN`
  - [ ] `KV_REST_API_READ_ONLY_TOKEN`
- [ ] `vercel.json` configuration verified
- [ ] Build succeeds locally (`npm run build`)
- [ ] No TypeScript errors (`npm run lint`)

### Domain & DNS

- [ ] DNS CNAME record configured:
  - Name: `agent`
  - Value: `cname.vercel-dns.com`
- [ ] Domain added in Vercel Dashboard: `agent.galyarderlabs.app`
- [ ] SSL certificate issued (automatic via Vercel)
- [ ] DNS propagation verified (use dnschecker.org)

---

## 🎨 Content & Design

### Copy & Messaging

- [ ] All text in `lib/copy.ts` reviewed and finalized
- [ ] Email address correct: `founders@galyarderlabs.app`
- [ ] No typos or grammatical errors
- [ ] All links functional (especially footer links)
- [ ] CTA buttons clear and compelling

### Visual Assets

- [ ] OG Image created and saved at `/public/og-image.png`
  - [ ] Size: 1200x630px
  - [ ] File size under 1MB
  - [ ] Branding consistent
  - [ ] Text readable at thumbnail size
- [ ] Favicon present (if custom favicon needed)
- [ ] All SVG icons loading correctly

### Responsive Design

- [ ] Desktop view tested (1920px, 1440px, 1280px)
- [ ] Tablet view tested (768px, 1024px)
- [ ] Mobile view tested (375px, 390px, 414px)
- [ ] Touch targets minimum 44x44px
- [ ] No horizontal scroll on any breakpoint

---

## 🔍 SEO & Meta Tags

### Meta Information

- [ ] Page title optimized: "GalyarderAgent — Execution, Engineered."
- [ ] Meta description compelling (150-160 characters)
- [ ] `metadataBase` set to production URL
- [ ] Open Graph tags verified:
  - [ ] `og:title`
  - [ ] `og:description`
  - [ ] `og:image` (full URL)
  - [ ] `og:type` = "website"
- [ ] Twitter Card tags verified:
  - [ ] `twitter:card` = "summary_large_image"
  - [ ] `twitter:image`

### Search Engine Configuration

- [ ] `robots.txt` configured and accessible
- [ ] `sitemap.xml` present and valid
- [ ] No pages accidentally set to `noindex`
- [ ] Canonical URLs correct
- [ ] Structured data considered (JSON-LD if applicable)

### Social Preview Testing

- [ ] Facebook preview tested: https://developers.facebook.com/tools/debug/
- [ ] Twitter preview tested: https://cards-dev.twitter.com/validator
- [ ] LinkedIn preview tested: https://www.linkedin.com/post-inspector/
- [ ] Image displays correctly on all platforms

---

## 📊 Analytics & Monitoring

### Vercel Analytics

- [ ] `@vercel/analytics` package installed
- [ ] `<Analytics />` component in layout.tsx
- [ ] Analytics enabled in `vercel.json`
- [ ] Dashboard accessible after first deployment

### Speed Insights

- [ ] `@vercel/speed-insights` package installed
- [ ] `<SpeedInsights />` component in layout.tsx
- [ ] Speed Insights enabled in `vercel.json`

### Logging

- [ ] Console logs for waitlist signups working
- [ ] Error logging configured
- [ ] API routes return proper status codes

---

## 🔒 Security

### Headers & Policies

- [ ] Security headers configured in `vercel.json`:
  - [ ] `X-Content-Type-Options: nosniff`
  - [ ] `X-Frame-Options: DENY`
  - [ ] `X-XSS-Protection: 1; mode=block`
  - [ ] `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] HTTPS enforced (automatic via Vercel)
- [ ] No secrets in client-side code
- [ ] API keys stored in environment variables only

### API Security

- [ ] Rate limiting functional (Upstash Ratelimit)
- [ ] Input validation with Zod schemas
- [ ] Email validation working
- [ ] Duplicate email prevention working
- [ ] Proper error messages (no stack traces to client)

---

## ✅ Functionality Testing

### Waitlist Form

- [ ] Form appears correctly
- [ ] Email field validates correctly
- [ ] Role dropdown works (Builder, Operator, Researcher)
- [ ] Consent checkbox required
- [ ] Success message displays on submission
- [ ] Error handling works (try invalid email)
- [ ] Form clears after successful submission
- [ ] Rate limiting prevents spam (test with 6+ submissions)

### Navigation

- [ ] All anchor links scroll smoothly
- [ ] "Skip to content" link works
- [ ] Mobile menu functional (if applicable)
- [ ] Footer links work
- [ ] Email link opens mail client: `mailto:founders@galyarderlabs.app`

### Accessibility

- [ ] Keyboard navigation works
- [ ] Focus indicators visible
- [ ] Alt text on images (if any)
- [ ] ARIA labels where needed
- [ ] Color contrast meets WCAG 2.1 AA standards
- [ ] Screen reader tested (VoiceOver/NVDA)

---

## 🌐 Browser Testing

### Desktop Browsers

- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

### Mobile Browsers

- [ ] Safari iOS
- [ ] Chrome Android
- [ ] Samsung Internet (if applicable)

---

## ⚡ Performance

### Lighthouse Scores (Target)

- [ ] Performance: 90+
- [ ] Accessibility: 95+
- [ ] Best Practices: 95+
- [ ] SEO: 100

### Load Times

- [ ] First Contentful Paint < 1.5s
- [ ] Largest Contentful Paint < 2.5s
- [ ] Time to Interactive < 3.0s
- [ ] Cumulative Layout Shift < 0.1

### Optimization

- [ ] Images optimized (WebP/AVIF where possible)
- [ ] Fonts loaded efficiently (font-display: swap)
- [ ] CSS minified
- [ ] JavaScript code-split
- [ ] No render-blocking resources

---

## 🗂️ Documentation

### Internal Docs

- [ ] README.md complete and accurate
- [ ] DEPLOYMENT.md reviewed
- [ ] OG_IMAGE_GUIDE.md created
- [ ] Comments in code for complex logic

### External Communication

- [ ] Team notified of launch
- [ ] Social media posts prepared (optional)
- [ ] Email announcement draft ready (optional)

---

## 🚢 Deployment

### Pre-Deploy

- [ ] All checks above completed
- [ ] Git repo clean (no uncommitted changes)
- [ ] Branch up to date with main
- [ ] Code reviewed (if team workflow)

### Deploy Process

```bash
# Run this before deploying
npm install
npm run lint
npm run build
./deploy.sh prod
```

- [ ] Preview deployment tested first (`./deploy.sh preview`)
- [ ] Production deployment executed (`./deploy.sh prod`)
- [ ] Production URL loads: https://agent.galyarderlabs.app
- [ ] All functionality tested on production

### Post-Deploy

- [ ] Test waitlist submission on production
- [ ] Verify email in Upstash KV store
- [ ] Check Vercel Analytics dashboard
- [ ] Monitor logs for errors (first 15 minutes)
- [ ] Test from different locations/devices
- [ ] Share URL with team for final review

---

## 🐛 Fallback Plan

### If Issues Occur

- [ ] Rollback plan documented
- [ ] Previous deployment URL saved
- [ ] Contact info ready: founders@galyarderlabs.app
- [ ] Vercel support docs bookmarked

### Quick Rollback

```bash
# In Vercel Dashboard:
# 1. Go to Deployments tab
# 2. Find last working deployment
# 3. Click "..." menu → "Promote to Production"
```

---

## 📈 Post-Launch Monitoring (First 48 Hours)

### Metrics to Watch

- [ ] Page views (Vercel Analytics)
- [ ] Waitlist signups (check Upstash KV)
- [ ] Error rate (Vercel logs)
- [ ] Core Web Vitals (Speed Insights)
- [ ] Social sharing engagement

### Action Items

- [ ] Monitor waitlist API for errors
- [ ] Check for 404s or broken links
- [ ] Review user feedback (if any)
- [ ] Update documentation if needed

---

## ✨ Optional Enhancements (Post-Launch)

Future improvements to consider:

- [ ] Add Google Analytics (if needed beyond Vercel Analytics)
- [ ] Implement A/B testing for CTA buttons
- [ ] Add blog section (#blog link currently placeholder)
- [ ] Create docs site (#docs link currently placeholder)
- [ ] Add testimonials section
- [ ] Implement dark/light mode toggle (currently dark-only)
- [ ] Add more animations (Framer Motion)
- [ ] Multilingual support (i18n)

---

## 🎉 Launch Sign-Off

**Deployment Date**: _______________

**Deployed By**: _______________

**Final Production URL**: https://agent.galyarderlabs.app

**Notes**:
```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

**Status**: ☐ Ready to Deploy | ☐ Deployed | ☐ Live

**Last Updated**: January 2025