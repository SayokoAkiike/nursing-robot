"""Tests for the domain registry tables added in backend.db.repositories
(roadmap item 4: Hospital/Ward/Room/Bed/Patient/Nurse/Robot). Same plain
insert/get/list CRUD style as tests/test_repositories.py and
tests/test_rounding_repositories.py."""
from backend.db import repositories

HOSPITAL_ROW = {"id": "HOSPITAL_MAIN", "name": "PreCare Hospital"}
WARD_ROW = {"id": "WARD_2", "hospital_id": "HOSPITAL_MAIN", "name": "Ward 2"}
ROOM_ROW = {"id": "ROOM_203", "ward_id": "WARD_2", "number": "203"}
BED_ROW = {"id": "ROOM_203_BED_A", "room_id": "ROOM_203", "label": "A"}
PATIENT_ROW = {
    "id": "PATIENT_A_ROOM_203",
    "display_name": "Patient A",
    "bed_id": "ROOM_203_BED_A",
    "allowed_kits": "KIT_TOILETING_A,KIT_WATER,ALERT_NURSE_ONLY",
}
NURSE_ROW = {"id": "NURSE_DEFAULT", "name": "Duty Nurse", "ward_id": "WARD_2"}
ROBOT_ROW = {"id": "ROBOT_1", "name": "Robot 1", "hospital_id": "HOSPITAL_MAIN"}


def test_get_hospital_missing_returns_none(robot_storage):
    assert repositories.get_hospital("does-not-exist") is None


def test_insert_and_get_hospital(robot_storage):
    repositories.insert_hospital(HOSPITAL_ROW)
    assert repositories.get_hospital("HOSPITAL_MAIN") == HOSPITAL_ROW
    assert repositories.list_hospitals() == [HOSPITAL_ROW]


def test_insert_and_get_ward(robot_storage):
    repositories.insert_hospital(HOSPITAL_ROW)
    repositories.insert_ward(WARD_ROW)
    assert repositories.get_ward("WARD_2") == WARD_ROW
    assert repositories.list_wards() == [WARD_ROW]


def test_insert_and_get_room(robot_storage):
    repositories.insert_hospital(HOSPITAL_ROW)
    repositories.insert_ward(WARD_ROW)
    repositories.insert_room(ROOM_ROW)
    assert repositories.get_room("ROOM_203") == ROOM_ROW
    assert repositories.list_rooms() == [ROOM_ROW]
    assert repositories.list_rooms(ward_id="WARD_2") == [ROOM_ROW]
    assert repositories.list_rooms(ward_id="no-such-ward") == []


def test_insert_and_get_bed(robot_storage):
    repositories.insert_hospital(HOSPITAL_ROW)
    repositories.insert_ward(WARD_ROW)
    repositories.insert_room(ROOM_ROW)
    repositories.insert_bed(BED_ROW)
    assert repositories.get_bed("ROOM_203_BED_A") == BED_ROW
    assert repositories.list_beds() == [BED_ROW]
    assert repositories.list_beds(room_id="ROOM_203") == [BED_ROW]
    assert repositories.list_beds(room_id="no-such-room") == []


def test_insert_and_get_patient(robot_storage):
    repositories.insert_hospital(HOSPITAL_ROW)
    repositories.insert_ward(WARD_ROW)
    repositories.insert_room(ROOM_ROW)
    repositories.insert_bed(BED_ROW)
    repositories.insert_patient(PATIENT_ROW)
    assert repositories.get_patient("PATIENT_A_ROOM_203") == PATIENT_ROW
    assert repositories.list_patients() == [PATIENT_ROW]


def test_insert_and_get_nurse(robot_storage):
    repositories.insert_hospital(HOSPITAL_ROW)
    repositories.insert_ward(WARD_ROW)
    repositories.insert_nurse(NURSE_ROW)
    assert repositories.get_nurse("NURSE_DEFAULT") == NURSE_ROW
    assert repositories.list_nurses() == [NURSE_ROW]


def test_insert_and_get_robot(robot_storage):
    repositories.insert_hospital(HOSPITAL_ROW)
    repositories.insert_robot(ROBOT_ROW)
    assert repositories.get_robot("ROBOT_1") == ROBOT_ROW
    assert repositories.list_robots() == [ROBOT_ROW]


def test_delete_all_data_clears_domain_registry_too(robot_storage):
    repositories.insert_hospital(HOSPITAL_ROW)
    repositories.insert_ward(WARD_ROW)
    repositories.insert_room(ROOM_ROW)
    repositories.insert_bed(BED_ROW)
    repositories.insert_patient(PATIENT_ROW)
    repositories.insert_nurse(NURSE_ROW)
    repositories.insert_robot(ROBOT_ROW)

    repositories.delete_all_data()

    assert repositories.list_hospitals() == []
    assert repositories.list_wards() == []
    assert repositories.list_rooms() == []
    assert repositories.list_beds() == []
    assert repositories.list_patients() == []
    assert repositories.list_nurses() == []
    assert repositories.list_robots() == []
