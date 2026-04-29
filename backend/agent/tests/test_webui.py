import pytest
from pathlib import Path
from aiohttp.test_utils import TestClient, TestServer
from g_agent.api.server import create_app
from g_agent.config.loader import load_config

async def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    config = load_config()
    app = create_app(config=config)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    return client

@pytest.mark.asyncio
async def test_webui_index(tmp_path: Path, monkeypatch):
    client = await _client(tmp_path, monkeypatch)
    try:
        # Check index.html is served at root
        resp = await client.get('/')
        assert resp.status == 200
        text = await resp.text()
        # React app typically has a root div
        assert '<div id="root">' in text
        assert '/assets/' in text
    finally:
        await client.close()

@pytest.mark.asyncio
async def test_webui_bootstrap(tmp_path: Path, monkeypatch):
    client = await _client(tmp_path, monkeypatch)
    try:
        resp = await client.get('/webui/bootstrap')
        assert resp.status == 200
        data = await resp.json()
        assert "token" in data
        assert "ws_path" in data
        assert "model_name" in data
    finally:
        await client.close()
