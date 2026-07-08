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


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
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
