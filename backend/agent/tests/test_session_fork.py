from pathlib import Path
from g_agent.session.sqlite_store import SessionSQLiteStore

def test_fork_session_lineage(tmp_path: Path):
    db_path = tmp_path / "sessions.db"
    store = SessionSQLiteStore(db_path)

    # 1. Create parent session
    parent = store.get_or_create_session(key="cli:parent")
    parent_id = parent["id"]

    # 2. Fork session
    child = store.fork_session(
        parent_id=parent_id,
        key="cli:child",
        channel="cli",
        chat_id="child",
        title="Child Session"
    )

    assert child["parent_session_id"] == parent_id
    assert child["key"] == "cli:child"

    # 3. Verify in DB
    with store._lock:
        row = store._conn.execute("SELECT parent_session_id FROM sessions WHERE key = ?", ("cli:child",)).fetchone()
        db_parent_id = row[0]
    assert db_parent_id == parent_id

def test_delete_session_cascade(tmp_path: Path):
    db_path = tmp_path / "sessions.db"
    store = SessionSQLiteStore(db_path)

    session = store.get_or_create_session("cli:test")
    sid = session["id"]

    store.append_message(sid, "user", "hello")

    # Delete
    assert store.delete_session(sid) is True

    # Verify gone
    assert store.get_session(sid) is None

    with store._lock:
        count = store._conn.execute("SELECT count(*) FROM messages WHERE session_id = ?", (sid,)).fetchone()[0]
    assert count == 0

def test_replace_messages_preserves_metadata_when_none(tmp_path: Path):
    """replace_messages with metadata=None should preserve existing session metadata."""
    db_path = tmp_path / "sessions.db"
    store = SessionSQLiteStore(db_path)

    # 1. Create session with metadata
    session = store.get_or_create_session("cli:test")
    sid = session["id"]

    # 2. Add messages and metadata
    store.append_message(sid, "user", "hello")
    store.replace_messages(sid, [{"role": "user", "content": "hello"}], metadata={"key": "value"})

    # 3. Verify metadata was set
    session_after = store.get_session(sid)
    assert session_after is not None
    import json
    metadata_json = session_after.get("metadata_json")
    assert metadata_json is not None
    metadata = json.loads(metadata_json)
    assert metadata == {"key": "value"}

    # 4. Replace messages with metadata=None (should preserve)
    store.replace_messages(sid, [{"role": "user", "content": "world"}], metadata=None)

    # 5. Verify metadata preserved
    session_final = store.get_session(sid)
    assert session_final is not None
    metadata_json_final = session_final.get("metadata_json")
    assert metadata_json_final is not None
    metadata_final = json.loads(metadata_json_final)
    assert metadata_final == {"key": "value"}

def test_replace_messages_replaces_metadata_when_dict(tmp_path: Path):
    """replace_messages with metadata={} should replace existing metadata."""
    db_path = tmp_path / "sessions.db"
    store = SessionSQLiteStore(db_path)

    session = store.get_or_create_session("cli:test")
    sid = session["id"]

    # Set initial metadata
    store.replace_messages(sid, [{"role": "user", "content": "hello"}], metadata={"old": "data"})

    # Replace with new metadata
    store.replace_messages(sid, [{"role": "user", "content": "world"}], metadata={"new": "data"})

    # Verify replaced
    session_final = store.get_session(sid)
    import json
    metadata = json.loads(session_final["metadata_json"])
    assert metadata == {"new": "data"}
    assert "old" not in metadata

def test_replace_messages_replaces_with_empty_dict(tmp_path: Path):
    """replace_messages with metadata={} should clear metadata."""
    db_path = tmp_path / "sessions.db"
    store = SessionSQLiteStore(db_path)

    session = store.get_or_create_session("cli:test")
    sid = session["id"]

    # Set initial metadata
    store.replace_messages(sid, [{"role": "user", "content": "hello"}], metadata={"key": "value"})

    # Replace with empty dict
    store.replace_messages(sid, [{"role": "user", "content": "world"}], metadata={})

    # Verify cleared
    session_final = store.get_session(sid)
    import json
    metadata = json.loads(session_final["metadata_json"])
    assert metadata == {}
