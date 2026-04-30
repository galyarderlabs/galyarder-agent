from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from g_agent.api import server as api_server
from g_agent.config.loader import load_config


async def _client(tmp_path: Path, monkeypatch, *, with_webui: bool = False) -> TestClient:
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    if with_webui:
        webui_dir = tmp_path / "g_agent" / "webui" / "dist"
        assets_dir = webui_dir / "assets"
        assets_dir.mkdir(parents=True)
        (webui_dir / "index.html").write_text(
            '<html><body><div id="root"></div><script src="/assets/app.js"></script></body></html>',
            encoding="utf-8",
        )
        monkeypatch.setattr(api_server, "__file__", str(tmp_path / "g_agent" / "api" / "server.py"))
    config = load_config()
    app = api_server.create_app(config=config)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    return client

@pytest.mark.asyncio
async def test_webui_index(tmp_path: Path, monkeypatch):
    client = await _client(tmp_path, monkeypatch, with_webui=True)
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
