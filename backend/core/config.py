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

