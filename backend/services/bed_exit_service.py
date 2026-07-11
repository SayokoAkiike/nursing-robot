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
from collections import deque

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


def hip_midpoint(
    landmarks: "list[Landmark] | None", min_visibility: float = DEFAULT_MIN_VISIBILITY
) -> "tuple[float, float, str] | None":
    """Extracts the (x, y, confidence) hip midpoint `assess()` uses
    internally -- exposed separately so `MotionTracker` (below) and
    `assess()` share exactly one definition of "where is the hip",
    rather than the temporal and static checks silently drifting apart
    over two copies of this averaging logic. Returns None under the same
    conditions `assess()` treats as "no usable hip position" (no/too-few
    landmarks, or both hips below `min_visibility`)."""
    if not landmarks or len(landmarks) <= RIGHT_HIP:
        return None
    left_hip, right_hip = landmarks[LEFT_HIP], landmarks[RIGHT_HIP]
    visible_hips = [p for p in (left_hip, right_hip) if p.visibility >= min_visibility]
    if not visible_hips:
        return None
    hip_x = sum(p.x for p in visible_hips) / len(visible_hips)
    hip_y = sum(p.y for p in visible_hips) / len(visible_hips)
    confidence = "high" if len(visible_hips) == 2 else "low"
    return hip_x, hip_y, confidence


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
    hip = hip_midpoint(landmarks, min_visibility)
    if landmarks is None or len(landmarks) <= RIGHT_HIP:
        return BedExitAssessment(
            person_detected=False, in_bed=False, confidence="low", detected_need="unknown"
        )
    if hip is None:
        return BedExitAssessment(
            person_detected=True, in_bed=False, confidence="low", detected_need="unknown"
        )

    hip_x, hip_y, confidence = hip
    in_bed = bed_region.contains(hip_x, hip_y)

    return BedExitAssessment(
        person_detected=True,
        in_bed=in_bed,
        confidence=confidence,
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


# ---------------------------------------------------------------------------
# PR33 (C): temporal fall detection -- velocity/acceleration of the hip
# position across frames, as a *second*, independent signal alongside
# assess()'s static "is the hip inside the bed region right now" check.
#
# Why this is needed in addition to the static check: a genuine fall is
# fast. The hip can pass through (or even briefly re-enter) the bed
# region's box mid-fall, or the whole event can happen between two of
# run_pose_demo.py's sampled frames such that no single frame's static
# position ever looks unambiguously "outside the bed" -- but the *speed*
# of the downward motion is itself a hallmark a purely positional check
# can't see. A patient calmly sitting up and walking to the bathroom
# produces smooth, bounded velocity; a fall produces a spike.
#
# Deliberately a separate class from BedRegion/assess() above rather than
# folding velocity into a single mega-function -- MotionTracker owns
# per-session state (a short position history) that assess() has no
# business holding, since assess() is a pure, stateless function of one
# frame by design (see its own docstring).
# ---------------------------------------------------------------------------

DEFAULT_MOTION_WINDOW = 5
DEFAULT_VELOCITY_THRESHOLD = 0.6  # normalized units / second, downward-positive
DEFAULT_ACCELERATION_THRESHOLD = 1.5  # normalized units / second^2

# Both thresholds are a starting point, not a calibrated clinical value --
# "normalized units" means fractions of the camera frame's height, so the
# right threshold genuinely depends on camera distance/angle and frame
# rate in a real installation. Expose them as constructor args (below)
# specifically so a real deployment can tune against its own footage
# rather than trusting these defaults blindly.


@dataclass(frozen=True)
class MotionSample:
    x: float
    y: float
    timestamp: float


@dataclass(frozen=True)
class MotionAssessment:
    sample_count: int
    velocity_y: float
    acceleration_y: float
    sudden_motion: bool


class MotionTracker:
    """Keeps a short rolling window of hip positions (via `add_sample()`,
    one call per processed frame) and derives vertical velocity/
    acceleration from it. One instance is meant to track one person/
    session for the duration of a `run_pose_demo.py` run -- construct a
    fresh one per monitoring session, not shared across patients/rooms.
    """

    def __init__(
        self,
        window_size: int = DEFAULT_MOTION_WINDOW,
        velocity_threshold: float = DEFAULT_VELOCITY_THRESHOLD,
        acceleration_threshold: float = DEFAULT_ACCELERATION_THRESHOLD,
    ):
        if window_size < 2:
            raise ValueError("window_size must be >= 2 to compute a velocity at all")
        self.window_size = window_size
        self.velocity_threshold = velocity_threshold
        self.acceleration_threshold = acceleration_threshold
        self._history: "deque[MotionSample]" = deque(maxlen=window_size)

    def reset(self) -> None:
        """Clears the position history -- call this whenever tracking
        should restart from scratch (e.g. the person left the frame
        entirely and a different/unrelated re-entry shouldn't be treated
        as a continuous motion trace with whatever was tracked before)."""
        self._history.clear()

    def add_sample(self, x: float, y: float, timestamp: float) -> MotionAssessment:
        """`timestamp`: seconds, monotonically increasing across calls
        (e.g. `time.monotonic()`) -- not required to be evenly spaced,
        since velocity is computed from actual elapsed time between
        samples rather than assuming a fixed frame rate."""
        self._history.append(MotionSample(x, y, timestamp))
        return self._compute()

    def _compute(self) -> MotionAssessment:
        samples = list(self._history)
        n = len(samples)
        if n < 2:
            return MotionAssessment(sample_count=n, velocity_y=0.0, acceleration_y=0.0, sudden_motion=False)

        velocities = []
        for prev, curr in zip(samples, samples[1:]):
            dt = curr.timestamp - prev.timestamp
            if dt <= 0:
                continue  # out-of-order/duplicate timestamp -- skip rather than divide by zero
            velocities.append((curr.y - prev.y) / dt)

        if not velocities:
            return MotionAssessment(sample_count=n, velocity_y=0.0, acceleration_y=0.0, sudden_motion=False)

        latest_velocity = velocities[-1]
        acceleration = 0.0
        if len(velocities) >= 2:
            dt_total = samples[-1].timestamp - samples[0].timestamp
            if dt_total > 0:
                acceleration = (velocities[-1] - velocities[0]) / dt_total

        sudden = (
            latest_velocity >= self.velocity_threshold
            or acceleration >= self.acceleration_threshold
        )
        return MotionAssessment(
            sample_count=n,
            velocity_y=latest_velocity,
            acceleration_y=acceleration,
            sudden_motion=sudden,
        )


def combine_assessments(
    static: BedExitAssessment, motion: "MotionAssessment | None"
) -> BedExitAssessment:
    """Upgrades a static `assess()` result to fall_risk if
    `MotionTracker` independently flagged sudden downward motion --
    catches a fall fast enough that no single frame's *position* alone
    looks unambiguously outside the bed region (see this section's
    module-level comment above for why that gap exists). Never
    downgrades: if the static check already says fall_risk, or motion is
    None/not sudden, the static result passes through unchanged."""
    if motion is None or not motion.sudden_motion:
        return static
    if static.detected_need == "fall_risk":
        return static
    return BedExitAssessment(
        person_detected=static.person_detected,
        in_bed=False,
        confidence="high",
        detected_need="fall_risk",
    )
