import pytest

from g_agent.context.compressor import ContextCompressor
from g_agent.providers.base import LLMProvider, LLMResponse


class ChatOnlyProvider(LLMProvider):
    def __init__(self):
        super().__init__(api_key=None, api_base=None)
        self.calls = []

    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, **kwargs):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return LLMResponse(content="summarized middle")

    def get_default_model(self) -> str:
        return "dummy"


@pytest.mark.asyncio
async def test_summarize_middle_uses_chat_provider_interface():
    provider = ChatOnlyProvider()
    compressor = ContextCompressor(provider)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "old 1"},
        {"role": "assistant", "content": "old 2"},
        {"role": "user", "content": "new 1"},
        {"role": "assistant", "content": "new 2"},
    ]

    result = await compressor.summarize_middle(messages, protect_first_n=1, protect_last_n=2)

    assert len(provider.calls) == 1
    assert provider.calls[0]["tools"] is None
    assert provider.calls[0]["max_tokens"] == 500
    assert provider.calls[0]["temperature"] == 0.2
    assert result == [
        {"role": "system", "content": "sys"},
        {"role": "system", "content": "[Conversation Summary: summarized middle]"},
        {"role": "user", "content": "new 1"},
        {"role": "assistant", "content": "new 2"},
    ]


class FailingProvider(ChatOnlyProvider):
    async def chat(self, *args, **kwargs):
        raise RuntimeError("provider down")


@pytest.mark.asyncio
async def test_summarize_middle_falls_back_to_reference_summary():
    compressor = ContextCompressor(FailingProvider())
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "old context"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "new"},
    ]

    result = await compressor.summarize_middle(messages, protect_first_n=1, protect_last_n=1)

    assert result[0] == {"role": "system", "content": "sys"}
    assert result[-1] == {"role": "user", "content": "new"}
    assert "Reference-only digest" in result[1]["content"]
    assert "old context" in result[1]["content"]
