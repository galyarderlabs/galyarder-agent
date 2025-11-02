# OG Image Creation Guide

## Specifications

### Required Dimensions
- **Size**: 1200x630 pixels (16:9 aspect ratio)
- **Format**: PNG or JPG
- **File size**: Keep under 1MB for faster loading
- **Path**: Save as `/public/og-image.png`

### Safe Zones
- **Title safe zone**: 1200x630px (full canvas)
- **Avoid text near edges**: Keep important content 60px from edges
- **Facebook mobile crop**: Center 1200x630px area
- **Twitter crop**: Center 1200x628px area

## Design Guidelines

### Brand Colors (from tailwind.config)
```
Background: #0a0a0a (near black)
Accent Red: #dc2626 / #ef4444
Text Primary: #f1f5f9 (slate-100)
Text Secondary: #64748b (slate-500)
Border: #1e293b (slate-800)
```

### Typography
- **Primary Font**: Inter (sans-serif)
- **Mono Font**: JetBrains Mono (for code/technical elements)
- **Title**: 72-80px, Bold
- **Subtitle**: 32-40px, Medium
- **Body**: 24-28px, Regular

### Content Structure

#### Option 1: Bold Statement
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
           Top Section
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Large Title (centered):
"Execution, Engineered."

Subtitle:
Protocol-driven AI agents for sovereign automation

Footer:
agent.galyarderlabs.app
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### Option 2: Technical Grid
```
┌──────────────────────────────┐
│ GalyarderAgent              │
│                              │
│ [Visual: Protocol Flow]      │
│  Define → Compose → Execute  │
│                              │
│ Execution, Engineered.       │
│ agent.galyarderlabs.app      │
└──────────────────────────────┘
```

### Visual Elements

**Recommended:**
- Subtle grid pattern background
- Terminal/code aesthetic
- Red accent highlights on key words
- Minimal geometric shapes
- Monospace text for technical terms

**Avoid:**
- Stock photos
- Gradients (keep flat design)
- Too much text (max 3 lines)
- Low contrast text
- Cluttered layouts

## Tools & Resources

### Design Tools

#### 1. Figma (Recommended)
- Free tier available
- Template: https://www.figma.com/community/file/1234567890/og-image-template
- Export at 2x for retina quality

#### 2. Canva
- Use custom dimensions: 1200x630px
- Free templates available
- Easy for non-designers

#### 3. Code-based (for developers)

**Using HTML/CSS + Playwright:**
```bash
npm install playwright
```

```javascript
// og-image-generator.js
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  await page.setViewportSize({ width: 1200, height: 630 });
  await page.setContent(`
    <!DOCTYPE html>
    <html>
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap" rel="stylesheet">
        <style>
          body {
            margin: 0;
            width: 1200px;
            height: 630px;
            background: #0a0a0a;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: 'Inter', sans-serif;
            color: #f1f5f9;
          }
          h1 {
            font-size: 80px;
            font-weight: 700;
            margin: 0;
            text-align: center;
          }
          .accent { color: #ef4444; }
          p {
            font-size: 32px;
            margin-top: 24px;
            color: #64748b;
          }
          .footer {
            position: absolute;
            bottom: 40px;
            font-size: 24px;
            color: #64748b;
          }
        </style>
      </head>
      <body>
        <h1>Execution, <span class="accent">Engineered</span>.</h1>
        <p>Protocol-driven AI agents for sovereign automation</p>
        <div class="footer">agent.galyarderlabs.app</div>
      </body>
    </html>
  `);
  
  await page.screenshot({ path: 'public/og-image.png' });
  await browser.close();
})();
```

Run: `node og-image-generator.js`

### Online Generators

1. **OG Image Generator** - https://og-image.vercel.app/
2. **Bannerbear** - https://www.bannerbear.com/
3. **Cloudinary** - Dynamic OG images via API

## Testing

### Preview Your OG Image

1. **Meta Debugger** (Facebook)
   - https://developers.facebook.com/tools/debug/
   - Enter: https://agent.galyarderlabs.app
   - Click "Scrape Again" to refresh

2. **Twitter Card Validator**
   - https://cards-dev.twitter.com/validator
   - Preview how it looks on Twitter

3. **LinkedIn Post Inspector**
   - https://www.linkedin.com/post-inspector/
   - Check LinkedIn preview

4. **Social Share Preview**
   - https://socialsharepreview.com/
   - See all platforms at once

### Local Testing

Add to your HTML `<head>` (already in layout.tsx):
```html
<meta property="og:image" content="https://agent.galyarderlabs.app/og-image.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:image" content="https://agent.galyarderlabs.app/og-image.png" />
```

## Quick Template (Copy & Customize)

### Figma Template Layers:
```
Layer 1: Background (#0a0a0a)
Layer 2: Grid pattern (opacity 5%)
Layer 3: Title "Execution, Engineered."
Layer 4: Subtitle "Protocol-driven AI agents"
Layer 5: Footer "agent.galyarderlabs.app"
Layer 6: Accent highlight (red underline/shape)
```

### Text Content Variations:

**Option A (Current):**
- Title: "Execution, Engineered."
- Subtitle: "Protocol-driven AI agents for sovereign automation"

**Option B:**
- Title: "GalyarderAgent"
- Subtitle: "Not prompts. Protocols."

**Option C:**
- Title: "AI That Executes"
- Subtitle: "Memory-aware agents with audit trails"

## Checklist

Before deploying:
- [ ] Image is exactly 1200x630px
- [ ] Text is readable at thumbnail size (200px wide)
- [ ] File size is under 1MB
- [ ] Saved as `/public/og-image.png`
- [ ] High contrast (light text on dark background)
- [ ] Brand colors used correctly
- [ ] No typos in text
- [ ] Tested on Meta Debugger
- [ ] Tested on Twitter Card Validator
- [ ] Looks good on mobile preview

## Need Help?

Contact: founders@galyarderlabs.app

---

**Quick Deploy After Creating Image:**
```bash
# Add the file
git add public/og-image.png

# Commit
git commit -m "Add OG image for social sharing"

# Deploy
vercel --prod
```

**Last Updated**: January 2025