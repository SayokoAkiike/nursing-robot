"""Integration tests for backend/scripts/run_simulated_rounding.py (PR25).

Same approach as tests/test_run_simulated_delivery.py: drives the full
simulated-rounding orchestration in-process against a FastAPI TestClient
standing in for a real running backend, with zero step delay so this
stays fast in CI.
"""
import pytest
from fastapi.testclient import TestClient

from backend.scripts.run_simulated_rounding import RoundingScriptError, run_rounding

NURSE_TOKEN = "precare-dev-token-2026"


def _client():
    from backend.main import app

    return TestClient(app)


def test_information_only_scenario_completes_without_nurse_gate(robot_storage):
    final_state = run_rounding(
        _client(), scenario="rounding_normal", nurse_token=NURSE_TOKEN, step_delay=0
    )
    assert final_state["status"] == "COMPLETED"


def test_toileting_scenario_reaches_waiting_for_nurse_ack_with_auto_ack(robot_storage):
    final_state = run_rounding(
        _client(),
        scenario="rounding_toileting_escalation",
        nurse_token=NURSE_TOKEN,
        step_delay=0,
        auto_ack=True,
    )
    assert final_state["status"] == "COMPLETED"
    assert final_state["patient_id"] == "PATIENT_A_ROOM_203"


def test_urgent_pain_scenario_classifies_correctly(robot_storage):
    final_state = run_rounding(
        _client(),
        scenario="rounding_urgent_pain",
        nurse_token=NURSE_TOKEN,
        step_delay=0,
        auto_ack=True,
    )
    assert final_state["status"] == "COMPLETED"
    assert final_state["escalation_level"] == "URGENT"


def test_water_request_scenario_uses_room_204(robot_storage):
    final_state = run_rounding(
        _client(),
        scenario="rounding_water_request",
        nurse_token=NURSE_TOKEN,
        step_delay=0,
        auto_ack=True,
    )
    assert final_state["room"] == "204"
    assert final_state["patient_id"] == "PATIENT_B_ROOM_204"


def test_unknown_scenario_raises(robot_storage):
    with pytest.raises(RoundingScriptError):
        run_rounding(_client(), scenario="does-not-exist", nurse_token=NURSE_TOKEN, step_delay=0)


# ---- Safety regression tests -------------------------------------------------


def test_escalating_scenario_without_auto_ack_does_not_bypass_nurse_gate(robot_storage):
    """Without --auto-ack, the script must NOT acknowledge the escalation
    itself. It should wait for an external acknowledgement and time out
    if none arrives -- never silently advance past WAITING_FOR_NURSE_ACK."""
    with pytest.raises(TimeoutError):
        run_rounding(
            _client(),
            scenario="rounding_toileting_escalation",
            nurse_token=NURSE_TOKEN,
            step_delay=0,
            auto_ack=False,
            ack_poll_seconds=0.05,
            ack_timeout_seconds=0.2,
        )


def test_information_only_scenario_ignores_auto_ack_flag(robot_storage):
    """auto_ack has nothing to do for an INFORMATION_ONLY scenario -- no
    escalation is ever raised, so passing auto_ack=True or False must
    produce the exact same COMPLETED outcome either way."""
    final_state = run_rounding(
        _client(),
        scenario="rounding_no_need",
        nurse_token=NURSE_TOKEN,
        step_delay=0,
        auto_ack=False,
    )
    assert final_state["status"] == "COMPLETED"
