"""Tests for Telegram-safe formatting."""

from g_agent.channels.telegram import _markdown_to_telegram_html


def test_telegram_markdown_escapes_raw_html():
    result = _markdown_to_telegram_html('hello <script>alert("x")</script> & done')

    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert "&amp; done" in result


def test_telegram_markdown_escapes_inline_and_block_code():
    result = _markdown_to_telegram_html("Use `<b>x</b>`\n```html\n<div>x</div>\n```")

    assert "<code>&lt;b&gt;x&lt;/b&gt;</code>" in result
    assert "<pre><code>&lt;div&gt;x&lt;/div&gt;\n</code></pre>" in result


def test_telegram_markdown_escapes_link_url_attributes():
    result = _markdown_to_telegram_html('[safe](https://example.com/?q=" onclick="bad")')

    assert '<a href="https://example.com/?q=&quot; onclick=&quot;bad&quot;">safe</a>' in result
    assert 'q=" onclick=' not in result


def test_telegram_markdown_keeps_supported_basic_markup():
    result = _markdown_to_telegram_html("**bold** _ital_ ~~gone~~")

    assert "<b>bold</b>" in result
    assert "<i>ital</i>" in result
    assert "<s>gone</s>" in result
