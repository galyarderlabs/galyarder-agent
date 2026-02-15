"""Tests for the selfie generation tool."""

import asyncio
import base64
import json
from pathlib import Path

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

    assert "Selfie sent" in result
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

    assert "Selfie sent" in result
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
            api_base="https://api.nebius.ai/v1",
            model="sdxl",
        ),
    )
    tool, _ = _make_tool(config=config, tmp_path=tmp_path)
    result = asyncio.run(tool.execute(context="sunset view"))

    assert "Selfie sent" in result
    assert "images/generations" in fake_client.last_url
    # Verify the saved file contains the decoded bytes
    selfie_dir = tmp_path / "state" / "selfies"
    assert any(selfie_dir.iterdir())
    saved_file = next(selfie_dir.iterdir())
    assert saved_file.read_bytes() == b"openai-image"


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

    assert "Selfie sent" in result
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
    """Test 18: OutboundMessage has media path and metadata."""
    fake_resp = _FakeResponse(content=b"media-img", content_type="image/jpeg")
    fake_client = _FakeAsyncClient(fake_resp)
    monkeypatch.setattr(
        "g_agent.agent.tools.selfie.httpx.AsyncClient",
        lambda **kw: fake_client,
    )

    tool, captured = _make_tool(tmp_path=tmp_path)
    asyncio.run(tool.execute(context="at a park"))

    assert len(captured) == 1
    msg = captured[0]
    assert msg.channel == "telegram"
    assert msg.chat_id == "123"
    assert len(msg.media) == 1
    assert msg.media[0].endswith(".jpeg")
    assert msg.metadata["media_type"] == "image"
    assert msg.metadata["mime_type"] == "image/jpeg"
    assert msg.metadata["caption"] == "at a park"


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
