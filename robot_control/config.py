# PreCare Dock — 設定の一元管理

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
    "KIT_TOILETING_A":  "Toileting preparation kit",
    "KIT_WATER":        "Water kit",
    "ALERT_NURSE_ONLY": "Nurse check only",
}

# デフォルト患者（デモ用）
DEFAULT_PATIENT_ID = "PATIENT_A_ROOM_203"
