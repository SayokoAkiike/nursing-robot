"""Tests for backend.services.need_classification_service.

Pure-function tests -- no DB fixture needed, unlike every other test file
in this suite (need_classification_service has no backend.db import at
all; see its module docstring for why).
"""
from backend.services import need_classification_service as ncs


def test_toileting_is_high_priority_nurse_notification():
    result = ncs.classify("トイレに行きたいです")
    assert result.detected_need == "toileting"
    assert result.escalation_level == "HIGH"
    assert result.route == "NURSE_NOTIFICATION"


def test_water_is_medium_priority():
    result = ncs.classify("お水が飲みたいです")
    assert result.detected_need == "water"
    assert result.escalation_level == "MEDIUM"
    assert result.route == "NURSE_NOTIFICATION"


def test_pain_is_urgent():
    result = ncs.classify("胸が痛いです、苦しいです")
    assert result.detected_need == "pain"
    assert result.escalation_level == "URGENT"
    assert result.route == "URGENT_ESCALATION"


def test_anxiety_is_medium_priority():
    result = ncs.classify("なんだか不安で眠れないんです")
    assert result.detected_need == "anxiety"
    assert result.escalation_level == "MEDIUM"


def test_temperature_is_low_priority():
    result = ncs.classify("ちょっと寒いです")
    assert result.detected_need == "temperature"
    assert result.escalation_level == "LOW"
    assert result.route == "NURSE_NOTIFICATION"


def test_nurse_check_is_high_priority():
    result = ncs.classify("看護師さんに来てほしいです")
    assert result.detected_need == "nurse_check"
    assert result.escalation_level == "HIGH"


def test_position_change_is_medium_priority():
    result = ncs.classify("体勢を変えたいです")
    assert result.detected_need == "position_change"
    assert result.escalation_level == "MEDIUM"


def test_information_only_needs_no_escalation():
    result = ncs.classify("大丈夫です、特にないです")
    assert result.detected_need == "information_only"
    assert result.escalation_level == "LOW"
    assert result.route == "INFORMATION_ONLY"


def test_unrecognized_text_falls_back_to_unknown():
    result = ncs.classify("きょうはいい天気ですね")
    assert result.detected_need == "unknown"
    assert result.escalation_level == "LOW"
    assert result.route == "INFORMATION_ONLY"
    assert result.confidence == "low"


def test_empty_response_does_not_raise():
    result = ncs.classify("")
    assert result.detected_need == "unknown"


def test_none_like_response_does_not_raise():
    result = ncs.classify(None)
    assert result.detected_need == "unknown"


def test_pain_keyword_wins_over_toileting_when_both_present():
    # Rule order matters: pain (URGENT) is checked before toileting (HIGH),
    # so a response mentioning both should classify as the more urgent one.
    result = ncs.classify("胸が痛いですが、トイレにも行きたいです")
    assert result.detected_need == "pain"
    assert result.escalation_level == "URGENT"


def test_need_label_and_suggested_action_have_entries_for_every_rule_need():
    for need, _level, _keywords in ncs._RULES:
        assert ncs.need_label(need)
        assert ncs.suggested_action(need)
    # And for the two non-rule fallback needs.
    assert ncs.need_label("unknown")
    assert ncs.suggested_action("unknown")
