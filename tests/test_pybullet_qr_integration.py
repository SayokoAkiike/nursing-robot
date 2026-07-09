"""QR overlay tests for perception/pybullet_source.py (Phase 4, PR18).

Two layers, cheapest-signal-first:
  1. A direct decode check -- do the composited frames actually contain
     readable QR codes, independent of the workflow state machine.
  2. A full integration test mirroring tests/test_synthetic_demo_perception_
     integration.py and tests/test_run_perception.py, proving the existing
     perception.run_perception pipeline can confirm and verify against
     PyBullet-sourced frames end to end.
"""
import cv2
from fastapi.testclient import TestClient

from backend.services import workflow_service
from perception.pybullet_source import PyBulletSource
from perception.run_perception import run
from perception.verification_client import VerificationClient

NURSE_TOKEN = "precare-dev-token-2026"


def test_qr_overlay_frames_are_decodable_by_cv2():
    source = PyBulletSource(preset="delivery_with_qr", steps=3, width=320, height=240)
    detector = cv2.QRCodeDetector()
    found = set()
    for frame in source.frames():
        ok, decoded_info, _points, _straight = detector.detectAndDecodeMulti(frame)
        if ok:
            found.update(v for v in decoded_info if v)

    assert "PATIENT_A_ROOM_203" in found
    assert "KIT_TOILETING_A" in found


def test_plain_delivery_preset_has_no_overlay_and_is_unaffected():
    """Regression guard: PR17's plain "delivery" preset must keep behaving
    exactly as before -- no QR overlay bleeding into it."""
    source = PyBulletSource(preset="delivery", steps=2, width=64, height=48)
    assert source.qr_overlay is None
    frames = list(source.frames())
    assert len(frames) == 2


def test_pybullet_frames_with_qr_overlay_drive_perception_pipeline(robot_storage):
    view = workflow_service.create_request("toileting")
    request_id = view["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")

    from backend.main import app

    client = VerificationClient(nurse_token=NURSE_TOKEN, client=TestClient(app))

    outcome = run(
        request_id=request_id,
        source_spec="pybullet:delivery_with_qr",
        confirm_frames=3,
        client=client,
    )

    assert outcome["patient_id"] == "PATIENT_A_ROOM_203"
    assert outcome["kit_id"] == "KIT_TOILETING_A"
    assert outcome["verification"]["ok"] is True
    assert outcome["verification"]["state"]["robot_state"] == "DOCKING"
