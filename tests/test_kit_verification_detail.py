"""Tests for PR9: kit_verifications expected/scanned detail.

`patient_id` / `kit_id` (kept for backward compatibility) are aliases for
`scanned_patient_id` / `scanned_kit_id` -- the QR value actually read. The
new `expected_*` columns record what *should* have been scanned (from
`care_requests.patient_id` / `robot_tasks.kit_id`), so an NG row's cause is
auditable without re-parsing the free-text `message`.
"""
from backend.core.errors import DomainError
from backend.db import repositories
from backend.services import workflow_service

import pytest


def _advance_to_verifying_patient(request_id):
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    return workflow_service.advance_state(request_id, "VERIFYING_PATIENT")


def test_successful_verification_records_matching_expected_and_scanned(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    _advance_to_verifying_patient(request_id)
    task = repositories.get_task_by_request_id(request_id)

    workflow_service.verify_ids(request_id, result["patient_id"], "KIT_TOILETING_A")

    rows = repositories.list_kit_verifications_for_task(task["id"])
    assert len(rows) == 1
    row = rows[0]
    assert row["result"] == "OK"
    assert row["expected_patient_id"] == result["patient_id"]
    assert row["scanned_patient_id"] == result["patient_id"]
    assert row["expected_kit_id"] == "KIT_TOILETING_A"
    assert row["scanned_kit_id"] == "KIT_TOILETING_A"
    # backward-compat aliases still populated
    assert row["patient_id"] == result["patient_id"]
    assert row["kit_id"] == "KIT_TOILETING_A"


def test_patient_mismatch_records_differing_expected_and_scanned_patient(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    _advance_to_verifying_patient(request_id)
    task = repositories.get_task_by_request_id(request_id)

    with pytest.raises(DomainError, match="patient_id mismatch"):
        workflow_service.verify_ids(request_id, "WRONG_PATIENT", "KIT_TOILETING_A")

    rows = repositories.list_kit_verifications_for_task(task["id"])
    row = rows[-1]
    assert row["result"] == "NG"
    assert row["expected_patient_id"] == result["patient_id"]
    assert row["scanned_patient_id"] == "WRONG_PATIENT"
    # kit_id matched in this case, so expected == scanned there
    assert row["expected_kit_id"] == row["scanned_kit_id"] == "KIT_TOILETING_A"


def test_kit_mismatch_records_differing_expected_and_scanned_kit(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    _advance_to_verifying_patient(request_id)
    task = repositories.get_task_by_request_id(request_id)

    with pytest.raises(DomainError, match="kit_id mismatch"):
        workflow_service.verify_ids(request_id, result["patient_id"], "KIT_WATER")

    rows = repositories.list_kit_verifications_for_task(task["id"])
    row = rows[-1]
    assert row["result"] == "NG"
    assert row["expected_patient_id"] == row["scanned_patient_id"] == result["patient_id"]
    assert row["expected_kit_id"] == "KIT_TOILETING_A"
    assert row["scanned_kit_id"] == "KIT_WATER"
