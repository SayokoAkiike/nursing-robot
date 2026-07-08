"""Aggregate analytics over care_requests / robot_tasks / kit_verifications.

PR10: intentionally simple, in-Python aggregation over the `list_all_*()`
repository functions rather than SQL-level GROUP BY / window functions --
this project's data volume is demo/portfolio scale, not a production
deployment, so keeping the aggregation logic in plain Python keeps it
trivially portable across SQLite/PostgreSQL and easy to unit test without
a real database's SQL dialect quirks. If data volume ever became a real
concern, these would be the functions to rewrite as SQL aggregates first
(see PR11's /analytics/state-durations for a case where that tradeoff is
revisited).
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
