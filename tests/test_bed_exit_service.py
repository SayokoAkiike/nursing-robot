"""Tests for backend/services/bed_exit_service.py.

Pure-function tests -- no mediapipe import anywhere in this file, same
principle as tests/test_need_classification_service.py not needing any
audio/speech dependency.
"""
from backend.services.bed_exit_service import BedRegion, Landmark, assess, suggested_action_for, summary_for

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
