"""WebSocket channel tests."""

from aiohttp.test_utils import TestClient, TestServer

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.manager import ChannelManager
from g_agent.channels.websocket import WEBSOCKET_CAPABILITIES, WebSocketChannel
from g_agent.config.schema import Config, WebSocketChannelConfig


async def test_websocket_channel_authenticates_and_maps_session(tmp_path) -> None:
    bus = MessageBus()
    channel = WebSocketChannel(
        WebSocketChannelConfig(token="secret", allow_from=["owner"]),
        bus,
    )
    client = TestClient(TestServer(channel.make_app()))
    await client.start_server()
    try:
        unauthorized = await client.get("/ws?chat_id=room-1")
        assert unauthorized.status == 401

        ws = await client.ws_connect("/ws?token=secret&chat_id=room-1&sender_id=owner")
        ready = await ws.receive_json()
        assert ready == {"type": "ready", "channel": "websocket", "chat_id": "room-1"}

        await ws.send_json(
            {
                "content": "hello web",
                "media": ["/tmp/image.png"],
                "metadata": {"client_event_id": "evt-1"},
            }
        )
        inbound = await bus.consume_inbound()
        assert inbound.channel == "websocket"
        assert inbound.chat_id == "room-1"
        assert inbound.sender_id == "owner"
        assert inbound.session_key == "websocket:room-1"
        assert inbound.content == "hello web"
        assert inbound.media == ["/tmp/image.png"]
        assert inbound.metadata["transport"] == "websocket"
        assert inbound.metadata["client_event_id"] == "evt-1"

        await channel.send(
            OutboundMessage(channel="websocket", chat_id="room-1", content="reply")
        )
        outbound = await ws.receive_json()
        assert outbound["type"] == "message"
        assert outbound["content"] == "reply"
    finally:
        await client.close()


def test_websocket_capabilities_are_control_room_friendly() -> None:
    assert WEBSOCKET_CAPABILITIES.supports_media_send is True
    assert WEBSOCKET_CAPABILITIES.supports_media_receive is True
    assert WEBSOCKET_CAPABILITIES.supports_threads is True
    assert WEBSOCKET_CAPABILITIES.max_text_chars == 32000


def test_channel_manager_registers_enabled_websocket_channel(tmp_path) -> None:
    config = Config()
    config.agents.defaults.workspace = str(tmp_path)
    config.channels.websocket.enabled = True

    manager = ChannelManager(config, MessageBus(), plugins=[])

    assert isinstance(manager.channels["websocket"], WebSocketChannel)
