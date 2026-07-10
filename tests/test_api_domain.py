"""API tests for the read-only domain registry endpoints (roadmap item 4):
GET /patients, /patients/{id}, /robots, /wards. No auth on any of these,
same as tests/test_api_escalations.py's GET routes."""
from backend.services import domain_service


def test_list_patients_empty_before_seeding(api_client):
    r = api_client.get("/patients")
    assert r.status_code == 200
    assert r.json() == []


def test_list_patients_after_seeding(api_client):
    domain_service.seed_default_domain_data()
    r = api_client.get("/patients")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert "PATIENT_A_ROOM_203" in ids
    assert "PATIENT_B_ROOM_204" in ids


def test_get_patient(api_client):
    domain_service.seed_default_domain_data()
    r = api_client.get("/patients/PATIENT_A_ROOM_203")
    assert r.status_code == 200
    body = r.json()
    assert body["room_number"] == "203"
    assert "KIT_TOILETING_A" in body["allowed_kits"]


def test_get_unknown_patient_is_404(api_client):
    r = api_client.get("/patients/does-not-exist")
    assert r.status_code == 404


def test_list_robots(api_client):
    domain_service.seed_default_domain_data()
    r = api_client.get("/robots")
    assert r.status_code == 200
    ids = {robot["id"] for robot in r.json()}
    assert "ROBOT_1" in ids


def test_list_wards_nests_rooms_and_beds(api_client):
    domain_service.seed_default_domain_data()
    r = api_client.get("/wards")
    assert r.status_code == 200
    wards = r.json()
    assert len(wards) == 1
    assert wards[0]["rooms"], "expected at least one room in the seeded ward"
    assert wards[0]["rooms"][0]["beds"], "expected at least one bed in the seeded room"
