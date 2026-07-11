"""Tests for backend/services/semantic_classification_service.py.

SentenceTransformer is mocked (same approach as
test_speech_recognizer.py / test_pose_detector.py mocking their ML
libraries) -- these tests exercise SemanticClassifier's own logic
(lazy loading, threshold behavior, category lookup) without downloading
the real ~470MB model. tests/test_rounding_service.py has one real
(non-mocked) end-to-end test of the fallback wiring, gated to skip on
network failure the same way PR29/30's real-model tests are.
"""
from unittest.mock import MagicMock, patch

import numpy as np

from backend.services import need_classification_service
from backend.services.semantic_classification_service import (
    EXAMPLE_UTTERANCES,
    SemanticClassifier,
)


def _fake_model_with_fixed_similarities(similarities_by_need: dict) -> MagicMock:
    """Builds a mock SentenceTransformer whose .encode() returns
    embeddings engineered so the cosine similarity between the query and
    each category's examples reflects similarities_by_need -- lets a
    test control exactly which category "wins" and by how much, without
    a real model."""
    need_list = list(EXAMPLE_UTTERANCES.keys())
    needs_in_order = []
    for need, examples in EXAMPLE_UTTERANCES.items():
        needs_in_order.extend([need] * len(examples))
    dim = len(need_list)

    example_embeddings = np.zeros((len(needs_in_order), dim))
    for i, need in enumerate(needs_in_order):
        axis = need_list.index(need)
        example_embeddings[i, axis] = 1.0

    query_embedding = np.zeros(dim)
    for need, sim in similarities_by_need.items():
        axis = need_list.index(need)
        query_embedding[axis] = sim

    model = MagicMock()

    def fake_encode(texts, normalize_embeddings=True):
        if len(texts) == 1:
            return np.array([query_embedding])
        return example_embeddings

    model.encode.side_effect = fake_encode
    return model


@patch("sentence_transformers.SentenceTransformer")
def test_classify_returns_best_matching_category_above_threshold(mock_st_cls):
    mock_st_cls.return_value = _fake_model_with_fixed_similarities({"toileting": 0.9})

    classifier = SemanticClassifier(similarity_threshold=0.5)
    result = classifier.classify("お手洗いに連れて行ってください")

    assert result.detected_need == "toileting"
    assert result.confidence == "semantic"
    assert result.escalation_level == need_classification_service.escalation_level_for("toileting")
    assert result.route == need_classification_service.route_for("toileting")


@patch("sentence_transformers.SentenceTransformer")
def test_classify_below_threshold_falls_back_to_unknown(mock_st_cls):
    mock_st_cls.return_value = _fake_model_with_fixed_similarities({"toileting": 0.3})

    classifier = SemanticClassifier(similarity_threshold=0.5)
    result = classifier.classify("何か関係のない発話")

    assert result.detected_need == "unknown"
    assert result.confidence == "low"


def test_classify_empty_response_is_unknown_without_loading_model():
    classifier = SemanticClassifier()
    result = classifier.classify("")
    assert result.detected_need == "unknown"
    assert classifier._model is None  # never touched the model for empty input


def test_model_not_loaded_until_first_classify():
    classifier = SemanticClassifier()
    assert classifier._model is None


@patch("sentence_transformers.SentenceTransformer")
def test_example_embeddings_cached_across_calls(mock_st_cls):
    mock_model = _fake_model_with_fixed_similarities({"pain": 0.9})
    mock_st_cls.return_value = mock_model

    classifier = SemanticClassifier(similarity_threshold=0.5)
    classifier.classify("痛いです")
    classifier.classify("痛いです")

    mock_st_cls.assert_called_once()


def test_every_known_need_has_example_utterances():
    """Regression guard: semantic_classification_service must have
    examples for every need need_classification_service's rules can
    produce, or a real gap would silently make some needs unreachable
    via the semantic fallback."""
    for need in need_classification_service.known_needs():
        assert need in EXAMPLE_UTTERANCES, f"no example utterances for {need!r}"
        assert len(EXAMPLE_UTTERANCES[need]) >= 2
