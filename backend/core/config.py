"""Application settings and domain constants.

Settings are resolved lazily (not at import time) so importing this module
never raises just because an env var is missing -- previously
`backend/auth.py` raised RuntimeError at import time if NURSE_TOKEN was
unset, which forced tests/conftest.py to set the env var before importing
anything from `backend`. That workaround is no longer needed.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.nurse_token: str = os.getenv("NURSE_TOKEN", "")
        # PR35 follow-up: separate from NURSE_TOKEN -- a robot/sensor is
        # a different actor than a nurse, and POST /escalations/vision-report
        # is unlike /rounding/* (which is unauthenticated but gated by a
        # valid session's state machine transitions -- you cannot just
        # spam an escalation without first legitimately progressing a
        # session through detect-patient/start-interaction/classify-need).
        # vision-report has no such state gating: it is a stateless,
        # one-shot POST that creates a real URGENT nurse_escalations row
        # directly. Left unauthenticated, anyone who can reach this API
        # could flood the nurse dashboard with fabricated fall-risk
        # alerts -- exactly the "alert fatigue" failure mode a real
        # deployment of a safety system cannot afford. See
        # backend/api/routes_analytics.py's escalation-anomalies for an
        # unrelated example of the same "don't let noise erode trust in
        # real signals" principle applied elsewhere in this codebase.
        self.robot_token: str = os.getenv("ROBOT_TOKEN", "")
        self.allowed_origins: list[str] = os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:8502"
        ).split(",")
        # Reserved for PR2 (PostgreSQL migration). Not used yet.
        self.database_url: str = os.getenv("DATABASE_URL", "")

    def require_nurse_token(self) -> str:
        if not self.nurse_token:
            raise RuntimeError(
                "NURSE_TOKEN is not set. Please define it in your .env file."
            )
        return self.nurse_token

    def require_robot_token(self) -> str:
        if not self.robot_token:
            raise RuntimeError(
                "ROBOT_TOKEN is not set. Please define it in your .env file."
            )
        return self.robot_token


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ---- Domain constants (moved from robot_control/config.py) ----------------

PATIENTS = {
    "PATIENT_A_ROOM_203": {
        "display_name": "Patient A",
        "room": "203",
        "allowed_kits": ["KIT_TOILETING_A", "KIT_WATER", "ALERT_NURSE_ONLY"],
    },
    "PATIENT_B_ROOM_204": {
        "display_name": "Patient B",
        "room": "204",
        "allowed_kits": ["KIT_WATER", "ALERT_NURSE_ONLY"],
    },
}

REQUEST_TYPES = {
    "toileting": {
        "label": "Toileting preparation",
        "kit": "KIT_TOILETING_A",
        "risk": "転倒リスクあり",
    },
    "water": {
        "label": "Water request",
        "kit": "KIT_WATER",
        "risk": "なし",
    },
    "nurse_check": {
        "label": "Nurse check",
        "kit": "ALERT_NURSE_ONLY",
        "risk": "要確認",
    },
}

KIT_NAMES = {
    "KIT_TOILETING_A": "Toileting preparation kit",
    "KIT_WATER": "Water kit",
    "ALERT_NURSE_ONLY": "Nurse check only",
}

DEFAULT_PATIENT_ID = "PATIENT_A_ROOM_203"

# How long a PENDING nurse_escalations row may sit unacknowledged before
# escalation_service.check_and_escalate_overdue() bumps its priority one
# step (see ESCALATION_PRIORITY_ESCALATION_PATH below). Values are seconds;
# short enough to demo without a real wait, long enough that a nurse
# glancing at the dashboard every few refreshes isn't fighting the clock.
# Tune freely -- nothing else in the codebase assumes these exact numbers.
ESCALATION_TIMEOUT_SECONDS = {
    "URGENT": 120,
    "HIGH": 300,
    "MEDIUM": 600,
    "LOW": 1800,
}

# The one-step-up path a priority takes when it times out. URGENT maps to
# itself -- there is nowhere higher to go, so
# check_and_escalate_overdue() treats "next == current" as "already at the
# top" and leaves it alone rather than looping.
ESCALATION_PRIORITY_ESCALATION_PATH = {
    "LOW": "MEDIUM",
    "MEDIUM": "HIGH",
    "HIGH": "URGENT",
    "URGENT": "URGENT",
}

