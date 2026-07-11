"""CLI entry point: `python -m backend.scripts.benchmark_classification_chain`.

Measures real wall-clock latency of each tier in the rounding need
classification chain (keyword -> semantic embedding -> local LLM, see
`rounding_service._classify_with_ml_fallbacks()`), plus the worst-case
end-to-end time when a phrase falls through all three tiers to
"unknown".

Why this exists: PR31/33/34 each added a tier to the fallback chain, and
each was verified independently (does it classify correctly, does it
degrade gracefully on failure) -- but nobody had actually measured the
chain's *combined* latency for the specific case that matters most for
UX: a patient's response none of the three tiers can confidently
classify. That's exactly the phrase a real conversation is most likely
to produce when the patient is confused, mumbling, or saying something
genuinely ambiguous -- and it's also the slowest path through the code,
since it's the only one that has to try every tier before giving up.

Run this AFTER the semantic/LLM models have already been downloaded at
least once (e.g. after running the rounding simulation with a phrase
that reaches each tier) -- first-use download time would otherwise
dominate the numbers and isn't what this is meant to measure. Loads each
model once and reuses it across all timed calls, same reasoning
SpeechRecognizer/PoseDetector/SemanticClassifier/LLMClassifier all
lazy-load once per instance rather than per call -- this script measures
steady-state inference latency, not cold-start cost.
"""
from __future__ import annotations

import argparse
import time

# Phrases chosen so each one is expected to resolve at a specific tier
# -- see need_classification_service.py's _RULES / semantic_classification_
# service.py's EXAMPLE_UTTERANCES for why each lands where it does.
KEYWORD_TIER_PHRASE = "トイレに行きたいです"  # literal keyword match
SEMANTIC_TIER_PHRASE = "用を足したいです"  # no literal keyword, embeds close to "toileting"
WORST_CASE_PHRASE = "うーん、なんだかなあ"  # genuinely ambiguous -- expected to fall through all three tiers


def _time_call(label: str, fn) -> float:
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    print(f"{label}: {elapsed * 1000:.0f}ms -> detected_need={result.detected_need!r} confidence={result.confidence!r}")
    return elapsed


def run(skip_llm: bool = False) -> dict:
    """Returns a dict of tier -> seconds, so a caller (or a future
    regression test with mocked tiers) can assert on the numbers rather
    than only reading stdout. `skip_llm=True` runs only the keyword +
    semantic tiers -- useful on a machine where llama-cpp-python isn't
    installed/built yet, since building it is a separate, already
    time-consuming step of its own (see requirements.txt's PR34 note)."""
    from backend.services import need_classification_service
    from backend.services.semantic_classification_service import SemanticClassifier

    timings: dict[str, float] = {}

    print("=== keyword tier (no model, should be near-instant) ===")
    timings["keyword"] = _time_call(
        "keyword", lambda: need_classification_service.classify(KEYWORD_TIER_PHRASE)
    )

    print("\n=== semantic tier (first call in this process loads the model) ===")
    semantic = SemanticClassifier()
    timings["semantic_cold"] = _time_call(
        "semantic (model load + inference)", lambda: semantic.classify(SEMANTIC_TIER_PHRASE)
    )
    print("=== semantic tier, model already loaded (steady state) ===")
    timings["semantic_warm"] = _time_call(
        "semantic (steady state)", lambda: semantic.classify(SEMANTIC_TIER_PHRASE)
    )

    if not skip_llm:
        from backend.services.llm_classification_service import LLMClassifier

        print("\n=== LLM tier (first call in this process loads the model) ===")
        llm = LLMClassifier()
        timings["llm_cold"] = _time_call(
            "llm (model load + inference)", lambda: llm.classify(WORST_CASE_PHRASE)
        )
        print("=== LLM tier, model already loaded (steady state) ===")
        timings["llm_warm"] = _time_call("llm (steady state)", lambda: llm.classify(WORST_CASE_PHRASE))

    print("\n=== worst case: full chain, all three tiers, steady state ===")
    print("(this is what a real patient conversation pays when nothing confidently matches)")
    start = time.perf_counter()
    from backend.services.rounding_service import _classify_with_ml_fallbacks

    result = _classify_with_ml_fallbacks(WORST_CASE_PHRASE)
    elapsed = time.perf_counter() - start
    timings["full_chain_worst_case"] = elapsed
    print(f"full chain: {elapsed * 1000:.0f}ms -> detected_need={result.detected_need!r}")

    print("\n=== summary ===")
    for label, seconds in timings.items():
        print(f"  {label}: {seconds * 1000:.0f}ms")

    return timings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip the LLM tier (e.g. llama-cpp-python not installed/built yet)",
    )
    args = parser.parse_args()
    run(skip_llm=args.skip_llm)


if __name__ == "__main__":
    main()
