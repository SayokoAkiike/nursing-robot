"""Tests for perception/verification_client.py.

Exercises the client against the real FastAPI app in-process, via
Starlette's `TestClient` (an httpx.Client subclass that runs the ASGI app
synchronously and, like `tests/conftest.py`'s `api_client` fixture, already
triggers the app's `lifespan` -- i.e. `init_db()` -- on first use). No live
server or subprocess is needed.
"""
import pytest
from fastapi.testclient import TestClient

from backend.services import workflow_service
from perception.verification_client import VerificationClient, VerificationClientError

NURSE_TOKEN = "precare-dev-token-2026"


@pytest.fixture
def perception_client(robot_storage):
    from backend.main import app

    http_client = TestClient(app)
    client = VerificationClient(nurse_token=NURSE_TOKEN, client=http_client)
    yield client
    client.close()


def test_get_state_idle(perception_client):
    assert perception_client.get_state()["robot_state"] == "IDLE"


def test_verify_ok_advances_state(perception_client):
    view = workflow_service.create_request("toileting")
    request_id = view["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")

    outcome = perception_client.verify(request_id, "PATIENT_A_ROOM_203", "KIT_TOILETING_A")

    assert outcome["ok"] is True
    assert outcome["state"]["robot_state"] == "DOCKING"


def test_verify_ng_raises_client_error(perception_client):
    view = workflow_service.create_request("toileting")
    request_id = view["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")

    with pytest.raises(VerificationClientError) as excinfo:
        perception_client.verify(request_id, "PATIENT_A_ROOM_203", "KIT_WATER")
    assert excinfo.value.status_code == 400


def test_verify_without_nurse_token_is_unauthorized(robot_storage):
    from backend.main import app

    http_client = TestClient(app)
    client = VerificationClient(nurse_token="", client=http_client)

    view = workflow_service.create_request("toileting")
    request_id = view["request_id"]

    with pytest.raises(VerificationClientError) as excinfo:
        client.verify(request_id, "PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    assert excinfo.value.status_code == 401
    client.close()
