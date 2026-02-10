"""Tests for ported channel configurations and provider registry integration in schema."""

from g_agent.config.schema import (
    ChannelsConfig,
    Config,
    EmailConfig,
    ProviderConfig,
    SlackChannelConfig,
    SlackDMConfig,
)

# ─── EmailConfig defaults ─────────────────────────────────────────────────


def test_email_config_defaults():
    cfg = EmailConfig()
    assert cfg.enabled is False
    assert cfg.consent_granted is False
    assert cfg.imap_port == 993
    assert cfg.smtp_port == 587
    assert cfg.imap_use_ssl is True
    assert cfg.smtp_use_tls is True
    assert cfg.smtp_use_ssl is False
    assert cfg.poll_interval_seconds == 30
    assert cfg.mark_seen is True
    assert cfg.max_body_chars == 12000
    assert cfg.auto_reply_enabled is True
    assert cfg.allow_from == []


def test_email_config_custom():
    cfg = EmailConfig(
        enabled=True,
        consent_granted=True,
        imap_host="imap.gmail.com",
        smtp_host="smtp.gmail.com",
        imap_username="test@gmail.com",
        imap_password="secret",
        smtp_username="test@gmail.com",
        smtp_password="secret",
        from_address="test@gmail.com",
        allow_from=["alice@example.com", "bob@example.com"],
        poll_interval_seconds=60,
    )
    assert cfg.enabled is True
    assert cfg.consent_granted is True
    assert len(cfg.allow_from) == 2
    assert cfg.poll_interval_seconds == 60


# ─── SlackDMConfig defaults ───────────────────────────────────────────────


def test_slack_dm_config_defaults():
    cfg = SlackDMConfig()
    assert cfg.enabled is True
    assert cfg.policy == "open"
    assert cfg.allow_from == []


def test_slack_dm_config_allowlist():
    cfg = SlackDMConfig(policy="allowlist", allow_from=["U123", "U456"])
    assert cfg.policy == "allowlist"
    assert len(cfg.allow_from) == 2


# ─── SlackChannelConfig defaults ──────────────────────────────────────────


def test_slack_channel_config_defaults():
    cfg = SlackChannelConfig()
    assert cfg.enabled is False
    assert cfg.mode == "socket"
    assert cfg.bot_token == ""
    assert cfg.app_token == ""
    assert cfg.group_policy == "mention"
    assert cfg.user_token_read_only is True
    assert cfg.group_allow_from == []
    assert isinstance(cfg.dm, SlackDMConfig)


def test_slack_channel_config_custom():
    cfg = SlackChannelConfig(
        enabled=True,
        bot_token="xoxb-test-token",
        app_token="xapp-test-token",
        group_policy="open",
        dm=SlackDMConfig(enabled=False),
    )
    assert cfg.enabled is True
    assert cfg.bot_token == "xoxb-test-token"
    assert cfg.app_token == "xapp-test-token"
    assert cfg.group_policy == "open"
    assert cfg.dm.enabled is False


# ─── ChannelsConfig includes new channels ─────────────────────────────────


def test_channels_config_has_email_and_slack():
    cfg = ChannelsConfig()
    assert hasattr(cfg, "email")
    assert hasattr(cfg, "slack_channel")
    assert isinstance(cfg.email, EmailConfig)
    assert isinstance(cfg.slack_channel, SlackChannelConfig)


# ─── ProviderConfig extra_headers ─────────────────────────────────────────


def test_provider_config_extra_headers_default():
    cfg = ProviderConfig()
    assert cfg.extra_headers is None


def test_provider_config_extra_headers_set():
    cfg = ProviderConfig(extra_headers={"APP-Code": "abc123"})
    assert cfg.extra_headers == {"APP-Code": "abc123"}


# ─── Full Config with new providers ───────────────────────────────────────


def test_config_has_dashscope_and_aihubmix():
    cfg = Config()
    assert hasattr(cfg.providers, "dashscope")
    assert hasattr(cfg.providers, "aihubmix")


def test_config_provider_map_includes_new_providers():
    cfg = Config()
    pm = cfg._provider_map()
    assert "dashscope" in pm
    assert "aihubmix" in pm


