"""CLI entry point: `python -m backend.scripts.run_pose_demo`.

Watches a frame source (same `--source` spec as `perception.run_perception`
-- webcam:0 / a video file / a directory of still images) for a person's
hip position relative to a configured `--bed-region`, using MediaPipe
Pose (`perception/pose_detector.py`) + pure assessment logic
(`backend/services/bed_exit_service.py`). Requires `--confirm-frames`
consecutive fall_risk frames before reporting anything (same debounce
principle `perception/qr_detector.py`'s StableQRDetector uses for QR
codes) -- one noisy frame should never trigger a nurse escalation.

PR33 (C): each frame's hip position is also fed into a `MotionTracker`
(velocity/acceleration across a short rolling window), and the two
signals are combined (`combine_assessments()`) -- a static "hip is
outside the bed region" check alone can miss a fall fast enough that no
single sampled frame's position looks unambiguously outside the bed;
the *speed* of the motion is a second, independent tell. See
bed_exit_service.py's PR33 section comment for the full reasoning.

Never records video/images anywhere -- frames are processed one at a
time and discarded; only the resulting escalation (room, patient_id,
summary text) is ever sent anywhere, via
`POST /escalations/vision-report`.

One-time setup (model file isn't bundled or auto-downloaded -- see
`perception/pose_detector.py`'s module docstring for why):
    python -m backend.scripts.download_pose_model

If MediaPipe raises `OSError: libGLESv2.so.2: cannot open shared object
file` or `libEGL.so.1: cannot open shared object file` the first time
`PoseDetector.detect()` actually runs (this happened when this feature
was first tried in a fresh Codespace -- the base devcontainer image
doesn't include these), install the two missing system libraries once:
    sudo apt-get update && sudo apt-get install -y libgles2 libegl1
Neither is a Python dependency (`pip install` won't surface this) --
MediaPipe's Tasks API links against them at the OS level even for
CPU-only inference.

Example:
    python -m backend.scripts.run_pose_demo \\\\
        --source webcam:0 \\\\
        --room 203 --patient-id PATIENT_A_ROOM_203 \\\\
        --bed-region 0.2,0.5,0.8,1.0 \\\\
        --base-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx

from backend.services.bed_exit_service import (
    BedRegion,
    MotionTracker,
    assess,
    combine_assessments,
    hip_midpoint,
    suggested_action_for,
    summary_for,
)
from perception.camera_source import open_source
from perception.pose_detector import PoseDetector

DEFAULT_MODEL_PATH = "perception/models/pose_landmarker_lite.task"


def _parse_bed_region(spec: str) -> BedRegion:
    parts = [float(p) for p in spec.split(",")]
    if len(parts) != 4:
        raise ValueError(f"--bed-region must be 'x_min,y_min,x_max,y_max', got: {spec!r}")
    return BedRegion(*parts)


def run(
    source_spec: str,
    bed_region: BedRegion,
    room: str,
    patient_id: str,
    model_path: str = DEFAULT_MODEL_PATH,
    base_url: str = "http://localhost:8000",
    confirm_frames: int = 5,
    max_frames: "int | None" = None,
    client: "httpx.Client | None" = None,
    frame_interval_seconds: float = 0.2,
) -> "dict | None":
    """Runs the monitoring loop; returns the raised escalation dict, or
    None if the source was exhausted (or `max_frames` reached) without a
    confirmed fall_risk finding.

    `client` can be injected (e.g. an in-process ASGI transport in
    tests); if omitted, a real HTTP client targeting `base_url` is
    created and closed automatically -- same pattern
    `perception.run_perception.run()` uses for VerificationClient.

    `frame_interval_seconds` (PR33/C): the assumed time between
    processed frames, used to timestamp `MotionTracker` samples --
    deliberately NOT `time.monotonic()`. A video-file or image-directory
    `--source` gets read as fast as disk I/O allows, which has nothing
    to do with the real camera frame rate the footage was captured at;
    using wall-clock time there would make velocity/acceleration wildly
    overestimated (and make this function's behavior depend on how fast
    the machine running it happens to be, which is also why the mocked
    test suite needs this to be deterministic). Default 0.2s (~5fps)
    assumes a monitoring loop sampling at a modest cadence, not
    processing every frame of a 30fps camera; pass the real interval for
    a `--source` where one is known.
    """
    detector = PoseDetector(model_path)
    source = open_source(source_spec)
    motion_tracker = MotionTracker()

    consecutive_fall_risk = 0
    frame_count = 0
    try:
        for frame in source.frames():
            frame_count += 1
            landmarks = detector.detect(frame)
            static_assessment = assess(landmarks, bed_region)

            hip = hip_midpoint(landmarks)
            if hip is None:
                # Nobody clearly visible this frame -- don't let a gap
                # in tracking manufacture a fake velocity spike once the
                # person reappears; start the motion trace over.
                motion_tracker.reset()
                motion = None
            else:
                hip_x, hip_y, _confidence = hip
                timestamp = frame_count * frame_interval_seconds
                motion = motion_tracker.add_sample(hip_x, hip_y, timestamp=timestamp)

            assessment = combine_assessments(static_assessment, motion)

            if assessment.detected_need == "fall_risk":
                consecutive_fall_risk += 1
            else:
                consecutive_fall_risk = 0

            motion_note = (
                f" velocity_y={motion.velocity_y:.2f} sudden_motion={motion.sudden_motion}"
                if motion is not None
                else ""
            )
            print(
                f"[frame {frame_count}] person_detected={assessment.person_detected} "
                f"in_bed={assessment.in_bed} confidence={assessment.confidence} "
                f"consecutive_fall_risk={consecutive_fall_risk}{motion_note}"
            )

            if consecutive_fall_risk >= confirm_frames:
                print(f"CONFIRMED fall_risk after {confirm_frames} consecutive frames -- reporting.")
                break
            if max_frames is not None and frame_count >= max_frames:
                return None
        else:
            return None
    finally:
        source.close()

    if consecutive_fall_risk < confirm_frames:
        return None

    summary = summary_for(assessment, room, patient_id)
    owns_client = client is None
    active_client = client or httpx.Client(base_url=base_url, timeout=5.0)
    try:
        response = active_client.post(
            "/escalations/vision-report",
            json={
                "room": room,
                "patient_id": patient_id,
                "summary": summary,
                "priority": "URGENT",
                "reason": "fall_risk",
                "suggested_action": suggested_action_for(assessment),
            },
        )
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            active_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="webcam:0 | video file | image directory")
    parser.add_argument("--room", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument(
        "--bed-region",
        default="0.2,0.5,0.8,1.0",
        help="x_min,y_min,x_max,y_max in normalized 0.0-1.0 image coordinates",
    )
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--base-url", default=os.getenv("PRECARE_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--confirm-frames", type=int, default=5)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument(
        "--frame-interval-seconds",
        type=float,
        default=0.2,
        help="Assumed time between processed frames, for MotionTracker's velocity calculation (PR33/C)",
    )
    args = parser.parse_args()

    try:
        bed_region = _parse_bed_region(args.bed_region)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    try:
        result = run(
            source_spec=args.source,
            bed_region=bed_region,
            room=args.room,
            patient_id=args.patient_id,
            model_path=args.model_path,
            base_url=args.base_url,
            confirm_frames=args.confirm_frames,
            max_frames=args.max_frames,
            frame_interval_seconds=args.frame_interval_seconds,
        )
    except (FileNotFoundError, httpx.HTTPError) as exc:
        print(f"run_pose_demo failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if result is None:
        print("No confirmed fall_risk finding within the given source/frame limit.")
    else:
        print(f"Escalation raised: {result}")


if __name__ == "__main__":
    main()
