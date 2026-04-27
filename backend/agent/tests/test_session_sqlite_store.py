"""Tests for SQLite session storage and search."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from g_agent.session.sqlite_store import SessionSQLiteStore


def test_sqlite_store_schema_is_idempotent_and_wal_enabled(tmp_path: Path):
    db_path = tmp_path / "sessions.db"

    first = SessionSQLiteStore(db_path)
    second = SessionSQLiteStore(db_path)

    with first._lock:
        journal_mode = first._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode == "wal"
    assert second.list_sessions() == []


def test_sqlite_store_append_read_and_search_filters(tmp_path: Path):
    store = SessionSQLiteStore(tmp_path / "sessions.db")

    cli = store.get_or_create_session("cli:default")
    telegram = store.get_or_create_session("telegram:123")
    store.append_message(cli["id"], "user", "run `uv run pytest` in /tmp/project")
    store.append_message(cli["id"], "assistant", "decision: keep JSONL rollback")
    store.append_message(telegram["id"], "user", "same needle from telegram https://example.com")

    history = store.get_history(cli["id"])
    assert [item["content"] for item in history] == [
        "run `uv run pytest` in /tmp/project",
        "decision: keep JSONL rollback",
    ]

    command_hits = store.search_messages("uv run pytest")
    assert command_hits[0]["session_key"] == "cli:default"

    path_hits = store.search_messages("/tmp/project", session_key="cli:default")
    assert [item["session_key"] for item in path_hits] == ["cli:default"]

    url_hits = store.search_messages("example.com", channel="telegram")
    assert [item["session_key"] for item in url_hits] == ["telegram:123"]

    excluded = store.search_messages("needle", exclude_session_key="telegram:123")
    assert excluded == []


def test_sqlite_store_handles_concurrent_writes(tmp_path: Path):
    store = SessionSQLiteStore(tmp_path / "sessions.db")
    session = store.get_or_create_session("cli:default")

    def write(index: int) -> int:
        return store.append_message(session["id"], "user", f"concurrent write {index}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        message_ids = list(pool.map(write, range(24)))

    assert len(set(message_ids)) == 24
    history = store.get_history(session["id"], limit=30)
    assert len(history) == 24
    assert store.search_messages("concurrent write", limit=30)


def test_sqlite_store_replace_messages_removes_stale_fts_rows(tmp_path: Path):
    store = SessionSQLiteStore(tmp_path / "sessions.db")
    session = store.get_or_create_session("cli:default")

    store.replace_messages(
        session["id"],
        [{"role": "user", "content": "old searchable phrase"}],
    )
    assert store.search_messages("old searchable phrase")

    store.replace_messages(
        session["id"],
        [{"role": "user", "content": "new searchable phrase"}],
    )
    assert store.search_messages("old searchable phrase") == []
    assert len(store.search_messages("new searchable phrase")) == 1


def test_sqlite_store_persists_media_refs_tool_calls_and_title(tmp_path: Path):
    store = SessionSQLiteStore(tmp_path / "sessions.db")
    session = store.get_or_create_session("telegram:123")
    media_path = tmp_path / "photo.txt"
    media_path.write_text("image-ish", encoding="utf-8")

    store.replace_messages(
        session["id"],
        [
            {
                "role": "user",
                "content": "inspect this photo",
                "content_type": "media",
                "media": [str(media_path)],
            },
            {
                "role": "assistant",
                "content": "done",
                "metadata": {
                    "tool_calls": [
                        {
                            "tool_name": "selfie",
                            "arguments": {"prompt": "test"},
                            "result_summary": "delivered",
                            "status": "success",
                        }
                    ]
                },
            },
        ],
    )

    with store._lock:
        session_row = store._conn.execute(
            "SELECT title, message_count, tool_call_count FROM sessions WHERE id = ?",
            (session["id"],),
        ).fetchone()
        media_row = store._conn.execute(
            "SELECT path, sha256 FROM media_refs WHERE session_id = ?",
            (session["id"],),
        ).fetchone()
        tool_row = store._conn.execute(
            "SELECT tool_name, result_summary, status FROM tool_calls WHERE session_id = ?",
            (session["id"],),
        ).fetchone()

    assert session_row["title"] == "inspect this photo"
    assert session_row["message_count"] == 2
    assert session_row["tool_call_count"] == 1
    assert media_row["path"] == str(media_path)
    assert media_row["sha256"]
    assert dict(tool_row) == {
        "tool_name": "selfie",
        "result_summary": "delivered",
        "status": "success",
    }
