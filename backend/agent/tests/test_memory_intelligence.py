import asyncio
import json
from pathlib import Path

from g_agent.agent.memory import MemoryStore
from g_agent.agent.tools.integrations import RecallTool


def _load_fact_records(memory_dir: Path) -> list[dict]:
    records: list[dict] = []
    content = (memory_dir / "FACTS.md").read_text(encoding="utf-8")
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith("{"):
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def test_remember_fact_writes_schema_record(tmp_path: Path):
    store = MemoryStore(tmp_path)
    result = store.remember_fact(
        fact="timezone: Asia/Jakarta",
        category="identity",
        source="user_input",
        confidence=0.91,
    )

    assert result["ok"] is True
    assert result["status"] == "added"

    records = _load_fact_records(tmp_path / "memory")
    item = next((entry for entry in records if entry.get("fact_key") == "timezone"), None)
    assert item is not None
    assert item["type"] == "identity"
    assert item["source"] == "user_input"
    assert item["confidence"] == 0.91
    assert item["last_seen"]
    assert item["supersedes"] == []

    long_term = store.read_long_term()
    assert "type=identity" in long_term
    assert "timezone: Asia/Jakarta" in long_term


def test_remember_fact_supersedes_previous_same_key(tmp_path: Path):
    store = MemoryStore(tmp_path)
    first = store.remember_fact("timezone: Asia/Jakarta", category="identity")
    second = store.remember_fact("timezone: UTC", category="identity")

    assert first["status"] == "added"
    assert second["status"] == "superseded"
    assert len(second["superseded_ids"]) == 1

    records = _load_fact_records(tmp_path / "memory")
    timezone_items = [item for item in records if item.get("fact_key") == "timezone"]
    active = [item for item in timezone_items if item.get("status") == "active"]
    superseded = [item for item in timezone_items if item.get("status") == "superseded"]
    assert len(active) == 1
    assert len(superseded) == 1
    assert active[0]["text"] == "timezone: UTC"
    assert superseded[0]["superseded_by"] == active[0]["id"]


def test_recall_explain_hides_superseded_fact(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.remember_fact("timezone: Asia/Jakarta", category="identity", confidence=0.92)
    store.remember_fact("timezone: UTC", category="identity", confidence=0.92)
    store.remember_fact("favorite editor: neovim", category="preferences", confidence=0.85)

    recalled = store.recall(query="what is my timezone", max_items=5, explain=True)
    assert recalled
    assert recalled[0]["text"] == "timezone: UTC"
    assert recalled[0]["why"]["overlap_count"] >= 1
    assert "timezone" in recalled[0]["why"]["overlap_terms"]
    assert all(item["text"] != "timezone: Asia/Jakarta" for item in recalled)

    recall_tool = RecallTool(workspace=tmp_path)
    output = asyncio.run(recall_tool.execute(query="timezone", explain=True))
    assert "why:" in output
    assert "timezone: UTC" in output


def test_bootstrap_fact_index_from_fixture_resolves_conflicts(tmp_path: Path):
    fixture = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "memory_conflicts.md"
    )
    store = MemoryStore(tmp_path)
    store.write_long_term(fixture.read_text(encoding="utf-8"))

    records = store._load_fact_index()
    active = [entry for entry in records if entry.get("status") == "active"]
    superseded = [entry for entry in records if entry.get("status") == "superseded"]

    timezone_active = [
        entry for entry in active
        if entry.get("fact_key") == "timezone"
    ]
    editor_active = [
        entry for entry in active
        if entry.get("fact_key") == "editor"
    ]
    focus_active = [
        entry for entry in active
        if entry.get("fact_key") == "focus"
    ]

    assert len(records) == 7
    assert len(active) == 3
    assert len(superseded) == 4
    assert timezone_active[0]["text"] == "timezone: Asia/Singapore"
    assert editor_active[0]["text"] == "editor: helix"
    assert focus_active[0]["text"] == "focus: g-agent memory quality"


