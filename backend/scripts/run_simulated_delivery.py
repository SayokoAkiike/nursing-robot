"""Drive a full PreCareBot delivery through a headless PyBullet simulation
end to end, against a real running backend (Phase 4, PR19).

Dev/demo tool only, like backend/scripts/seed_demo_data.py -- never
imported or run automatically. Reuses the exact same public HTTP API
surface a real robot (or the perception CLI, or the nurse dashboard)
would use:
  - perception.verification_client.VerificationClient for request
    creation / state transitions
  - perception.run_perception.run() (unmodified, PR4/PR18) for the
    QR-verification step, driven by PyBullet-rendered frames
    ("pybullet:delivery_with_qr", PR17/PR18)

Because every call here goes through the real API with a real nurse
token, none of PreCareBot's safety constraints are bypassed: QR
verification still has to actually succeed (via the real
perception/qr_detector.py pipeline reading the simulated camera frames),
and KIT_RELEASED still requires the task to be sitting in
WAITING_FOR_NURSE_CONFIRMATION first (backend/services/workflow_service.py
enforces this regardless of caller).

By default this script *stops* at WAITING_FOR_NURSE_CONFIRMATION and
waits for a human to confirm via the real nurse dashboard (or a manual
curl) -- it does not press that button itself. Pass --auto-confirm only
if you explicitly want the script to do that for you; the flag itself is
your conscious confirmation, not a way to silently bypass the gate (it
still needs a valid nurse token to succeed, same as the dashboard does).

Example:
    python -m backend.scripts.run_simulated_delivery --nurse-token $NURSE_TOKEN
    python -m backend.scripts.run_simulated_delivery --nurse-token $NURSE_TOKEN --auto-confirm
"""
from __future__ import annotations

import argparse
import os
import time

from perception.run_perception import run as run_perception
from perception.verification_client import VerificationClient, VerificationClientError

DEFAULT_PATIENT_ID = "PATIENT_A_ROOM_203"
DEFAULT_REQUEST_TYPE = "toileting"
DEFAULT_SOURCE_SPEC = "pybullet:delivery_with_qr"


def _step(label: str) -> None:
    print(f"\n=== {label} ===")


def run_delivery(
    client: VerificationClient,
    request_type: str = DEFAULT_REQUEST_TYPE,
    patient_id: str = DEFAULT_PATIENT_ID,
    source_spec: str = DEFAULT_SOURCE_SPEC,
    step_delay: float = 1.0,
    auto_confirm: bool = False,
    confirm_poll_seconds: float = 2.0,
    confirm_timeout_seconds: float = 120.0,
) -> dict:
    """Runs one simulated delivery through the real API; returns the final
    /requests/{id} view. Raises TimeoutError if nurse confirmation never
    arrives (auto_confirm=False) within confirm_timeout_seconds."""
    _step("Creating patient request")
    created = client.create_request(request_type, patient_id=patient_id)
    request_id = created["request_id"]
    print(f"request_id={request_id} patient_id={patient_id} request_type={request_type}")

    _step("KIT_SELECTED")
    client.transition(request_id, "KIT_SELECTED")
    time.sleep(step_delay)

    _step("MOVING_TO_BEDSIDE (robot begins PyBullet navigation)")
    client.transition(request_id, "MOVING_TO_BEDSIDE")

    _step("VERIFYING_PATIENT (PyBullet camera feed -> QR detection -> verify)")
    client.transition(request_id, "VERIFYING_PATIENT")
    outcome = run_perception(
        request_id=request_id,
        source_spec=source_spec,
        client=client,
    )
    print(f"QR confirmed: patient_id={outcome['patient_id']} kit_id={outcome['kit_id']}")
    print(f"verification: ok={outcome['verification']['ok']}, state={outcome['verification']['state']['robot_state']}")

    _step("DOCKING (reached automatically on successful verification)")
    time.sleep(step_delay)

    _step("TRAY_LIFTING")
    client.transition(request_id, "TRAY_LIFTING")
    time.sleep(step_delay)

    _step("WAITING_FOR_NURSE_CONFIRMATION")
    client.transition(request_id, "WAITING_FOR_NURSE_CONFIRMATION")

    if auto_confirm:
        print(
            "\n--auto-confirm was passed: this script will press the confirm "
            "button itself using the nurse token it was given. In a real "
            "deployment, only a human nurse would do this."
        )
        time.sleep(step_delay)
        client.transition(request_id, "KIT_RELEASED")
    else:
        print(
            f"\nWaiting for nurse confirmation on request {request_id}.\n"
            "Open the nurse dashboard and confirm this request, or run:\n"
            f'  curl -X POST $BASE_URL/tasks/{request_id}/transition '
            '-H "x-nurse-token: $NURSE_TOKEN" -H "Content-Type: application/json" '
            '-d \'{"next_state": "KIT_RELEASED"}\'\n'
        )
        waited = 0.0
        while waited < confirm_timeout_seconds:
            state = client.get_request(request_id)
            if state["robot_state"] != "WAITING_FOR_NURSE_CONFIRMATION":
                break
            time.sleep(confirm_poll_seconds)
            waited += confirm_poll_seconds
        else:
            raise TimeoutError(
                f"No nurse confirmation received within {confirm_timeout_seconds}s "
                f"for request {request_id}. Task is left at WAITING_FOR_NURSE_CONFIRMATION "
                "-- confirm it manually whenever you're ready."
            )

    _step("COMPLETED")
    client.transition(request_id, "COMPLETED")
    final_state = client.get_request(request_id)
    print(f"\nDelivery complete. Final state: {final_state['robot_state']}")
    return final_state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.getenv("PRECARE_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--nurse-token", default=os.getenv("NURSE_TOKEN", ""))
    parser.add_argument("--request-type", default=DEFAULT_REQUEST_TYPE)
    parser.add_argument("--patient-id", default=DEFAULT_PATIENT_ID)
    parser.add_argument("--source", default=DEFAULT_SOURCE_SPEC, help='e.g. "pybullet:delivery_with_qr"')
    parser.add_argument("--step-delay", type=float, default=1.0, help="Seconds to pause between transitions")
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Press the nurse-confirmation button (KIT_RELEASED) automatically instead of waiting for a human.",
    )
    args = parser.parse_args()

    if not args.nurse_token:
        raise SystemExit("NURSE_TOKEN is required (set --nurse-token or the NURSE_TOKEN env var).")

    client = VerificationClient(base_url=args.base_url, nurse_token=args.nurse_token)
    try:
        run_delivery(
            client,
            request_type=args.request_type,
            patient_id=args.patient_id,
            source_spec=args.source,
            step_delay=args.step_delay,
            auto_confirm=args.auto_confirm,
        )
    except (VerificationClientError, TimeoutError, RuntimeError) as exc:
        raise SystemExit(f"run_simulated_delivery failed: {exc}") from exc
    finally:
        client.close()


if __name__ == "__main__":
    main()
