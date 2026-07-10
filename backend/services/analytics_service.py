"""Aggregate analytics over care_requests / robot_tasks / kit_verifications.

PR10: intentionally simple, in-Python aggregation over the `list_all_*()`
repository functions rather than SQL-level GROUP BY / window functions --
this project's data volume is demo/portfolio scale, not a production
deployment, so keeping the aggregation logic in plain Python keeps it
trivially portable across SQLite/PostgreSQL and easy to unit test without
a real database's SQL dialect quirks. If data volume ever became a real
concern, these would be the functions to rewrite as SQL aggregates first
(see PR11's `state_durations()` below for a case where that tradeoff is
revisited in miniature: still Python, but genuinely closer to a
window-function computation than the other two).
"""
from datetime import datetime

from backend.db import repositories

ERROR_STATE = "ERROR"
COMPLETED_STATUS = "COMPLETED"
CANCELLED_STATUS = "CANCELLED"
NG_RESULT = "NG"


def _parse_iso(value: "datetime | str | None") -> datetime | None:
    """PR15: repositories now return real `datetime` objects (DateTime
    columns), so this is usually just a passthrough. Kept tolerant of a
    plain string too as a defensive fallback -- cheap insurance against any
    caller that hasn't been migrated, at no real cost."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def summary() -> dict:
    """GET /analytics/summary: headline counts across the whole system."""
    requests = repositories.list_all_care_requests()
    tasks = repositories.list_all_robot_tasks()
    verifications = repositories.list_all_kit_verifications()

    total_requests = len(requests)
    completed_requests = sum(1 for r in requests if r["status"] == COMPLETED_STATUS)
    cancelled_requests = sum(1 for r in requests if r["status"] == CANCELLED_STATUS)
    error_tasks = sum(1 for t in tasks if t["state"] == ERROR_STATE)

    verification_attempts = len(verifications)
    verification_failures_count = sum(1 for v in verifications if v["result"] == NG_RESULT)
    verification_failure_rate = (
        verification_failures_count / verification_attempts if verification_attempts else 0.0
    )

    durations = []
    for r in requests:
        if r["status"] != COMPLETED_STATUS:
            continue
        started = _parse_iso(r["created_at"])
        finished = _parse_iso(r["completed_at"])
        if started is None or finished is None:
            continue
        durations.append((finished - started).total_seconds())
    average_completion_seconds = sum(durations) / len(durations) if durations else None

    return {
        "total_requests": total_requests,
        "completed_requests": completed_requests,
        "cancelled_requests": cancelled_requests,
        "error_tasks": error_tasks,
        "verification_attempts": verification_attempts,
        "verification_failure_rate": round(verification_failure_rate, 4),
        "average_completion_seconds": (
            round(average_completion_seconds, 1) if average_completion_seconds is not None else None
        ),
    }


def verification_failures() -> list:
    """GET /analytics/verification-failures: NG counts grouped by message.

    `message` is the free-text reason already written by
    `workflow_service.verify_ids` ("patient_id mismatch" / "kit_id
    mismatch" / whatever `verification_service` returns), so grouping by it
    doubles as grouping by failure type without needing a separate enum.
    """
    verifications = repositories.list_all_kit_verifications()
    counts: dict[str, int] = {}
    for v in verifications:
        if v["result"] != NG_RESULT:
            continue
        key = v["message"] or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return [
        {"failure_type": failure_type, "count": count}
        for failure_type, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ]


def state_durations() -> list:
    """GET /analytics/state-durations: average time spent in each robot_tasks
    state, derived from consecutive `task_state_transitions` rows.

    Each transition row records the *instant* a task moved from
    `from_state` to `to_state`. There's no explicit "exited_at" column, so
    the time spent *in* `to_state` has to be read off the next transition
    row for the same task_id: `next.occurred_at - this.occurred_at`. This
    is a manual version of what a SQL `lead() over (partition by task_id
    order by occurred_at)` window function would give directly -- doing it
    in Python here (rather than adding real window-function SQL) keeps
    this consistent with `summary()` / `verification_failures()` above,
    and this project's data volume doesn't need the SQL version yet.

    Two cases intentionally produce no duration sample for a given row:
      - A task_id with only one transition ever recorded has no "next" row
        to diff against.
      - The *last* transition recorded for any task_id -- its `to_state`
        is either where that task is still sitting right now, or where its
        lifecycle permanently ended (a new request always gets a brand new
        task_id, so a task_id's row is never revisited after its last
        transition). Either way, no exit time exists to compute, so it is
        left out rather than guessed at.

    Only *closed* intervals (a row with a following row for the same
    task_id) are counted. This means in-progress tasks contribute samples
    for every state they've already passed through, just not their current
    (still-open) state.
    """
    transitions = repositories.list_task_state_transitions()

    by_task: dict[str, list[dict]] = {}
    for row in transitions:
        by_task.setdefault(row["task_id"], []).append(row)

    samples_by_state: dict[str, list[float]] = {}
    for rows in by_task.values():
        # Already ordered oldest-first within each task_id, since
        # list_task_state_transitions() orders globally by id (an
        # autoincrement column) and id order is a superset of each task's
        # own chronological order.
        for current_row, next_row in zip(rows, rows[1:]):
            started = _parse_iso(current_row["occurred_at"])
            ended = _parse_iso(next_row["occurred_at"])
            if started is None or ended is None:
                continue
            state = current_row["to_state"]
            samples_by_state.setdefault(state, []).append((ended - started).total_seconds())

    result = [
        {
            "state": state,
            "sample_count": len(values),
            "average_seconds": round(sum(values) / len(values), 3),
            "min_seconds": round(min(values), 3),
            "max_seconds": round(max(values), 3),
        }
        for state, values in samples_by_state.items()
    ]
    result.sort(key=lambda row: str(row["state"]))
    return result


# ---------------------------------------------------------------------------
# PR27: rounding / escalation analytics.
#
# `patients_detected` / `interactions_started` are counted from each
# rounding_sessions row's *current* `status` rather than from a separate
# event log (PR22's schema doesn't add a rounding equivalent of PR8's
# task_state_transitions -- see rounding_service.py's module docstring for
# why). This is safe specifically because reaching PATIENT_DETECTED or
# INTERACTION_STARTED is a strictly sequential prerequisite no matter which
# way a session eventually branches (INFORMATION_ONLY / escalated /
# DELIVERY_REQUIRED all pass through both first) -- so "current status is
# at-or-past milestone X" is equivalent to "this session reached X at some
# point", with no ambiguity. The same is NOT true for "did this session
# escalate", since an escalated session and a plain INFORMATION_ONLY
# session can both end up at the same final COMPLETED status -- so
# escalations_created / urgent_escalations are counted directly from
# nurse_escalations rows instead, never inferred from rounding_sessions.status.
# ---------------------------------------------------------------------------

_REACHED_PATIENT_DETECTED = {
    "PATIENT_DETECTED",
    "APPROACHING_BEDSIDE",
    "INTERACTION_STARTED",
    "NEED_CLASSIFIED",
    "INFORMATION_PROVIDED",
    "ESCALATING_TO_NURSE",
    "WAITING_FOR_NURSE_ACK",
    "NURSE_ACKNOWLEDGED",
    "DELIVERY_REQUIRED",
    "COMPLETED",
}
_REACHED_INTERACTION_STARTED = _REACHED_PATIENT_DETECTED - {
    "PATIENT_DETECTED",
    "APPROACHING_BEDSIDE",
}
URGENT_PRIORITY = "URGENT"


def rounding_summary() -> dict:
    """GET /analytics/rounding-summary: headline counts for the rounding /
    check-in workflow, mirroring summary()'s role for the delivery flow."""
    sessions = repositories.list_all_rounding_sessions()
    interactions = repositories.list_all_patient_interactions()
    escalations = repositories.list_nurse_escalations()

    total_rounding_sessions = len(sessions)
    patients_detected = sum(
        1 for s in sessions if s["status"] in _REACHED_PATIENT_DETECTED
    )
    interactions_started = sum(
        1 for s in sessions if s["status"] in _REACHED_INTERACTION_STARTED
    )
    needs_classified = len(interactions)
    escalations_created = len(escalations)
    urgent_escalations = sum(1 for e in escalations if e["priority"] == URGENT_PRIORITY)

    ack_durations = []
    for e in escalations:
        created = _parse_iso(e["created_at"])
        acked = _parse_iso(e["acknowledged_at"])
        if created is None or acked is None:
            continue
        ack_durations.append((acked - created).total_seconds())
    average_time_to_ack = (
        round(sum(ack_durations) / len(ack_durations), 1) if ack_durations else None
    )

    return {
        "total_rounding_sessions": total_rounding_sessions,
        "patients_detected": patients_detected,
        "interactions_started": interactions_started,
        "needs_classified": needs_classified,
        "escalations_created": escalations_created,
        "urgent_escalations": urgent_escalations,
        "average_time_to_ack": average_time_to_ack,
    }


def escalation_breakdown() -> dict:
    """GET /analytics/escalation-breakdown: nurse_escalations grouped by
    priority, detected_need, and status.

    `detected_need` isn't a nurse_escalations column -- it's read off each
    escalation's parent rounding_sessions row (joined via
    rounding_session_id) rather than the escalation's own free-text
    `reason` field, since `reason` is caller-supplied and optional (see
    rounding_service.escalate()'s docstring) while
    rounding_sessions.detected_need is always set by classify_need()
    before an escalation can even be raised.
    """
    escalations = repositories.list_nurse_escalations()

    by_priority: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_need: dict[str, int] = {}

    session_cache: dict[str, dict | None] = {}

    def _session_for(session_id: str) -> dict | None:
        if session_id not in session_cache:
            session_cache[session_id] = repositories.get_rounding_session(session_id)
        return session_cache[session_id]

    for e in escalations:
        priority = e["priority"] or "UNKNOWN"
        by_priority[priority] = by_priority.get(priority, 0) + 1

        status = e["status"] or "UNKNOWN"
        by_status[status] = by_status.get(status, 0) + 1

        rounding_session = _session_for(e["rounding_session_id"])
        need = (rounding_session or {}).get("detected_need") or "unknown"
        by_need[need] = by_need.get(need, 0) + 1

    def _to_rows(counts: dict[str, int], key_name: str) -> list:
        return [
            {key_name: key, "count": count}
            for key, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        ]

    return {
        "by_priority": _to_rows(by_priority, "priority"),
        "by_detected_need": _to_rows(by_need, "detected_need"),
        "by_status": _to_rows(by_status, "status"),
    }
