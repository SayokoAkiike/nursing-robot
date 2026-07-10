"""API tests for the PR27 rounding analytics endpoints.

No API-level tests existed yet for /analytics/* (only
tests/test_analytics_service.py exercises the service layer directly) --
this file covers just the two new endpoints this PR adds, consistent with
that PR's own scope.
"""


def test_rounding_summary_endpoint(api_client):
    r = api_client.get("/analytics/rounding-summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_rounding_sessions"] == 0
    assert body["average_time_to_ack"] is None


def test_escalation_breakdown_endpoint(api_client):
    r = api_client.get("/analytics/escalation-breakdown")
    assert r.status_code == 200
    assert r.json() == {"by_priority": [], "by_detected_need": [], "by_status": []}


def test_rounding_summary_reflects_real_session(api_client):
    session_id = api_client.post("/rounding/start", json={"room": "203"}).json()[
        "rounding_session_id"
    ]
    api_client.post(
        f"/rounding/{session_id}/detect-patient",
        json={"patient_id": "PATIENT_A_ROOM_203"},
    )

    r = api_client.get("/analytics/rounding-summary")
    body = r.json()
    assert body["total_rounding_sessions"] == 1
    assert body["patients_detected"] == 1
    assert body["interactions_started"] == 0
