"""Tests for backend.services.domain_service (roadmap item 4)."""
from backend.core.config import PATIENTS
from backend.services import domain_service


def test_split_allowed_kits_roundtrips_join_allowed_kits():
    kits = ["KIT_TOILETING_A", "KIT_WATER", "ALERT_NURSE_ONLY"]
    assert domain_service.split_allowed_kits(domain_service.join_allowed_kits(kits)) == kits


def test_split_allowed_kits_handles_none_and_empty():
    assert domain_service.split_allowed_kits(None) == []
    assert domain_service.split_allowed_kits("") == []


def test_seed_default_domain_data_creates_expected_rows(robot_storage):
    result = domain_service.seed_default_domain_data()
    assert result == {"seeded": True, "hospitals": 1, "patients": len(PATIENTS)}

    from backend.db import repositories

    assert len(repositories.list_hospitals()) == 1
    assert len(repositories.list_wards()) == 1
    assert len(repositories.list_nurses()) == 1
    assert len(repositories.list_robots()) == 1
    assert {p["id"] for p in repositories.list_patients()} == set(PATIENTS)
    # One room+bed per patient in this MVP's seed data.
    assert len(repositories.list_rooms()) == len(PATIENTS)
    assert len(repositories.list_beds()) == len(PATIENTS)


def test_seed_default_domain_data_is_idempotent(robot_storage):
    first = domain_service.seed_default_domain_data()
    second = domain_service.seed_default_domain_data()

    assert first["seeded"] is True
    assert second["seeded"] is False
    assert second["hospitals"] == first["hospitals"]
    assert second["patients"] == first["patients"]

    from backend.db import repositories

    # No duplicate rows from calling it twice.
    assert len(repositories.list_patients()) == len(PATIENTS)


def test_get_patient_view_resolves_room_and_ward(robot_storage):
    domain_service.seed_default_domain_data()

    view = domain_service.get_patient_view("PATIENT_A_ROOM_203")

    assert view is not None
    assert view["room_number"] == "203"
    assert view["ward_name"] == "Ward 2"
    assert set(view["allowed_kits"]) == set(PATIENTS["PATIENT_A_ROOM_203"]["allowed_kits"])


def test_get_patient_view_missing_returns_none(robot_storage):
    assert domain_service.get_patient_view("does-not-exist") is None


def test_list_patients_view_returns_every_seeded_patient(robot_storage):
    domain_service.seed_default_domain_data()
    views = domain_service.list_patients_view()
    assert {v["id"] for v in views} == set(PATIENTS)


def test_list_wards_view_nests_rooms_beds_and_patient_occupancy(robot_storage):
    domain_service.seed_default_domain_data()

    wards = domain_service.list_wards_view()

    assert len(wards) == 1
    ward = wards[0]
    assert ward["name"] == "Ward 2"
    assert len(ward["rooms"]) == len(PATIENTS)
    for room in ward["rooms"]:
        assert len(room["beds"]) == 1
        assert room["beds"][0]["patient_id"] is not None
