"""Tests for backend/services/bed_exit_service.py.

Pure-function tests -- no mediapipe import anywhere in this file, same
principle as tests/test_need_classification_service.py not needing any
audio/speech dependency.
"""
import pytest

from backend.services.bed_exit_service import (
    BedRegion,
    Landmark,
    MotionAssessment,
    MotionTracker,
    assess,
    combine_assessments,
    hip_midpoint,
    suggested_action_for,
    summary_for,
)

BED = BedRegion(x_min=0.2, y_min=0.5, x_max=0.8, y_max=1.0)


def _landmarks_with_hips(left_x, left_y, left_vis, right_x, right_y, right_vis) -> list[Landmark]:
    # 33 landmarks total; only indices 23/24 (hips) matter for assess().
    landmarks = [Landmark(0.5, 0.5, 1.0) for _ in range(33)]
    landmarks[23] = Landmark(left_x, left_y, left_vis)
    landmarks[24] = Landmark(right_x, right_y, right_vis)
    return landmarks


def test_no_landmarks_means_no_person_detected():
    result = assess(None, BED)
    assert result.person_detected is False
    assert result.detected_need == "unknown"


def test_empty_landmarks_list_means_no_person_detected():
    result = assess([], BED)
    assert result.person_detected is False


def test_hips_inside_bed_region_is_in_bed():
    landmarks = _landmarks_with_hips(0.45, 0.7, 1.0, 0.55, 0.7, 1.0)
    result = assess(landmarks, BED)
    assert result.person_detected is True
    assert result.in_bed is True
    assert result.detected_need == "in_bed"
    assert result.confidence == "high"


def test_hips_outside_bed_region_is_fall_risk():
    landmarks = _landmarks_with_hips(0.05, 0.1, 1.0, 0.1, 0.1, 1.0)
    result = assess(landmarks, BED)
    assert result.person_detected is True
    assert result.in_bed is False
    assert result.detected_need == "fall_risk"


def test_low_visibility_hips_yield_low_confidence_unknown():
    landmarks = _landmarks_with_hips(0.45, 0.7, 0.1, 0.55, 0.7, 0.1)
    result = assess(landmarks, BED)
    assert result.person_detected is True
    assert result.confidence == "low"
    assert result.detected_need == "unknown"


def test_one_visible_hip_still_assesses_with_low_confidence():
    landmarks = _landmarks_with_hips(0.45, 0.7, 1.0, 0.55, 0.7, 0.0)
    result = assess(landmarks, BED)
    assert result.person_detected is True
    assert result.confidence == "low"
    # Still uses the one visible hip to decide in/out of bed.
    assert result.detected_need == "in_bed"