# ─── _match_provider with registry ───────────────────────────────────────


def test_match_provider_anthropic():
    cfg = Config.model_validate(
        {
            "providers": {"anthropic": {"api_key": "sk-ant-test"}},
            "agents": {"defaults": {"model": "claude-sonnet-4-5"}},
        }
    )
    p, name = cfg._match_provider("claude-sonnet-4-5")
    assert name == "anthropic"
    assert p is not None
    assert p.api_key == "sk-ant-test"


def test_match_provider_dashscope():
    cfg = Config.model_validate(
        {
            "providers": {"dashscope": {"api_key": "sk-dash-test"}},
            "agents": {"defaults": {"model": "qwen-turbo"}},
        }
    )
    p, name = cfg._match_provider("qwen-turbo")
    assert name == "dashscope"
    assert p is not None


def test_match_provider_no_key_returns_none():
    cfg = Config()
    p, name = cfg._match_provider("claude-sonnet-4-5")
    assert p is None
    assert name is None


# ─── get_provider / get_provider_name ─────────────────────────────────────


def test_get_provider_returns_config():
    cfg = Config.model_validate(
        {
            "providers": {
                "openai": {"api_key": "sk-test", "extra_headers": {"X-Custom": "val"}},
            },
            "agents": {"defaults": {"model": "gpt-4o"}},
        }
    )
    p = cfg.get_provider("gpt-4o")
    assert p is not None
    assert p.api_key == "sk-test"
    assert p.extra_headers == {"X-Custom": "val"}


def test_get_provider_name_returns_string():
    cfg = Config.model_validate(
        {
            "providers": {"gemini": {"api_key": "gsk-test"}},
            "agents": {"defaults": {"model": "gemini-2.5-pro"}},
        }
    )
    name = cfg.get_provider_name("gemini-2.5-pro")
    assert name == "gemini"


# ─── Full Config JSON round-trip with new channels ──────────────────────


def test_config_roundtrip_with_email_and_slack():
    """Config with email + slack_channel serializes and deserializes."""
    cfg = Config.model_validate(
        {
            "channels": {
                "email": {
                    "enabled": True,
                    "consent_granted": True,
                    "imap_host": "imap.test.com",
                    "smtp_host": "smtp.test.com",
                },
                "slack_channel": {
                    "enabled": True,
                    "bot_token": "xoxb-test",
                    "app_token": "xapp-test",
                },
            },
        }
    )
    assert cfg.channels.email.enabled is True
    assert cfg.channels.email.consent_granted is True
    assert cfg.channels.email.imap_host == "imap.test.com"
    assert cfg.channels.slack_channel.enabled is True
    assert cfg.channels.slack_channel.bot_token == "xoxb-test"

    # Round-trip
    data = cfg.model_dump()
    cfg2 = Config.model_validate(data)
    assert cfg2.channels.email.imap_host == "imap.test.com"
    assert cfg2.channels.slack_channel.app_token == "xapp-test"


# ─── _model_provider_hints includes new providers ─────────────────────────


def test_model_provider_hints_dashscope():
    cfg = Config()
    hints = cfg._model_provider_hints("dashscope/qwen-turbo")
    assert "dashscope" in hints


def test_model_provider_hints_qwen_prefix():
    cfg = Config()
    hints = cfg._model_provider_hints("qwen/qwen-turbo")
    assert "dashscope" in hints


def test_model_provider_hints_aihubmix():
    cfg = Config()
    hints = cfg._model_provider_hints("aihubmix/gpt-4o")
    assert "aihubmix" in hints


# ─── _explicit_provider_from_model includes new providers ─────────────────


def test_explicit_provider_dashscope():
    cfg = Config()
    name = cfg._explicit_provider_from_model("dashscope/qwen-turbo")
    assert name == "dashscope"


def test_explicit_provider_qwen_alias():
    cfg = Config()
    name = cfg._explicit_provider_from_model("qwen/qwen-turbo")
    assert name == "dashscope"


def test_explicit_provider_aihubmix():
    cfg = Config()
    name = cfg._explicit_provider_from_model("aihubmix/gpt-4o")
    assert name == "aihubmix"
