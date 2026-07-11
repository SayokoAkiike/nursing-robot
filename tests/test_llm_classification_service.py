"""Tests for backend/services/llm_classification_service.py.

llama_cpp.Llama is mocked (same approach as every other ML wrapper's
tests in this codebase: test_speech_recognizer.py, test_pose_detector.py,
test_semantic_classification_service.py) -- these exercise
LLMClassifier's own logic (lazy loading, prompt construction, output
parsing, empty-input short-circuit) without downloading the real
~730MB GGUF model or compiling llama-cpp-python's C++ backend.
tests/test_rounding_service.py has the real (non-mocked) end-to-end
test of the full three-tier fallback chain, gated to skip on failure
the same way PR29/30/31's real-model tests are.
"""
from unittest.mock import MagicMock, patch


from backend.services import need_classification_service
from backend.services.llm_classification_service import LLMClassifier


def _fake_chat_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_classify_empty_response_is_unknown_without_loading_model():
    classifier = LLMClassifier()
    result = classifier.classify("")
    assert result.detected_need == "unknown"
    assert classifier._model is None  # never touched the model for empty input


def test_model_not_loaded_until_first_classify():
    classifier = LLMClassifier()
    assert classifier._model is None


@patch("llama_cpp.Llama")
def test_classify_parses_exact_category_name(mock_llama_cls):
    mock_model = MagicMock()
    mock_model.create_chat_completion.return_value = _fake_chat_response("toileting")
    mock_llama_cls.from_pretrained.return_value = mock_model

    classifier = LLMClassifier()
    result = classifier.classify("お手洗いに連れて行ってほしいです")

    assert result.detected_need == "toileting"
    assert result.confidence == "llm"
    assert result.escalation_level == need_classification_service.escalation_level_for("toileting")
    assert result.route == need_classification_service.route_for("toileting")


@patch("llama_cpp.Llama")
def test_classify_tolerates_extra_text_around_category_name(mock_llama_cls):
    """Small local models don't always follow 'output nothing but the
    category name' perfectly -- the parser must still find a known
    category name embedded in a longer response."""
    mock_model = MagicMock()
    mock_model.create_chat_completion.return_value = _fake_chat_response(
        "カテゴリ: pain です。至急対応が必要と思われます。"
    )
    mock_llama_cls.from_pretrained.return_value = mock_model

    classifier = LLMClassifier()
    result = classifier.classify("なんだか胸のあたりがつらいです")

    assert result.detected_need == "pain"
    assert result.escalation_level == "URGENT"


@patch("llama_cpp.Llama")
def test_classify_unrecognized_output_is_unknown(mock_llama_cls):
    mock_model = MagicMock()
    mock_model.create_chat_completion.return_value = _fake_chat_response("???")
    mock_llama_cls.from_pretrained.return_value = mock_model

    classifier = LLMClassifier()
    result = classifier.classify("何か曖昧な発話")

    assert result.detected_need == "unknown"
    assert result.confidence == "low"


@patch("llama_cpp.Llama")
def test_classify_information_only_output(mock_llama_cls):
    mock_model = MagicMock()
    mock_model.create_chat_completion.return_value = _fake_chat_response("information_only")
    mock_llama_cls.from_pretrained.return_value = mock_model

    classifier = LLMClassifier()
    result = classifier.classify("特に困っていることはありません")

    assert result.detected_need == "information_only"
    assert result.route == "INFORMATION_ONLY"


@patch("llama_cpp.Llama")
def test_classify_reuses_loaded_model_across_calls(mock_llama_cls):
    mock_model = MagicMock()
    mock_model.create_chat_completion.return_value = _fake_chat_response("unknown")
    mock_llama_cls.from_pretrained.return_value = mock_model

    classifier = LLMClassifier()
    classifier.classify("テスト")
    classifier.classify("テスト2")

    mock_llama_cls.from_pretrained.assert_called_once()


@patch("llama_cpp.Llama")
def test_from_pretrained_called_with_configured_repo_and_filename(mock_llama_cls):
    mock_model = MagicMock()
    mock_model.create_chat_completion.return_value = _fake_chat_response("unknown")
    mock_llama_cls.from_pretrained.return_value = mock_model

    classifier = LLMClassifier(repo_id="custom/repo-GGUF", filename="*Q8_0.gguf")
    classifier.classify("テスト")

    _args, kwargs = mock_llama_cls.from_pretrained.call_args
    assert kwargs["repo_id"] == "custom/repo-GGUF"
    assert kwargs["filename"] == "*Q8_0.gguf"


@patch("llama_cpp.Llama")
def test_classify_uses_zero_temperature_for_determinism(mock_llama_cls):
    mock_model = MagicMock()
    mock_model.create_chat_completion.return_value = _fake_chat_response("unknown")
    mock_llama_cls.from_pretrained.return_value = mock_model

    LLMClassifier().classify("テスト")

    _args, kwargs = mock_model.create_chat_completion.call_args
    assert kwargs["temperature"] == 0.0


def test_every_known_need_is_a_valid_llm_output_category():
    """Regression guard: the system prompt's category list must stay in
    sync with need_classification_service.known_needs(), or a need the
    keyword/semantic tiers can produce would never be reachable via the
    LLM tier either."""
    from backend.services.llm_classification_service import _SYSTEM_PROMPT

    for need in need_classification_service.known_needs():
        assert need in _SYSTEM_PROMPT, f"{need!r} missing from the LLM system prompt's category list"
