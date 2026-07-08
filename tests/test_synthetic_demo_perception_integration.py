"""Integration test: the PR5 synthetic video actually drives the PR4
perception pipeline end to end.

This is the point of generating a synthetic video at all -- it should be
usable as a drop-in `--source` for `perception.run_perception`, standing
in for a real (or a live) camera without any real footage or personal
data. Uses a short/fast SceneConfig so this stays quick in CI.
"""
from fastapi.testclient import TestClient

from backend.services import workflow_service
from perception.run_perception import run
from perception.verification_client import VerificationClient
from vision.qr_detection.demo.generate_synthetic_video import generate_video
from vision.qr_detection.demo.synthetic_frames import SceneConfig

NURSE_TOKEN = "precare-dev-token-2026"


def test_synthetic_video_drives_perception_pipeline(tmp_path, robot_storage):
    view = workflow_service.create_request("toileting")
    request_id = view["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")

    config = SceneConfig(
        patient_id="PATIENT_A_ROOM_203",
        kit_id="KIT_TOILETING_A",
        seconds_per_code=2.5,
        fps=15,
        occlusion_fraction=0.1,
        seed=3,
    )
    video_path = str(tmp_path / "demo.mp4")
    generate_video(config, video_path)

    from backend.main import app

    client = VerificationClient(nurse_token=NURSE_TOKEN, client=TestClient(app))

    outcome = run(
        request_id=request_id,
        source_spec=video_path,
        confirm_frames=3,
        client=client,
    )

    assert outcome["patient_id"] == "PATIENT_A_ROOM_203"
    assert outcome["kit_id"] == "KIT_TOILETING_A"
    assert outcome["verification"]["ok"] is True
    assert outcome["verification"]["state"]["robot_state"] == "DOCKING"