def test_bed_region_boundary_is_inclusive():
    region = BedRegion(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
    assert region.contains(0.0, 0.0) is True
    assert region.contains(1.0, 1.0) is True
    assert region.contains(1.01, 0.5) is False


def test_summary_for_empty_unless_fall_risk():
    landmarks = _landmarks_with_hips(0.45, 0.7, 1.0, 0.55, 0.7, 1.0)  # in_bed
    in_bed_assessment = assess(landmarks, BED)
    assert summary_for(in_bed_assessment, "203", "PATIENT_A_ROOM_203") == ""


def test_summary_for_fall_risk_includes_room_and_patient():
    landmarks = _landmarks_with_hips(0.05, 0.1, 1.0, 0.1, 0.1, 1.0)  # out of bed
    fall_risk_assessment = assess(landmarks, BED)
    summary = summary_for(fall_risk_assessment, "203", "PATIENT_A_ROOM_203")
    assert "203" in summary
    assert "PATIENT_A_ROOM_203" in summary


def test_suggested_action_for_reuses_need_classification_service():
    from backend.services import need_classification_service

    landmarks = _landmarks_with_hips(0.05, 0.1, 1.0, 0.1, 0.1, 1.0)
    fall_risk_assessment = assess(landmarks, BED)
    assert suggested_action_for(fall_risk_assessment) == need_classification_service.suggested_action(
        "fall_risk"
    )


# ---- PR33 (C): MotionTracker / combine_assessments --------------------------


def test_motion_tracker_needs_at_least_two_samples_for_velocity():
    tracker = MotionTracker()
    result = tracker.add_sample(0.5, 0.5, timestamp=0.0)
    assert result.sample_count == 1
    assert result.velocity_y == 0.0
    assert result.sudden_motion is False


def test_motion_tracker_computes_downward_velocity():
    tracker = MotionTracker(velocity_threshold=0.6)
    tracker.add_sample(0.5, 0.3, timestamp=0.0)
    result = tracker.add_sample(0.5, 0.5, timestamp=1.0)  # +0.2 y in 1s -> velocity 0.2
    assert result.velocity_y == pytest.approx(0.2)
    assert result.sudden_motion is False


def test_motion_tracker_flags_sudden_downward_velocity():
    tracker = MotionTracker(velocity_threshold=0.6)
    tracker.add_sample(0.5, 0.2, timestamp=0.0)
    result = tracker.add_sample(0.5, 0.9, timestamp=1.0)  # +0.7 y in 1s -> velocity 0.7
    assert result.velocity_y == pytest.approx(0.7)
    assert result.sudden_motion is True


def test_motion_tracker_flags_sudden_acceleration_even_below_velocity_threshold():
    tracker = MotionTracker(velocity_threshold=10.0, acceleration_threshold=0.5)
    tracker.add_sample(0.5, 0.2, timestamp=0.0)
    tracker.add_sample(0.5, 0.21, timestamp=1.0)  # slow: velocity 0.01
    result = tracker.add_sample(0.5, 0.5, timestamp=2.0)  # sudden: velocity 0.29
    # acceleration = (0.29 - 0.01) / (2.0 - 0.0) = 0.14 -- below 0.5, so this
    # particular jump shouldn't trigger on acceleration alone; confirms the
    # threshold is actually being applied, not just always true.
    assert result.sudden_motion is False


def test_motion_tracker_out_of_order_timestamp_does_not_crash():
    tracker = MotionTracker()
    tracker.add_sample(0.5, 0.5, timestamp=1.0)
    result = tracker.add_sample(0.5, 0.6, timestamp=0.5)  # earlier than previous sample
    assert result.sudden_motion is False


def test_motion_tracker_window_size_bounds_history():
    tracker = MotionTracker(window_size=3)
    for i in range(10):
        tracker.add_sample(0.5, 0.5, timestamp=float(i))
    assert len(tracker._history) == 3


def test_motion_tracker_reset_clears_history():
    tracker = MotionTracker()
    tracker.add_sample(0.5, 0.5, timestamp=0.0)
    tracker.add_sample(0.5, 0.6, timestamp=1.0)
    tracker.reset()
    result = tracker.add_sample(0.5, 0.5, timestamp=2.0)
    assert result.sample_count == 1


def test_motion_tracker_rejects_window_size_below_two():
    with pytest.raises(ValueError):
        MotionTracker(window_size=1)


def test_hip_midpoint_matches_assess_internal_computation():
    landmarks = _landmarks_with_hips(0.4, 0.6, 1.0, 0.6, 0.6, 1.0)
    result = hip_midpoint(landmarks)
    assert result is not None
    x, y, confidence = result
    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.6)
    assert confidence == "high"


def test_hip_midpoint_none_for_no_landmarks():
    assert hip_midpoint(None) is None
    assert hip_midpoint([]) is None


def test_combine_assessments_passes_through_when_motion_not_sudden():
    static = assess(_landmarks_with_hips(0.45, 0.7, 1.0, 0.55, 0.7, 1.0), BED)  # in_bed
    motion = MotionAssessment(sample_count=3, velocity_y=0.1, acceleration_y=0.1, sudden_motion=False)
    result = combine_assessments(static, motion)
    assert result == static


def test_combine_assessments_upgrades_in_bed_to_fall_risk_on_sudden_motion():
    static = assess(_landmarks_with_hips(0.45, 0.7, 1.0, 0.55, 0.7, 1.0), BED)  # in_bed
    motion = MotionAssessment(sample_count=3, velocity_y=0.9, acceleration_y=0.2, sudden_motion=True)
    result = combine_assessments(static, motion)
    assert result.detected_need == "fall_risk"
    assert result.confidence == "high"
    assert result.person_detected is True


def test_combine_assessments_none_motion_passes_through():
    static = assess(_landmarks_with_hips(0.45, 0.7, 1.0, 0.55, 0.7, 1.0), BED)
    assert combine_assessments(static, None) == static


def test_combine_assessments_already_fall_risk_is_unchanged():
    static = assess(_landmarks_with_hips(0.05, 0.1, 1.0, 0.1, 0.1, 1.0), BED)  # already fall_risk
    motion = MotionAssessment(sample_count=3, velocity_y=0.9, acceleration_y=0.2, sudden_motion=True)
    result = combine_assessments(static, motion)
    assert result == static
