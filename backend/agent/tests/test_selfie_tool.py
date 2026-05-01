"""Tests for the selfie generation tool."""

import asyncio
import base64
import json
from pathlib import Path

import httpx

from g_agent.agent.tools.selfie import SelfieTool, extract_physical_description
from g_agent.bus.events import OutboundMessage
from g_agent.config.loader import convert_keys, convert_to_camel
from g_agent.config.schema import (
    Config,
    ImageGenProviderConfig,
    VisualIdentityConfig,
)

# ── Helpers ────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, content=b"", status_code=200, content_type="image/jpeg", json_data=None):
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._json_data = json_data
        self.text = content.decode(errors="replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._json_data is not None:
            return self._json_data
        return json.loads(self.content)


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response
        self.last_url = None
        self.last_json = None
        self.last_headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def post(self, url, **kw):
        self.last_url = url
        self.last_json = kw.get("json")
        self.last_headers = kw.get("headers")
        return self._response


class _FakeLLMResponse:
    def __init__(self, content=""):
        self.content = content
        self.has_tool_calls = False
        self.tool_calls = []
        self.finish_reason = "stop"
        self.usage = {}


class _FakeLLMProvider:
    def __init__(self, response_text=""):
        self._response_text = response_text
        self.last_messages = None
        self.last_kwargs = {}

    async def chat(self, messages=None, tools=None, **kwargs):
        self.last_messages = messages
        self.last_kwargs = kwargs
        return _FakeLLMResponse(self._response_text)


def _make_config(**overrides):
    """Build VisualIdentityConfig with sensible test defaults."""
    defaults = {
        "enabled": True,
        "physical_description": "a young Asian woman with long black hair and brown eyes",
        "image_gen": ImageGenProviderConfig(
            provider="huggingface",
            api_key="hf-test-key",
            model="test-model",
        ),
    }
    defaults.update(overrides)
    return VisualIdentityConfig(**defaults)


def _make_tool(config=None, tmp_path=None, send_callback=None, llm_provider=None):
    """Build SelfieTool for tests."""
    captured: list[OutboundMessage] = []

    async def _send(msg):
        captured.append(msg)

    tool = SelfieTool(
        config=config or _make_config(),
        send_callback=send_callback or _send,
        workspace=tmp_path or Path("/tmp/test-workspace"),
        llm_provider=llm_provider or _FakeLLMProvider(),
    )
    tool.set_context("telegram", "123")
    return tool, captured


# ── Config Tests (1-2) ─────────────────────────────────────────────


def test_visual_config_defaults():
    """Test 1: VisualIdentityConfig has correct defaults."""
    cfg = VisualIdentityConfig()
    assert cfg.enabled is False
    assert cfg.reference_image == ""
    assert cfg.physical_description == ""
    assert cfg.default_format == "jpeg"
    assert "mirror" in cfg.prompt_templates
    assert "direct" in cfg.prompt_templates
    assert "outfit" in cfg.mirror_keywords
    assert "beach" in cfg.direct_keywords


def test_visual_config_camel_roundtrip():
    """Test 2: Config survives camelCase save/load roundtrip."""
    c = Config()
    d = convert_to_camel(c.model_dump())
    assert "visual" in d
    assert d["visual"]["enabled"] is False
    assert "imageGen" in d["visual"]
    c2 = Config.model_validate(convert_keys(d))
    assert c2.visual.enabled is False
    assert c2.visual.image_gen.provider == ""


# ── Guard Tests (3-5) ──────────────────────────────────────────────


def test_selfie_disabled_returns_error(tmp_path):
    """Test 3: Disabled config returns error."""
    config = _make_config(enabled=False)
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="at the park"))
    assert "not enabled" in result.lower()


def test_selfie_no_provider_returns_error(tmp_path):
    """Test 4: No provider configured returns error."""
    config = _make_config(image_gen=ImageGenProviderConfig())
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="at the park"))
    assert "no image generation provider" in result.lower()


def test_selfie_no_description_returns_error(tmp_path):
    """Test 5: No description and no reference image returns error."""
    config = _make_config(physical_description="", reference_image="")
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="at the park"))
    assert "no physical description" in result.lower()


# ── Mode Detection Tests (6-10) ───────────────────────────────────


