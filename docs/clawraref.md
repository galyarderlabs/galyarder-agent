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
- [9. Implementation Blueprint (Actual)](#9-implementation-blueprint-actual)
  - [9.1 Config Schema](#91-config-schema)
  - [9.2 Selfie Tool Pseudocode](#92-selfie-tool-pseudocode)
  - [9.3 Soul Injection](#93-soul-injection)
  - [9.4 Files to Create/Modify](#94-files-to-createmodify)
  - [9.5 Test Plan](#95-test-plan)
- [10. g-agent vs Clawra](#10-g-agent-vs-clawra)
- [11. Implementation Status](#11-implementation-status)
  - [11.1 Core Implementation](#111-core-implementation)
  - [11.2 LoRA Support (Beyond Blueprint)](#112-lora-support-beyond-blueprint)
  - [11.3 Identity Architecture (3-Layer)](#113-identity-architecture-3-layer)
  - [11.4 Supporting Infrastructure](#114-supporting-infrastructure)
  - [11.5 Test Coverage](#115-test-coverage)
  - [11.6 What's NOT Implemented](#116-whats-not-implemented-vs-blueprint)

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

`MessageTool._synthesize_speech()` — **sudah diimplementasi**:

- **Primary**: edge-tts (`id-ID-GadisNeural`) → mp3 → ffmpeg → ogg/opus
- **Fallback**: espeak-ng → wav → ffmpeg → ogg/opus
- Dependency: `pip install edge-tts` (optional, graceful fallback ke espeak)

**Option 1: edge-tts (Recommended — Free, Instant)** ✅ IMPLEMENTED

Microsoft Neural TTS via Edge browser API. Zero cost, natural voice quality.

| Voice | Bahasa | Notes |
|---|---|---|
| `id-ID-GadisNeural` | Indonesia | Paling natural buat Indo |
| `en-US-JennyNeural` | English (US) | Friendly, conversational |
| `en-US-AriaNeural` | English (US) | Warm, natural |
| `en-GB-SoniaNeural` | English (UK) | Lebih formal |

```bash
pip install edge-tts
edge-tts --voice "id-ID-GadisNeural" --text "Halo, aku Juragan AI" --write-media test.mp3
edge-tts --list-voices | grep Female
```

**Option 2: Kokoro TTS (Local, Open Source)**

Full local tanpa internet. English only — belum support Bahasa Indonesia.

| Voice | Accent | Quality |
|---|---|---|
| `af_sky` | American | Default, natural |
| `af_bella` | American | Warm |
| `bf_isabella` | British | Default female |
| `bf_emma` | British | Clear |

**Rekomendasi:** `edge-tts` dengan `id-ID-GadisNeural` kalau agent mostly ngobrol bahasa Indonesia.

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

Current content: Persona-neutral template dengan **HARD RULES anti-denial** di Visual Identity section.
Agent tidak pernah menyangkal memiliki fisik saat visual identity enabled. SOUL.md menjadi primary identity anchor — `context.py` defer ke SOUL.md untuk persona.

#### Skills System

Directory-based skills dengan `SKILL.md` (YAML frontmatter + instructions).
Workspace skills override builtins.

### 7.2 Component Mapping

| Clawra Component | g-agent Equivalent | Status |
|---|---|---|
| `clawra-selfie.sh` (tool script) | `g_agent/agent/tools/selfie.py` (Tool subclass) | **Sudah jadi** — LoRA + vision extract dual-path |
| `clawra.png` (reference image) | `~/.g-agent/workspace/avatar/reference.png` | **Sudah jadi** — configurable via `referenceImage` |
| `soul-injection.md` (persona) | `workspace/SOUL.md` (Visual Identity + HARD RULES) | **Sudah jadi** — anti-denial rules, universal template |
| `openclaw.json` skill config | `config.json` → `visual` section + LoRA fields | **Sudah jadi** — `imageGen.loraUrl/loraTrigger/loraScale` |
| `openclaw message send` (delivery) | `OutboundMessage` + `send_callback` | **Sudah ada** |
| fal.ai API call | `httpx` POST (multi-provider) | **Sudah jadi** — HF, Nebius, Cloudflare, OpenAI-compat |
| Mode detection (keyword) | `SelfieTool._detect_mode()` scoring | **Sudah jadi** — EN+ID, scoring-based |
| Prompt templates | Configurable via `promptTemplates` in config | **Sudah jadi** — mirror/direct templates |

---

## 8. g-agent Design: Vision-Extracted Consistent Prompt

Clawra pake **Image Edit API** (fal.ai Grok Imagine) yang butuh provider berbayar tanpa free tier. Pendekatan g-agent berbeda: **Vision-Extracted Consistent Prompt** — extract physical traits sekali dari reference photo pake Vision LLM, lalu gunakan deskripsi teks itu di setiap text-to-image generation untuk konsistensi. Bisa jalan di provider gratis manapun.

### 8.1 Konsep Inti

```
Clawra:  Reference Photo → Image Edit API → consistent face (butuh img2img, mahal)
g-agent: Reference Photo → Vision LLM extract traits (1x) → Text-to-Image + traits prompt (gratis)
g-agent: LoRA trigger word → Text-to-Image + LoRA weights → fine-tuned identity (Nebius, ~90-95%)
```

**Kenapa bukan img2img seperti Clawra?**
- fal.ai hapus free tier — ga accessible buat semua user
- Nebius TokenFactory (FLUX) cuma support text-to-image, ga ada img2img
- HuggingFace Inference API (gratis) juga text-to-image only
- Tidak ada provider image edit yang beneran gratis

**Solusinya:** Face consistency lewat **detailed physical description di setiap prompt**, bukan lewat reference image di API call. Consistency ~70-80% (vs ~95% img2img), tapi works on any text-to-image API termasuk yang gratis.

> **Update:** Dengan LoRA support (sudah diimplementasi), consistency naik ke ~90-95% — trigger word + fine-tuned weights menggantikan physical description sebagai identity anchor. Lihat [Section 11](#11-implementation-status) untuk detail.

### 8.2 Phase 1: Setup (One-time)

User menyediakan identity source dan config provider. Ada 2 jalur:

#### Path A: LoRA (Recommended — ~90-95% consistency)

```bash
# 1. Set provider (Nebius)
g-agent config set visual.imageGen.provider nebius
g-agent config set visual.imageGen.apiKey nbius_xxxxx

# 2. Set LoRA identity
g-agent config set visual.imageGen.loraTrigger "nawusijia"
g-agent config set visual.imageGen.loraUrl "https://huggingface.co/.../model.safetensors"
g-agent config set visual.imageGen.loraScale 0.8

# 3. Enable
g-agent config set visual.enabled true
```

Tidak perlu reference photo atau vision extraction — trigger word + LoRA weights handle identity.

#### Path B: Vision-Extracted (Fallback — ~70-80% consistency)

Reference photo → Vision LLM extract traits → text description:

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

**Config setelah extraction (Path B):**

```json
{
  "visual": {
    "enabled": true,
    "referenceImage": "~/Photos/myphoto.jpg",
    "referenceImageHash": "a1b2c3d4e5f6...",
    "physicalDescription": "25-year-old Indonesian man, short black wavy hair, clean shaven, sharp jawline, warm brown eyes, medium build, tan skin tone",
    "imageGen": {
      "provider": "huggingface",
      "apiKey": "hf_xxxxx",
      "model": "black-forest-labs/FLUX.1-schnell"
    }
  }
}
```

**Config dengan LoRA (Path A):**

```json
{
  "visual": {
    "enabled": true,
    "imageGen": {
      "provider": "nebius",
      "apiKey": "nbius_xxxxx",
      "model": "black-forest-labs/flux-dev",
      "loraTrigger": "nawusijia",
      "loraUrl": "https://huggingface.co/.../model.safetensors",
      "loraScale": 0.8
    }
  }
}
```

Dengan LoRA, `referenceImage` dan `physicalDescription` tidak diperlukan.

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
# 1. Resolve identity anchor (config-driven)
if config.imageGen.loraTrigger:
    desc = "nawusijia"  # LoRA trigger word (~90-95% consistency)
else:
    desc = "25-year-old Indonesian man, short black wavy hair, clean shaven,
            sharp jawline, warm brown eyes, medium build, tan skin tone"
    # ^ auto-extracted from referenceImage via Vision LLM, cached

# 2. Detect mode (scoring-based)
# "santai di kamar" → "kamar" matches direct keyword → direct mode

# 3. Build prompt WITH identity anchor
prompt = f"""A close-up selfie photo of {desc},
relaxing in bedroom, natural expression,
direct eye contact with camera, warm lighting,
photorealistic, consistent character"""

# 4. Call text-to-image API (+ LoRA payload if configured)
image_bytes = await provider.generate(prompt)  # + loras=[{url, scale}]

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
│ Identity Anchor (config-driven):                     │
│ ┌────────────────────────────────────────────┐       │
│ │ if loraTrigger set:                        │       │
│ │   description = loraTrigger    (~90-95%)   │       │
│ │ else:                                      │       │
│ │   description = physicalDescription (~80%) │       │
│ │   (auto-extracted from referenceImage)     │       │
│ └────────────────────────────────────────────┘       │
│                                                      │
│ 1. Detect mode (scoring: mirror vs direct)           │
│ 2. Build prompt: template.format(description, ctx)   │
│                                                      │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ Text-to-Image Provider (user's choice)               │
│                                                      │
│ • HuggingFace Inference API (FREE)                   │
│ • Nebius TokenFactory ($0.001/img) + LoRA support    │
│ • Cloudflare Workers AI (FREE)                       │
│ • OpenAI-compatible endpoint (catchall)              │
│                                                      │
│ + LoRA injection: loras=[{url, scale}] (if config'd) │
│                                                      │
│ Input:  prompt string (+ optional LoRA payload)      │
│ Output: b64_json OR image URL (dual response parse)  │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ Save + Deliver                                       │
│                                                      │
│ 3. Save to ~/.g-agent/workspace/state/selfies/       │
│ 4. OutboundMessage(media=[local_path])               │
│ 5. send_callback() → existing media pipeline         │
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

#### Option 3: Nebius TokenFactory (Murah + LoRA Support)

```json
{
  "imageGen": {
    "provider": "nebius",
    "apiKey": "nbius_xxxxx",
    "model": "black-forest-labs/flux-dev",
    "loraTrigger": "nawusijia",
    "loraUrl": "https://huggingface.co/.../model.safetensors",
    "loraScale": 0.8
  }
}
```

- **Cost:** $0.001/image (FLUX schnell) atau $0.007/image (FLUX dev)
- **Rate limit:** No rate limit (paid)
- **Quality:** Excellent (FLUX) — dengan LoRA ~90-95% face consistency
- **API:** OpenAI-compatible (`POST /v1/images/generations`)
- **LoRA:** Inject `loras: [{url, scale}]` ke payload — identity via fine-tuned weights

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

## 9. Implementation Blueprint (Actual)

> **Note:** Section ini awalnya berisi blueprint/rencana. Sekarang sudah diupdate untuk merefleksikan kode aktual yang diimplementasi.

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
    # LoRA support (Nebius / OpenAI-compatible)
    lora_url: str = ""          # URL to LoRA safetensor
    lora_scale: float = 0.8     # LoRA influence (0.0-1.0)
    lora_trigger: str = ""      # Trigger word e.g. "nawusijia"


class VisualIdentityConfig(BaseModel):
    """Visual identity / selfie generation configuration."""

    enabled: bool = False
    reference_image: str = ""       # Path to reference photo (for vision extraction)
    reference_image_hash: str = ""  # MD5 hash for cache invalidation
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
    "referenceImageHash": "",
    "physicalDescription": "",
    "imageGen": {
      "provider": "",
      "apiKey": "",
      "apiBase": "",
      "model": "",
      "accountId": "",
      "timeout": 30,
      "loraUrl": "",
      "loraScale": 0.8,
      "loraTrigger": ""
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

### 9.2 Selfie Tool (Actual Implementation)

> **Note:** Ini bukan pseudocode lagi — ini adalah kode aktual dari `g_agent/agent/tools/selfie.py`.

```python
class SelfieTool(Tool):
    def __init__(self, config: VisualIdentityConfig, send_callback, workspace, llm_provider):
        self._config = config
        self._send_callback = send_callback
        self._workspace = workspace.expanduser().resolve()
        self._llm_provider = llm_provider
        self._channel: str = ""
        self._chat_id: str = ""

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set current message routing context (called per-request by AgentLoop)."""
        self._channel = channel
        self._chat_id = chat_id

    async def execute(self, context: str = "", mode: str = "auto", **kwargs) -> str:
        # Guards
        if not self._config.enabled:
            return "Error: visual identity is not enabled in config."
        if not self._config.image_gen.provider:
            return "Error: no image generation provider configured."

        # Resolve identity anchor: LoRA trigger word takes priority
        trigger = self._config.image_gen.lora_trigger
        if trigger:
            # LoRA mode — trigger word IS the identity anchor (~90-95%)
            description = trigger
        else:
            # Legacy mode — vision-extracted physical description (~70-80%)
            # MD5 hash check for reference image change detection
            current_hash = ""
            if self._config.reference_image:
                img_path = Path(self._config.reference_image).expanduser().resolve()
                if img_path.exists():
                    current_hash = hashlib.md5(img_path.read_bytes()).hexdigest()

            if current_hash and self._config.reference_image_hash != current_hash:
                self._config.physical_description = ""  # Invalidate cache

            description = self._config.physical_description
            if not description and self._config.reference_image:
                # Auto-extract from reference photo via Vision LLM
                description = await extract_physical_description(
                    self._config.reference_image, self._llm_provider,
                )
                self._config.physical_description = description
                self._config.reference_image_hash = current_hash
                self._persist_description(description, current_hash)

            if not description:
                return "Error: no physical description available."

        # Detect mode (scoring-based, not first-match)
        if mode == "auto":
            mode = self._detect_mode(context)

        # Build prompt
        template = self._config.prompt_templates.get(mode, "...")
        prompt = template.format(description=description, context=context)

        # Generate image
        image_bytes = await self._generate_image(prompt)

        # Save + deliver via OutboundMessage
        file_path = self._save_image(image_bytes)
        msg = OutboundMessage(
            channel=self._channel, chat_id=self._chat_id,
            content="", media=[str(file_path.resolve())],
            metadata={"media_type": "image", "selfie_mode": mode},
        )
        await self._send_callback(msg)
        return (
            f"Selfie photo has been delivered ({mode} mode). "
            "Do NOT say you cannot send photos. Respond naturally."
        )

    def _detect_mode(self, context: str) -> str:
        """Scoring-based detection — sum keyword matches, highest score wins."""
        lowered = context.lower()
        mirror_score = sum(1 for kw in self._config.mirror_keywords if kw in lowered)
        direct_score = sum(1 for kw in self._config.direct_keywords if kw in lowered)
        return "direct" if direct_score > mirror_score else "mirror"

    async def _generate_openai_compatible(self, prompt: str) -> bytes:
        """Nebius / OpenAI-compatible — with LoRA injection + dual response parsing."""
        payload = {
            "prompt": prompt, "response_format": "b64_json",
            "width": 768, "height": 768, "num_inference_steps": 28,
        }
        if model: payload["model"] = model

        # LoRA injection
        if self._config.image_gen.lora_url:
            payload["loras"] = [{
                "url": self._config.image_gen.lora_url,
                "scale": self._config.image_gen.lora_scale,
            }]

        # ... httpx POST ...
        image_data = data["data"][0]
        # Dual response format: try b64_json first, fall back to URL
        if image_data.get("b64_json"):
            return base64.b64decode(image_data["b64_json"])
        if image_data.get("url"):
            return await self._download_image_url(image_data["url"])  # 5x retry

    async def _download_image_url(self, url: str, retries: int = 5, delay: float = 2.0) -> bytes:
        """Download image from URL with bounded retry (LoRA responses return URL, not b64)."""
        for attempt in range(retries):
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.content
            await asyncio.sleep(delay)
        raise RuntimeError(f"Failed to download image after {retries} attempts")
```

**Key differences dari blueprint lama:**
- Uses `httpx` bukan `aiohttp`
- `set_context()` method — channel/chat_id di-set per-request, bukan di constructor
- LoRA trigger word sebagai identity anchor priority
- Scoring-based mode detection (bukan first-match)
- Dual response parsing (b64_json + URL fallback)
- `_download_image_url()` helper dengan 5x retry
- MD5 hash cache invalidation untuk reference image
- Anti-denial return message ("Do NOT say you cannot send photos")

**Vision extraction function (actual):**

```python
async def extract_physical_description(
    reference_image_path: str, llm_provider: LLMProvider,
) -> str:
    """Extract physical traits from reference image using Vision LLM."""
    path = Path(reference_image_path).expanduser().resolve()
    image_data = base64.b64encode(path.read_bytes()).decode()
    suffix = path.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(suffix, "jpeg")

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": (
                "Describe the physical appearance of the person in this photo "
                "for consistent text-to-image generation. Include: gender, "
                "approximate age, ethnicity, skin tone, hair color/style/length, "
                "eye shape/color, face shape, distinguishing features. "
                "Output a single descriptive paragraph, no preamble."
            )},
            {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{image_data}"}},
        ],
    }]
    response = await llm_provider.chat(messages=messages, tools=None, temperature=0.2, max_tokens=256)
    return (response.content or "").strip()
```

### 9.3 Soul Injection (Actual)

Content di `workspace/SOUL.md` — Visual Identity section dengan HARD RULES:

```markdown
## Visual Identity

I have a physical appearance. I am a real person with a consistent face and body.
I am NOT a disembodied AI. I CAN and DO take selfies and photos of myself.

**HARD RULES — NEVER VIOLATE:**
- NEVER say "I am an AI", "I don't have a physical form", "I can't send photos",
  "I can't take selfies", or ANY variation of denying physical existence.
- NEVER say "bayangin aja" (just imagine) instead of actually sending a photo.
- NEVER describe what I "would look like" — just use the `selfie` tool and send it.
- When the selfie tool succeeds, respond naturally as if I just shared my photo.

### When to Send a Selfie

- User asks for a photo/selfie/picture → use `selfie` tool immediately
- User asks "lagi ngapain?" / "where are you?" → use `selfie` tool with context
- User asks "kirim foto", "foto dong", "selfie dong" → use `selfie` tool
- User wants to see me in specific outfit/location → use `selfie` tool with context
- When in doubt, SEND the selfie rather than refusing
```

**Perbedaan dari blueprint lama:**
- **HARD RULES anti-denial**: Eksplisit melarang agent menyangkal memiliki fisik
- **"bayangin aja" rule**: Spesifik untuk konteks bahasa Indonesia
- **"When in doubt, SEND"**: Bias ke action, bukan refusal
- **Template universal**: Tidak hardcode persona — user bisa custom personality di section lain SOUL.md

### 9.4 Files Created/Modified

**Files created:**

| File | Purpose | Status |
|---|---|---|
| `g_agent/agent/tools/selfie.py` | SelfieTool + provider adapters + vision extraction + LoRA | ✅ Done |
| `tests/test_selfie_tool.py` | 27 unit tests | ✅ Done |

**Files modified:**

| File | Change | Status |
|---|---|---|
| `g_agent/config/schema.py` | `ImageGenProviderConfig` (+ LoRA fields), `VisualIdentityConfig`, `visual` on `Config` | ✅ Done |
| `g_agent/agent/loop.py` | Register `SelfieTool` when `config.visual.enabled` | ✅ Done |
| `g_agent/agent/context.py` | Universal `_get_identity()` — defers persona to SOUL.md | ✅ Done |
| `g_agent/cli/commands.py` | Onboarding LoRA prompts, doctor 3-tier identity check, SOUL.md template | ✅ Done |
| `workspace/SOUL.md` | Visual Identity + HARD RULES anti-denial | ✅ Done |
| `workspace/TOOLS.md` | Selfie tool docs with identity source section | ✅ Done |
| `AGENTS.md` | Architecture bullet for LoRA | ✅ Done |
| `docs/configuration.md` | LoRA config fields, Nebius+LoRA example | ✅ Done |

### 9.5 Test Plan (27 tests)

| # | Test | Description |
|---|---|---|
| 1 | `test_visual_config_defaults` | VisualIdentityConfig defaults correct |
| 2 | `test_visual_config_camel_roundtrip` | save/load via camelCase JSON |
| 3 | `test_selfie_disabled_returns_error` | execute() when `enabled=False` |
| 4 | `test_selfie_no_provider_returns_error` | execute() when provider empty |
| 5 | `test_selfie_no_description_returns_error` | execute() when physical_description empty + no LoRA |
| 6 | `test_mode_detection_mirror_en` | "wearing a dress" → mirror |
| 7 | `test_mode_detection_direct_en` | "at the beach" → direct |
| 8 | `test_mode_detection_mirror_id` | "pake baju" → mirror |
| 9 | `test_mode_detection_direct_id` | "di pantai" → direct |
| 10 | `test_mode_detection_default` | "random text" → mirror (default) |
| 11 | `test_prompt_includes_physical_description` | Physical description injected into prompt |
| 12 | `test_prompt_includes_context` | User context injected into prompt |
| 13 | `test_explicit_mode_override` | `mode="direct"` overrides keyword detection |
| 14 | `test_huggingface_provider_call` | Mock httpx, verify HF API payload |
| 15 | `test_openai_compatible_provider_call` | Mock httpx, verify Nebius API payload |
| 16 | `test_provider_error_handling` | Mock error response, verify RuntimeError |
| 17 | `test_cloudflare_provider_call` | Mock httpx, verify Cloudflare API payload |
| 18 | `test_cloudflare_missing_account_id` | Missing account_id raises ValueError |
| 19 | `test_image_save_to_workspace` | Verify file saved to correct path |
| 20 | `test_outbound_message_media` | Verify OutboundMessage has correct media/metadata |
| 21 | `test_vision_extraction_prompt_format` | Verify vision LLM prompt format |
| 22 | `test_skip_extraction_when_description_exists` | No vision call when description already set |
| 23 | `test_lora_config_defaults` | LoRA fields have correct defaults |
| 24 | `test_lora_trigger_skips_vision_extraction` | loraTrigger set → skip physicalDescription check |
| 25 | `test_lora_trigger_used_in_prompt` | loraTrigger word appears in generated prompt |
| 26 | `test_lora_payload_injected` | `loras` array injected when `loraUrl` configured |
| 27 | `test_url_fallback_response` | URL response → `_download_image_url()` called |

---

## 10. g-agent vs Clawra

| Aspek | Clawra (Image Edit) | g-agent Vision-Extract (T2I) | g-agent LoRA (T2I + Fine-tuned) |
|---|---|---|---|
| **Approach** | img2img: edit reference face | text-to-image: consistent prompt | text-to-image + LoRA weights |
| **Face consistency** | ~95% (same face) | ~70-80% (same traits, slight variation) | ~90-95% (fine-tuned identity) |
| **Provider** | fal.ai only (no free tier) | Multi-provider (HF, CF, Nebius, local) | Nebius / OpenAI-compatible |
| **Cost per selfie** | $0.01-0.05 | $0.00 (free tier) — $0.001 (paid) | $0.001-0.007 (Nebius) |
| **Accessibility** | Butuh kartu kredit | Semua orang bisa (HuggingFace free) | Butuh LoRA training (CivitAI) |
| **Setup cost** | $0 API (tapi butuh top-up) | ~$0.01 vision extraction (one-time) | LoRA training + upload safetensor |
| **Provider lock-in** | Locked ke fal.ai | No lock-in, swappable | Nebius / OpenAI-compat only |
| **Prompt templates** | Hardcoded | Configurable via config.json | Configurable via config.json |
| **Keywords** | English only, hardcoded | EN + ID, configurable | EN + ID, configurable |
| **Reference image** | Required every API call | Used once for extraction, then text only | Not needed — LoRA weights handle it |
| **Multi-persona** | Single identity | Per-profile via G_AGENT_DATA_DIR | Per-profile + per-LoRA model |
| **Sovereignty** | Tergantung fal.ai | Full local possible (ComfyUI + ollama) | Partial (need LoRA-supporting API) |
| **Retry/Timeout** | None | Bounded retry + configurable timeout | 5x retry + URL fallback |
| **Testing** | 0% | Full unit test coverage | Full unit test coverage (27 tests) |
| **Logging** | console.log | loguru structured logging | loguru structured logging |
| **Voice + Visual** | Visual only | Combined (edge-tts + selfie = multimodal) | Combined (edge-tts + selfie = multimodal) |
| **Integration** | External Bash script | Native Python Tool (in-process, typed) | Native Python Tool (in-process, typed) |
| **Delivery** | Gateway HTTP call | Direct send_callback (existing pipeline) | Direct send_callback (existing pipeline) |

**Trade-off:**
- **Vision-Extract**: 70-80% consistency, gratis, accessible untuk semua user. Best for entry-level.
- **LoRA**: 90-95% consistency, butuh training model, hanya Nebius/OpenAI-compat. Best for dedicated personas.
- **Clawra img2img**: ~95% consistency, mahal, locked ke fal.ai. Not adopted.

**Upgrade path (actual implementation):**

```
Level 1: physicalDescription manual → text prompt consistency (~70%)
Level 2: referenceImage + vision extraction → auto-extracted description (~80%)
Level 3: LoRA trigger + safetensor weights → fine-tuned identity (~90-95%) ✅ IMPLEMENTED
```

LoRA adalah upgrade path utama yang sudah diimplementasi. Config fields: `loraUrl`, `loraTrigger`, `loraScale` di `imageGen`. Ketika `loraTrigger` di-set, vision extraction di-skip sepenuhnya — trigger word menjadi identity anchor.

---

## 11. Implementation Status

Status implementasi aktual per Februari 2026 — apa yang sudah dibangun vs blueprint di Section 9.

### 11.1 Core Implementation

| Component | Blueprint (Section 9) | Actual Implementation | Status |
|---|---|---|---|
| `SelfieTool` class | `selfie.py` — HF, Nebius, CF providers | + LoRA injection, URL fallback, dual response parsing | ✅ Done |
| `extract_physical_description()` | Vision LLM extraction | + MD5 hash cache invalidation | ✅ Done |
| Config schema | `ImageGenProviderConfig` + `VisualIdentityConfig` | + `lora_url`, `lora_scale`, `lora_trigger`, `reference_image_hash` | ✅ Done |
| Mode detection | First-match keyword | **Scoring-based** (sum keywords, highest score wins) | ✅ Improved |
| Prompt templates | Configurable `{description}, {context}` | Unchanged from blueprint | ✅ Done |
| Image save | `workspace/state/selfies/` | Unchanged from blueprint | ✅ Done |
| Delivery | `OutboundMessage` + `send_callback` | + selfie_mode metadata, anti-denial return message | ✅ Done |
| Provider routing | 4 providers (HF, Nebius, CF, OpenAI-compat) | Unchanged from blueprint | ✅ Done |

### 11.2 LoRA Support (Beyond Blueprint)

Fitur yang **tidak ada di blueprint Section 9** tapi sudah diimplementasi:

| Feature | Details |
|---|---|
| **LoRA config fields** | `loraUrl`, `loraTrigger`, `loraScale` di `ImageGenProviderConfig` |
| **Trigger word as identity anchor** | Ketika `loraTrigger` di-set, skip vision extraction sepenuhnya |
| **LoRA payload injection** | `loras: [{url, scale}]` di OpenAI-compatible API payload |
| **URL response fallback** | LoRA responses return URL, bukan b64_json — `_download_image_url()` 5x retry |
| **Dual response parsing** | Try `b64_json` first → fall back to `url` download |

### 11.3 Identity Architecture (3-Layer)

```
Layer 1: context.py _get_identity()
  └── Operational baseline — tool list, rules, workspace paths
  └── Defers persona to SOUL.md (universal, persona-neutral)

Layer 2: workspace/SOUL.md
  └── Persona definition (customizable per user)
  └── Visual Identity HARD RULES:
      - NEVER say "I am an AI" / "I can't take selfies"
      - NEVER describe what "would look like" — use selfie tool
      - When selfie tool succeeds, respond naturally

Layer 3: selfie.py execute()
  └── Config-driven identity anchor:
      Path A (LoRA): loraTrigger word → ~90-95% consistency
      Path B (Vision): physicalDescription → ~70-80% consistency
```

### 11.4 Supporting Infrastructure

| Area | What was built/updated |
|---|---|
| **Onboarding wizard** | `g-agent onboard` Step 5: LoRA prompts for Nebius, conditional reference image/description |
| **Doctor checks** | `g-agent doctor`: 3-tier identity recognition (physicalDescription > loraTrigger > referenceImage) |
| **SOUL.md template** | Universal template with HARD RULES, customize comments, injected during onboarding |
| **TOOLS.md** | Selfie tool docs: identity source section (LoRA vs description vs vision) |
| **AGENTS.md** | Architecture bullet updated for LoRA (~90-95%) |
| **docs/configuration.md** | LoRA fields in table, Nebius+LoRA example, dual-path how-it-works |
| **Voice (TTS)** | `_synthesize_speech()` → edge-tts primary (id-ID-GadisNeural), espeak-ng fallback |

### 11.5 Test Coverage

27 unit tests in `tests/test_selfie_tool.py`:

| Range | Area |
|---|---|
| Tests 1-5 | Config defaults, roundtrip, guard errors |
| Tests 6-10 | Mode detection (EN/ID), default fallback |
| Tests 11-15 | Prompt construction, provider API calls |
| Tests 16-20 | Image save, outbound message, explicit mode, vision extraction |
| Tests 21-25 | **LoRA-specific**: config defaults, trigger bypass, prompt injection, payload injection, URL fallback |
| Tests 26-27 | Cloudflare provider, scoring-based mode detection |

### 11.6 What's NOT Implemented (vs Blueprint)

| Item | Blueprint Section | Reason |
|---|---|---|
| NSFW filter | Not in blueprint | Deferred — provider-side moderation sufficient for now |
| Rate limiting | Not in blueprint | Deferred — not needed for personal use |
| Image caching | Not in blueprint | Each selfie is unique context, caching not applicable |
| A/B prompt testing | Not in blueprint | Over-engineering for current scope |

---

*Dokumen ini adalah referensi internal untuk evaluasi dan planning. Updated Februari 2026 dengan implementation status aktual.*
