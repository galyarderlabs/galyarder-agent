
from g_agent.agent.tools.google_workspace import (
    GmailForwardTool,
    GmailReplyAllTool,
    GmailReplyTool,
    GwsClient,
)


def test_build_env_forwards_credentials_file():
    client = GwsClient(gws_path="/tmp/gws", credentials_file="/tmp/creds.json")
    env = client._build_env()
    assert env is not None
    assert env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] == "/tmp/creds.json"


def test_build_env_respects_existing_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE", "/existing/creds.json")
    client = GwsClient(gws_path="/tmp/gws", credentials_file="/tmp/new_creds.json")
    env = client._build_env()
    assert env is not None
    assert env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] == "/existing/creds.json"


def test_build_env_without_creds():
    client = GwsClient(gws_path="/tmp/gws", credentials_file="")
    env = client._build_env()
    assert env is not None
    assert "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE" not in env


def test_gmail_reply_tool_schema():
    client = GwsClient(gws_path="/tmp/gws")
    tool = GmailReplyTool(client)
    assert tool.name == "gmail_reply"
    assert "messageId" in tool.parameters["required"]
    assert "body" in tool.parameters["required"]


def test_gmail_reply_all_tool_schema():
    client = GwsClient(gws_path="/tmp/gws")
    tool = GmailReplyAllTool(client)
    assert tool.name == "gmail_reply_all"
    assert "messageId" in tool.parameters["required"]
    assert "body" in tool.parameters["required"]
    assert "remove" in tool.parameters["properties"]
    assert "cc" in tool.parameters["properties"]


def test_gmail_forward_tool_schema():
    client = GwsClient(gws_path="/tmp/gws")
    tool = GmailForwardTool(client)
    assert tool.name == "gmail_forward"
    assert "messageId" in tool.parameters["required"]
    assert "to" in tool.parameters["required"]
    assert "body" in tool.parameters["properties"]