def test_mode_detection_mirror_en(tmp_path):
    """Test 6: English mirror keyword detected."""
    tool, _ = _make_tool(tmp_path=tmp_path)
    assert tool._detect_mode("wearing a dress at the party") == "mirror"


def test_mode_detection_direct_en(tmp_path):
    """Test 7: English direct keyword detected."""
    tool, _ = _make_tool(tmp_path=tmp_path)
    assert tool._detect_mode("at the beach on a sunny day") == "direct"


def test_mode_detection_mirror_id(tmp_path):
    """Test 8: Indonesian mirror keyword detected."""
    tool, _ = _make_tool(tmp_path=tmp_path)
    assert tool._detect_mode("lagi pake baju baru") == "mirror"


def test_mode_detection_direct_id(tmp_path):
    """Test 9: Indonesian direct keyword detected."""
    tool, _ = _make_tool(tmp_path=tmp_path)
    assert tool._detect_mode("lagi di pantai") == "direct"


def test_mode_detection_default(tmp_path):
    """Test 10: Random text defaults to mirror."""
    tool, _ = _make_tool(tmp_path=tmp_path)
    assert tool._detect_mode("random text nothing special") == "mirror"


# ── Prompt Tests (11-13) ──────────────────────────────────────────


def test_prompt_includes_physical_description(tmp_path, monkeypatch):
    """Test 11: Generated prompt includes physical description."""
    fake_image = b"fake-image-bytes"
    fake_resp = _FakeResponse(content=fake_image, content_type="image/jpeg")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config()
    tool, captured = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="at a coffee shop"))

    assert "Selfie photo has been delivered" in result
    assert config.physical_description in fake_client.last_json["inputs"]


def test_prompt_includes_context(tmp_path, monkeypatch):
    """Test 12: Generated prompt includes the user's context."""
    fake_resp = _FakeResponse(content=b"img", content_type="image/jpeg")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    tool, _ = _make_tool(tmp_path=tmp_path)
    asyncio.run(tool.execute(context="at a coffee shop"))

    assert "at a coffee shop" in fake_client.last_json["inputs"]


def test_explicit_mode_override(tmp_path, monkeypatch):
    """Test 13: Explicit mode='direct' overrides keyword detection."""
    fake_resp = _FakeResponse(content=b"img", content_type="image/jpeg")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    tool, captured = _make_tool(tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="wearing a suit", mode="direct"))

    assert "direct mode" in result
    assert "direct eye contact" in fake_client.last_json["inputs"]


# ── Provider Call Tests (14-16) ───────────────────────────────────


def test_huggingface_provider_call(tmp_path, monkeypatch):
    """Test 14: HuggingFace provider sends correct request."""
    fake_resp = _FakeResponse(content=b"hf-image", content_type="image/jpeg")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    tool, _ = _make_tool(tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="in the office"))

    assert "Selfie photo has been delivered" in result
    assert "test-model" in fake_client.last_url
    assert fake_client.last_headers["Authorization"] == "Bearer hf-test-key"


def test_openai_compatible_provider_call(tmp_path, monkeypatch):
    """Test 15: OpenAI-compatible provider decodes b64_json."""
    b64_img = base64.b64encode(b"openai-image").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="sk-test",
            api_base="http://example.test/v1",
            model="sdxl",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="sunset view"))

    assert "Selfie photo has been delivered" in result
    assert "images/generations" in fake_client.last_url
    # Verify the saved file contains the decoded bytes
    selfie_dir = tmp_path / "state" / "selfies"
    assert any(selfie_dir.iterdir())
    saved_file = next(selfie_dir.iterdir())
    assert saved_file.read_bytes() == b"openai-image"


def test_openai_compatible_gpt_image_uses_openai_payload(tmp_path, monkeypatch):
    """OpenAI image models should not receive provider-specific generation fields."""
    b64_img = base64.b64encode(b"gpt-image").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="sk-test",
            api_base="http://127.0.0.1:8317/v1",
            model="gpt-image-test",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="studio photo"))

    assert "Selfie photo has been delivered" in result
    assert fake_client.last_json["model"] == "gpt-image-test"
    assert fake_client.last_json["size"] == "1024x1024"
    assert "width" not in fake_client.last_json
    assert "height" not in fake_client.last_json
    assert "num_inference_steps" not in fake_client.last_json


