# Quick Start Guide

**Deploy GalyarderAgent Landing to `agent.galyarderlabs.app` in 10 minutes.**

---

## ✅ Prerequisites

- Node.js 20+ installed
- Vercel account
- Access to DNS for `galyarderlabs.app`
- Upstash Redis account (for waitlist)

---

## 🚀 Deploy in 5 Steps

### 1. Install Dependencies

```bash
cd galyarderagent-landing
npm install
```

### 2. Setup Environment Variables

Get credentials from [Upstash Console](https://console.upstash.com/):

```bash
# Create .env.local for local testing
cat > .env.local << EOF
KV_REST_API_URL=your_upstash_redis_url
KV_REST_API_TOKEN=your_upstash_token
KV_REST_API_READ_ONLY_TOKEN=your_upstash_readonly_token
EOF
```

### 3. Test Locally

```bash
npm run dev
# Visit http://localhost:3000
# Test waitlist form
```

### 4. Deploy to Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy (use the script!)
./deploy.sh prod

# Or manually:
# vercel --prod
```

### 5. Configure Domain

**In Vercel Dashboard:**
1. Go to Project Settings → Domains
2. Add: `agent.galyarderlabs.app`
3. Copy the CNAME instruction

**In Your DNS Provider:**
```
Type: CNAME
Name: agent
Value: cname.vercel-dns.com
TTL: Auto (or 3600)
```

Wait 2-10 minutes for DNS propagation.

---

## ✨ What's Already Configured

✅ **Analytics**: Vercel Analytics + Speed Insights  
✅ **Email**: `founders@galyarderlabs.app`  
✅ **Security**: Rate limiting, security headers  
✅ **SEO**: Sitemap, robots.txt, OG tags  
✅ **Performance**: Turbopack, optimized build  

---

## 📝 Before Going Live

**Must Do:**
- [ ] Add environment variables to Vercel Dashboard
- [ ] Create OG image at `/public/og-image.png` (1200x630px)
- [ ] Test waitlist form on production
- [ ] Verify DNS propagation

**Optional:**
- [ ] Review copy in `lib/copy.ts`
- [ ] Test on mobile devices
- [ ] Run through `CHECKLIST.md`

---

## 🎨 Create OG Image (2 minutes)

**Quick Method:**
```bash
# Use the HTML generator in OG_IMAGE_GUIDE.md
node og-image-generator.js
# Saves to: public/og-image.png
```

**Or use Figma/Canva:**
- Size: 1200x630px
- Background: #0a0a0a (dark)
- Title: "Execution, Engineered."
- Subtitle: "Protocol-driven AI agents"
- Save as: `public/og-image.png`

See `OG_IMAGE_GUIDE.md` for detailed instructions.

---

## 🔥 Set Environment Variables in Vercel

1. Go to: https://vercel.com/dashboard
2. Select project: `galyarderagent-landing`
3. Settings → Environment Variables
4. Add these three variables:
   - `KV_REST_API_URL`
   - `KV_REST_API_TOKEN`
   - `KV_REST_API_READ_ONLY_TOKEN`
5. Redeploy: `vercel --prod`

---

## 🧪 Testing Checklist

After deployment, test these:

```bash
# 1. Site loads
curl -I https://agent.galyarderlabs.app

# 2. Waitlist form works
# Go to site → scroll to form → submit email

# 3. Check OG image
# Visit: https://developers.facebook.com/tools/debug/
# Enter: https://agent.galyarderlabs.app

# 4. Monitor logs
vercel logs --follow
```

---

## 📊 View Analytics

- **Vercel Dashboard**: https://vercel.com/dashboard
- Navigate to: Analytics tab
- View: Page views, Web Vitals, Speed Insights

---

## 🐛 Troubleshooting

### Build Fails
```bash
npm run lint
npm run build
# Fix any errors, then redeploy
```

### Domain Not Working
```bash
# Check DNS propagation
dig agent.galyarderlabs.app
# Or visit: https://dnschecker.org
```

### Waitlist Not Working
- Check environment variables in Vercel
- Verify Upstash Redis is running
- Check Vercel logs: `vercel logs`

---

## 📚 Full Documentation

- **Deployment Guide**: See `DEPLOYMENT.md`
- **Launch Checklist**: See `CHECKLIST.md`
- **OG Image Guide**: See `OG_IMAGE_GUIDE.md`
- **Project README**: See `README.md`

---

## 🎯 Post-Launch

**Immediate:**
1. Test waitlist signup
2. Check Upstash KV for entries
3. Monitor Vercel logs for errors

**First Week:**
1. Review analytics daily
2. Test on various devices
3. Gather feedback from team

---

## 🆘 Need Help?

**Contact**: founders@galyarderlabs.app

**Resources:**
- Vercel Docs: https://vercel.com/docs
- Upstash Docs: https://docs.upstash.com
- Next.js Docs: https://nextjs.org/docs

---

## 🎉 Success Criteria

Your site is live when:
- ✅ https://agent.galyarderlabs.app loads
- ✅ Waitlist form accepts submissions
- ✅ OG image shows in social previews
- ✅ Analytics tracking in Vercel Dashboard
- ✅ No errors in Vercel logs

---

**Ready? Run this:**

```bash
./deploy.sh prod
```

**Go ship it! 🚀**