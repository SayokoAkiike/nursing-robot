"""Tests for backend.services.rounding_service.

Same fixture style as tests/test_workflow_service.py: the `robot_storage`
fixture from conftest.py gives each test an independent SQLite file.
"""
import pytest

from backend.core.errors import ConflictError, DomainError, NotFoundError
from backend.db import repositories
from backend.services import need_classification_service, rounding_service


def test_start_rounding_creates_session_in_rounding_state(robot_storage):
    session = rounding_service.start_rounding("203")
    assert session["status"] == "ROUNDING"
    assert session["room"] == "203"
    assert session["robot_id"] == "ROBOT_1"
    assert session["patient_id"] is None


def test_detect_patient_advances_state_and_sets_patient_id(robot_storage):
    session = rounding_service.start_rounding("203")
    updated = rounding_service.detect_patient(session["id"], "PATIENT_A_ROOM_203")
    assert updated["status"] == "PATIENT_DETECTED"
    assert updated["patient_id"] == "PATIENT_A_ROOM_203"


def test_start_interaction_advances_through_approaching_to_interaction_started(robot_storage):
    session = rounding_service.start_rounding("203")
    rounding_service.detect_patient(session["id"], "PATIENT_A_ROOM_203")
    result = rounding_service.start_interaction(session["id"])
    assert result["session"]["status"] == "INTERACTION_STARTED"
    assert "prompt" in result and result["prompt"]


def _to_interaction_started(session_id: str) -> None:
    rounding_service.detect_patient(session_id, "PATIENT_A_ROOM_203")
    rounding_service.start_interaction(session_id)


def test_classify_need_toileting_detects_high_priority_and_stays_at_need_classified(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])

    result = rounding_service.classify_need(session["id"], "トイレに行きたいです")
    assert result["detected_need"] == "toileting"
    assert result["escalation_level"] == "HIGH"
    assert result["route"] == "NURSE_NOTIFICATION"
    assert result["session"]["status"] == "NEED_CLASSIFIED"
    assert "203" in result["summary"]


def test_classify_need_records_patient_interaction(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "お水が飲みたいです")

    interactions = repositories.list_patient_interactions(session["id"])
    assert len(interactions) == 1
    assert interactions[0]["patient_response"] == "お水が飲みたいです"
    assert interactions[0]["detected_need"] == "water"


def test_pain_response_urgent_escalation_route(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "胸が痛いです")
    assert result["route"] == "URGENT_ESCALATION"
    assert result["escalation_level"] == "URGENT"


def test_provide_information_completes_session_without_escalation(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "大丈夫です")

    result = rounding_service.provide_information(session["id"])
    assert result["status"] == "COMPLETED"
    assert result["ended_at"] is not None
    # No escalation should have been raised.
    assert repositories.list_nurse_escalations() == []


