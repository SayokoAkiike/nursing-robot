"""Classical evaluation benchmark for perception/qr_detector.py.

Deliberately not an ML/eval-pipeline in the MLOps sense -- this is a
parameter sweep over the one tunable knob `StableQRDetector` actually has
(`confirm_frames`), scored against the PR5 synthetic scene generator's
ground truth. It answers a concrete question: for a given confirm_frames
setting, how many frames does it typically take to confirm each QR code,
how often does confirmation fail to happen at all, and how many
"unstable" (interrupted) readings occur along the way. Runs entirely
in-memory against `vision.qr_detection.demo.synthetic_frames` -- no video
file is read or written, so this stays fast enough to run in CI.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import statistics

from perception.qr_detector import StableQRDetector
from vision.qr_detection.demo.synthetic_frames import SceneConfig, generate_frames


@dataclasses.dataclass
class EvaluationResult:
    seed: int
    confirm_frames: int
    patient_confirmed: bool
    patient_frames_to_confirm: "int | None"
    kit_confirmed: bool
    kit_frames_to_confirm: "int | None"
    unstable_detection_count: int
    false_positive_count: int
    total_frames: int


def evaluate_once(config: SceneConfig, confirm_frames: int) -> EvaluationResult:
    """Runs one StableQRDetector over one synthetic scene and scores it
    against that scene's known patient_id/kit_id."""
    detector = StableQRDetector(confirm_frames=confirm_frames)
    patient_frames_to_confirm = None
    kit_frames_to_confirm = None
    false_positive_count = 0

    for frame, info in generate_frames(config):
        result = detector.process_frame(frame)
        for value in result.newly_confirmed:
            if value == config.patient_id and patient_frames_to_confirm is None:
                patient_frames_to_confirm = info.frame_index
            elif value == config.kit_id and kit_frames_to_confirm is None:
                kit_frames_to_confirm = info.frame_index
            elif value not in (config.patient_id, config.kit_id):
                false_positive_count += 1

    return EvaluationResult(
        seed=config.seed,
        confirm_frames=confirm_frames,
        patient_confirmed=patient_frames_to_confirm is not None,
        patient_frames_to_confirm=patient_frames_to_confirm,
        kit_confirmed=kit_frames_to_confirm is not None,
        kit_frames_to_confirm=kit_frames_to_confirm,
        unstable_detection_count=detector.unstable_detection_count,
        false_positive_count=false_positive_count,
        total_frames=config.total_frames,
    )


def evaluate_many(
    seeds: "list[int]",
    confirm_frames_values: "list[int]",
    base_config: "SceneConfig | None" = None,
) -> "list[EvaluationResult]":
    """Runs `evaluate_once` for every (confirm_frames, seed) combination."""
    base = base_config or SceneConfig()
    results = []
    for confirm_frames in confirm_frames_values:
        for seed in seeds:
            config = dataclasses.replace(base, seed=seed)
            results.append(evaluate_once(config, confirm_frames))
    return results


def summarize(results: "list[EvaluationResult]") -> dict:
    """Groups results by confirm_frames and computes aggregate stats."""
    by_confirm_frames: "dict[int, list[EvaluationResult]]" = {}
    for r in results:
        by_confirm_frames.setdefault(r.confirm_frames, []).append(r)

    summary = {}
    for confirm_frames, group in sorted(by_confirm_frames.items()):
        n = len(group)
        patient_times = [r.patient_frames_to_confirm for r in group if r.patient_frames_to_confirm is not None]
        kit_times = [r.kit_frames_to_confirm for r in group if r.kit_frames_to_confirm is not None]
        summary[confirm_frames] = {
            "runs": n,
            "patient_success_rate": sum(r.patient_confirmed for r in group) / n,
            "kit_success_rate": sum(r.kit_confirmed for r in group) / n,
            "mean_patient_frames_to_confirm": statistics.mean(patient_times) if patient_times else None,
            "mean_kit_frames_to_confirm": statistics.mean(kit_times) if kit_times else None,
            "max_patient_frames_to_confirm": max(patient_times) if patient_times else None,
            "max_kit_frames_to_confirm": max(kit_times) if kit_times else None,
            "mean_unstable_detection_count": statistics.mean(r.unstable_detection_count for r in group),
            "total_false_positives": sum(r.false_positive_count for r in group),
        }
    return summary


def _parse_int_list(spec: str) -> "list[int]":
    return [int(x) for x in spec.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate StableQRDetector against the synthetic QR scene")
    parser.add_argument("--seeds", default="0,1,2,3,4", help="Comma-separated RNG seeds, one run each")
    parser.add_argument("--confirm-frames", default="1,2,3,5", help="Comma-separated confirm_frames values to sweep")
    parser.add_argument("--seconds-per-code", type=float, default=SceneConfig.seconds_per_code)
    parser.add_argument("--fps", type=int, default=SceneConfig.fps)
    parser.add_argument("--output", default=None, help="Optional path to write full results + summary as JSON")
    args = parser.parse_args()

    seeds = _parse_int_list(args.seeds)
    confirm_frames_values = _parse_int_list(args.confirm_frames)
    base_config = SceneConfig(seconds_per_code=args.seconds_per_code, fps=args.fps)

    results = evaluate_many(seeds, confirm_frames_values, base_config)
    summary = summarize(results)

    def _fmt(value):
        return f"{value:.1f}" if value is not None else "n/a"

    print(f"{'confirm_frames':>14} {'patient_ok':>11} {'kit_ok':>8} {'mean_p_frames':>14} {'mean_k_frames':>14} {'mean_unstable':>14} {'false_pos':>10}")
    for confirm_frames, stats in summary.items():
        print(
            f"{confirm_frames:>14} "
            f"{stats['patient_success_rate']*100:>10.0f}% "
            f"{stats['kit_success_rate']*100:>7.0f}% "
            f"{_fmt(stats['mean_patient_frames_to_confirm']):>14} "
            f"{_fmt(stats['mean_kit_frames_to_confirm']):>14} "
            f"{stats['mean_unstable_detection_count']:>14.2f} "
            f"{stats['total_false_positives']:>10}"
        )

    if args.output:
        payload = {
            "results": [dataclasses.asdict(r) for r in results],
            "summary": summary,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\nWrote full results to {args.output}")


if __name__ == "__main__":
    main()
