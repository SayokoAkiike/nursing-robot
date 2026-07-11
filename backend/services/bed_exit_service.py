"""Pure logic for turning pose landmarks into a bed-exit / fall-risk
assessment (PR30).

Lives in `backend/services/`, not `perception/`, and has no mediapipe
import -- exactly the same "pure function, independent of the ML
wrapper" split `need_classification_service.py` established for the
rounding conversation (`classify()` takes plain text, not an audio
object; this module's `assess()` takes plain `Landmark` tuples, not a
mediapipe result object). `perception/pose_detector.py` is what actually
runs MediaPipe Pose and converts its output into the `Landmark` shape
this module consumes -- keeping `backend/services/*` perception-agnostic
(see `escalation_service.raise_direct_escalation()`'s docstring for why
that boundary matters).

Reuses `need_classification_service`'s existing "fall_risk" category
(keyword-detected from speech) rather than inventing a second, slightly
different label -- a patient out of bed unsupervised is the same
underlying risk whether the rounding robot heard "ふらふらして、一人で立ち
上がってしまいました" or a camera saw it directly.
"""
from dataclasses import dataclass

from backend.services import need_classification_service

# Standard BlazePose 33-point landmark indices (stable across MediaPipe
# Pose Landmarker's model variants -- see
# https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker).
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_HIP = 23
RIGHT_HIP = 24

DEFAULT_MIN_VISIBILITY = 0.5


@dataclass(frozen=True)
class Landmark:
    """One normalized (0.0-1.0, image-relative) pose landmark point."""

    x: float
    y: float
    visibility: float = 1.0


@dataclass(frozen=True)
class BedRegion:
    """A rectangle in the same normalized 0.0-1.0 coordinates pose
    landmarks use, marking where the bed occupies the camera's frame.
    Configured once per camera placement (e.g. via a CLI flag on
    `backend/scripts/run_pose_demo.py`) -- this module never infers bed
    location on its own."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def contains(self, x: float, y: float) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


@dataclass(frozen=True)
class BedExitAssessment:
    person_detected: bool
    in_bed: bool
    confidence: str  # "high" | "low"
    detected_need: str  # "fall_risk" | "in_bed" | "unknown"


def assess(
    landmarks: "list[Landmark] | None",
    bed_region: BedRegion,
    min_visibility: float = DEFAULT_MIN_VISIBILITY,
) -> BedExitAssessment:
    """`landmarks`: the 33 BlazePose landmarks for one detected person
    (indexable 0-32), or None/too-short if no person was detected in the
    frame at all. Never raises -- an empty or low-confidence frame just
    yields a low-confidence "unknown" assessment, matching
    `need_classification_service.classify()`'s own never-raises
    contract: a monitoring loop shouldn't crash just because one frame
    had nobody clearly visible in it."""
    if not landmarks or len(landmarks) <= RIGHT_HIP:
        return BedExitAssessment(
            person_detected=False, in_bed=False, confidence="low", detected_need="unknown"
        )

    left_hip, right_hip = landmarks[LEFT_HIP], landmarks[RIGHT_HIP]
    visible_hips = [p for p in (left_hip, right_hip) if p.visibility >= min_visibility]
    if not visible_hips:
        return BedExitAssessment(
            person_detected=True, in_bed=False, confidence="low", detected_need="unknown"
        )

    hip_x = sum(p.x for p in visible_hips) / len(visible_hips)
    hip_y = sum(p.y for p in visible_hips) / len(visible_hips)
    in_bed = bed_region.contains(hip_x, hip_y)

    return BedExitAssessment(
        person_detected=True,
        in_bed=in_bed,
        confidence="high" if len(visible_hips) == 2 else "low",
        detected_need="in_bed" if in_bed else "fall_risk",
    )


def summary_for(assessment: BedExitAssessment, room: str, patient_id: str) -> str:
    """Empty string for anything that isn't an actual fall_risk finding
    -- callers (run_pose_demo.py) only raise an escalation when this is
    non-empty, same "only escalate on a real finding" shape
    rounding_service.classify_need()'s route already has."""
    if assessment.detected_need != "fall_risk":
        return ""
    need_label = need_classification_service.need_label("fall_risk")
    return f"{room}号室 {patient_id} が離床（{need_label}）を検知されました。"


def suggested_action_for(assessment: BedExitAssessment) -> str:
    return need_classification_service.suggested_action("fall_risk")
