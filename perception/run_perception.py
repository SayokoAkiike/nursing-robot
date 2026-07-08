"""CLI entry point: `python -m perception.run_perception`.

Watches a frame source for a patient-ID QR code and a kit QR code, requires
each to be read `--confirm-frames` consecutive times before trusting it
(see `perception/qr_detector.py`), and once both are confirmed calls
`POST /tasks/{request_id}/verify` against the running backend.

Example (once the PR5 synthetic demo video exists):
    python -m perception.run_perception \\
        --request-id abc12345 \\
        --source vision/qr_detection/demo/synthetic_delivery.mp4 \\
        --base-url http://localhost:8000 \\
        --nurse-token $NURSE_TOKEN

`--source` also accepts "webcam:0" for a live camera, or a directory of
still images (used by the test suite and by `perception/qr_detector.py`
demos that don't need an encoded video file).
"""
from __future__ import annotations

import argparse
import os
import sys

from perception.camera_source import open_source
from perception.qr_detector import StableQRDetector
from perception.verification_client import VerificationClient, VerificationClientError

PATIENT_PREFIX = "PATIENT_"


def _classify(value: str) -> str:
    return "patient_id" if value.startswith(PATIENT_PREFIX) else "kit_id"


def run(
    request_id: str,
    source_spec: str,
    base_url: str = "http://localhost:8000",
    nurse_token: str = "",
    confirm_frames: int = 3,
    max_frames: "int | None" = None,
    client: "VerificationClient | None" = None,
) -> dict:
    """Runs the perception loop; returns the verification result dict.

    `client` can be injected (e.g. pointed at an in-process ASGI transport
    in tests); if omitted, a real HTTP client targeting `base_url` is
    created and closed automatically.

    Raises RuntimeError if the frame source is exhausted before both a
    patient_id and a kit_id have been confirmed.
    """
    detector = StableQRDetector(confirm_frames=confirm_frames)
    source = open_source(source_spec)
    candidates: dict[str, str] = {}

    frame_count = 0
    try:
        for frame in source.frames():
            frame_count += 1
            result = detector.process_frame(frame)
            for value in result.newly_confirmed:
                role = _classify(value)
                if role not in candidates:
                    candidates[role] = value
                    print(f"[frame {frame_count}] confirmed {role} = {value}")
            if "patient_id" in candidates and "kit_id" in candidates:
                break
            if max_frames is not None and frame_count >= max_frames:
                break
    finally:
        source.close()

    if "patient_id" not in candidates or "kit_id" not in candidates:
        missing = [r for r in ("patient_id", "kit_id") if r not in candidates]
        raise RuntimeError(
            f"Could not confirm {', '.join(missing)} within {frame_count} frames "
            f"(unstable_detection_count={detector.unstable_detection_count})"
        )

    owns_client = client is None
    active_client = client or VerificationClient(base_url=base_url, nurse_token=nurse_token)
    try:
        outcome = active_client.verify(request_id, candidates["patient_id"], candidates["kit_id"])
    finally:
        if owns_client:
            active_client.close()

    return {
        "patient_id": candidates["patient_id"],
        "kit_id": candidates["kit_id"],
        "frames_processed": frame_count,
        "unstable_detection_count": detector.unstable_detection_count,
        "verification": outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="PreCareBot perception pipeline")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--source", required=True, help="webcam:0 | video file | image directory")
    parser.add_argument("--base-url", default=os.getenv("PRECARE_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--nurse-token", default=os.getenv("NURSE_TOKEN", ""))
    parser.add_argument("--confirm-frames", type=int, default=3)
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    try:
        outcome = run(
            request_id=args.request_id,
            source_spec=args.source,
            base_url=args.base_url,
            nurse_token=args.nurse_token,
            confirm_frames=args.confirm_frames,
            max_frames=args.max_frames,
        )
    except (RuntimeError, VerificationClientError) as exc:
        print(f"perception failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(outcome)


if __name__ == "__main__":
    main()
