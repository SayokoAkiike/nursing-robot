"""Generate synthetic demo data for PreCareBot's Analytics API (PR12).

Dev/demo tool only. It is never imported or run automatically by
`backend/main.py` or anything else -- it only runs when explicitly invoked:

    python -m backend.scripts.seed_demo_data --days 7 --tasks 30

Safety:
  - Refuses to run if a task is currently active on the default robot (see
    `_check_robot_is_free`), so it never overwrites or interferes with a
    real in-progress task.
  - Every synthetic request is driven through real `workflow_service`
    functions to a genuine terminal state (COMPLETED / IDLE via cancel or
    reset / ERROR) before the next one starts -- the resulting
    care_requests / robot_tasks / kit_verifications / task_state_transitions
    / robot_events rows are exactly what real usage would have produced,
    not hand-crafted fixtures. This also means it inherits
    `workflow_service.create_request`'s own one-task-per-robot concurrency
    guard automatically.
  - After each request is generated with real wall-clock timestamps, its
    timestamps are shifted by a random offset within the requested --days
    window (`repositories.shift_timestamps_for_request`). The shift is
    uniform across every row belonging to that request, so all of its
    internal durations/orderings are preserved exactly as they really
    happened -- only which day it appears to have happened on is
    fabricated.

Scenario mix (chosen at random per task):
  - normal completion
  - patient cancel (from REQUEST_RECEIVED)
  - nurse cancel (from KIT_SELECTED)
  - QR verification failure -- patient_id mismatch
  - QR verification failure -- kit_id mismatch
  - emergency stop
  - "long wait" completion -- a real multi-second pause at
    WAITING_FOR_NURSE_CONFIRMATION before releasing, so
    /analytics/state-durations has a visible outlier instead of every
    sample being near-instant. This is a real sleep, not a fabricated
    timestamp -- see the module docstring above for why only the *day* is
    fabricated, never a duration.
"""
import argparse
import random
import time

from backend.db import repositories
from backend.services import workflow_service

PATIENTS = [
    ("PATIENT_A_ROOM_203", "toileting", "KIT_TOILETING_A"),
    ("PATIENT_B_ROOM_204", "water", "KIT_WATER"),
]

SCENARIOS = [
    "normal",
    "patient_cancel",
    "nurse_cancel",
    "qr_patient_mismatch",
    "qr_kit_mismatch",
    "emergency_stop",
    "long_wait",
]


def _check_robot_is_free() -> None:
    active = repositories.get_active_task_for_robot(workflow_service.DEFAULT_ROBOT_ID)
    if active is not None:
        raise RuntimeError(
            "A task is currently active on the default robot -- refusing to seed "
            "demo data on top of a real in-progress task. Finish, cancel, or reset "
            "it first."
        )


def _run_normal(patient_id: str, request_type: str, kit_id: str) -> str:
    result = workflow_service.create_request(request_type, patient_id=patient_id)
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")
    workflow_service.verify_ids(request_id, patient_id, kit_id)
    workflow_service.advance_state(request_id, "TRAY_LIFTING")
    workflow_service.advance_state(request_id, "WAITING_FOR_NURSE_CONFIRMATION")
    workflow_service.advance_state(request_id, "KIT_RELEASED")
    workflow_service.advance_state(request_id, "COMPLETED")
    return request_id


def _run_long_wait(patient_id: str, request_type: str, kit_id: str, wait_seconds: float) -> str:
    result = workflow_service.create_request(request_type, patient_id=patient_id)
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")
    workflow_service.verify_ids(request_id, patient_id, kit_id)
    workflow_service.advance_state(request_id, "TRAY_LIFTING")
    workflow_service.advance_state(request_id, "WAITING_FOR_NURSE_CONFIRMATION")
    time.sleep(wait_seconds)
    workflow_service.advance_state(request_id, "KIT_RELEASED")
    workflow_service.advance_state(request_id, "COMPLETED")
    return request_id


