"""Embedding-based semantic classification of a patient's free-text
response (PR31) -- a fallback for cases the keyword rules in
`need_classification_service.py` miss because the patient phrased it
differently ("お手洗いに連れて行ってください" instead of the literal
"トイレ"/"お手洗い"/"立ちたい" keywords that module matches on).

Offline / self-hosted, same reasoning `perception/speech_recognizer.py`
documents for choosing faster-whisper over a cloud STT API: no patient
text is ever sent to a third-party service. Model weights (a small
multilingual sentence-embedding model, ~470MB) download once from
Hugging Face on first use, then run fully locally (CPU).

This module never *replaces* the keyword rules -- see
`rounding_service.classify_need()` for how the two are combined: keyword
matching runs first (fast, deterministic, zero ML dependency, and every
existing test asserting a specific category for a specific phrase keeps
passing unchanged), and this module is only consulted when that returns
"unknown". A `SemanticClassifier` construction/import failure (e.g. the
one-time model download failing due to no network) degrades to the
keyword result rather than raising -- an optional accuracy improvement
must never be able to break the rounding workflow it's improving.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.services import need_classification_service
from backend.services.need_classification_service import Classification

DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_SIMILARITY_THRESHOLD = 0.55

# Representative paraphrases per category -- deliberately more numerous
# and more varied in phrasing than need_classification_service.py's
# keyword lists, since the whole point of this module is catching
# phrasings the keyword list doesn't. Hand-authored (no training dataset
# exists or is needed for embedding similarity), grouped under exactly
# the needs need_classification_service.known_needs() already defines,
# so escalation_level/route can always be looked up from that single
# source of truth via escalation_level_for()/route_for().
EXAMPLE_UTTERANCES: dict[str, list[str]] = {
    "pain": [
        "痛いです",
        "胸が痛いです",
        "苦しいです",
        "体のあちこちが痛みます",
        "呼吸が苦しくてつらいです",
    ],
    "fall_risk": [
        "ふらふらします",
        "めまいがして立っていられません",
        "転びそうになりました",
        "一人で立ち上がってしまいました",
        "足元がおぼつかなくて怖いです",
    ],
    "toileting": [
        "トイレに行きたいです",
        "お手洗いに連れて行ってください",
        "用を足したいです",
        "立ちたいので手伝ってください",
        "排泄の介助をお願いします",
    ],
    "nurse_check": [
        "看護師さんに来てほしいです",
        "誰か来てもらえますか",
        "スタッフの方を呼んでください",
    ],
    "water": [
        "水が飲みたいです",
        "喉が渇きました",
        "何か飲み物をください",
    ],
    "anxiety": [
        "不安です",
        "怖くて眠れません",
        "気持ちが落ち着きません",
        "心配なことがあります",
    ],
    "position_change": [
        "向きを変えたいです",
        "体勢がつらいので変えてください",
        "同じ姿勢で疲れました",
    ],
    "temperature": [
        "寒いです",
        "暑くてつらいです",
        "部屋の温度を調整してほしいです",
    ],
    "information_only": [
        "大丈夫です",
        "特にありません",
        "問題ないです",
        "困っていることはありません",
    ],
}


@dataclass(frozen=True)
class SemanticMatch:
    detected_need: str
    similarity: float


class SemanticClassifier:
    """Lazily loads the embedding model and encodes
    `EXAMPLE_UTTERANCES` on first `classify()` call -- constructing this
    class must stay cheap, same reasoning
    `perception/speech_recognizer.SpeechRecognizer` and
    `perception/pose_detector.PoseDetector` lazy-load their models."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self._model = None
        self._example_needs: "list[str] | None" = None
        self._example_embeddings = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _get_example_embeddings(self):
        if self._example_embeddings is None:
            model = self._get_model()
            needs: list[str] = []
            texts: list[str] = []
            for need, examples in EXAMPLE_UTTERANCES.items():
                for example in examples:
                    needs.append(need)
                    texts.append(example)
            self._example_needs = needs
            self._example_embeddings = model.encode(texts, normalize_embeddings=True)
        return self._example_needs, self._example_embeddings

    def best_match(self, patient_response: str) -> "SemanticMatch | None":
        """Returns the closest-matching category and its cosine
        similarity, or None for an empty response. Never raises for a
        model/inference problem beyond what `_get_model()` itself
        raises -- callers (classify() below, and
        rounding_service.classify_need()) are the ones that decide
        whether to catch that and degrade to the keyword result."""
        text = (patient_response or "").strip()
        if not text:
            return None

        model = self._get_model()
        needs, example_embeddings = self._get_example_embeddings()
        query_embedding = model.encode([text], normalize_embeddings=True)[0]

        # Cosine similarity == dot product since both sides are
        # normalized (normalize_embeddings=True above).
        similarities = example_embeddings @ query_embedding
        best_index = int(similarities.argmax())
        return SemanticMatch(detected_need=needs[best_index], similarity=float(similarities[best_index]))

    def classify(self, patient_response: str) -> Classification:
        """Same return shape as
        `need_classification_service.classify()` so
        `rounding_service.classify_need()` can use either
        interchangeably. Falls through to the same ("unknown", "LOW",
        "INFORMATION_ONLY", "low") result that module returns when
        nothing matches well enough (similarity below
        `similarity_threshold`) -- this module never invents a category
        need_classification_service doesn't already know about."""
        match = self.best_match(patient_response)
        if match is None or match.similarity < self.similarity_threshold:
            return Classification(
                detected_need="unknown",
                escalation_level="LOW",
                route=need_classification_service.route_for("unknown"),
                confidence="low",
            )
        return Classification(
            detected_need=match.detected_need,
            escalation_level=need_classification_service.escalation_level_for(match.detected_need),
            route=need_classification_service.route_for(match.detected_need),
            confidence="semantic",
        )
