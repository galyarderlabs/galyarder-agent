"""Selfie generation tool for visual identity."""

import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from loguru import logger

from g_agent.agent.tools.base import Tool
from g_agent.bus.events import OutboundMessage
from g_agent.config.schema import VisualIdentityConfig
from g_agent.providers.base import LLMProvider


async def extract_physical_description(
    reference_image_path: str,
    llm_provider: LLMProvider,
) -> str:
    """Extract physical traits from a reference image using vision LLM."""
    path = Path(reference_image_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Reference image not found: {path}")

    image_data = base64.b64encode(path.read_bytes()).decode()
    suffix = path.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(suffix, "jpeg")
    data_uri = f"data:image/{mime};base64,{image_data}"

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Describe the physical appearance of the person in this photo "
                        "for consistent text-to-image generation. Include: gender, "
                        "approximate age, ethnicity, skin tone, hair color/style/length, "
                        "eye shape/color, face shape, distinguishing features. "
                        "Output a single descriptive paragraph, no preamble."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                },
            ],
        }
    ]

    response = await llm_provider.chat(
        messages=messages,
        tools=None,
        temperature=0.2,
        max_tokens=256,
    )
    return (response.content or "").strip()


class SelfieTool(Tool):
    """Generate and send a selfie photo of the agent."""

    def __init__(
        self,
        config: VisualIdentityConfig,
        send_callback: Callable[[OutboundMessage], Awaitable[None]],
        workspace: Path,
        llm_provider: LLMProvider,
    ):
        self._config = config
        self._send_callback = send_callback
        self._workspace = workspace.expanduser().resolve()
        self._llm_provider = llm_provider
        self._channel: str = ""
        self._chat_id: str = ""

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set current message routing context."""
        self._channel = channel
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "selfie"

    @property
    def description(self) -> str:
        return "Generate and send a selfie photo of the agent in a specified context."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "Scene description for image generation, e.g. 'at a beach' or 'wearing a suit'.",
                },
                "caption": {
                    "type": "string",
                    "description": (
                        "Short casual text message to send WITH the photo, written in your "
                        "natural voice. Example: 'nih, lagi di kamar habis kerja.' "
                        "This is the ONLY text the user will see — no follow-up message will be sent."
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["mirror", "direct", "auto"],
                    "description": "Selfie mode. 'auto' detects from context keywords.",
                },
            },
            "required": ["context", "caption"],
        }

    async def execute(
        self,
        context: str = "",
        caption: str = "",
        mode: str = "auto",
        **kwargs: Any,
    ) -> str:
        context = (context or "").strip()
        caption = (caption or "").strip()
        mode = (mode or "auto").strip().lower()

        # Guards
        if not self._config.enabled:
            return "Error: visual identity is not enabled in config."
        if not self._config.image_gen.provider:
            return "Error: no image generation provider configured."

        # Resolve identity anchor: Combine physical description with LoRA trigger if available
        current_hash = ""
        if self._config.reference_image:
            try:
                img_path = Path(self._config.reference_image).expanduser().resolve()
                if img_path.exists():
                    import hashlib

                    current_hash = hashlib.md5(img_path.read_bytes()).hexdigest()
            except Exception as e:
                logger.warning(f"Failed to calculate image hash: {e}")

        if current_hash and self._config.reference_image_hash != current_hash:
            logger.info("Reference image changed. Invalidating physical description cache.")
            self._config.physical_description = ""

        base_description = self._config.physical_description

        trigger = self._config.image_gen.lora_trigger
        if trigger:
            logger.debug(f"Using LoRA trigger alongside physical description: {trigger}")
            if base_description:
                description = f"{trigger}, {base_description}"
            else:
                description = trigger
        else:
            description = base_description

        if not description and self._config.reference_image:
            try:
                description = await extract_physical_description(
                    self._config.reference_image,
                    self._llm_provider,
                )
                self._config.physical_description = description
                self._config.reference_image_hash = current_hash
                self._persist_description(description, current_hash)
                logger.info("Extracted physical description from reference image")
            except Exception as e:
                logger.error(f"Vision extraction failed: {e}")
                return f"Error: failed to extract physical description: {e}"

        if not description:
            return (
                "Error: no physical description available. "
                "Configure lora_trigger in image_gen, provide a reference photo "
                "via 'g-agent onboard', or set visual.physicalDescription in config."
            )

        # Detect mode
        if mode == "auto":
            mode = self._detect_mode(context)

        # Build prompt
        template = self._config.prompt_templates.get(
            mode, self._config.prompt_templates.get("direct", "")
        )
        prompt = template.format(description=description, context=context)

        # Generate image
        try:
            image_bytes = await self._generate_image(prompt)
        except Exception as e:
            logger.error(f"Selfie image generation failed: {e}")
            return f"Error: image generation failed: {e}"

        # Save to workspace
        selfie_dir = self._workspace / "state" / "selfies"
        selfie_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        ext = self._config.default_format
        file_path = selfie_dir / f"selfie-{timestamp}.{ext}"
        file_path.write_bytes(image_bytes)
        resolved_path = str(file_path.resolve())

        # Send via outbound
        channel = self._channel
        chat_id = self._chat_id
        if not channel or not chat_id:
            return f"Selfie saved to {resolved_path} but no channel context to send."

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=caption,
            media=[resolved_path],
            metadata={
                "media_type": "image",
                "mime_type": f"image/{ext}",
                "selfie_mode": mode,
            },
        )
        try:
            await self._send_callback(msg)
            return (
                f"Selfie photo has been delivered to {channel}:{chat_id} ({mode} mode). "
                f"Caption sent with photo: '{caption}'. "
                "The photo and caption are already visible to the user. "
                "Do NOT send any additional text response."
            )
        except Exception as e:
            return f"Error sending selfie: {e}"

    def _detect_mode(self, context: str) -> str:
        """Detect mirror vs direct mode from context keywords."""
        lowered = context.lower()
        mirror_score = sum(1 for kw in self._config.mirror_keywords if kw in lowered)
        direct_score = sum(1 for kw in self._config.direct_keywords if kw in lowered)
        if direct_score > mirror_score:
            return "direct"
        return "mirror"

    def _persist_description(self, description: str, ref_hash: str = "") -> None:
        """Persist extracted description and image hash back to config file."""
        try:
            from g_agent.config.loader import load_config, save_config

            config = load_config()
            config.visual.physical_description = description
            config.visual.reference_image_hash = ref_hash
            save_config(config)
        except Exception as e:
            logger.warning(f"Failed to persist physical description: {e}")

    async def _generate_image(self, prompt: str) -> bytes:
        """Route image generation to the configured provider."""
        provider = self._config.image_gen.provider.strip().lower()
        if provider == "huggingface":
            return await self._generate_huggingface(prompt)
        if provider == "openai-compatible":
            return await self._generate_openai_compatible(prompt)
        if provider == "cloudflare":
            return await self._generate_cloudflare(prompt)
        raise ValueError(f"Unsupported image generation provider: {provider}")

    async def _generate_huggingface(self, prompt: str) -> bytes:
        """Generate image via Hugging Face Inference API."""
        model = self._config.image_gen.model or "stabilityai/stable-diffusion-xl-base-1.0"
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {self._config.image_gen.api_key}"}
        async with httpx.AsyncClient(timeout=self._config.image_gen.timeout) as client:
            resp = await client.post(url, headers=headers, json={"inputs": prompt})
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "json" in content_type:
                data = resp.json()
                if isinstance(data, list) and data:
                    b64 = data[0].get("generated_image") or data[0].get("image", "")
                    return base64.b64decode(b64)
                raise RuntimeError(f"Unexpected HuggingFace response: {data}")
            return resp.content

    async def _generate_openai_compatible(self, prompt: str) -> bytes:
        """Generate image via an OpenAI-compatible image API."""
        api_base = self._config.image_gen.api_base.rstrip("/")
        if not api_base:
            raise ValueError("api_base is required for openai-compatible image generation.")
        model = self._config.image_gen.model
        url = f"{api_base}/images/generations"
        headers = {"Authorization": f"Bearer {self._config.image_gen.api_key}"}
        if model.startswith("gpt-image-"):
            payload: dict[str, Any] = {
                "prompt": prompt,
                "response_format": "b64_json",
                "size": "1024x1024",
            }
        else:
            payload = {
                "prompt": prompt,
                "response_format": "b64_json",
                "width": 768,
                "height": 768,
                "num_inference_steps": 28,
            }
        if model:
            payload["model"] = model

        # Inject LoRA if configured
        if self._config.image_gen.lora_url:
            payload["loras"] = [
                {
                    "url": self._config.image_gen.lora_url,
                    "scale": self._config.image_gen.lora_scale,
                }
            ]

        import json

        logger.debug(f"Image gen payload: {json.dumps(payload)}")

        async with httpx.AsyncClient(timeout=self._config.image_gen.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            image_data = data["data"][0]
            # Try b64_json first, fall back to URL (LoRA responses may return URL)
            if image_data.get("b64_json"):
                return base64.b64decode(image_data["b64_json"])
            if image_data.get("url"):
                return await self._download_image_url(image_data["url"])
            raise RuntimeError(f"No image data in response: {list(image_data.keys())}")

    async def _download_image_url(
        self,
        url: str,
        retries: int = 5,
        delay: float = 2.0,
    ) -> bytes:
        """Download image from URL with retry."""
        import asyncio

        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(retries):
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.content
                logger.warning(
                    f"Image download attempt {attempt + 1}/{retries} "
                    f"failed: HTTP {resp.status_code}"
                )
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
        raise RuntimeError(f"Failed to download image after {retries} attempts")

    async def _generate_cloudflare(self, prompt: str) -> bytes:
        """Generate image via Cloudflare Workers AI."""
        account_id = self._config.image_gen.account_id
        if not account_id:
            raise ValueError("Cloudflare Workers AI requires account_id in image_gen config.")
        model = self._config.image_gen.model or "@cf/black-forest-labs/flux-1-schnell"
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        headers = {"Authorization": f"Bearer {self._config.image_gen.api_key}"}
        async with httpx.AsyncClient(timeout=self._config.image_gen.timeout) as client:
            resp = await client.post(url, headers=headers, json={"prompt": prompt})
            resp.raise_for_status()
            return resp.content