def _run_patient_cancel(patient_id: str, request_type: str, kit_id: str) -> str:
    result = workflow_service.create_request(request_type, patient_id=patient_id)
    request_id = result["request_id"]
    workflow_service.cancel_request(request_id, actor="patient")
    return request_id


def _run_nurse_cancel(patient_id: str, request_type: str, kit_id: str) -> str:
    result = workflow_service.create_request(request_type, patient_id=patient_id)
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.cancel_request(request_id, actor="nurse")
    return request_id


def _run_qr_patient_mismatch(patient_id: str, request_type: str, kit_id: str) -> str:
    result = workflow_service.create_request(request_type, patient_id=patient_id)
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")
    other_patient = next(p for p, _, _ in PATIENTS if p != patient_id)
    try:
        workflow_service.verify_ids(request_id, other_patient, kit_id)
    except Exception:
        pass
    return request_id


def _run_qr_kit_mismatch(patient_id: str, request_type: str, kit_id: str) -> str:
    result = workflow_service.create_request(request_type, patient_id=patient_id)
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    workflow_service.advance_state(request_id, "VERIFYING_PATIENT")
    wrong_kit = "KIT_WATER" if kit_id != "KIT_WATER" else "KIT_TOILETING_A"
    try:
        workflow_service.verify_ids(request_id, patient_id, wrong_kit)
    except Exception:
        pass
    return request_id


def _run_emergency_stop(patient_id: str, request_type: str, kit_id: str) -> str:
    result = workflow_service.create_request(request_type, patient_id=patient_id)
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.emergency_stop(request_id)
    return request_id


SCENARIO_FUNCS = {
    "normal": _run_normal,
    "patient_cancel": _run_patient_cancel,
    "nurse_cancel": _run_nurse_cancel,
    "qr_patient_mismatch": _run_qr_patient_mismatch,
    "qr_kit_mismatch": _run_qr_kit_mismatch,
    "emergency_stop": _run_emergency_stop,
}


def seed(
    days: int,
    tasks: int,
    long_wait_seconds: float = 3.0,
    seed_value: int | None = None,
) -> list[tuple[str, str]]:
    """Generate `tasks` synthetic requests spread across the last `days`
    days. Returns a list of (request_id, scenario) for whatever called it
    (the CLI just prints these; tests assert on them directly)."""
    if seed_value is not None:
        random.seed(seed_value)

    _check_robot_is_free()

    window_seconds = days * 24 * 60 * 60
    created: list[tuple[str, str]] = []
    for _ in range(tasks):
        patient_id, request_type, kit_id = random.choice(PATIENTS)
        scenario = random.choice(SCENARIOS)

        if scenario == "long_wait":
            request_id = _run_long_wait(patient_id, request_type, kit_id, long_wait_seconds)
        else:
            request_id = SCENARIO_FUNCS[scenario](patient_id, request_type, kit_id)

        delta_seconds = -random.uniform(0, window_seconds)
        repositories.shift_timestamps_for_request(request_id, delta_seconds)
        created.append((request_id, scenario))

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=7, help="Spread generated requests across the last N days (default: 7)")
    parser.add_argument("--tasks", type=int, default=20, help="Number of synthetic requests to generate (default: 20)")
    parser.add_argument(
        "--long-wait-seconds",
        type=float,
        default=3.0,
        help="Real sleep duration for the long_wait scenario, in seconds (default: 3.0)",
    )
    parser.add_argument("--seed", type=int, default=None, help="random.seed() value, for reproducible demo data")
    args = parser.parse_args()

    created = seed(args.days, args.tasks, args.long_wait_seconds, args.seed)
    for i, (request_id, scenario) in enumerate(created, start=1):
        print(f"[{i}/{len(created)}] {scenario:20s} {request_id}")
    print(f"\nSeeded {len(created)} requests across the last {args.days} day(s).")


if __name__ == "__main__":
    main()
