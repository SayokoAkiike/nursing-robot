HEADERS = {"x-nurse-token": "precare-dev-token-2026"}


def test_backend_importable():
    from backend.main import app
    assert app is not None

def test_patient_ui_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location("patient_app", "ui/patient_request_app/app.py")
    assert spec is not None

def test_get_state(api_client):
    assert api_client.get("/state").json()["robot_state"] == "IDLE"

def test_create_request(api_client):
    r = api_client.post("/requests", json={"request_type": "toileting"})
    assert r.status_code == 200
    assert r.json()["robot_state"] == "REQUEST_RECEIVED"

def test_unknown_request_type(api_client):
    assert api_client.post("/requests", json={"request_type": "unknown"}).status_code == 400

def test_transition_requires_nurse_token(api_client):
    api_client.post("/requests", json={"request_type": "toileting"})
    assert api_client.post("/transition", json={"next_state": "KIT_SELECTED"}).status_code == 401

def test_transition_with_token(api_client):
    api_client.post("/requests", json={"request_type": "toileting"})
    r = api_client.post("/transition", json={"next_state": "KIT_SELECTED"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["robot_state"] == "KIT_SELECTED"

def test_invalid_transition(api_client):
    api_client.post("/requests", json={"request_type": "toileting"})
    assert api_client.post("/transition", json={"next_state": "COMPLETED"}, headers=HEADERS).status_code == 400

def test_kit_released_without_nurse_confirmation(api_client):
    api_client.post("/requests", json={"request_type": "toileting"})
    assert api_client.post("/transition", json={"next_state": "KIT_RELEASED"}, headers=HEADERS).status_code == 403

def test_emergency_stop(api_client):
    api_client.post("/requests", json={"request_type": "toileting"})
    r = api_client.post("/emergency-stop", headers=HEADERS)
    assert r.json()["robot_state"] == "ERROR"

def test_reset(api_client):
    api_client.post("/requests", json={"request_type": "toileting"})
    api_client.post("/emergency-stop", headers=HEADERS)
    r = api_client.post("/reset", headers=HEADERS)
    assert r.json()["robot_state"] == "IDLE"

def test_get_logs(api_client):
    assert isinstance(api_client.get("/logs").json(), list)

def test_cancel_ok(api_client):
    api_client.post("/requests", json={"request_type": "toileting"})
    r = api_client.post("/cancel", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["robot_state"] == "IDLE"

def test_cancel_from_moving_fails(api_client):
    api_client.post("/requests", json={"request_type": "toileting"})
    api_client.post("/transition", json={"next_state": "KIT_SELECTED"}, headers=HEADERS)
    api_client.post("/transition", json={"next_state": "MOVING_TO_BEDSIDE"}, headers=HEADERS)
    assert api_client.post("/cancel", headers=HEADERS).status_code == 400