def test_openai_compatible_codex_image_models_use_openai_payload(tmp_path, monkeypatch):
    """Codex response models should use OpenAI Images payload shape for OmniRoute."""
    for model in ("cx/gpt-5.5", "cx/gpt-5.4", "cx/gpt-5.3-codex"):
        b64_img = base64.b64encode(model.encode()).decode()
        json_data = {"data": [{"b64_json": b64_img, "revised_prompt": "ok"}]}
        fake_resp = _FakeResponse(
            content=json.dumps(json_data).encode(),
            content_type="application/json",
            json_data=json_data,
        )
        fake_client = _FakeAsyncClient(fake_resp)
        monkeypatch.setattr(
            "g_agent.agent.tools.selfie.httpx.AsyncClient",
            lambda **kw: fake_client,
        )

        config = _make_config(
            image_gen=ImageGenProviderConfig(
                provider="openai-compatible",
                api_key="sk-test",
                api_base="http://localhost:20128/v1",
                model=model,
            ),
        )
        tool, _ = _make_tool(config=config, tmp_path=tmp_path)
        result = asyncio.run(tool.execute(context="studio photo"))

        assert "Selfie photo has been delivered" in result
        assert fake_client.last_json["model"] == model
        assert fake_client.last_json["response_format"] == "b64_json"
        assert fake_client.last_json["size"] == "1024x1024"
        assert "width" not in fake_client.last_json
        assert "height" not in fake_client.last_json
        assert "num_inference_steps" not in fake_client.last_json


def test_provider_error_handling(tmp_path, monkeypatch):
    """Test 16: Provider error surfaces as error message."""
    fake_resp = _FakeResponse(content=b"", status_code=500)
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    tool, _ = _make_tool(tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="at the gym"))

    assert "Error: image generation failed" in result


def test_image_generation_empty_exception_uses_exception_class_name(tmp_path, monkeypatch):
    """Blank provider exceptions should still produce actionable error details."""

    class _TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, **kw):
            raise httpx.TimeoutException("")

    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: _TimeoutClient(),
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="sk-test",
            api_base="http://127.0.0.1:20128/v1",
            model="cx/gpt-5.5",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="studio photo"))

    assert result == "Error: image generation failed: TimeoutException"



def test_openai_compatible_http_error_includes_provider_body(tmp_path, monkeypatch):
    """OpenAI-compatible errors should include sanitized provider response details."""
    error_body = {
        "error": {
            "message": "No credentials for image provider: openai",
            "type": "invalid_request_error",
            "code": "bad_request",
        }
    }
    fake_resp = _FakeResponse(
        content=json.dumps(error_body).encode(),
        status_code=400,
        content_type="application/json",
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="sk-test-secret-1234567890",
            api_base="http://127.0.0.1:20128/v1",
            model="gpt-image-test",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="studio photo"))

    assert "Error: image generation failed" in result
    assert "Image API HTTP 400" in result
    assert "No credentials for image provider: openai" in result
    assert "sk-test-secret" not in result


def test_cloudflare_provider_call(tmp_path, monkeypatch):
    """Test 16b: Cloudflare provider sends correct request with account_id."""
    fake_resp = _FakeResponse(content=b"cf-image", content_type="image/png")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="cloudflare",
            api_key="cf-test-key",
            account_id="abc123",
            model="@cf/black-forest-labs/flux-1-schnell",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="at the office"))

    assert "Selfie photo has been delivered" in result
    assert "abc123" in fake_client.last_url
    assert "flux-1-schnell" in fake_client.last_url
    assert fake_client.last_headers["Authorization"] == "Bearer cf-test-key"


def test_cloudflare_missing_account_id(tmp_path, monkeypatch):
    """Test 16c: Cloudflare without account_id returns error."""
    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="cloudflare",
            api_key="cf-test-key",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="at the gym"))

    assert "Error: image generation failed" in result
    assert "account_id" in result


# ── URL Construction Tests (16d-16g) ──────────────────────────────


def test_openai_url_construction_v1_base(tmp_path, monkeypatch):
    """Test 16d: api_base='http://localhost:20128/v1' constructs correct URL."""
    b64_img = base64.b64encode(b"test-image").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="sk-test",
            api_base="http://localhost:20128/v1",
            model="gpt-image-test",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="test scene"))

    assert "Selfie photo has been delivered" in result
    assert fake_client.last_url == "http://localhost:20128/v1/images/generations"


