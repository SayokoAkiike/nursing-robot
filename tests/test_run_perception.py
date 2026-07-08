"""End-to-end test for perception/run_perception.py.

Builds a directory of synthetic frames (a patient-ID QR repeated enough
times to be confirmed, then a kit QR repeated enough times to be
confirmed) and runs the full pipeline against the real FastAPI app
in-process (via a `VerificationClient` wrapping Starlette's `TestClient`,
injected through `run()`'s `client` parameter) -- no real camera, video
file, or live server needed.
"""
import io

import cv2
import numpy as np
import qrcode
from fastapi.testclient import TestClient
from PIL import Image

from backend.services import workflow_service
from perception.run_perception import run
from perception.verification_client import VerificationClient

NURSE_TOKEN = "precare-dev-token-2026"


def _save_qr_frame(path, data: str, box_size: int = 6):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    arr = np.array(Image.open(buf))
    cv2.imwrite(str(path), cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))


def _build_frame_dir(tmp_path, patient_id: str, kit_id: str, repeats: int = 4):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    idx = 0
    for _ in range(repeats):
        _save_qr_frame(frame_dir / f"{idx:04d}.png", patient_id)
        idx += 1
    for _ in range(repeats):
        _save_qr_frame(frame_dir / f"{idx:04d}.png", kit_id)
        idx += 1
    return str(frame_dir)


def test_run_perception_confirms_and_verifies(tmp_path, robot_storage):
    view = workflow_service.create_request("toileting")
    request_id = view["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")

    source_dir = _build_frame_dir(tmp_path, "PATIENT_A_ROOM_203", "KIT_TOILETING_A")

    from backend.main import app

    client = VerificationClient(nurse_token=NURSE_TOKEN, client=TestClient(app))

    outcome = run(
        request_id=request_id,
        source_spec=source_dir,
        confirm_frames=3,
        client=client,
    )

    assert outcome["patient_id"] == "PATIENT_A_ROOM_203"
    assert outcome["kit_id"] == "KIT_TOILETING_A"
    assert outcome["verification"]["ok"] is True
    assert outcome["verification"]["state"]["robot_state"] == "DOCKING"


def test_run_perception_raises_if_not_enough_frames(tmp_path, robot_storage):
    view = workflow_service.create_request("toileting")
    request_id = view["request_id"]

    # Only 2 repeats of each value but confirm_frames=3 -> never confirmed.
    source_dir = _build_frame_dir(tmp_path, "PATIENT_A_ROOM_203", "KIT_TOILETING_A", repeats=2)

    import pytest

    with pytest.raises(RuntimeError):
        run(request_id=request_id, source_spec=source_dir, confirm_frames=3)