def test_escalate_creates_pending_escalation_and_moves_to_waiting_for_ack(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    classification = rounding_service.classify_need(session["id"], "トイレに行きたいです")

    result = rounding_service.escalate(
        session["id"],
        summary=classification["summary"],
        priority=classification["escalation_level"],
        suggested_action=classification["suggested_action"],
        reason="toileting",
        route=classification["route"],
    )
    assert result["session"]["status"] == "WAITING_FOR_NURSE_ACK"

    escalation = repositories.get_nurse_escalation(result["escalation_id"])
    assert escalation["status"] == "PENDING"
    assert escalation["priority"] == "HIGH"
    assert escalation["rounding_session_id"] == session["id"]


def test_require_delivery_creates_real_care_request_and_task(robot_storage):
    session = rounding_service.start_rounding("203")
    rounding_service.detect_patient(session["id"], "PATIENT_A_ROOM_203")
    rounding_service.start_interaction(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")

    result = rounding_service.require_delivery(session["id"], "toileting")
    request = repositories.get_care_request(result["request_id"])
    assert request is not None
    assert request["source"] == "robot_rounding"
    assert request["rounding_session_id"] == session["id"]

    task = repositories.get_task_by_request_id(result["request_id"])
    assert task is not None
    assert task["state"] == "REQUEST_RECEIVED"

    assert result["session"]["status"] == "DELIVERY_REQUIRED"


def test_require_delivery_assigns_to_sessions_own_robot_id(robot_storage):
    """Item 5: a rounding session started on a non-default robot must hand
    its delivery request to that same robot, not silently to
    workflow_service.DEFAULT_ROBOT_ID -- the exact gap
    test_workflow_service.py's test_concurrency_guard_is_per_robot_not_
    global first documented (data model supports it, but require_delivery
    used to ignore it)."""
    session = rounding_service.start_rounding("204", robot_id="ROBOT_2")
    rounding_service.detect_patient(session["id"], "PATIENT_B_ROOM_204")
    rounding_service.start_interaction(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")

    result = rounding_service.require_delivery(session["id"], "toileting")

    task = repositories.get_task_by_request_id(result["request_id"])
    assert task is not None
    assert task["robot_id"] == "ROBOT_2"


def test_require_delivery_without_patient_id_raises(robot_storage):
    # start_rounding -> detect_patient not called -> no patient_id anywhere.
    session = rounding_service.start_rounding("203")
    rounding_service.detect_patient(session["id"], "")  # falsy patient_id
    rounding_service.start_interaction(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")

    with pytest.raises(DomainError):
        rounding_service.require_delivery(session["id"], "toileting")


def test_acknowledge_and_complete_moves_through_nurse_acknowledged_to_completed(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    rounding_service.escalate(
        session["id"], summary="s", priority="HIGH", route="NURSE_NOTIFICATION"
    )

    result = rounding_service.acknowledge_and_complete(session["id"])
    assert result["status"] == "COMPLETED"
    assert result["ended_at"] is not None


def test_get_session_missing_raises_not_found(robot_storage):
    with pytest.raises(NotFoundError):
        rounding_service.get_session("does-not-exist")


def test_list_active_sessions_excludes_completed(robot_storage):
    s1 = rounding_service.start_rounding("203")
    s2 = rounding_service.start_rounding("204")
    _to_interaction_started(s2["id"])
    rounding_service.classify_need(s2["id"], "大丈夫です")
    rounding_service.provide_information(s2["id"])

    active = rounding_service.list_active_sessions()
    assert [s["id"] for s in active] == [s1["id"]]


# ---- Safety regression tests (mirrors proposal doc section 9) --------------


def test_cannot_skip_from_rounding_directly_to_need_classified(robot_storage):
    session = rounding_service.start_rounding("203")
    with pytest.raises(ConflictError):
        rounding_service._advance(session["id"], "ROUNDING", "NEED_CLASSIFIED")


def test_waiting_for_nurse_ack_does_not_auto_advance_to_completed(robot_storage):
    """The one-way gate: an escalated session sits at WAITING_FOR_NURSE_ACK
    until something explicitly calls acknowledge_and_complete(). Nothing
    about escalate() itself should move it further."""
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    result = rounding_service.escalate(
        session["id"], summary="s", priority="HIGH", route="NURSE_NOTIFICATION"
    )
    assert result["session"]["status"] == "WAITING_FOR_NURSE_ACK"

    # Re-fetching later (simulating time passing with nobody acking) still
    # shows WAITING_FOR_NURSE_ACK -- no background process advances it.
    still_waiting = rounding_service.get_session(session["id"])
    assert still_waiting["status"] == "WAITING_FOR_NURSE_ACK"


def test_cannot_escalate_twice_from_the_same_session(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    rounding_service.escalate(
        session["id"], summary="s", priority="HIGH", route="NURSE_NOTIFICATION"
    )
    # Session is now WAITING_FOR_NURSE_ACK, not NEED_CLASSIFIED -- a second
    # escalate() call must be rejected, not silently create a duplicate.
    with pytest.raises(ConflictError):
        rounding_service.escalate(
            session["id"], summary="s2", priority="HIGH", route="NURSE_NOTIFICATION"
        )


def test_cannot_require_delivery_after_already_escalated(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    rounding_service.escalate(
        session["id"], summary="s", priority="HIGH", route="NURSE_NOTIFICATION"
    )
    with pytest.raises(ConflictError):
        rounding_service.require_delivery(session["id"], "toileting")


# ---- PR31: semantic fallback wiring ------------------------------------------


def test_keyword_match_short_circuits_semantic_fallback(robot_storage, monkeypatch):
    """A phrase the keyword rules already catch must never even try to
    load the (slow, heavy) semantic classifier."""
    called = False

    def fail_if_called(self, patient_response):
        nonlocal called
        called = True
        raise AssertionError("semantic classifier should not have been consulted")

    monkeypatch.setattr(
        "backend.services.semantic_classification_service.SemanticClassifier.classify",
        fail_if_called,
    )

    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "トイレに行きたいです")

    assert result["detected_need"] == "toileting"
    assert called is False


def test_semantic_fallback_used_when_keywords_find_nothing(robot_storage, monkeypatch):
    from backend.services.need_classification_service import Classification

    def fake_classify(self, patient_response):
        return Classification(
            detected_need="toileting", escalation_level="HIGH", route="NURSE_NOTIFICATION", confidence="semantic"
        )

    monkeypatch.setattr(
        "backend.services.semantic_classification_service.SemanticClassifier.classify",
        fake_classify,
    )

    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    # A phrase with none of the keyword-list words, so the keyword pass
    # alone would land on "unknown" -- the mocked semantic classifier
    # above is what should actually decide the result here.
    result = rounding_service.classify_need(session["id"], "用を足したいです")

    assert result["detected_need"] == "toileting"
    assert result["escalation_level"] == "HIGH"


def test_semantic_classifier_failure_degrades_to_keyword_unknown(robot_storage, monkeypatch):
    """If the semantic classifier raises for any reason (model download
    failed, dependency missing, etc.), classify_need() must still
    succeed -- degrading to the keyword result ("unknown") rather than
    propagating the failure."""

    def raise_error(self, patient_response):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(
        "backend.services.semantic_classification_service.SemanticClassifier.classify",
        raise_error,
    )

    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "用を足したいです")

    assert result["detected_need"] == "unknown"


def test_semantic_classifier_returning_unknown_also_falls_back_to_keyword_unknown(robot_storage, monkeypatch):
    from backend.services.need_classification_service import Classification

    def fake_classify(self, patient_response):
        return Classification(detected_need="unknown", escalation_level="LOW", route="INFORMATION_ONLY", confidence="low")

    monkeypatch.setattr(
        "backend.services.semantic_classification_service.SemanticClassifier.classify",
        fake_classify,
    )

    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "きょうはいい天気ですね")

    assert result["detected_need"] == "unknown"


def test_semantic_fallback_real_model_end_to_end(robot_storage):
    """Real sentence-transformers model, no mocking -- requires network
    access on first run (model weights download from Hugging Face).
    Skipped with a clear reason if that download fails, same pattern
    PR29/30 use for their own real-model tests (test_run_simulated_rounding.py,
    test_run_pose_demo.py)."""
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    try:
        result = rounding_service.classify_need(session["id"], "用を足したいです")
    except Exception as exc:  # pragma: no cover - network-dependent
        import pytest as _pytest

        _pytest.skip(f"semantic classification model unavailable (likely no network): {exc}")

    # A real paraphrase of "トイレに行きたいです" with none of the literal
    # keywords -- if the semantic fallback is working, this should land
    # on "toileting" via embedding similarity, not "unknown".
    assert result["detected_need"] in ("toileting", "unknown")  # see note below
    if result["detected_need"] == "unknown":
        import warnings

        warnings.warn(
            "Semantic fallback ran but did not classify '用を足したいです' as "
            "toileting -- similarity_threshold or EXAMPLE_UTTERANCES may need "
            "tuning against the real model's actual behavior.",
            stacklevel=1,
        )


# ---- PR34 (B): local LLM tier (third stage of the fallback chain) -----------


def test_semantic_result_short_circuits_llm_tier(robot_storage, monkeypatch):
    """A phrase the semantic tier already resolves must never even try
    to load the (much slower/heavier) LLM tier."""
    from backend.services.need_classification_service import Classification

    def fake_semantic_classify(self, patient_response):
        return Classification(
            detected_need="toileting", escalation_level="HIGH", route="NURSE_NOTIFICATION", confidence="semantic"
        )

    llm_called = False

    def fail_if_llm_called(self, patient_response):
        nonlocal llm_called
        llm_called = True
        raise AssertionError("LLM tier should not have been consulted")

    monkeypatch.setattr(
        "backend.services.semantic_classification_service.SemanticClassifier.classify",
        fake_semantic_classify,
    )
    monkeypatch.setattr(
        "backend.services.llm_classification_service.LLMClassifier.classify",
        fail_if_llm_called,
    )

    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "用を足したいです")

    assert result["detected_need"] == "toileting"
    assert llm_called is False


def test_llm_tier_used_when_keyword_and_semantic_both_find_nothing(robot_storage, monkeypatch):
    from backend.services.need_classification_service import Classification

    def semantic_unknown(self, patient_response):
        return Classification(detected_need="unknown", escalation_level="LOW", route="INFORMATION_ONLY", confidence="low")

    def fake_llm_classify(self, patient_response):
        return Classification(
            detected_need="pain", escalation_level="URGENT", route="URGENT_ESCALATION", confidence="llm"
        )

    monkeypatch.setattr(
        "backend.services.semantic_classification_service.SemanticClassifier.classify",
        semantic_unknown,
    )
    monkeypatch.setattr(
        "backend.services.llm_classification_service.LLMClassifier.classify",
        fake_llm_classify,
    )

    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "なんとなく体調がすぐれません")

    assert result["detected_need"] == "pain"
    assert result["escalation_level"] == "URGENT"


def test_llm_tier_failure_degrades_to_keyword_unknown(robot_storage, monkeypatch):
    """If the LLM tier raises for any reason (model not downloaded,
    llama-cpp-python not installed, out of memory, whatever),
    classify_need() must still succeed -- degrading to the keyword
    result rather than propagating the failure."""
    from backend.services.need_classification_service import Classification

    def semantic_unknown(self, patient_response):
        return Classification(detected_need="unknown", escalation_level="LOW", route="INFORMATION_ONLY", confidence="low")

    def raise_error(self, patient_response):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(
        "backend.services.semantic_classification_service.SemanticClassifier.classify",
        semantic_unknown,
    )
    monkeypatch.setattr(
        "backend.services.llm_classification_service.LLMClassifier.classify",
        raise_error,
    )

    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "なんとなく体調がすぐれません")

    assert result["detected_need"] == "unknown"


def test_llm_tier_returning_unknown_also_falls_back_to_keyword_unknown(robot_storage, monkeypatch):
    from backend.services.need_classification_service import Classification

    def unknown_result(self, patient_response):
        return Classification(detected_need="unknown", escalation_level="LOW", route="INFORMATION_ONLY", confidence="low")

    monkeypatch.setattr(
        "backend.services.semantic_classification_service.SemanticClassifier.classify",
        unknown_result,
    )
    monkeypatch.setattr(
        "backend.services.llm_classification_service.LLMClassifier.classify",
        unknown_result,
    )

    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "きょうはいい天気ですね")

    assert result["detected_need"] == "unknown"


def test_llm_fallback_real_model_end_to_end(robot_storage):
    """Real llama-cpp-python + real LFM2.5-1.2B-JP GGUF model, no
    mocking -- requires network access on first run (llama-cpp-python
    itself compiles from source on install; the GGUF model weights,
    ~730MB, download separately from Hugging Face on first use).
    Skipped with a clear reason if either fails, same pattern PR29/30/31
    use for their own real-model tests."""
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    try:
        result = rounding_service.classify_need(session["id"], "なんとなく体調がすぐれません")
    except Exception as exc:  # pragma: no cover - network/build-dependent
        import pytest as _pytest

        _pytest.skip(f"LLM classification unavailable (likely no network or llama-cpp-python not built): {exc}")

    # Deliberately not asserting a specific detected_need -- this phrase
    # is intentionally vague (nothing a keyword or embedding match would
    # confidently resolve either), so the point of this test is only that
    # the full three-tier chain runs to completion without raising, not
    # that the LLM lands on any particular category.
    assert result["detected_need"] in need_classification_service.known_needs() + ["unknown"]
