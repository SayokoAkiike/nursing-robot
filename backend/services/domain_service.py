"""Domain registry service (roadmap item 4): Hospital -> Ward -> Room -> Bed,
plus Patient/Nurse/Robot, backed by real tables (backend/db/models.py)
instead of only the static `PATIENTS` dict in backend/core/config.py.

Scope note -- please read before wiring a new call site to this module:
this is a purely additive registry layer. The existing patient_id/robot_id/
room *string* columns on care_requests/robot_tasks/rounding_sessions/
nurse_escalations etc. are deliberately left untouched here -- migrating
every one of those to a real FK against patients/robots/rooms is a separate,
higher-risk change that touches the safety-critical delivery and rounding
flows' tests, and is intentionally out of scope for this change (matching
this codebase's practice of one concern per change -- e.g. PR22 added the
rounding tables purely additively, with PR23 wiring the actual orchestration
on top as its own change).

`backend/services/verification_service.py`'s `allowed_kits` check and
`backend/core/config.PATIENTS` are therefore left as the live source of
truth for the delivery flow's safety gate for now. `seed_default_domain_data()`
below mirrors that same PATIENTS data into the new tables so the two stay
consistent, but a caller that needs the *authoritative, safety-checked*
list should keep reading `backend.core.config.PATIENTS` until a deliberate
follow-up switches that call site over.
"""
from typing import Sequence

from backend.core.config import PATIENTS
from backend.db import repositories

DEFAULT_HOSPITAL_ID = "HOSPITAL_MAIN"
DEFAULT_WARD_ID = "WARD_2"
# Matches workflow_service.DEFAULT_ROBOT_ID / rounding_service.DEFAULT_ROBOT_ID
# (both "ROBOT_1" today) -- not imported directly to avoid a service-to-service
# import for one string constant; kept in sync by convention/tests instead.
DEFAULT_ROBOT_ID = "ROBOT_1"
DEFAULT_NURSE_ID = "NURSE_DEFAULT"


def join_allowed_kits(kit_ids: Sequence[str]) -> str:
    return ",".join(kit_ids)


def split_allowed_kits(value: "str | None") -> list[str]:
    if not value:
        return []
    return [k for k in value.split(",") if k]


def seed_default_domain_data() -> dict:
    """Idempotent: if a hospitals row already exists, does nothing and
    returns the existing counts -- safe to call repeatedly (a re-run of the
    seed script, or a future app-startup hook) without duplicating rows or
    raising on a primary-key collision.

    Seeds exactly the same one hospital / one ward / one room+bed per
    patient / two patients / one nurse / one robot that the rest of the
    codebase already hard-codes (backend.core.config.PATIENTS,
    workflow_service.DEFAULT_ROBOT_ID) -- this mirrors, rather than
    reinvents, the demo's existing "world" so both stay consistent.
    """
    existing_hospitals = repositories.list_hospitals()
    if existing_hospitals:
        return {
            "seeded": False,
            "hospitals": len(existing_hospitals),
            "patients": len(repositories.list_patients()),
        }

    repositories.insert_hospital({"id": DEFAULT_HOSPITAL_ID, "name": "PreCare Hospital"})
    repositories.insert_ward(
        {"id": DEFAULT_WARD_ID, "hospital_id": DEFAULT_HOSPITAL_ID, "name": "Ward 2"}
    )
    repositories.insert_nurse(
        {"id": DEFAULT_NURSE_ID, "name": "Duty Nurse", "ward_id": DEFAULT_WARD_ID}
    )
    repositories.insert_robot(
        {"id": DEFAULT_ROBOT_ID, "name": "Robot 1", "hospital_id": DEFAULT_HOSPITAL_ID}
    )

    for patient_id, info in PATIENTS.items():
        room_number = info.get("room", patient_id)
        room_id = f"ROOM_{room_number}"
        bed_id = f"{room_id}_BED_A"
        if repositories.get_room(room_id) is None:
            repositories.insert_room(
                {"id": room_id, "ward_id": DEFAULT_WARD_ID, "number": room_number}
            )
        repositories.insert_bed({"id": bed_id, "room_id": room_id, "label": "A"})
        repositories.insert_patient(
            {
                "id": patient_id,
                "display_name": info.get("display_name", patient_id),
                "bed_id": bed_id,
                "allowed_kits": join_allowed_kits(info.get("allowed_kits", [])),
            }
        )

    return {"seeded": True, "hospitals": 1, "patients": len(PATIENTS)}


def get_patient_view(patient_id: str) -> "dict | None":
    """One patient plus its resolved bed/room/ward chain and allowed_kits
    as a real list (not the comma-joined storage form) -- the shape a
    GET /patients/{id} response or a future ward-map UI wants, without every
    caller re-deriving the join by hand."""
    patient = repositories.get_patient(patient_id)
    if patient is None:
        return None
    view = dict(patient)
    view["allowed_kits"] = split_allowed_kits(patient["allowed_kits"])
    bed = repositories.get_bed(patient["bed_id"]) if patient["bed_id"] else None
    room = repositories.get_room(bed["room_id"]) if bed else None
    ward = repositories.get_ward(room["ward_id"]) if room else None
    view["room_number"] = room["number"] if room else None
    view["ward_name"] = ward["name"] if ward else None
    return view


def list_patients_view() -> list:
    return [get_patient_view(p["id"]) for p in repositories.list_patients()]


def list_robots_view() -> list:
    """Every seeded robot plus its live IDLE/BUSY status (item 5), derived
    from `robot_tasks` the same way `workflow_service.get_current_state()`
    derives one robot's status -- `repositories.get_active_task_for_robot`
    is the shared DB-layer function both call, so this can't drift from
    what the delivery flow itself considers "busy". Lets a caller (a
    fleet-status view, or `pick_available_robot_id()` below) see every
    robot's status at once instead of only ROBOT_1's."""
    return [
        {**robot, "status": "BUSY" if repositories.get_active_task_for_robot(robot["id"]) else "IDLE"}
        for robot in repositories.list_robots()
    ]


def pick_available_robot_id() -> "str | None":
    """First IDLE robot's id, or None if every seeded robot is BUSY (or
    none are seeded yet). Optional helper for a future caller that wants
    to assign a delivery to *some* free robot rather than a specific one
    -- not wired into `workflow_service.create_request()`'s default,
    which deliberately stays DEFAULT_ROBOT_ID so existing behavior is
    unchanged unless a caller opts in."""
    for robot in list_robots_view():
        if robot["status"] == "IDLE":
            return robot["id"]
    return None


def list_wards_view() -> list:
    """Nested Ward -> Room -> Bed (+ occupying patient_id, if any) tree, for
    a future ward-map view. The naive per-row query loop below is fine at
    this MVP's scale (single-digit rooms/beds); revisit with a real join if
    this ever needs to scale to a real ward's room count."""
    all_patients = repositories.list_patients()
    wards = []
    for ward in repositories.list_wards():
        rooms = []
        for room in repositories.list_rooms(ward_id=ward["id"]):
            beds = []
            for bed in repositories.list_beds(room_id=room["id"]):
                occupant = next((p for p in all_patients if p["bed_id"] == bed["id"]), None)
                beds.append({**bed, "patient_id": occupant["id"] if occupant else None})
            rooms.append({**room, "beds": beds})
        wards.append({**ward, "rooms": rooms})
    return wards
