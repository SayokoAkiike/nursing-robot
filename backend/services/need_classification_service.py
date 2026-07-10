"""Rule-based classification of a patient's free-text response during a
rounding interaction (PR23).

No LLM, no speech recognition -- keyword matching against
`backend/db/models.py::PatientInteractionRow.patient_response`, exactly as
scoped in the proposal doc ("まずはLLMや音声認識は使わず、ルールベースで構いません").
Deliberately has no import from `backend.db` or `backend.services.*` -- it
is a pure function of the input text, independent of persistence and of
`rounding_service`'s orchestration, so it can be unit-tested (and later
swapped for a smarter classifier) without touching either.
"""
from dataclasses import dataclass

# Ordered rules: each is (detected_need, escalation_level, keywords).
# First matching rule wins (see classify() below) -- ordered roughly
# life-safety-first, since some phrasings could plausibly match more than
# one need (e.g. "苦しい" alone) and the more urgent interpretation should
# win a tie.
_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("pain", "URGENT", ("痛い", "胸が痛い", "苦しい")),
    # fall_risk sits right after pain and ahead of toileting on purpose:
    # this whole product exists to prevent a patient standing up alone
    # before a nurse arrives (see README's "解決する問題"), so a response
    # indicating the patient is already unsteady, already up, or has
    # already fallen is exactly the scenario the rounding conversation is
    # meant to catch -- it should outrank a routine "トイレに行きたい"
    # even though both currently would also trip PATIENTS' toileting risk
    # flag on the delivery side. Kept below "pain" only because a chest
    # pain report can be the more acute of the two if both are ever
    # mentioned together.
    ("fall_risk", "URGENT", ("ふらふら", "めまい", "転びそう", "転んで", "転倒", "一人で立ち上が")),
    ("toileting", "HIGH", ("トイレ", "お手洗い", "立ちたい")),
    ("nurse_check", "HIGH", ("看護師", "来てほしい")),
    ("water", "MEDIUM", ("水", "飲みたい")),
    ("anxiety", "MEDIUM", ("不安", "怖い", "眠れない")),
    ("position_change", "MEDIUM", ("向きを変えたい", "体勢")),
    ("temperature", "LOW", ("寒い", "暑い")),
    ("information_only", "LOW", ("大丈夫", "特にない")),
]

# route, keyed by detected_need. "unknown" (no rule matched) and
# "information_only" both route to INFORMATION_ONLY -- from the rounding
# session's point of view, "nothing was understood" and "patient says
# they're fine" both mean no nurse action is needed, they just differ in
# whether a human should later review the transcript (a distinction
# `rounding_service` can make from `detected_need` itself without needing a
# different route).
_ROUTES: dict[str, str] = {
    "pain": "URGENT_ESCALATION",
    "fall_risk": "URGENT_ESCALATION",
    "toileting": "NURSE_NOTIFICATION",
    "nurse_check": "NURSE_NOTIFICATION",
    "water": "NURSE_NOTIFICATION",
    "anxiety": "NURSE_NOTIFICATION",
    "position_change": "NURSE_NOTIFICATION",
    "temperature": "NURSE_NOTIFICATION",
    "information_only": "INFORMATION_ONLY",
    "unknown": "INFORMATION_ONLY",
}

# Human-readable labels / suggested actions, used by rounding_service to
# build the nurse-facing `summary` / `suggested_action` text (see the
# proposal doc's classify-need response example). Kept here, next to the
# rules that produce `detected_need`, rather than in rounding_service.
NEED_LABELS: dict[str, str] = {
    "pain": "強い痛み・苦しさ",
    "fall_risk": "転倒の危険（ふらつき・一人での立ち上がり）",
    "toileting": "トイレ介助",
    "nurse_check": "看護師の訪室",
    "water": "飲水介助",
    "anxiety": "不安・不眠",
    "position_change": "体位変換",
    "temperature": "室温調整",
    "information_only": "特になし",
    "unknown": "内容不明",
}

SUGGESTED_ACTIONS: dict[str, str] = {
    "pain": "至急、看護師が訪室して状態を確認してください。",
    "fall_risk": "至急、看護師が訪室し、患者の安全を直接確認してください。転倒・転落の恐れがあります。",
    "toileting": "看護師が訪室して介助してください。",
    "nurse_check": "看護師が訪室してください。",
    "water": "看護師または巡回ロボットが飲水を届けてください。",
    "anxiety": "看護師が訪室し、状況を確認してください。",
    "position_change": "看護師が訪室して体位変換を介助してください。",
    "temperature": "室温を確認し、必要な調整をしてください。",
    "information_only": "対応不要です。",
    "unknown": "会話内容を確認し、必要に応じて訪室してください。",
}


@dataclass(frozen=True)
class Classification:
    detected_need: str
    escalation_level: str
    route: str
    confidence: str


def classify(patient_response: str) -> Classification:
    """Classify one patient response. Never raises -- an empty string or a
    response matching no rule falls through to ("unknown", "LOW",
    "INFORMATION_ONLY", "low"), matching `rounding_service`'s expectation
    that classification always succeeds (a rounding session shouldn't
    error out just because the demo's rule set doesn't recognize a
    phrase)."""
    text = patient_response or ""
    for need, level, keywords in _RULES:
        if any(keyword in text for keyword in keywords):
            return Classification(
                detected_need=need,
                escalation_level=level,
                route=_ROUTES[need],
                confidence="high",
            )
    return Classification(
        detected_need="unknown",
        escalation_level="LOW",
        route=_ROUTES["unknown"],
        confidence="low",
    )


def need_label(detected_need: str) -> str:
    return NEED_LABELS.get(detected_need, detected_need)


def suggested_action(detected_need: str) -> str:
    return SUGGESTED_ACTIONS.get(detected_need, SUGGESTED_ACTIONS["unknown"])
