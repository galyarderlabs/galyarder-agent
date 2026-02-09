from g_agent.agent.tools.web import _strip_tags


def test_strip_tags_removes_script_and_style_blocks() -> None:
    text = _strip_tags("<p>hello </p><script>alert(1)</script><style>.x{}</style><div>world</div>")
    assert text == "hello world"


def test_strip_tags_handles_script_end_tag_with_space() -> None:
    text = _strip_tags("<script>alert(1)</script >safe")
    assert text == "safe"
