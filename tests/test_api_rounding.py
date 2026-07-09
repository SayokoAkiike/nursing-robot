"""API tests for /rounding/* endpoints.

Same style as tests/test_api.py -- the `api_client` fixture from
conftest.py gives each test a FastAPI TestClient backed by an independent
SQLite file.
"""
HEADERS = {"x-nurse-token": "precare-dev-token-2026"}


def _start_session(api_client, room="203"):
    r = api_client.post("/rounding/start", json={"room": room})
    assert r.status_code == 200
    return r.json()["rounding_session_id"]


def _to_interaction_started(api_client, session_id):
    api_client.post(
        f"/rounding/{session_id}/detect-patient",
        json={"patient_id": "PATIENT_A_ROOM_203"},
    )
    api_client.post(f"/rounding/{session_id}/start-interaction")


def test_start_rounding(api_client):
    r = api_client.post("/rounding/start", json={"room": "203"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ROUNDING"
    assert "rounding_session_id" in body


def test_get_rounding_session(api_client):
    session_id = _start_session(api_client)
    r = api_client.get(f"/rounding/{session_id}")
    assert r.status_code == 200
    assert r.json()["room"] == "203"


def test_get_unknown_rounding_session_is_404(api_client):
    assert api_client.get("/rounding/does-not-exist").status_code == 404


def test_detect_patient(api_client):
    session_id = _start_session(api_client)
    r = api_client.post(
        f"/rounding/{session_id}/detect-patient",
        json={"patient_id": "PATIENT_A_ROOM_203"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "PATIENT_DETECTED"
    assert r.json()["patient_id"] == "PATIENT_A_ROOM_203"


def test_start_interaction_returns_prompt(api_client):
    session_id = _start_session(api_client)
    api_client.post(
        f"/rounding/{session_id}/detect-patient",
        json={"patient_id": "PATIENT_A_ROOM_203"},
    )
    r = api_client.post(f"/rounding/{session_id}/start-interaction")
    assert r.status_code == 200
    assert r.json()["prompt"]
    assert r.json()["status"] == "INTERACTION_STARTED"


def test_classify_need_toileting(api_client):
    session_id = _start_session(api_client)
    _to_interaction_started(api_client, session_id)
    r = api_client.post(
        f"/rounding/{session_id}/classify-need",
        json={"patient_response": "トイレに行きたいです"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["detected_need"] == "toileting"
    assert body["escalation_level"] == "HIGH"
    assert body["route"] == "NURSE_NOTIFICATION"


def test_provide_information_completes_session(api_client):
    session_id = _start_session(api_client)
    _to_interaction_started(api_client, session_id)
    api_client.post(
        f"/rounding/{session_id}/classify-need", json={"patient_response": "大丈夫です"}
    )
    r = api_client.post(f"/rounding/{session_id}/provide-information")
    assert r.status_code == 200
    assert r.json()["status"] == "COMPLETED"


def test_escalate_creates_pending_escalation(api_client):
    session_id = _start_session(api_client)
    _to_interaction_started(api_client, session_id)
    classify = api_client.post(
        f"/rounding/{session_id}/classify-need",
        json={"patient_response": "トイレに行きたいです"},
    ).json()

    r = api_client.post(
        f"/rounding/{session_id}/escalate",
        json={
            "summary": classify["summary"],
            "priority": classify["escalation_level"],
            "suggested_action": classify["suggested_action"],
            "route": classify["route"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "WAITING_FOR_NURSE_ACK"
    assert "escalation_id" in body


def test_require_delivery_creates_care_request(api_client):
    session_id = _start_session(api_client)
    _to_interaction_started(api_client, session_id)
    api_client.post(
        f"/rounding/{session_id}/classify-need",
        json={"patient_response": "トイレに行きたいです"},
    )

    r = api_client.post(
        f"/rounding/{session_id}/require-delivery",
        json={"request_type": "toileting"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "DELIVERY_REQUIRED"
    assert "request_id" in body

    # The created request is a real one, reachable through the existing
    # delivery API surface.
    followup = api_client.get(f"/requests/{body['request_id']}")
    assert followup.status_code == 200
    assert followup.json()["robot_state"] == "REQUEST_RECEIVED"


# ---- Safety regression tests -------------------------------------------------


def test_cannot_escalate_before_need_classified(api_client):
    session_id = _start_session(api_client)
    r = api_client.post(
        f"/rounding/{session_id}/escalate",
        json={"summary": "s", "priority": "HIGH"},
    )
    assert r.status_code == 409


def test_cannot_start_interaction_before_detect_patient(api_client):
    session_id = _start_session(api_client)
    r = api_client.post(f"/rounding/{session_id}/start-interaction")
    assert r.status_code == 409
