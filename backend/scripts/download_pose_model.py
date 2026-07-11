"""One-time download of the MediaPipe Pose Landmarker model bundle
(PR30).

Unlike faster-whisper (which auto-downloads its model on first use),
MediaPipe's Tasks API requires an explicit local `.task` file path --
there is no equivalent auto-fetch. This script is that one manual step,
run once per machine/environment (a fresh Codespace, in particular).

Downloads `pose_landmarker_lite` (the smallest of the three official
variants -- lite/full/heavy -- trading some accuracy for speed on CPU,
appropriate for a demo/prototype rather than a clinical-grade device).

Usage:
    python -m backend.scripts.download_pose_model
    python -m backend.scripts.download_pose_model --dest /custom/path.task
"""
from __future__ import annotations

import argparse
from pathlib import Path

from perception.pose_detector import DEFAULT_MODEL_URL

DEFAULT_DEST = Path(__file__).resolve().parent.parent.parent / "perception" / "models" / "pose_landmarker_lite.task"


def download(dest: "str | Path" = DEFAULT_DEST, url: str = DEFAULT_MODEL_URL) -> Path:
    import httpx

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        print(f"Already present: {dest} (delete it first to re-download)")
        return dest

    print(f"Downloading {url}\n  -> {dest}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
        response.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    print(f"Done ({dest.stat().st_size / 1024 / 1024:.1f} MB).")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default=str(DEFAULT_DEST))
    parser.add_argument("--url", default=DEFAULT_MODEL_URL)
    args = parser.parse_args()
    download(dest=args.dest, url=args.url)


if __name__ == "__main__":
    main()