def test_openai_url_construction_api_v1_base(tmp_path, monkeypatch):
    """Test 16e: api_base='http://localhost:20128/api/v1' constructs correct URL."""
    b64_img = base64.b64encode(b"test-image").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="sk-test",
            api_base="http://localhost:20128/api/v1",
            model="gpt-image-test",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="test scene"))

    assert "Selfie photo has been delivered" in result
    assert fake_client.last_url == "http://localhost:20128/api/v1/images/generations"


def test_openai_url_construction_full_endpoint(tmp_path, monkeypatch):
    """Test 16f: api_base='http://localhost:20128/v1/images/generations' uses as-is."""
    b64_img = base64.b64encode(b"test-image").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="sk-test",
            api_base="http://localhost:20128/v1/images/generations",
            model="gpt-image-test",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="test scene"))

    assert "Selfie photo has been delivered" in result
    assert fake_client.last_url == "http://localhost:20128/v1/images/generations"


def test_openai_url_construction_trailing_slash(tmp_path, monkeypatch):
    """Test 16g: api_base with trailing slash is handled correctly."""
    b64_img = base64.b64encode(b"test-image").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="sk-test",
            api_base="http://localhost:20128/v1/",
            model="gpt-image-test",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="test scene"))

    assert "Selfie photo has been delivered" in result
    assert fake_client.last_url == "http://localhost:20128/v1/images/generations"


# ── File & Delivery Tests (17-18) ─────────────────────────────────


def test_image_save_to_workspace(tmp_path, monkeypatch):
    """Test 17: Image saved with correct path and extension."""
    fake_resp = _FakeResponse(content=b"saved-image", content_type="image/jpeg")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    tool, _ = _make_tool(tmp_path=tmp_path)
    asyncio.run(tool.execute(context="morning coffee"))

    selfie_dir = tmp_path / "state" / "selfies"
    assert selfie_dir.exists()
    files = list(selfie_dir.glob("selfie-*.jpeg"))
    assert len(files) == 1
    assert files[0].read_bytes() == b"saved-image"


def test_outbound_message_media(tmp_path, monkeypatch):
    """Test 18: OutboundMessage has media path, metadata, and optional caption."""
    fake_resp = _FakeResponse(content=b"media-img", content_type="image/jpeg")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    tool, captured = _make_tool(tmp_path=tmp_path)
    asyncio.run(tool.execute(context="at a park", caption="Here I am at the park!"))

    assert len(captured) == 1
    msg = captured[0]
    assert msg.channel == "telegram"
    assert msg.chat_id == "123"
    assert len(msg.media) == 1
    assert msg.media[0].endswith(".jpeg")
    assert msg.content == "Here I am at the park!"
    assert msg.metadata["media_type"] == "image"
    assert msg.metadata["mime_type"] == "image/jpeg"
    assert msg.metadata["selfie_mode"] == "direct"


# ── Vision Extraction Tests (19-20) ──────────────────────────────


