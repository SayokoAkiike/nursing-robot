"""Local LLM classification fallback for rounding need classification
(PR34/B) -- the third and most expensive tier of the classification
chain, after keyword matching (`need_classification_service.py`) and
sentence-embedding similarity (`semantic_classification_service.py`)
have both come back "unknown".

Offline / self-hosted, same reasoning `perception/speech_recognizer.py`
and `semantic_classification_service.py` give for choosing local
inference over a cloud API: no patient text is ever sent to a
third-party service, even in the LLM tier.

Model: LiquidAI/LFM2.5-1.2B-JP-GGUF (Q4_K_M, ~730MB), a first-party
GGUF release of a 1.2B-parameter model specifically tuned for Japanese,
run via llama-cpp-python (a llama.cpp binding with no torch dependency
-- unlike sentence-transformers, this stays lightweight on disk). Model
weights download once from Hugging Face on first use via
`Llama.from_pretrained()`.

Deliberately the LAST tier tried, not the first: an LLM call is by far
the most expensive of the three (CPU decode time, largest download),
and the keyword/embedding tiers already resolve the overwhelming
majority of real phrasings on their own. See
`rounding_service._classify_with_ml_fallbacks()` for how the three
tiers are chained, and its docstring for why a failure at this tier
(model not downloaded, out of memory, whatever) must degrade to
whatever the earlier tiers already found rather than breaking
classify_need() -- a safety-relevant step in the rounding workflow.
"""
from __future__ import annotations

from backend.services import need_classification_service
from backend.services.need_classification_service import Classification

DEFAULT_REPO_ID = "LiquidAI/LFM2.5-1.2B-JP-GGUF"
DEFAULT_FILENAME = "*Q4_K_M.gguf"
DEFAULT_N_CTX = 512
DEFAULT_MAX_TOKENS = 16

_SYSTEM_PROMPT = (
    "あなたは病院の巡回ロボットの一部として、患者の発言を次のカテゴリの"
    "いずれか一つだけに分類するアシスタントです。カテゴリ名以外の文字は"
    "一切出力しないでください。\n"
    "カテゴリ: pain, fall_risk, toileting, nurse_check, water, anxiety, "
    "position_change, temperature, information_only, unknown"
)


class LLMClassifier:
    """Lazily loads the GGUF model on first `classify()` call --
    constructing this class must stay cheap, same reasoning every other
    lazy-loaded ML wrapper in this codebase gives
    (SpeechRecognizer/PoseDetector/SemanticClassifier)."""

    def __init__(
        self,
        repo_id: str = DEFAULT_REPO_ID,
        filename: str = DEFAULT_FILENAME,
        n_ctx: int = DEFAULT_N_CTX,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.repo_id = repo_id
        self.filename = filename
        self.n_ctx = n_ctx
        self.max_tokens = max_tokens
        self._model = None

    def _get_model(self):
        if self._model is None:
            from llama_cpp import Llama

            self._model = Llama.from_pretrained(
                repo_id=self.repo_id,
                filename=self.filename,
                n_ctx=self.n_ctx,
                verbose=False,
            )
        return self._model

    def _extract_need(self, raw_output: str) -> str:
        """The model is instructed to output nothing but a category
        name, but small local models don't always follow instructions
        perfectly -- this matches the first known need name that
        appears anywhere in the output (case-insensitive) rather than
        requiring an exact-equals match, and falls back to "unknown"
        for anything else (extra punctuation, a short explanation
        despite being told not to, etc.)."""
        text = raw_output.strip().lower()
        for need in need_classification_service.known_needs():
            if need in text:
                return need
        if "unknown" in text or "information_only" in text:
            return "unknown" if "unknown" in text else "information_only"
        return "unknown"

    def classify(self, patient_response: str) -> Classification:
        """Same return shape as `need_classification_service.classify()`
        / `semantic_classification_service.SemanticClassifier.classify()`
        so all three tiers are interchangeable to their caller."""
        text = (patient_response or "").strip()
        if not text:
            return Classification(
                detected_need="unknown",
                escalation_level="LOW",
                route=need_classification_service.route_for("unknown"),
                confidence="low",
            )

        model = self._get_model()
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=self.max_tokens,
            temperature=0.0,
        )
        raw_output = response["choices"][0]["message"]["content"] or ""
        detected_need = self._extract_need(raw_output)

        if detected_need in ("unknown", "information_only"):
            return Classification(
                detected_need=detected_need,
                escalation_level="LOW",
                route=need_classification_service.route_for(detected_need),
                confidence="low" if detected_need == "unknown" else "llm",
            )
        return Classification(
            detected_need=detected_need,
            escalation_level=need_classification_service.escalation_level_for(detected_need),
            route=need_classification_service.route_for(detected_need),
            confidence="llm",
        )
