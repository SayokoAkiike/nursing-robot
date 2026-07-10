#!/usr/bin/env python3
"""Adds a "fall_risk" detected_need category to the rounding conversation
classifier (roadmap item 3), as targeted find/replace edits.

Run from the repo root (where backend/main.py lives):
    python3 apply_patch_fall_risk.py

Each edit asserts its "old" snippet is found exactly once before replacing --
if a file has already been modified (or diverges from what this was built
against), it fails loudly with the file/index instead of silently
corrupting anything.
"""
import pathlib
import sys

ROOT = pathlib.Path(".")
if not (ROOT / "backend" / "main.py").exists():
    sys.exit("ERROR: run this from the repository root (directory containing backend/main.py).")

EDITS = [
    # -- backend/services/need_classification_service.py ------------------
    ("backend/services/need_classification_service.py",
     '''_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("pain", "URGENT", ("痛い", "胸が痛い", "苦しい")),
    ("toileting", "HIGH", ("トイレ", "お手洗い", "立ちたい")),''',
     '''_RULES: list[tuple[str, str, tuple[str, ...]]] = [
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
    ("toileting", "HIGH", ("トイレ", "お手洗い", "立ちたい")),'''),

    ("backend/services/need_classification_service.py",
     '''_ROUTES: dict[str, str] = {
    "pain": "URGENT_ESCALATION",
    "toileting": "NURSE_NOTIFICATION",''',
     '''_ROUTES: dict[str, str] = {
    "pain": "URGENT_ESCALATION",
    "fall_risk": "URGENT_ESCALATION",
    "toileting": "NURSE_NOTIFICATION",'''),

    ("backend/services/need_classification_service.py",
     '''NEED_LABELS: dict[str, str] = {
    "pain": "強い痛み・苦しさ",
    "toileting": "トイレ介助",''',
     '''NEED_LABELS: dict[str, str] = {
    "pain": "強い痛み・苦しさ",
    "fall_risk": "転倒の危険（ふらつき・一人での立ち上がり）",
    "toileting": "トイレ介助",'''),

    ("backend/services/need_classification_service.py",
     '''SUGGESTED_ACTIONS: dict[str, str] = {
    "pain": "至急、看護師が訪室して状態を確認してください。",
    "toileting": "看護師が訪室して介助してください。",''',
     '''SUGGESTED_ACTIONS: dict[str, str] = {
    "pain": "至急、看護師が訪室して状態を確認してください。",
    "fall_risk": "至急、看護師が訪室し、患者の安全を直接確認してください。転倒・転落の恐れがあります。",
    "toileting": "看護師が訪室して介助してください。",'''),

    # -- tests/test_need_classification_service.py -------------------------
    ("tests/test_need_classification_service.py",
     '''def test_pain_keyword_wins_over_toileting_when_both_present():
    # Rule order matters: pain (URGENT) is checked before toileting (HIGH),
    # so a response mentioning both should classify as the more urgent one.
    result = ncs.classify("胸が痛いですが、トイレにも行きたいです")
    assert result.detected_need == "pain"
    assert result.escalation_level == "URGENT"''',
     '''def test_pain_keyword_wins_over_toileting_when_both_present():
    # Rule order matters: pain (URGENT) is checked before toileting (HIGH),
    # so a response mentioning both should classify as the more urgent one.
    result = ncs.classify("胸が痛いですが、トイレにも行きたいです")
    assert result.detected_need == "pain"
    assert result.escalation_level == "URGENT"


def test_fall_risk_is_urgent():
    result = ncs.classify("ふらふらして、一人で立ち上がってしまいました")
    assert result.detected_need == "fall_risk"
    assert result.escalation_level == "URGENT"
    assert result.route == "URGENT_ESCALATION"


def test_fall_risk_keyword_wins_over_toileting_when_both_present():
    # Rule order matters here too: fall_risk sits ahead of toileting (see
    # need_classification_service._RULES's comment) because a patient who
    # is already unsteady/up on their own is the exact scenario this
    # product exists to catch, even if they also mention wanting the
    # toilet in the same breath.
    result = ncs.classify("ふらふらしますが、トイレに行きたいです")
    assert result.detected_need == "fall_risk"
    assert result.escalation_level == "URGENT"'''),

    # -- backend/scripts/run_simulated_rounding.py --------------------------
    ("backend/scripts/run_simulated_rounding.py",
     '''    "rounding_urgent_pain": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "胸が痛いです、苦しいです",
        "expected_need": "pain",
        "expected_priority": "URGENT",
    },
}''',
     '''    "rounding_urgent_pain": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "胸が痛いです、苦しいです",
        "expected_need": "pain",
        "expected_priority": "URGENT",
    },
    "rounding_fall_risk": {
        "room": DEFAULT_ROOM,
        "patient_id": DEFAULT_PATIENT_ID,
        "simulated_response": "ふらふらして、一人で立ち上がってしまいました",
        "expected_need": "fall_risk",
        "expected_priority": "URGENT",
    },
}'''),

    # -- tests/test_run_simulated_rounding.py -------------------------------
    ("tests/test_run_simulated_rounding.py",
     '''def test_water_request_scenario_uses_room_204(robot_storage):''',
     '''def test_fall_risk_scenario_classifies_correctly(robot_storage):
    final_state = run_rounding(
        _client(),
        scenario="rounding_fall_risk",
        nurse_token=NURSE_TOKEN,
        step_delay=0,
        auto_ack=True,
    )
    assert final_state["status"] == "COMPLETED"
    assert final_state["escalation_level"] == "URGENT"
    assert final_state["detected_need"] == "fall_risk"


def test_water_request_scenario_uses_room_204(robot_storage):'''),

    # -- README.md -----------------------------------------------------------
    ("README.md",
     '''実際の人物検出・音声認識は行わず（Phase 4.5の設計方針どおり）、6つの名前付きシナリオ（`rounding_normal` / `rounding_patient_detected` / `rounding_toileting_escalation` / `rounding_water_request` / `rounding_no_need` / `rounding_urgent_pain`）それぞれに紐づく疑似患者応答を、本物のAPI（`/rounding/*`、`/escalations/*`）越しに一気通貫で流す開発・デモ用スクリプト。分類結果（`detected_need`/`escalation_level`）を期待値と照合するので、単なるデモではなく`need_classification_service`のルールセットに対するE2Eスモークテストも兼ねる。''',
     '''実際の人物検出・音声認識は行わず（Phase 4.5の設計方針どおり）、7つの名前付きシナリオ（`rounding_normal` / `rounding_patient_detected` / `rounding_toileting_escalation` / `rounding_water_request` / `rounding_no_need` / `rounding_urgent_pain` / `rounding_fall_risk`）それぞれに紐づく疑似患者応答を、本物のAPI（`/rounding/*`、`/escalations/*`）越しに一気通貫で流す開発・デモ用スクリプト。分類結果（`detected_need`/`escalation_level`）を期待値と照合するので、単なるデモではなく`need_classification_service`のルールセットに対するE2Eスモークテストも兼ねる。`rounding_fall_risk`は本製品が最も防ぎたい状況（患者が看護師を待たず一人でふらついて立ち上がってしまう）を再現するシナリオで、`fall_risk`はpainと同じURGENT/URGENT_ESCALATIONだが、通常のトイレ希望（toileting/HIGH）より優先されるようルール順で明示的に上位に置かれている。'''),
]

for relpath, old, new in EDITS:
    path = ROOT / relpath
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        sys.exit(f"ERROR: expected exactly 1 match for a snippet in {relpath}, found {count}. Aborting before any further changes.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {relpath}")

print("All targeted edits applied.")