def test_recall_ranking_deterministic_for_score_ties(tmp_path: Path, monkeypatch):
    store = MemoryStore(tmp_path)

    first = {
        "source": "profile",
        "text": "beta alpha",
        "age_days": 0,
        "type": "profile",
        "confidence": 0.9,
        "meta": {"fact_id": "fact_b"},
    }
    second = {
        "source": "profile",
        "text": "alpha beta",
        "age_days": 0,
        "type": "profile",
        "confidence": 0.9,
        "meta": {"fact_id": "fact_a"},
    }
    order = {"flip": False}

    def fake_iter_memory_candidates(*args, **kwargs):
        order["flip"] = not order["flip"]
        if order["flip"]:
            return [first, second]
        return [second, first]

    monkeypatch.setattr(store, "_iter_memory_candidates", fake_iter_memory_candidates)

    recalled_first = store.recall(query="alpha beta", max_items=2)
    recalled_second = store.recall(query="alpha beta", max_items=2)

    assert [item["text"] for item in recalled_first] == [item["text"] for item in recalled_second]
    assert [item["text"] for item in recalled_first] == ["alpha beta", "beta alpha"]


def test_multilingual_fixture_overlap_ranking(tmp_path: Path):
    fixture = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "memory_multilingual.md"
    )
    store = MemoryStore(tmp_path)
    store.write_long_term(fixture.read_text(encoding="utf-8"))
    store._load_fact_index()

    mixed_query = "jadwal weekly meeting architecture"
    recalled_meeting = store.recall(query=mixed_query, max_items=3)
    assert recalled_meeting
    assert recalled_meeting[0]["text"] == "jadwal meeting weekly architecture review"

    focus_query = "fokus build memory quality"
    recalled_focus = store.recall(query=focus_query, max_items=3)
    assert recalled_focus
    assert recalled_focus[0]["text"] == "fokus: build agent memory quality"


def test_recall_semantic_normalization_handles_mixed_language_synonyms(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.write_long_term(
        "# Long-term Memory\n\n"
        "- [2026-01-09 09:00] (projects) jadwal rapat mingguan arsitektur\n"
        "- [2026-01-09 10:00] (projects) sales followup enterprise\n"
    )
    store._load_fact_index()

    recalled = store.recall(query="weekly meeting architecture schedule", max_items=2, explain=True)
    assert recalled
    assert recalled[0]["text"] == "jadwal rapat mingguan arsitektur"
    assert recalled[0]["why"]["overlap_count"] >= 3
    assert "weekly" in recalled[0]["why"]["overlap_terms"]
    assert "meeting" in recalled[0]["why"]["overlap_terms"]


def test_detect_cross_scope_fact_conflicts_profile_long_term_custom(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.remember_fact("timezone: UTC", category="identity", source="user_input")
    store.upsert_profile_field("Identity", "timezone", "Asia/Jakarta")
    (tmp_path / "memory" / "assistant_profile.md").write_text(
        "# Assistant Profile\n\n- timezone: Asia/Singapore\n",
        encoding="utf-8",
    )

    conflicts = store.detect_cross_scope_fact_conflicts()
    timezone_conflict = next((item for item in conflicts if item.get("key") == "timezone"), None)

    assert timezone_conflict is not None
    assert set(timezone_conflict["scopes"]) == {"custom", "long-term", "profile"}
    assert timezone_conflict["preferred_scope"] == "profile"
    assert timezone_conflict["preferred_value"] == "Asia/Jakarta"

    values = {item["value"] for item in timezone_conflict["conflicting_facts"]}
    assert values == {"Asia/Singapore", "UTC"}
    sources = {item["source"] for item in timezone_conflict["conflicting_facts"]}
    assert "assistant_profile" in sources
    assert "long-term" in sources


def test_detect_summary_fact_drift_flags_conflict_only(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.remember_fact("timezone: UTC", category="identity", source="user_input")
    store.append_session_summary("chat-1", "timezone: UTC")
    store.append_session_summary("chat-2", "timezone: Asia/Jakarta")

    drifts = store.detect_summary_fact_drift()
    assert len(drifts) == 1
    assert drifts[0]["key"] == "timezone"
    assert drifts[0]["active_fact"] == "timezone: UTC"
    assert "Asia/Jakarta" in drifts[0]["summary_fact"]
