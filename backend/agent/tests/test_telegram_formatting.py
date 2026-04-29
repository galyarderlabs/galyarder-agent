import pytest
from g_agent.channels.telegram import _markdown_to_telegram_html

def test_telegram_format_basic():
    text = "Hello **world**!"
    assert _markdown_to_telegram_html(text) == "Hello <b>world</b>!"

def test_telegram_format_html_escape():
    text = "Check <this> & that"
    assert _markdown_to_telegram_html(text) == "Check &lt;this&gt; &amp; that"

def test_telegram_format_links():
    text = "Go to [Google](https://google.com)"
    # Note: the formatter escapes the URL in restore_link
    assert _markdown_to_telegram_html(text) == 'Go to <a href="https://google.com">Google</a>'

def test_telegram_format_code_inline():
    text = "Use `print('hi')`"
    assert _markdown_to_telegram_html(text) == "Use <code>print('hi')</code>"

def test_telegram_format_code_block():
    text = "```python\nprint('<hi>')\n```"
    # Result should have escaped HTML and pre/code tags
    result = _markdown_to_telegram_html(text)
    assert "&lt;hi&gt;" in result
    assert "<pre><code>" in result
    assert "</code></pre>" in result


def test_telegram_format_nested_entities():
    # Bold inside italic
    text = "_italic **bold** italic_"
    formatted = _markdown_to_telegram_html(text)
    assert formatted == "<i>italic <b>bold</b> italic</i>"

def test_telegram_format_mixed_escape():
    text = "<b>Already HTML</b>"
    # Should be escaped so it's literal in Telegram
    assert _markdown_to_telegram_html(text) == "&lt;b&gt;Already HTML&lt;/b&gt;"
