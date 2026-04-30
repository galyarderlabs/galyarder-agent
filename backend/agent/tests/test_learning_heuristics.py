from pathlib import Path
from g_agent.learning.reviewer import BackgroundLearningReviewer, LearningReviewInput
from g_agent.learning.apply import apply_learning_candidate


def test_reviewer_profile_requires_explicit_directive(tmp_path: Path):
    """Profile candidates require explicit user directive, not agent self-declaration."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    # Explicit directive - should create candidate
    review_explicit = LearningReviewInput(
        session_key="cli:test",
        user_content="change your name to Keiya",
        assistant_content="Understood, I will use Keiya as my name.",
    )
    candidates = reviewer.review_turn(review_explicit)
    profile_cands = [c for c in candidates if c.kind == "profile"]
    assert len(profile_cands) == 1
    assert "Keiya" in profile_cands[0].content["text"]
    assert profile_cands[0].content["text"] == review_explicit.user_content

    # Agent self-declaration without user directive - should NOT create candidate
    review_self = LearningReviewInput(
        session_key="cli:test",
        user_content="ok",
        assistant_content="Siap boss, mulai sekarang panggil saya Keiya.",
    )
    candidates_self = reviewer.review_turn(review_self)
    profile_cands_self = [c for c in candidates_self if c.kind == "profile"]
    assert len(profile_cands_self) == 0, "Agent self-declaration should not create profile candidate"


def test_reviewer_relationship_requires_explicit_definition(tmp_path: Path):
    """Relationship candidates require explicit definition, not casual mentions."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    # Explicit definition - should create candidate
    review_explicit = LearningReviewInput(
        session_key="cli:test",
        user_content="You are my technical assistant and advisor.",
        assistant_content="Understood, I will act as your technical assistant.",
    )
    candidates = reviewer.review_turn(review_explicit)
    rel_cands = [c for c in candidates if c.kind == "relationship"]
    assert len(rel_cands) == 1
    assert "assistant" in rel_cands[0].content["text"]

    # Casual mention - should NOT create candidate
    review_casual = LearningReviewInput(
        session_key="cli:test",
        user_content="thanks boss",
        assistant_content="You're welcome!",
    )
    candidates_casual = reviewer.review_turn(review_casual)
    rel_cands_casual = [c for c in candidates_casual if c.kind == "relationship"]
    assert len(rel_cands_casual) == 0, "Casual mention should not create relationship candidate"


def test_reviewer_routine_requires_schedule_and_time(tmp_path: Path):
    """Routine candidates require both recurring schedule and time specification."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    # Complete routine with schedule and time - should create candidate
    review_complete = LearningReviewInput(
        session_key="cli:test",
        user_content="Send me a daily summary report every day at 9:00 AM",
        assistant_content="I'll set that up for you.",
    )
    candidates = reviewer.review_turn(review_complete)
    routine_cands = [c for c in candidates if c.kind == "routine"]
    assert len(routine_cands) == 1

    # Schedule without time - should NOT create candidate
    review_no_time = LearningReviewInput(
        session_key="cli:test",
        user_content="Send me a daily summary report every day",
        assistant_content="I'll set that up for you.",
    )
    candidates_no_time = reviewer.review_turn(review_no_time)
    routine_cands_no_time = [c for c in candidates_no_time if c.kind == "routine"]
    assert len(routine_cands_no_time) == 0, "Routine without time should not create candidate"

    # Vague future reference - should NOT create candidate
    review_vague = LearningReviewInput(
        session_key="cli:test",
        user_content="nanti kirim laporan ya",
        assistant_content="Baik.",
    )
    candidates_vague = reviewer.review_turn(review_vague)
    routine_cands_vague = [c for c in candidates_vague if c.kind == "routine"]
    assert len(routine_cands_vague) == 0, "Vague future reference should not create routine candidate"

    # URL with colon should NOT trigger false positive
    review_url = LearningReviewInput(
        session_key="cli:test",
        user_content="Check https://example.com:8080/status every day for updates",
        assistant_content="I'll monitor that.",
    )
    candidates_url = reviewer.review_turn(review_url)
    routine_cands_url = [c for c in candidates_url if c.kind == "routine"]
    assert len(routine_cands_url) == 0, "URL with colon should not create routine candidate"


def test_reviewer_memory_requires_explicit_directive(tmp_path: Path):
    """Memory candidates require explicit remember/preference directive."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    # Explicit remember directive - should create candidate
    review_explicit = LearningReviewInput(
        session_key="cli:test",
        user_content="Remember that I prefer using pytest over unittest",
        assistant_content="Noted, I'll use pytest for testing.",
    )
    candidates = reviewer.review_turn(review_explicit)
    memory_cands = [c for c in candidates if c.kind == "memory"]
    assert len(memory_cands) == 1
    assert "pytest" in memory_cands[0].content["text"]

    # Casual mention without directive - should NOT create candidate
    review_casual = LearningReviewInput(
        session_key="cli:test",
        user_content="biasanya saya pakai pytest",
        assistant_content="Ok.",
    )
    candidates_casual = reviewer.review_turn(review_casual)
    memory_cands_casual = [c for c in candidates_casual if c.kind == "memory"]
    assert len(memory_cands_casual) == 0, "Casual mention should not create memory candidate"

    # Too short directive (less than 5 words) - should NOT create candidate
    review_short = LearningReviewInput(
        session_key="cli:test",
        user_content="remember that ok",
        assistant_content="Ok.",
    )
    candidates_short = reviewer.review_turn(review_short)
    memory_cands_short = [c for c in candidates_short if c.kind == "memory"]
    assert len(memory_cands_short) == 0, "Too-short directive should not create memory candidate"


