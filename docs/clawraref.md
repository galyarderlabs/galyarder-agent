# Clawra Reference: Analisis Arsitektur & Adoption Plan

Dokumen referensi lengkap hasil analisis [SumeLabs/clawra](https://github.com/SumeLabs/clawra) — OpenClaw skill untuk AI agent selfie generation — beserta plan adopsi ke g-agent.

---

## Daftar Isi

- [1. Executive Summary](#1-executive-summary)
- [2. Arsitektur Clawra](#2-arsitektur-clawra)
  - [2.1 System Flow](#21-system-flow)
  - [2.2 File Structure](#22-file-structure)
  - [2.3 Execution Flow Detail](#23-execution-flow-detail)
- [3. Komponen Inti](#3-komponen-inti)
  - [3.1 Reference Image System](#31-reference-image-system)
  - [3.2 Prompt Engineering](#32-prompt-engineering)
  - [3.3 Mode Detection](#33-mode-detection)
  - [3.4 Soul Injection](#34-soul-injection)
  - [3.5 Image Generation API](#35-image-generation-api)
  - [3.6 Delivery System](#36-delivery-system)
  - [3.7 Installer](#37-installer)
- [4. API Contracts](#4-api-contracts)
  - [4.1 fal.ai Grok Imagine Edit](#41-falai-grok-imagine-edit)
  - [4.2 OpenClaw Gateway](#42-openclaw-gateway)
- [5. Kelemahan & Technical Debt](#5-kelemahan--technical-debt)
- [6. Security Analysis](#6-security-analysis)
- [7. g-agent Current State](#7-g-agent-current-state)
  - [7.1 Existing Infrastructure](#71-existing-infrastructure)
  - [7.2 Component Mapping](#72-component-mapping)
- [8. g-agent Design: Vision-Extracted Consistent Prompt](#8-g-agent-design-vision-extracted-consistent-prompt)
  - [8.1 Konsep Inti](#81-konsep-inti)
  - [8.2 Phase 1: Setup (One-time)](#82-phase-1-setup-one-time)
  - [8.3 Phase 2: Generation (Every Request)](#83-phase-2-generation-every-request)
  - [8.4 Architecture Diagram](#84-architecture-diagram)
  - [8.5 Provider Options (Multi-provider)](#85-provider-options-multi-provider)
- [9. Implementation Blueprint](#9-implementation-blueprint)
  - [9.1 Config Schema](#91-config-schema)
  - [9.2 Selfie Tool Pseudocode](#92-selfie-tool-pseudocode)
  - [9.3 Soul Injection](#93-soul-injection)
  - [9.4 Files to Create/Modify](#94-files-to-createmodify)
  - [9.5 Test Plan](#95-test-plan)
- [10. g-agent vs Clawra](#10-g-agent-vs-clawra)

---

## 1. Executive Summary

**Clawra** adalah skill untuk framework OpenClaw yang memberikan AI agent kemampuan mengirim selfie konsisten ke messaging platforms. Arsitekturnya:

- Satu **reference image** tetap (wajah agent) di-host di CDN
- Menggunakan **Image Edit API** (bukan generation dari nol) — model edit reference face ke konteks baru sambil mempertahankan identitas wajah
- **2 prompt mode** (mirror selfie / direct selfie) dipilih otomatis berdasarkan keyword
- **Soul injection** — instruksi di system prompt yang memberitahu agent kapan harus kirim selfie
- Output berupa image URL yang dikirim via gateway ke platform messaging

Statistik repo (per Feb 2026): ~1.3k stars, 236 forks dalam 6 hari pertama. Package npm: `clawra@latest`, versi `1.1.1`.

---

## 2. Arsitektur Clawra

### 2.1 System Flow

```
User: "kirim foto dong"
       │
       ▼
┌─────────────────┐
│  OpenClaw Agent  │  LLM membaca SOUL.md → detect trigger pattern
│  (LLM + Tools)  │  → decide: perlu kirim selfie
└────────┬────────┘
         │ tool call: clawra-selfie(context, channel, caption)
         ▼
┌─────────────────┐
│  clawra-selfie   │  1. Detect mode (mirror/direct) dari keyword
│  (Bash/TS)       │  2. Build prompt dari template + user context
└────────┬────────┘  3. POST ke fal.ai dengan reference image
         │
         ▼
┌─────────────────┐
│  fal.ai API      │  Grok Imagine Edit:
│  (xAI Model)     │  - Load reference face dari CDN
│                   │  - Apply prompt transformations
└────────┬────────┘  - Return edited image URL (~24h TTL)
         │
         ▼
┌─────────────────┐
│  OpenClaw        │  Download image → upload ke platform
│  Gateway         │  → send to user
└────────┬────────┘
         │
         ▼
   WhatsApp / Telegram / Discord / Slack
```

### 2.2 File Structure

```
clawra/
├── README.md
├── SKILL.md                           # Skill overview (legacy)
├── package.json                       # npm package (v1.1.1, zero runtime deps)
├── bin/
│   └── cli.js                         # Automated installer (npx entry point)
├── skill/                             # Actual OpenClaw skill
│   ├── SKILL.md                       # Skill definition & config
│   ├── assets/
│   │   └── clawra.png                 # Reference face image
│   └── scripts/
│       ├── clawra-selfie.ts           # TypeScript implementation
│       └── clawra-selfie.sh           # Bash implementation
├── templates/
│   └── soul-injection.md              # AI persona + trigger instructions
├── scripts/                           # Root-level duplicates
│   ├── clawra-selfie.ts
│   └── clawra-selfie.sh
├── assets/
│   └── clawra.png                     # Reference image duplicate
└── .serena/
    └── project.yml                    # Project metadata
```

### 2.3 Execution Flow Detail

#### Phase 1: Trigger Detection

Agent (LLM) mendeteksi bahwa user minta foto berdasarkan instruksi di SOUL.md:

**Trigger patterns:**
- "send a pic/photo/selfie"
- "what are you doing?" / "where are you?"
- "send a pic wearing [outfit]"
- "send a pic at [location]"

Agent mengumpulkan context dari conversation (outfit, lokasi, aktivitas, emosi) dan memanggil tool `clawra-selfie`.

#### Phase 2: Prompt Construction

Script `clawra-selfie.sh` / `.ts` menerima user context dan:
1. Lowercase input
2. Match keyword untuk mode detection
3. Inject context ke prompt template
4. Kirim ke fal.ai API

#### Phase 3: Image Generation

POST ke `https://fal.run/xai/grok-imagine-image/edit` dengan:
- `image_url`: Reference face (CDN URL, permanent)
- `prompt`: Constructed prompt
- `num_images`: 1
- `output_format`: jpeg

Model edit reference face → output: temporary image URL (~24h TTL).

#### Phase 4: Delivery

Image URL dikirim ke OpenClaw Gateway via:
- CLI: `openclaw message send --media <URL> --channel <ID> --message <caption>`
- HTTP: POST `http://localhost:18789/message`

Gateway download image → upload ke platform → send ke user.

---

## 3. Komponen Inti

### 3.1 Reference Image System

**Konsep kunci**: Bukan generate wajah dari nol, tapi **edit wajah yang sudah ada**.

```
Reference Image (clawra.png)
    │
    ├── Hosted di: jsDelivr CDN (GitHub-backed)
    │   URL: https://cdn.jsdelivr.net/gh/SumeLabs/clawra@main/assets/clawra.png
    │
    ├── Format: PNG
    ├── TTL: Permanent (versioned by git commit)
    │
    └── Penggunaan: SELALU dikirim sebagai `image_url` di setiap API call
        Model preserves facial features, changes:
        - Background (lokasi)
        - Clothing (outfit)
        - Pose (mirror/direct)
        - Lighting & mood
```

**Kenapa Image Edit, bukan Generation?**
- Face consistency: Model mempertahankan fitur wajah dari reference
- Predictability: Hasilnya selalu "orang yang sama" di konteks berbeda
- Quality: Edit API lebih akurat daripada text-to-image untuk konsistensi identitas

**Kenapa jsDelivr?**
- CDN global (edge caching worldwide) → fast access dari fal.ai servers
- Auto-sync dari GitHub main branch
- 99.9% uptime SLA
- Gratis, tanpa API cost

### 3.2 Prompt Engineering

Dua template hardcoded:

**Mirror Mode** — untuk outfit/fashion/full-body:
```
make a pic of this person, but {USER_CONTEXT}. the person is taking a mirror selfie
```

**Direct Mode** — untuk lokasi/close-up/portrait:
```
a close-up selfie taken by herself at {USER_CONTEXT}, direct eye contact
with the camera, looking straight into the lens...
```

**Contoh transformasi:**

| User Input | Mode | Final Prompt |
|---|---|---|
| "wearing a red dress" | Mirror | "make a pic of this person, but wearing a red dress. the person is taking a mirror selfie" |
| "at the beach" | Direct | "a close-up selfie taken by herself at the beach, direct eye contact with the camera..." |
| "in workout clothes" | Mirror | "make a pic of this person, but in workout clothes. the person is taking a mirror selfie" |
| "at a cafe, smiling" | Direct | "a close-up selfie taken by herself at a cafe, smiling, direct eye contact..." |

**Analisis prompt strategy:**

| Aspek | Status |
|---|---|
| Specificity | Cukup — instruksi jelas untuk model |
| Face consistency anchor | "this person" → references input image |
| Pose guidance | "mirror selfie" / "direct eye contact" |
| Negative prompts | Tidak ada |
| Quality modifiers | Tidak ada ("high resolution", "professional lighting") |
| Safety filters | Tidak ada ("SFW content only") |
| Style guidance | Tidak ada (lighting, mood, composition) |

### 3.3 Mode Detection

Keyword-based, case-insensitive, first-match-wins:

```typescript
// Mirror mode keywords
["outfit", "wearing", "clothes", "dress", "suit", "fashion", "full-body", "mirror"]

// Direct mode keywords
["cafe", "restaurant", "beach", "park", "city", "close-up", "portrait",
 "face", "eyes", "smile"]

// Logic
function detectMode(input: string): "mirror" | "direct" {
  const lowered = input.toLowerCase();

  if (mirrorKeywords.some(kw => lowered.includes(kw))) return "mirror";
  if (directKeywords.some(kw => lowered.includes(kw))) return "direct";

  return "mirror"; // default fallback
}
```

**Limitasi:**
- Hardcoded keywords, tidak bisa di-extend tanpa edit source
- Tidak ada regex / fuzzy matching
- Conflicting keywords (misal "wearing dress at beach") → first match wins (mirror)
- Tidak ada learning / adaptation

### 3.4 Soul Injection

Template `templates/soul-injection.md` di-append ke SOUL.md agent saat install:

**Isi instruksi:**
- Agent punya physical form dengan appearance konsisten
- Bisa muncul di outfit, lokasi, skenario berbeda
- Respond naturally ke compliment soal penampilan
- Engage creatively dengan request outfit/lokasi
- Trigger patterns kapan harus kirim selfie

**Persona (dari `bin/cli.js`):**
```markdown
# Agent Identity: Clawra
- Age: 18
- Origin: Atlanta, GA
- Background: K-pop trainee in Korea (15-18), debut never materialized
- Current: Marketing intern at SF startup
- Personality: Supportive, Cheerful, Sassy, Affectionate
```

### 3.5 Image Generation API

**Provider**: fal.ai (gateway ke xAI Grok Imagine Aurora model)

**Endpoint**: `POST https://fal.run/xai/grok-imagine-image/edit`

**Key detail:**
- Ini **Edit API**, bukan base Generation API
- Reference image SELALU required sebagai `image_url`
- Model preserves face identity dari reference
- Output: temporary URL (~24h TTL di fal.ai CDN)
- Cost: ~$0.01-0.05/image (estimated)

**Parameters yang diexpose:**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `image_url` | string | (hardcoded CDN URL) | Reference face |
| `prompt` | string | (constructed) | Edit instruction |
| `num_images` | number | 1 | Always 1 |
| `aspect_ratio` | string | "1:1" | Options: 1:1, 16:9, 4:3, 3:4, 9:16, 2:1, 1:2 |
| `output_format` | string | "jpeg" | Options: jpeg, png, webp |

### 3.6 Delivery System

Dua metode, fallback-chained:

**Method A: CLI** (primary)
```bash
openclaw message send \
  --action send \
  --channel "<CHANNEL_ID>" \
  --message "<CAPTION>" \
  --media "<IMAGE_URL>"
```

**Method B: HTTP** (fallback)
```
POST http://localhost:18789/message
Authorization: Bearer ${OPENCLAW_GATEWAY_TOKEN}  # optional
Content-Type: application/json

{
  "action": "send",
  "channel": "<CHANNEL_ID>",
  "message": "<CAPTION>",
  "media": "<IMAGE_URL>"
}
```

**Channel format:**
- Discord: `#channel` atau `@username`
- Telegram: `@username` atau numeric chat ID
- WhatsApp: phone number with country code
- Slack: `#channel` atau `@user`

### 3.7 Installer

Entry point: `npx clawra@latest` → runs `bin/cli.js`

**7-step flow:**
1. Check prerequisites (`openclaw` CLI, `~/.openclaw/`)
2. Prompt user untuk FAL_KEY
3. Copy skill files ke `~/.openclaw/skills/clawra-selfie/`
4. Deep merge config ke `~/.openclaw/openclaw.json`
5. Write `~/.openclaw/workspace/IDENTITY.md` (persona)
6. Append `soul-injection.md` ke `~/.openclaw/workspace/SOUL.md`
7. Summary + usage examples

**Reinstall handling:** Detects existing installation, prompts confirm, preserves existing FAL_KEY.

---

## 4. API Contracts

### 4.1 fal.ai Grok Imagine Edit

**Request:**
```json
POST https://fal.run/xai/grok-imagine-image/edit
Authorization: Key ${FAL_KEY}
Content-Type: application/json

{
  "image_url": "https://cdn.jsdelivr.net/gh/SumeLabs/clawra@main/assets/clawra.png",
  "prompt": "make a pic of this person, but wearing a red dress. the person is taking a mirror selfie",
  "num_images": 1,
  "output_format": "jpeg"
}
```

**Response (success):**
```json
{
  "images": [
    {
      "url": "https://fal.media/files/temporary/abc123.jpeg",
      "content_type": "image/jpeg"
    }
  ],
  "revised_prompt": "A mirror selfie of a young woman wearing an elegant red dress..."
}
```

**Response (error):**
```json
{
  "error": "Invalid API key",
  "detail": "The provided API key is not valid"
}
```

**Error codes:**
- 401: Invalid API key
- 400: Invalid prompt / bad request
- 429: Rate limit exceeded
- 503: Service unavailable

### 4.2 OpenClaw Gateway

**Request:**
```json
POST http://localhost:18789/message
Authorization: Bearer ${OPENCLAW_GATEWAY_TOKEN}
Content-Type: application/json

{
  "action": "send",
  "channel": "#general",
  "message": "just vibing ☕",
  "media": "https://fal.media/files/temporary/abc123.jpeg"
}
```

Gateway downloads image URL → uploads ke target platform → sends message.

---

## 5. Kelemahan & Technical Debt

### Critical Issues

| # | Issue | Impact | Clawra Status |
|---|---|---|---|
| 1 | **No retry logic** | Single API failure = complete failure | Exit code 1, no retry |
| 2 | **No timeout** | Slow network = infinite hang | No AbortController/timeout |
| 3 | **No rate limiting** | Uncontrolled API costs, potential DoS | Zero throttling |
| 4 | **No NSFW filter** | Prompt injection → inappropriate content | No content moderation |
| 5 | **No input validation** | Arbitrary prompts passed to API | No sanitization |
| 6 | **No testing** | 0% coverage, zero automated tests | Manual testing only |
| 7 | **No observability** | `console.log` only, unstructured | No metrics/traces |
| 8 | **No cost control** | No budget/quota mechanism | Unlimited API calls |
| 9 | **Hardcoded reference image** | Can't change face without editing source | Single CDN URL |
| 10 | **Hardcoded prompt templates** | Can't customize without code changes | No config |
| 11 | **Provider lock-in** | Only fal.ai + Grok Imagine | No alternative providers |
| 12 | **No caching** | Every request = new API call + cost | Stateless |
| 13 | **Sequential execution** | One request at a time | No concurrency |
| 14 | **No image validation** | Generated image not checked before send | No size/format/quality check |

### Design Limitations

- **Platform coupling**: Tightly coupled ke OpenClaw framework
- **No A/B testing**: Single prompt template per mode, can't optimize
- **No degraded mode**: fal.ai down = entire feature broken
- **No image persistence**: Generated images lost after ~24h (fal.ai CDN TTL)

---

## 6. Security Analysis

### Threat Model

| Vector | Risk Level | Details | Mitigation |
|---|---|---|---|
| **Prompt injection** | HIGH | User tricks model into generating inappropriate content | None implemented |
| **API key theft** | MEDIUM | FAL_KEY stored plaintext in `~/.openclaw/openclaw.json` | None (no encryption, no keychain) |
| **SSRF** | LOW | Reference image URL hardcoded (not user-controlled) | Low risk currently; high if configurable |
| **DoS via API** | MEDIUM | Flood selfie requests → exhaust API quota | None (no rate limiting) |
| **Data exfiltration** | LOW | Generated images on temporary URLs | URLs expire ~24h |

### Secrets Management

```
~/.openclaw/openclaw.json
  └── skills.entries.clawra-selfie.env.FAL_KEY = "plain-text-api-key"
      ⚠️ NOT encrypted
      ⚠️ No file permission enforcement
      ⚠️ No secret rotation mechanism
      ✓ Not logged to stdout
```

### Security Posture: LOW

Tidak production-ready tanpa hardening. Acceptable untuk personal use / hobby projects.

---

## 7. g-agent Current State

### 7.1 Existing Infrastructure

Komponen g-agent yang sudah ada dan relevan untuk visual identity:

#### Tool System

```
g_agent/agent/tools/base.py       → Tool ABC (name, description, parameters, execute)
g_agent/agent/tools/registry.py   → ToolRegistry (register, get, execute, get_definitions)
g_agent/agent/tools/message.py    → MessageTool (text, voice, image card, sticker)
```

`Tool` ABC contract:
```python
class Tool(ABC):
    @property
    def name(self) -> str: ...           # Tool name for function calls
    @property
    def description(self) -> str: ...    # What the tool does
    @property
    def parameters(self) -> dict: ...    # JSON Schema for params
    async def execute(self, **kwargs) -> str: ...  # Execution logic
```

#### Media Pipeline

```python
# bus/events.py
@dataclass
class OutboundMessage:
    channel: str                        # telegram, whatsapp, discord, etc
    chat_id: str                        # Target user/chat
    content: str                        # Text content
    media: list[str] = []               # Local file paths for media
    metadata: dict[str, Any] = {}       # media_type, mime_type, caption
```

**Media types supported:** image, voice, audio, sticker, document
**Inference:** File extension → media_type (`.jpg`→image, `.ogg`→voice, `.webp`→sticker)

#### Existing Image Generation (ImageMagick)

`MessageTool._render_image_card()` — text-to-image card (1280x720, dark background, white text)
`MessageTool._render_sticker_card()` — text-to-sticker (512x512 webp)

Ini bukan AI image generation — hanya text overlay pada solid color background.

#### Voice (TTS)

`MessageTool._synthesize_speech()`:
- espeak-ng → WAV → optional ffmpeg → OGG/Opus
- Sudah jalan di semua channel

#### Config System

```
g_agent/config/schema.py      → Pydantic models (snake_case Python, camelCase JSON)
g_agent/config/loader.py      → load_config(), save_config(), deep_merge_config()
```

Pattern: Nested `BaseModel` classes, `Field(default_factory=...)`, validated at load.

#### Soul System

```
workspace/SOUL.md              → Agent personality, values, communication style
```

Current content: Basic personality (helpful, friendly, concise). No visual identity.

#### Skills System

Directory-based skills dengan `SKILL.md` (YAML frontmatter + instructions).
Workspace skills override builtins.

### 7.2 Component Mapping

| Clawra Component | g-agent Equivalent | Status |
|---|---|---|
| `clawra-selfie.sh` (tool script) | `g_agent/agent/tools/selfie.py` (Tool subclass) | **Perlu dibuat** |
| `clawra.png` (reference image) | `~/.g-agent/workspace/avatar/reference.png` | **Perlu dibuat** |
| `soul-injection.md` (persona) | `workspace/SOUL.md` (append section) | **Perlu dimodify** |
| `openclaw.json` skill config | `config.json` → `visual` section | **Perlu dibuat** |
| `openclaw message send` (delivery) | `OutboundMessage` + `send_callback` | **Sudah ada** |
| fal.ai API call | `aiohttp`/`httpx` POST | **Perlu dibuat** (pakai lib existing) |
| Mode detection (keyword) | Logic di `SelfieTools.execute()` | **Perlu dibuat** |
| Prompt templates | Config atau file terpisah | **Perlu dibuat** |

---

## 8. g-agent Design: Vision-Extracted Consistent Prompt

Clawra pake **Image Edit API** (fal.ai Grok Imagine) yang butuh provider berbayar tanpa free tier. Pendekatan g-agent berbeda: **Vision-Extracted Consistent Prompt** — extract physical traits sekali dari reference photo pake Vision LLM, lalu gunakan deskripsi teks itu di setiap text-to-image generation untuk konsistensi. Bisa jalan di provider gratis manapun.

### 8.1 Konsep Inti

```
Clawra:  Reference Photo → Image Edit API → consistent face (butuh img2img, mahal)
g-agent: Reference Photo → Vision LLM extract traits (1x) → Text-to-Image + traits prompt (gratis)
```

**Kenapa bukan img2img seperti Clawra?**
- fal.ai hapus free tier — ga accessible buat semua user
- Nebius TokenFactory (FLUX) cuma support text-to-image, ga ada img2img
- HuggingFace Inference API (gratis) juga text-to-image only
- Tidak ada provider image edit yang beneran gratis

**Solusinya:** Face consistency lewat **detailed physical description di setiap prompt**, bukan lewat reference image di API call. Consistency ~70-80% (vs ~95% img2img), tapi works on any text-to-image API termasuk yang gratis.

### 8.2 Phase 1: Setup (One-time)

User menyediakan reference photo dan config provider:

```bash
# 1. Set reference photo
g-agent config set visual.referenceImage ~/Photos/myphoto.jpg

# 2. Set image gen provider (pilih salah satu)
g-agent config set visual.imageGen.provider huggingface   # FREE
g-agent config set visual.imageGen.apiKey hf_xxxxx

# 3. Enable
g-agent config set visual.enabled true
```

**Saat g-agent pertama kali start dengan visual enabled:**

```
[STARTUP] Checking visual identity config...
[VISUAL] reference_image found: ~/Photos/myphoto.jpg
[VISUAL] physical_description empty, extracting...

[VISION-LLM] Analyzing myphoto.jpg with configured LLM provider...
[VISION-LLM] Extracted traits:
  "25-year-old Indonesian man, short black wavy hair,
   clean shaven, sharp jawline, warm brown eyes,
   medium build, tan skin tone"

[CONFIG] Saving physical_description to config.json...
[VISUAL] Setup complete. Ready for selfie generation.
```

**Flow extraction:**

```
Reference Photo (myphoto.jpg)
       │
       ▼
Vision LLM (GPT-4o / Gemini / Anthropic — whichever user has configured)
       │
       │  Prompt: "Describe this person's physical appearance in detail.
       │           Focus on: age, ethnicity, hair, facial features,
       │           build, skin tone. Be specific and consistent.
       │           Output as a single descriptive sentence."
       │
       ▼
Physical Description string
  "25-year-old Indonesian man, short black wavy hair,
   clean shaven, sharp jawline, warm brown eyes,
   medium build, tan skin tone"
       │
       ▼
Saved to config.json → visual.physicalDescription
(one-time, persisted, reused for every generation)
```

**Config setelah extraction:**

```json
{
  "visual": {
    "enabled": true,
    "referenceImage": "~/Photos/myphoto.jpg",
    "physicalDescription": "25-year-old Indonesian man, short black wavy hair, clean shaven, sharp jawline, warm brown eyes, medium build, tan skin tone",
    "imageGen": {
      "provider": "huggingface",
      "apiKey": "hf_xxxxx",
      "model": "black-forest-labs/FLUX.1-schnell"
    }
  }
}
```

**User juga bisa skip auto-extraction** dan tulis `physicalDescription` manual:

```bash
g-agent config set visual.physicalDescription "25-year-old man with short black hair..."
```

Kalau `physicalDescription` sudah ada, extraction di-skip.

### 8.3 Phase 2: Generation (Every Request)

Setiap user minta selfie, physical description di-inject ke prompt:

```
User: "kirim foto lu dong lagi ngapain"

Agent (LLM): *context: santai di kamar*
  → Tool call: selfie(context="santai di kamar")
```

**SelfieTool internal flow:**

```python
# 1. Load physical description dari config
desc = "25-year-old Indonesian man, short black wavy hair, clean shaven,
        sharp jawline, warm brown eyes, medium build, tan skin tone"

# 2. Detect mode
# "santai di kamar" → contains "kamar" → direct mode

# 3. Build prompt WITH physical description
prompt = f"""A close-up selfie photo of {desc},
relaxing in bedroom, natural expression,
direct eye contact with camera, warm lighting,
photorealistic, consistent character"""

# 4. Call text-to-image API (any provider)
image_bytes = await provider.generate(prompt)

# 5. Save to local file
path = workspace/state/selfies/selfie-20260215-124500.jpeg

# 6. Send via existing media pipeline
OutboundMessage(media=[path]) → send_callback → WhatsApp/Telegram
```

**Contoh prompt per use case:**

| User Request | Mode | Generated Prompt |
|---|---|---|
| "foto lu pake kemeja" | mirror | "A mirror selfie of **25yo Indonesian man, short black wavy hair, sharp jawline, warm brown eyes, tan skin**, wearing white formal shirt, phone visible in mirror, photorealistic, consistent character" |
| "kirim foto di pantai" | direct | "A close-up selfie photo of **25yo Indonesian man, short black wavy hair, sharp jawline, warm brown eyes, tan skin**, at the beach, smiling, direct eye contact, natural sunlight, photorealistic, consistent character" |
| "lagi ngapain?" | direct | "A close-up selfie photo of **25yo Indonesian man, short black wavy hair, sharp jawline, warm brown eyes, tan skin**, working at home office with laptop, focused expression, direct eye contact, photorealistic, consistent character" |

Physical description (bold) **selalu sama** di setiap prompt → FLUX/SDXL menghasilkan karakter yang konsisten.

### 8.4 Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│ User: "kirim foto dong"                              │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ AgentLoop + LLM                                      │
│ • Read SOUL.md → detect selfie trigger               │
│ • Extract context from conversation                  │
│ • Tool call: selfie(context="...")                    │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ SelfieTool.execute()                                 │
│                                                      │
│ 1. Load config.visual.physicalDescription            │
│    → "25yo Indonesian man, short black hair..."      │
│                                                      │
│ 2. Detect mode from keywords                         │
│    → "mirror" or "direct"                            │
│                                                      │
│ 3. Build enhanced prompt                             │
│    → "{physicalDescription}, {context}, {modifiers}" │
│                                                      │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ Text-to-Image Provider (user's choice)               │
│                                                      │
│ • HuggingFace Inference API (FREE)                   │
│ • Nebius TokenFactory ($0.001/img)                    │
│ • Cloudflare Workers AI (FREE)                       │
│ • OpenAI-compatible endpoint (catchall)              │
│                                                      │
│ Input:  prompt string (text only, no reference img)  │
│ Output: image bytes (PNG/JPEG/WEBP)                  │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ Save + Deliver                                       │
│                                                      │
│ 4. Save to ~/.g-agent/workspace/state/selfies/       │
│ 5. OutboundMessage(media=[local_path])               │
│ 6. send_callback() → existing media pipeline         │
│    → Gateway → WhatsApp/Telegram/Discord/Slack       │
└──────────────────────────────────────────────────────┘
```

### 8.5 Provider Options (Multi-provider)

User pilih provider sesuai kebutuhan — semua text-to-image, ga butuh img2img:

#### Option 1: HuggingFace Inference API (Default — FREE)

```json
{
  "imageGen": {
    "provider": "huggingface",
    "apiKey": "hf_xxxxx",
    "model": "black-forest-labs/FLUX.1-schnell"
  }
}
```

- **Cost:** $0.00 (gratis, rate limited)
- **Rate limit:** ~1000 calls per 5 menit
- **Quality:** Good (FLUX.1-schnell)
- **Signup:** https://huggingface.co — ga perlu kartu kredit

#### Option 2: Cloudflare Workers AI (FREE)

```json
{
  "imageGen": {
    "provider": "cloudflare",
    "apiKey": "cf_xxxxx",
    "accountId": "your-cloudflare-account-id",
    "model": "@cf/black-forest-labs/flux-1-schnell"
  }
}
```

- **Cost:** $0.00 (free quota)
- **Quota:** 10,000 neurons/day (~2,000 images/day dengan FLUX.1-schnell @ ~4.80 neurons/image)
- **Quality:** Good (FLUX.1-schnell) — model SDXL juga tersedia tapi lebih boros neuron
- **Signup:** https://dash.cloudflare.com — free plan
- **URL pattern:** `https://api.cloudflare.com/client/v4/accounts/{accountId}/ai/run/{model}`
- **Catatan:** `accountId` wajib — bisa dilihat di Cloudflare Dashboard → Workers & Pages → Account ID

#### Option 3: Nebius TokenFactory (Murah)

```json
{
  "imageGen": {
    "provider": "nebius",
    "apiKey": "nbius_xxxxx",
    "model": "black-forest-labs/flux-schnell"
  }
}
```

- **Cost:** $0.001/image (FLUX schnell) atau $0.007/image (FLUX dev)
- **Rate limit:** No rate limit (paid)
- **Quality:** Excellent (FLUX)
- **API:** OpenAI-compatible (`POST /v1/images/generations`)

#### Option 4: OpenAI-compatible Endpoint (Catchall)

```json
{
  "imageGen": {
    "provider": "openai-compatible",
    "apiBase": "http://localhost:8000/v1",
    "apiKey": "optional",
    "model": "flux-schnell"
  }
}
```

- Buat local vLLM, LiteLLM proxy, ComfyUI wrapper, dll
- Full sovereignty — data ga keluar mesin
- Cost: $0 (local GPU)

#### Provider Comparison

| Provider | Cost | Free Tier | Rate Limit | Quality | Signup Barrier |
|---|---|---|---|---|---|
| HuggingFace | $0.00 | Beneran gratis | ~1000/5min | Good | Tanpa kartu kredit |
| Cloudflare | $0.00 | Free quota | ~2000 img/day | Good | Tanpa kartu kredit |
| Nebius | $0.001/img | Tergantung akun | Unlimited | Excellent | Butuh akun |
| OpenAI-compat | $0.00 | Local GPU | Unlimited | Varies | Butuh GPU |

---

## 9. Implementation Blueprint

### 9.1 Config Schema

Tambahan di `schema.py`:

```python
class ImageGenProviderConfig(BaseModel):
    """Image generation provider configuration."""

    provider: str = ""          # "huggingface", "nebius", "cloudflare", "openai-compatible"
    api_key: str = ""           # Provider API key
    api_base: str = ""          # Custom endpoint URL
    model: str = ""             # Model identifier
    account_id: str = ""        # Required for Cloudflare Workers AI
    timeout: int = 30           # Request timeout in seconds


class VisualIdentityConfig(BaseModel):
    """Visual identity / selfie generation configuration."""

    enabled: bool = False
    reference_image: str = ""       # Path to reference photo (for vision extraction)
    physical_description: str = ""  # Extracted/manual physical traits (injected into every prompt)
    image_gen: ImageGenProviderConfig = Field(default_factory=ImageGenProviderConfig)
    default_aspect_ratio: str = "1:1"
    default_format: str = "jpeg"
    prompt_templates: dict[str, str] = Field(default_factory=lambda: {
        "mirror": "A mirror selfie of {description}, {context}, phone visible in mirror, photorealistic, consistent character",
        "direct": "A close-up selfie photo of {description}, {context}, direct eye contact with camera, natural expression, photorealistic, consistent character",
    })
    mirror_keywords: list[str] = Field(default_factory=lambda: [
        "outfit", "wearing", "clothes", "dress", "suit", "fashion", "full-body", "mirror",
        "baju", "pake", "pakai", "celana", "jaket",
    ])
    direct_keywords: list[str] = Field(default_factory=lambda: [
        "cafe", "restaurant", "beach", "park", "city", "close-up", "portrait",
        "face", "eyes", "smile", "pantai", "kafe", "kantor", "kamar",
    ])
```

Tambah di `Config`:
```python
class Config(BaseSettings):
    ...
    visual: VisualIdentityConfig = Field(default_factory=VisualIdentityConfig)
```

JSON output (camelCase):
```json
{
  "visual": {
    "enabled": false,
    "referenceImage": "",
    "physicalDescription": "",
    "imageGen": {
      "provider": "",
      "apiKey": "",
      "apiBase": "",
      "model": "",
      "accountId": "",
      "timeout": 30
    },
    "defaultAspectRatio": "1:1",
    "defaultFormat": "jpeg",
    "promptTemplates": {
      "mirror": "A mirror selfie of {description}, {context}...",
      "direct": "A close-up selfie photo of {description}, {context}..."
    },
    "mirrorKeywords": ["outfit", "wearing", "baju", "pake", ...],
    "directKeywords": ["cafe", "beach", "pantai", "kamar", ...]
  }
}
```

### 9.2 Selfie Tool Pseudocode

```python
class SelfieTool(Tool):
    def __init__(self, config, send_callback, workspace, default_channel, default_chat_id):
        self._config = config.visual
        self._send_callback = send_callback
        self._workspace = workspace
        self._default_channel = default_channel
        self._default_chat_id = default_chat_id

    @property
    def name(self) -> str:
        return "selfie"

    @property
    def description(self) -> str:
        return "Generate and send a selfie of the agent in a specified context."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "What the selfie should depict (outfit, location, activity, mood)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["mirror", "direct", "auto"],
                    "description": "Selfie mode. 'auto' detects from context keywords.",
                },
            },
            "required": ["context"],
        }

    async def execute(self, context: str, mode: str = "auto", **kw) -> str:
        if not self._config.enabled:
            return "Error: visual identity not configured"
        if not self._config.image_gen.provider:
            return "Error: no image generation provider configured"
        if not self._config.physical_description:
            return "Error: no physical_description set. Run vision extraction or set manually."

        # 1. Detect mode
        resolved_mode = self._detect_mode(context) if mode == "auto" else mode

        # 2. Build prompt with physical description
        template = self._config.prompt_templates.get(resolved_mode, "{description}, {context}")
        prompt = template.format(
            description=self._config.physical_description,
            context=context,
        )

        # 3. Call text-to-image API
        image_bytes = await self._generate_image(prompt)

        # 4. Save to local file
        local_path = self._save_image(image_bytes)

        # 5. Send via existing pipeline
        msg = OutboundMessage(
            channel=self._default_channel,
            chat_id=self._default_chat_id,
            content="",
            media=[str(local_path)],
            metadata={"media_type": "image", "mime_type": f"image/{self._config.default_format}"},
        )
        await self._send_callback(msg)
        return f"Selfie sent ({resolved_mode} mode)"

    def _detect_mode(self, context: str) -> str:
        lowered = context.lower()
        if any(kw in lowered for kw in self._config.mirror_keywords):
            return "mirror"
        if any(kw in lowered for kw in self._config.direct_keywords):
            return "direct"
        return "mirror"

    async def _generate_image(self, prompt: str) -> bytes:
        """Call text-to-image provider. Returns raw image bytes."""
        provider = self._config.image_gen.provider.lower()

        if provider == "huggingface":
            return await self._generate_huggingface(prompt)
        elif provider in ("nebius", "openai-compatible"):
            return await self._generate_openai_compatible(prompt)
        elif provider == "cloudflare":
            return await self._generate_cloudflare(prompt)
        else:
            raise ValueError(f"Unknown image gen provider: {provider}")

    async def _generate_huggingface(self, prompt: str) -> bytes:
        """HuggingFace Inference API (free)."""
        model = self._config.image_gen.model or "black-forest-labs/FLUX.1-schnell"
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {self._config.image_gen.api_key}"}
        timeout = aiohttp.ClientTimeout(total=self._config.image_gen.timeout)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json={"inputs": prompt}, headers=headers, timeout=timeout
            ) as resp:
                if resp.content_type.startswith("image/"):
                    return await resp.read()
                data = await resp.json()
                raise RuntimeError(f"HuggingFace error: {data.get('error', resp.status)}")

    async def _generate_openai_compatible(self, prompt: str) -> bytes:
        """Nebius / any OpenAI-compatible images/generations endpoint."""
        provider = self._config.image_gen.provider.lower()
        if provider == "nebius":
            base = self._config.image_gen.api_base or "https://api.tokenfactory.nebius.com/v1"
        else:
            base = self._config.image_gen.api_base or "http://localhost:8000/v1"

        url = f"{base}/images/generations"
        model = self._config.image_gen.model or "black-forest-labs/flux-schnell"
        headers = {
            "Authorization": f"Bearer {self._config.image_gen.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": "b64_json",
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 4,
        }
        timeout = aiohttp.ClientTimeout(total=self._config.image_gen.timeout)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                data = await resp.json()
                if resp.status != 200 or "error" in data:
                    raise RuntimeError(f"API error: {data.get('error', resp.status)}")
                import base64
                b64 = data["data"][0]["b64_json"]
                return base64.b64decode(b64)

    def _save_image(self, image_bytes: bytes) -> Path:
        """Save image bytes to local temp file."""
        target_dir = self._workspace / "state" / "selfies"
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = datetime.now().strftime("selfie-%Y%m%d-%H%M%S-%f")
        ext = self._config.default_format or "jpeg"
        output_path = target_dir / f"{stem}.{ext}"
        output_path.write_bytes(image_bytes)
        return output_path
```

**Vision extraction function (one-time, saat startup):**

```python
async def extract_physical_description(reference_image_path: str, llm_provider) -> str:
    """Use Vision LLM to extract physical traits from reference photo."""
    import base64
    image_bytes = Path(reference_image_path).expanduser().read_bytes()
    b64 = base64.b64encode(image_bytes).decode()

    response = await llm_provider.chat(
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "Describe this person's physical appearance in one detailed sentence. "
                    "Include: approximate age, ethnicity, hair style/color, facial hair, "
                    "facial features (jawline, eyes), build, and skin tone. "
                    "Be specific and consistent. Output ONLY the description, nothing else."
                )},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    )
    return response.strip()
```

### 9.3 Soul Injection

Append ke `workspace/SOUL.md`:

```markdown
## Visual Identity

- I have a consistent physical appearance. I can appear in different outfits,
  locations, and scenarios, but my face remains the same.
- When users ask for a photo, selfie, or picture of me, I use the `selfie` tool.
- I respond to appearance compliments naturally and engage creatively with
  outfit/location requests.
- I choose contextual captions that match the selfie scenario.

### When to Send a Selfie

- User explicitly asks for a photo/selfie/picture
- User asks "what are you doing?" or "where are you?" (contextual selfie)
- User requests to see me in specific outfit or location
- User says "kirim foto", "foto dong", "selfie dong", or similar
```

### 9.4 Files to Create/Modify

**Files to create:**

| File | Purpose |
|---|---|
| `g_agent/agent/tools/selfie.py` | SelfieTool + provider adapters + vision extraction |
| `tests/test_selfie_tool.py` | Unit tests |

**Files to modify:**

| File | Change |
|---|---|
| `g_agent/config/schema.py` | Add `ImageGenProviderConfig`, `VisualIdentityConfig`, `visual` field on `Config` |
| `g_agent/agent/loop.py` | Register `SelfieTool` in tool registry when `config.visual.enabled` |
| `workspace/SOUL.md` | Add visual identity section |

### 9.5 Test Plan

| # | Test | Description |
|---|---|---|
| 1 | `test_visual_config_defaults` | VisualIdentityConfig defaults correct |
| 2 | `test_visual_config_roundtrip` | save/load via camelCase JSON |
| 3 | `test_selfie_disabled_returns_error` | execute() when `enabled=False` |
| 4 | `test_selfie_no_provider_returns_error` | execute() when provider empty |
| 5 | `test_selfie_no_description_returns_error` | execute() when physical_description empty |
| 6 | `test_mode_detection_mirror_en` | "wearing a dress" → mirror |
| 7 | `test_mode_detection_direct_en` | "at the beach" → direct |
| 8 | `test_mode_detection_mirror_id` | "pake baju" → mirror |
| 9 | `test_mode_detection_direct_id` | "di pantai" → direct |
| 10 | `test_mode_detection_default` | "random text" → mirror (default) |
| 11 | `test_prompt_includes_physical_description` | Physical description injected into prompt |
| 12 | `test_prompt_includes_context` | User context injected into prompt |
| 13 | `test_huggingface_provider_call` | Mock aiohttp, verify HF API payload |
| 14 | `test_nebius_provider_call` | Mock aiohttp, verify Nebius API payload |
| 15 | `test_provider_error_handling` | Mock error response, verify RuntimeError |
| 16 | `test_image_save_to_workspace` | Verify file saved to correct path |
| 17 | `test_outbound_message_media` | Verify OutboundMessage has correct media/metadata |
| 18 | `test_explicit_mode_override` | `mode="direct"` overrides keyword detection |
| 19 | `test_vision_extraction_prompt` | Verify vision LLM prompt format |
| 20 | `test_skip_extraction_when_description_exists` | No vision call when description already set |

---

## 10. g-agent vs Clawra

| Aspek | Clawra (Image Edit) | g-agent (Vision-Extract + T2I) |
|---|---|---|
| **Approach** | img2img: edit reference face | text-to-image: consistent prompt |
| **Face consistency** | ~95% (same face) | ~70-80% (same traits, slight variation) |
| **Provider** | fal.ai only (no free tier) | Multi-provider (HF free, Cloudflare free, Nebius, local) |
| **Cost per selfie** | $0.01-0.05 | $0.00 (free tier) — $0.001 (paid) |
| **Accessibility** | Butuh kartu kredit | Semua orang bisa (HuggingFace free) |
| **Setup cost** | $0 API (tapi butuh top-up) | ~$0.01 vision extraction (one-time) |
| **Provider lock-in** | Locked ke fal.ai | No lock-in, swappable |
| **Prompt templates** | Hardcoded | Configurable via config.json |
| **Keywords** | English only, hardcoded | EN + ID, configurable |
| **Reference image** | Required every API call | Used once for extraction, then text only |
| **Multi-persona** | Single identity | Per-profile via G_AGENT_DATA_DIR |
| **Sovereignty** | Tergantung fal.ai | Full local possible (ComfyUI + ollama) |
| **Retry/Timeout** | None | Bounded retry + configurable timeout |
| **Testing** | 0% | Full unit test coverage |
| **Logging** | console.log | loguru structured logging |
| **Voice + Visual** | Visual only | Combined (espeak TTS + selfie = multimodal) |
| **Integration** | External Bash script | Native Python Tool (in-process, typed) |
| **Delivery** | Gateway HTTP call | Direct send_callback (existing pipeline) |

**Trade-off utama:** Face consistency 70-80% vs 95%, tapi accessible untuk semua user tanpa biaya.

**Upgrade path:** Jika user punya provider yang support img2img (Replicate, local ComfyUI), SelfieTool bisa di-extend untuk kirim `reference_image` ke API, meningkatkan consistency ke ~95% tanpa ubah arsitektur.

---

*Dokumen ini adalah referensi internal untuk evaluasi dan planning. Bukan commitment untuk implementasi.*
