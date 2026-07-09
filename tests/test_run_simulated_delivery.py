"""Integration tests for backend/scripts/run_simulated_delivery.py (PR19).

Runs the full simulated-delivery orchestration in-process (an ASGI
TestClient standing in for a real running backend, exactly like
tests/test_run_perception.py and tests/test_synthetic_demo_perception_
integration.py already do), with zero step delay so this stays fast in CI.
"""
import pytest
from fastapi.testclient import TestClient

from backend.scripts.run_simulated_delivery import run_delivery
from perception.verification_client import VerificationClient

NURSE_TOKEN = "precare-dev-token-2026"


def test_run_delivery_completes_end_to_end_with_auto_confirm(robot_storage):
    from backend.main import app

    client = VerificationClient(nurse_token=NURSE_TOKEN, client=TestClient(app))

    final_state = run_delivery(client, step_delay=0, auto_confirm=True)

    assert final_state["robot_state"] == "COMPLETED"
    assert final_state["patient_id"] == "PATIENT_A_ROOM_203"


def test_run_delivery_without_auto_confirm_does_not_bypass_nurse_gate(robot_storage):
    """Safety regression guard: without --auto-confirm, the script must NOT
    press KIT_RELEASED itself. It should wait for an external confirmation
    and time out if none arrives -- never silently advance past the gate."""
    from backend.main import app

    client = VerificationClient(nurse_token=NURSE_TOKEN, client=TestClient(app))

    with pytest.raises(TimeoutError):
        run_delivery(
            client,
            step_delay=0,
            auto_confirm=False,
            confirm_poll_seconds=0.05,
            confirm_timeout_seconds=0.2,
        )
