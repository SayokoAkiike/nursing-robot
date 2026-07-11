"""Tests for backend/scripts/benchmark_classification_chain.py.

This script's whole purpose is measuring *real* wall-clock latency, so
these tests don't assert on actual timing numbers (which would be
flaky by nature) -- they mock every tier and check the script's own
logic instead: that it calls each tier the expected number of times,
that skip_llm actually skips the LLM tier, and that the returned timing
dict has the expected keys. Real timing numbers are meant to be read
from this script's own stdout when run manually against real models
(see the module docstring) -- there is no meaningful pass/fail
assertion for "was this fast enough" here.
"""
from unittest.mock import patch

from backend.scripts.benchmark_classification_chain import run


def _fake_classification(detected_need="unknown", confidence="low"):
    from backend.services.need_classification_service import Classification

    return Classification(detected_need=detected_need, escalation_level="LOW", route="INFORMATION_ONLY", confidence=confidence)


@patch("backend.services.rounding_service._classify_with_ml_fallbacks")
@patch("backend.services.llm_classification_service.LLMClassifier")
@patch("backend.services.semantic_classification_service.SemanticClassifier")
def test_run_returns_timing_for_every_tier(mock_semantic_cls, mock_llm_cls, mock_full_chain):
    mock_semantic_cls.return_value.classify.return_value = _fake_classification()
    mock_llm_cls.return_value.classify.return_value = _fake_classification()
    mock_full_chain.return_value = _fake_classification()

    timings = run()

    assert set(timings.keys()) == {
        "keyword",
        "semantic_cold",
        "semantic_warm",
        "llm_cold",
        "llm_warm",
        "full_chain_worst_case",
    }
    assert all(isinstance(v, float) and v >= 0 for v in timings.values())


@patch("backend.services.rounding_service._classify_with_ml_fallbacks")
@patch("backend.services.semantic_classification_service.SemanticClassifier")
def test_skip_llm_omits_llm_timings(mock_semantic_cls, mock_full_chain):
    mock_semantic_cls.return_value.classify.return_value = _fake_classification()
    mock_full_chain.return_value = _fake_classification()

    timings = run(skip_llm=True)

    assert "llm_cold" not in timings
    assert "llm_warm" not in timings
    assert "keyword" in timings
    assert "semantic_warm" in timings


@patch("backend.services.rounding_service._classify_with_ml_fallbacks")
@patch("backend.services.llm_classification_service.LLMClassifier")
@patch("backend.services.semantic_classification_service.SemanticClassifier")
def test_semantic_classifier_constructed_once_and_reused(mock_semantic_cls, mock_llm_cls, mock_full_chain):
    """The whole point of measuring 'cold' vs 'warm' is the same
    instance across both calls -- constructing a fresh SemanticClassifier
    for the second call would defeat the comparison."""
    mock_semantic_cls.return_value.classify.return_value = _fake_classification()
    mock_llm_cls.return_value.classify.return_value = _fake_classification()
    mock_full_chain.return_value = _fake_classification()

    run()

    mock_semantic_cls.assert_called_once()
    assert mock_semantic_cls.return_value.classify.call_count == 2


@patch("backend.services.rounding_service._classify_with_ml_fallbacks")
@patch("backend.services.llm_classification_service.LLMClassifier")
@patch("backend.services.semantic_classification_service.SemanticClassifier")
def test_llm_classifier_constructed_once_and_reused(mock_semantic_cls, mock_llm_cls, mock_full_chain):
    mock_semantic_cls.return_value.classify.return_value = _fake_classification()
    mock_llm_cls.return_value.classify.return_value = _fake_classification()
    mock_full_chain.return_value = _fake_classification()

    run()

    mock_llm_cls.assert_called_once()
    assert mock_llm_cls.return_value.classify.call_count == 2
