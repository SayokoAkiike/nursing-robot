"""CLI: generate the synthetic QR delivery demo video.

    python -m vision.qr_detection.demo.generate_synthetic_video

Writes an .mp4 (default: vision/qr_detection/demo/synthetic_delivery.mp4)
built entirely from synthetically rendered QR codes -- no real camera
footage, no personal data. The video is intentionally *not* committed to
git (see .gitignore); regenerate it locally with this script whenever
needed. A ground-truth metadata JSON is written alongside it (same name,
`.json` extension) recording, per frame, which QR value should be visible
and whether that frame was deliberately occluded -- this is what the PR6
evaluation benchmark is expected to score detector output against.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os

import cv2

from vision.qr_detection.demo.synthetic_frames import SceneConfig, generate_frames

DEFAULT_OUTPUT = os.path.join(os.path.dirname(__file__), "synthetic_delivery.mp4")


def generate_video(config: SceneConfig, output_path: str, metadata_path: "str | None" = None) -> str:
    """Renders `config`'s scene to `output_path` (.mp4) and writes ground
    truth metadata to `metadata_path` (defaults to `output_path` with a
    `.json` extension). Returns the metadata path."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    if metadata_path is None:
        metadata_path = os.path.splitext(output_path)[0] + ".json"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, config.fps, (config.frame_size, config.frame_size))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer for: {output_path}")

    frame_records = []
    try:
        for frame, info in generate_frames(config):
            writer.write(frame)
            frame_records.append(dataclasses.asdict(info))
    finally:
        writer.release()

    metadata = {"config": dataclasses.asdict(config), "frames": frame_records}
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic QR demo video")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata-output", default=None)
    parser.add_argument("--patient-id", default=SceneConfig.patient_id)
    parser.add_argument("--kit-id", default=SceneConfig.kit_id)
    parser.add_argument("--fps", type=int, default=SceneConfig.fps)
    parser.add_argument("--seconds-per-code", type=float, default=SceneConfig.seconds_per_code)
    parser.add_argument("--seed", type=int, default=SceneConfig.seed)
    args = parser.parse_args()

    config = SceneConfig(
        patient_id=args.patient_id,
        kit_id=args.kit_id,
        fps=args.fps,
        seconds_per_code=args.seconds_per_code,
        seed=args.seed,
    )
    metadata_path = generate_video(config, args.output, args.metadata_output)
    print(f"Wrote video: {args.output}")
    print(f"Wrote metadata: {metadata_path}")
    print(f"Total frames: {config.total_frames}")


if __name__ == "__main__":
    main()
