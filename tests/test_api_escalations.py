"""API tests for /escalations/* endpoints."""
HEADERS = {"x-nurse-token": "precare-dev-token-2026"}


def _escalated_session(api_client):
    session_id = api_client.post("/rounding/start", json={"room": "203"}).json()[
        "rounding_session_id"
    ]
    api_client.post(
        f"/rounding/{session_id}/detect-patient",
        json={"patient_id": "PATIENT_A_ROOM_203"},
    )
    api_client.post(f"/rounding/{session_id}/start-interaction")
    classify = api_client.post(
        f"/rounding/{session_id}/classify-need",
        json={"patient_response": "トイレに行きたいです"},
    ).json()
    escalate = api_client.post(
        f"/rounding/{session_id}/escalate",
        json={
            "summary": classify["summary"],
            "priority": classify["escalation_level"],
            "suggested_action": classify["suggested_action"],
            "route": classify["route"],
        },
    ).json()
    return session_id, escalate["escalation_id"]


def test_list_escalations_empty(api_client):
    r = api_client.get("/escalations")
    assert r.status_code == 200
    assert r.json() == []


def test_list_escalations_shows_pending(api_client):
    _session_id, escalation_id = _escalated_session(api_client)
    r = api_client.get("/escalations")
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert escalation_id in ids


def test_get_escalation(api_client):
    _session_id, escalation_id = _escalated_session(api_client)
    r = api_client.get(f"/escalations/{escalation_id}")
    assert r.status_code == 200
    assert r.json()["priority"] == "HIGH"


def test_get_unknown_escalation_is_404(api_client):
    assert api_client.get("/escalations/does-not-exist").status_code == 404


def test_ack_requires_nurse_token(api_client):
    _session_id, escalation_id = _escalated_session(api_client)
    r = api_client.post(
        f"/escalations/{escalation_id}/ack", json={"acknowledged_by": "nurse_demo"}
    )
    assert r.status_code == 401


def test_ack_with_token_completes_session(api_client):
    session_id, escalation_id = _escalated_session(api_client)
    r = api_client.post(
        f"/escalations/{escalation_id}/ack",
        json={"acknowledged_by": "nurse_demo"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["escalation"]["status"] == "ACKNOWLEDGED"
    assert body["rounding_session"]["status"] == "COMPLETED"

    # Session is no longer PENDING, so it drops off the default dashboard
    # ordering's "needs attention" set (still listed, just not pending).
    escalation_after = api_client.get(f"/escalations/{escalation_id}").json()
    assert escalation_after["status"] == "ACKNOWLEDGED"


def test_ack_twice_conflicts(api_client):
    _session_id, escalation_id = _escalated_session(api_client)
    api_client.post(
        f"/escalations/{escalation_id}/ack",
        json={"acknowledged_by": "nurse_demo"},
        headers=HEADERS,
    )
    r = api_client.post(
        f"/escalations/{escalation_id}/ack",
        json={"acknowledged_by": "nurse_demo_2"},
        headers=HEADERS,
    )
    assert r.status_code == 409


def test_list_escalations_filtered_by_status(api_client):
    _session_id, escalation_id = _escalated_session(api_client)
    api_client.post(
        f"/escalations/{escalation_id}/ack",
        json={"acknowledged_by": "nurse_demo"},
        headers=HEADERS,
    )
    pending = api_client.get("/escalations", params={"status": "PENDING"}).json()
    assert pending == []
    acked = api_client.get("/escalations", params={"status": "ACKNOWLEDGED"}).json()
    assert len(acked) == 1


# ---- PR30: POST /escalations/vision-report ----------------------------------


def test_vision_report_creates_pending_escalation_unauthenticated(api_client):
    """Unauthenticated on purpose -- represents a sensor/robot
    observation, not a nurse action (mirrors /rounding/* endpoints'
    reasoning)."""
    r = api_client.post(
        "/escalations/vision-report",
        json={
            "room": "203",
            "patient_id": "PATIENT_A_ROOM_203",
            "summary": "203号室 PATIENT_A_ROOM_203 が離床を検知されました。",
            "priority": "URGENT",
            "reason": "fall_risk",
            "suggested_action": "至急、看護師が訪室してください。",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["source"] == "vision_pose"
    assert body["rounding_session_id"] is None


def test_vision_report_defaults_priority_and_reason(api_client):
    r = api_client.post(
        "/escalations/vision-report",
        json={"room": "203", "patient_id": "PATIENT_A_ROOM_203", "summary": "s"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["priority"] == "URGENT"
    assert body["reason"] == "fall_risk"


def test_vision_report_appears_in_escalations_list(api_client):
    api_client.post(
        "/escalations/vision-report",
        json={"room": "203", "patient_id": "PATIENT_A_ROOM_203", "summary": "s"},
    )
    escalations = api_client.get("/escalations").json()
    assert any(e["source"] == "vision_pose" for e in escalations)
