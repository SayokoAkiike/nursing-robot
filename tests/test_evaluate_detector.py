"""Tests for perception/evaluate_detector.py."""
import json

from perception.evaluate_detector import evaluate_many, evaluate_once, summarize
from vision.qr_detection.demo.synthetic_frames import SceneConfig


def test_evaluate_once_confirms_both_codes_in_a_clean_scene():
    config = SceneConfig(seconds_per_code=1.5, fps=12, occlusion_fraction=0.0, seed=0)
    result = evaluate_once(config, confirm_frames=3)

    assert result.patient_confirmed is True
    assert result.kit_confirmed is True
    assert result.patient_frames_to_confirm is not None
    assert result.kit_frames_to_confirm is not None
    # Kit phase comes after patient phase, so it should confirm later.
    assert result.kit_frames_to_confirm > result.patient_frames_to_confirm
    assert result.false_positive_count == 0


def test_higher_confirm_frames_takes_at_least_as_long_in_a_clean_scene():
    config = SceneConfig(seconds_per_code=1.5, fps=12, occlusion_fraction=0.0, noise_sigma=0.0, seed=1)
    fast = evaluate_once(config, confirm_frames=1)
    slow = evaluate_once(config, confirm_frames=5)

    assert fast.patient_frames_to_confirm <= slow.patient_frames_to_confirm
    assert fast.kit_frames_to_confirm <= slow.kit_frames_to_confirm


def test_unstable_detection_count_is_nonzero_when_occlusion_interrupts_streaks():
    config = SceneConfig(seconds_per_code=2.0, fps=15, occlusion_fraction=0.4, seed=2)
    result = evaluate_once(config, confirm_frames=5)
    assert result.unstable_detection_count >= 0  # sanity: metric is being tracked
    # With frequent occlusion and a fairly demanding threshold, at least
    # some interrupted streaks are expected across the scene.
    assert result.unstable_detection_count > 0


def test_evaluate_many_produces_one_result_per_seed_per_confirm_frames_value():
    results = evaluate_many(
        seeds=[0, 1, 2],
        confirm_frames_values=[1, 3],
        base_config=SceneConfig(seconds_per_code=0.5, fps=10),
    )
    assert len(results) == 3 * 2
    assert {r.confirm_frames for r in results} == {1, 3}
    assert {r.seed for r in results} == {0, 1, 2}


def test_summarize_computes_success_rate_and_means():
    results = evaluate_many(
        seeds=[0, 1, 2, 3],
        confirm_frames_values=[2],
        base_config=SceneConfig(seconds_per_code=1.0, fps=10, occlusion_fraction=0.0),
    )
    summary = summarize(results)

    assert set(summary.keys()) == {2}
    stats = summary[2]
    assert stats["runs"] == 4
    assert stats["patient_success_rate"] == 1.0
    assert stats["kit_success_rate"] == 1.0
    assert stats["mean_patient_frames_to_confirm"] is not None
    assert stats["mean_kit_frames_to_confirm"] is not None
    assert stats["total_false_positives"] == 0


def test_summarize_handles_no_confirmations_gracefully():
    from perception.evaluate_detector import EvaluationResult

    results = [
        EvaluationResult(
            seed=0,
            confirm_frames=99,
            patient_confirmed=False,
            patient_frames_to_confirm=None,
            kit_confirmed=False,
            kit_frames_to_confirm=None,
            unstable_detection_count=0,
            false_positive_count=0,
            total_frames=10,
        )
    ]
    summary = summarize(results)
    assert summary[99]["patient_success_rate"] == 0.0
    assert summary[99]["mean_patient_frames_to_confirm"] is None
    assert summary[99]["max_patient_frames_to_confirm"] is None


def test_cli_writes_json_output(tmp_path, capsys):
    import sys

    from perception.evaluate_detector import main

    output_path = str(tmp_path / "results.json")
    argv = [
        "evaluate_detector.py",
        "--seeds", "0,1",
        "--confirm-frames", "2",
        "--seconds-per-code", "0.5",
        "--fps", "10",
        "--output", output_path,
    ]
    old_argv = sys.argv
    sys.argv = argv
    try:
        main()
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    assert "confirm_frames" in captured.out

    payload = json.loads(open(output_path, encoding="utf-8").read())
    assert len(payload["results"]) == 2
    assert "2" in {str(k) for k in payload["summary"].keys()}
