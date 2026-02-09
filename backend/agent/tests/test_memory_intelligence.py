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