def test_vision_extraction_prompt_format(tmp_path):
    """Test 19: Vision extraction sends correct multimodal message format."""
    ref_image = tmp_path / "reference.jpg"
    ref_image.write_bytes(b"fake-jpg-content")

    provider = _FakeLLMProvider("young woman with black hair, brown eyes")
    result = asyncio.run(
        extract_physical_description(str(ref_image), provider)
    )

    assert result == "young woman with black hair, brown eyes"
    assert provider.last_messages is not None
    msg = provider.last_messages[0]
    assert msg["role"] == "user"
    assert isinstance(msg["content"], list)
    assert msg["content"][0]["type"] == "text"
    assert msg["content"][1]["type"] == "image_url"
    assert msg["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert provider.last_kwargs.get("temperature") == 0.2
    assert provider.last_kwargs.get("max_tokens") == 256


def test_skip_extraction_when_description_exists(tmp_path, monkeypatch):
    """Test 20: No vision extraction when physical_description already set."""
    fake_resp = _FakeResponse(content=b"skip-img", content_type="image/jpeg")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    provider = _FakeLLMProvider("should not be called")
    config = _make_config(
        physical_description="existing description",
        reference_image="/some/path.jpg",
    )
    tool, _ = _make_tool(
        config=config, tmp_path=tmp_path, llm_provider=provider
    )
    asyncio.run(tool.execute(context="casual day"))

    # Provider.chat should NOT have been called for extraction
    assert provider.last_messages is None


# ── LoRA Tests (21-25) ────────────────────────────────────────────


def test_lora_config_defaults():
    """Test 21: ImageGenProviderConfig has correct LoRA defaults."""
    cfg = ImageGenProviderConfig()
    assert cfg.lora_url == ""
    assert cfg.lora_scale == 0.8
    assert cfg.lora_trigger == ""


def test_lora_trigger_skips_vision_extraction(tmp_path, monkeypatch):
    """Test 22: LoRA trigger word bypasses vision extraction entirely."""
    b64_img = base64.b64encode(b"lora-image").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    provider = _FakeLLMProvider("should not be called")
    config = _make_config(
        physical_description="",
        reference_image="",
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="proxy-test",
            api_base="http://example.test/v1",
            lora_trigger="nawusijia",
            lora_url="https://example.com/lora.safetensors",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path, llm_provider=provider)
    result = asyncio.run(tool.execute(context="at the park"))

    assert "Selfie photo has been delivered" in result
    # Vision extraction should NOT have been called
    assert provider.last_messages is None
    # Prompt should contain the trigger word
    assert "nawusijia" in fake_client.last_json["prompt"]


def test_lora_trigger_used_in_prompt(tmp_path, monkeypatch):
    """Test 23: LoRA trigger word is used alongside {description} in prompt template."""
    b64_img = base64.b64encode(b"trigger-img").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        physical_description="a specific detailed description",
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="proxy-test",
            api_base="http://example.test/v1",
            lora_trigger="mytrigger",
            lora_url="https://example.com/lora.safetensors",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    asyncio.run(tool.execute(context="wearing a red dress"))

    # Trigger word and description should be combined in prompt
    prompt = fake_client.last_json["prompt"]
    assert "mytrigger" in prompt
    assert "a specific detailed description" in prompt


def test_lora_payload_injected(tmp_path, monkeypatch):
    """Test 24: LoRA URL and scale are injected into the API payload."""
    b64_img = base64.b64encode(b"lora-payload").decode()
    json_data = {"data": [{"b64_json": b64_img}]}
    fake_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="proxy-test",
            api_base="http://example.test/v1",
            lora_trigger="testtrigger",
            lora_url="https://example.com/model.safetensors",
            lora_scale=0.75,
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    asyncio.run(tool.execute(context="at a cafe"))

    payload = fake_client.last_json
    assert "loras" in payload
    assert payload["loras"][0]["url"] == "https://example.com/model.safetensors"
    assert payload["loras"][0]["scale"] == 0.75
    assert payload["width"] == 768
    assert payload["height"] == 768
    assert payload["num_inference_steps"] == 28


def test_url_fallback_response(tmp_path, monkeypatch):
    """Test 25: When response has 'url' instead of 'b64_json', image is downloaded."""
    # First call: API returns URL response
    json_data = {"data": [{"url": "https://example.com/generated.webp"}]}
    api_resp = _FakeResponse(
        content=json.dumps(json_data).encode(),
        content_type="application/json",
        json_data=json_data,
    )

    # Second call: Download the image URL
    download_resp = _FakeResponse(content=b"downloaded-image-bytes")

    class _FakeAsyncClientMulti:
        def __init__(self):
            self.last_json = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, **kw):
            self.last_json = kw.get("json")
            return api_resp

        async def get(self, url, **kw):
            return download_resp

    fake_client = _FakeAsyncClientMulti()
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    config = _make_config(
        image_gen=ImageGenProviderConfig(
            provider="openai-compatible",
            api_key="proxy-test",
            api_base="http://example.test/v1",
            lora_trigger="urltrigger",
            lora_url="https://example.com/lora.safetensors",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="casual day"))

    assert "Selfie photo has been delivered" in result
    selfie_dir = tmp_path / "state" / "selfies"
    saved_file = next(selfie_dir.iterdir())
    assert saved_file.read_bytes() == b"downloaded-image-bytes"