def test_reviewer_no_false_positives_casual_conversation(tmp_path: Path):
    """Casual conversation should not trigger any learning candidates."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    casual_exchanges = [
        ("apa kabar?", "baik bro."),
        ("thanks boss", "you're welcome"),
        ("nanti ya", "ok"),
        ("setiap kali gini nih", "haha iya"),
        ("biasanya gitu", "memang"),
    ]

    for user_msg, assistant_msg in casual_exchanges:
        review = LearningReviewInput(
            session_key="cli:test",
            user_content=user_msg,
            assistant_content=assistant_msg,
        )
        candidates = reviewer.review_turn(review)
        assert len(candidates) == 0, f"Casual exchange '{user_msg}' should not create candidates"


def test_apply_profile_requires_manual_review(tmp_path: Path):
    """Profile candidates must return manual_review_required, not auto-apply."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    review = LearningReviewInput(
        session_key="cli:test",
        user_content="change your name to TestBot",
        assistant_content="Ok, I'll use TestBot.",
    )
    candidates = reviewer.enqueue_turn(review)
    profile_cands = [c for c in candidates if c.kind == "profile"]
    assert len(profile_cands) == 1

    candidate_id = profile_cands[0].id
    result = apply_learning_candidate(tmp_path, candidate_id)

    assert not result.ok
    assert result.code == "manual_review_required"
    assert "manual review" in result.message.lower()


def test_apply_relationship_requires_manual_review(tmp_path: Path):
    """Relationship candidates must return manual_review_required, not auto-apply."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    review = LearningReviewInput(
        session_key="cli:test",
        user_content="You are my coding partner and mentor.",
        assistant_content="Understood.",
    )
    candidates = reviewer.enqueue_turn(review)
    rel_cands = [c for c in candidates if c.kind == "relationship"]
    assert len(rel_cands) == 1

    candidate_id = rel_cands[0].id
    result = apply_learning_candidate(tmp_path, candidate_id)

    assert not result.ok
    assert result.code == "manual_review_required"
    assert "manual review" in result.message.lower()


def test_apply_routine_requires_manual_review(tmp_path: Path):
    """Routine candidates must return manual_review_required, not auto-scaffold."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    review = LearningReviewInput(
        session_key="cli:test",
        user_content="Send me a status update every day at 10:00 AM",
        assistant_content="I'll set that up.",
    )
    candidates = reviewer.enqueue_turn(review)
    routine_cands = [c for c in candidates if c.kind == "routine"]
    assert len(routine_cands) == 1

    candidate_id = routine_cands[0].id
    result = apply_learning_candidate(tmp_path, candidate_id)

    assert not result.ok
    assert result.code == "manual_review_required"
    assert "manual" in result.message.lower()


def test_apply_tool_quirk_requires_manual_review(tmp_path: Path):
    """Tool quirk candidates must return manual_review_required, not auto-apply."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    review = LearningReviewInput(
        session_key="cli:test",
        user_content="run the tests",
        assistant_content="Running tests...",
        tool_calls=[
            {"tool_name": "pytest", "status": "failure", "result_summary": "ModuleNotFoundError"}
        ],
    )
    candidates = reviewer.enqueue_turn(review)
    quirk_cands = [c for c in candidates if c.kind == "tool_quirk"]
    assert len(quirk_cands) == 1

    candidate_id = quirk_cands[0].id
    result = apply_learning_candidate(tmp_path, candidate_id)

    assert not result.ok
    assert result.code == "manual_review_required"
    assert "manual" in result.message.lower()


def test_apply_memory_validates_explicit_directive(tmp_path: Path):
    """Memory apply should validate explicit directive is present."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    # Valid explicit memory
    review_valid = LearningReviewInput(
        session_key="cli:test",
        user_content="Remember that I prefer using ruff for linting",
        assistant_content="Noted.",
    )
    candidates_valid = reviewer.enqueue_turn(review_valid)
    memory_cands = [c for c in candidates_valid if c.kind == "memory"]
    assert len(memory_cands) == 1

    candidate_id = memory_cands[0].id
    result = apply_learning_candidate(tmp_path, candidate_id)

    assert result.ok
    assert result.code == "applied"


def test_apply_skill_lifecycle_preserved(tmp_path: Path):
    """Skill candidates should still support apply with validation."""
    reviewer = BackgroundLearningReviewer(tmp_path)

    # Create skill candidate with multiple tool calls
    review = LearningReviewInput(
        session_key="cli:test",
        user_content="analyze the codebase",
        assistant_content="Analyzing...",
        tool_calls=[
            {"tool_name": "glob", "status": "success"},
            {"tool_name": "read", "status": "success"},
            {"tool_name": "grep", "status": "success"},
        ],
    )
    candidates = reviewer.enqueue_turn(review)
    skill_cands = [c for c in candidates if c.kind == "skill"]
    assert len(skill_cands) == 1

    # Skill apply should work (has validation/rollback infrastructure)
    candidate_id = skill_cands[0].id
    result = apply_learning_candidate(tmp_path, candidate_id)

    # May fail validation but should not return manual_review_required
    assert result.code in {"applied", "draft_validation_failed", "activation_failed"}
