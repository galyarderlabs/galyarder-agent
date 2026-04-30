from g_agent.channels.capabilities import split_text

def test_split_text_preserves_code_blocks():
    # max_chars=50, total text ~100
    text = "Intro text here.\n```python\nprint('hello world')\nprint('line 2')\nprint('line 3')\n```\nOutro."
    # If it splits inside the code block, it should close and reopen.
    # Note: current implementation doesn't do this yet.
    chunks = split_text(text, 50)
    # We want to check if chunks are balanced if they contain ```
    for chunk in chunks:
        assert chunk.count("```") % 2 == 0, f"Chunk has unbalanced code blocks: {chunk}"

def test_split_text_basic():
    text = "Hello\nWorld"
    # 11 chars total. 
    # If limit is 12, no split.
    assert split_text(text, 12) == ["Hello\nWorld"]
    # If limit is 10, split.
    chunks = split_text(text, 10)
    assert len(chunks) == 2
    assert chunks[0].strip() == "Hello"
    assert chunks[1].strip() == "World"
