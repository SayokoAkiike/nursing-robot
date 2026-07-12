"""Demo-only synthetic data seeder for the Analytics/anomaly-detection
demo page (demo/pages/4_📊_Analytics.py).

Unlike backend/scripts/seed_demo_data.py (delivery-workflow data,
care_requests/robot_tasks), this seeds *rounding* data -- specifically
enough distinct patients with varied escalation patterns for
backend/services/escalation_anomaly_service.py's MIN_PATIENTS_FOR_ANALYSIS
(5) threshold to actually be crossed, since the public demo otherwise
only ever has the two real patients from robot_control/config.py's
PATIENTS dict.

Every row is produced by driving the real API (POST /rounding/*,
POST /escalations/{id}/ack for some), the same "no hand-crafted
fixtures" principle backend/scripts/seed_demo_data.py documents for its
own domain -- not because this file reuses that script directly (its
scenario data models a different workflow), but because the same
reasoning applies here: what escalation_anomaly_service.py sees should
be indistinguishable from what real rounding sessions would have
produced.

detect_patient()/start_rounding() accept any patient_id/room string --
verified directly in backend/services/rounding_service.py, no FK
constraint or PATIENTS-dict validation exists at that layer -- so these
synthetic patient IDs never need to (and deliberately don't) collide
with the two real demo patients the tablet/nurse pages use.
"""
from __future__ import annotations

import random

import requests

from ui.common.backend_bootstrap import DEMO_BACKEND_URL

NURSE_TOKEN = "precare-dev-token-2026"

# A handful of patients with an unremarkable, roughly-similar escalation
# pattern, plus one deliberate outlier (many more, higher-priority
# escalations) so the anomaly detector has a genuine signal to find --
# without this, "5+ patients with near-identical synthetic behavior"
# would make IsolationForest's flags close to arbitrary.
_NORMAL_PATIENT_PHRASES = [
    "お水が飲みたいです",
    "少し不安で眠れないんです",
    "向きを変えたいです",
    "寒いです",
]
_OUTLIER_PATIENT_PHRASES = [
    "胸が痛いです、苦しいです",
    "ふらふらして、一人で立ち上がってしまいました",
    "トイレに行きたいです",
    "胸が痛いです、苦しいです",
    "ふらふらして、一人で立ち上がってしまいました",
]


def _run_one_rounding(room: str, patient_id: str, phrase: str, auto_ack: bool) -> None:
    started = requests.post(f"{DEMO_BACKEND_URL}/rounding/start", json={"room": room}, timeout=5).json()
    session_id = started["rounding_session_id"]
    requests.post(
        f"{DEMO_BACKEND_URL}/rounding/{session_id}/detect-patient",
        json={"patient_id": patient_id},
        timeout=5,
    )
    requests.post(f"{DEMO_BACKEND_URL}/rounding/{session_id}/start-interaction", timeout=5)
    classification = requests.post(
        f"{DEMO_BACKEND_URL}/rounding/{session_id}/classify-need",
        json={"patient_response": phrase, "input_mode": "simulated"},
        timeout=5,
    ).json()

    route = classification["route"]
    if route == "INFORMATION_ONLY":
        requests.post(f"{DEMO_BACKEND_URL}/rounding/{session_id}/provide-information", timeout=5)
        return

    if route in ("NURSE_NOTIFICATION", "URGENT_ESCALATION"):
        esc = requests.post(
            f"{DEMO_BACKEND_URL}/rounding/{session_id}/escalate",
            json={
                "summary": classification["summary"],
                "priority": classification["escalation_level"],
                "suggested_action": classification["suggested_action"],
                "reason": classification["detected_need"],
                "route": route,
            },
            headers={"x-nurse-token": NURSE_TOKEN},
            timeout=5,
        ).json()
        if auto_ack:
            requests.post(
                f"{DEMO_BACKEND_URL}/escalations/{esc['id']}/ack",
                json={"acknowledged_by": "demo_seed"},
                headers={"x-nurse-token": NURSE_TOKEN},
                timeout=5,
            )


def seed_anomaly_demo_data() -> dict:
    """Creates ~7 synthetic patients' worth of rounding/escalation
    history (one deliberate outlier) via the real API. Idempotent-ish in
    spirit (each call adds a *new* batch of sessions with fresh random
    patient-id suffixes) rather than strictly idempotent -- re-clicking
    the demo button multiple times just gives the anomaly detector more
    data to work with, which is a fine outcome for a demo, unlike
    backend/scripts/seed_demo_data.py's real-robot safety check (there is
    no real robot state here to protect)."""
    rng = random.Random()
    batch_id = rng.randint(1000, 9999)
    created_patients = []

    for i in range(6):
        patient_id = f"DEMO_PATIENT_{batch_id}_{i}"
        room = str(210 + i)
        phrases = rng.sample(_NORMAL_PATIENT_PHRASES, k=2)
        for phrase in phrases:
            _run_one_rounding(room, patient_id, phrase, auto_ack=(i % 2 == 0))
        created_patients.append(patient_id)

    outlier_id = f"DEMO_PATIENT_{batch_id}_OUTLIER"
    for phrase in _OUTLIER_PATIENT_PHRASES:
        _run_one_rounding("299", outlier_id, phrase, auto_ack=False)
    created_patients.append(outlier_id)

    return {"created_patients": created_patients, "outlier_patient_id": outlier_id}
