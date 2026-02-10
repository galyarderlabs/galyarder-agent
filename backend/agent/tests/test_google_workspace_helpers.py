from g_agent.agent.tools.google_workspace import _extract_doc_text, _format_person_line


def test_extract_doc_text_reads_paragraph_runs() -> None:
    payload = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Hello "}},
                            {"textRun": {"content": "World"}},
                        ]
                    }
                }
            ]
        }
    }
    assert _extract_doc_text(payload) == "Hello World"


def test_extract_doc_text_truncates() -> None:
    payload = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "abcdefghij"}},
                        ]
                    }
                }
            ]
        }
    }
    result = _extract_doc_text(payload, max_chars=5)
    assert result.startswith("abcde")
    assert "truncated" in result


def test_format_person_line_compact() -> None:
    person = {
        "resourceName": "people/c123",
        "names": [{"displayName": "Galih"}],
        "emailAddresses": [{"value": "mhmdgalih@example.com"}],
        "phoneNumbers": [{"value": "+628123456789"}],
    }
    line = _format_person_line(person)
    assert "Galih" in line
    assert "mhmdgalih@example.com" in line
    assert "+628123456789" in line
    assert "people/c123" in line
