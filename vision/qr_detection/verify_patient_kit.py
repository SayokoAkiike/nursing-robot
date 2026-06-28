"""
患者ID・キットID照合スクリプト (Day 9)
実行方法: python vision/qr_detection/verify_patient_kit.py
"""

# ── 正しい患者ID → キットIDの対応表 ─────────────────
VALID_COMBINATIONS = {
    "PATIENT_A_ROOM_203": ["KIT_TOILETING_A", "KIT_WATER"],
    "PATIENT_B_ROOM_204": ["KIT_WATER", "KIT_IV_ALERT"],
}

# キットIDの日本語名
KIT_NAMES = {
    "KIT_TOILETING_A": "トイレ介助キット",
    "KIT_WATER":       "給水キット",
    "KIT_IV_ALERT":    "点滴確認キット",
}


def verify(patient_id: str, kit_id: str) -> dict:
    """
    患者IDとキットIDを照合する。

    Returns:
        {
            "ok": True/False,
            "patient_id": str,
            "kit_id": str,
            "kit_name": str,
            "message": str,
        }
    """
    kit_name = KIT_NAMES.get(kit_id, kit_id)

    if patient_id not in VALID_COMBINATIONS:
        return {
            "ok": False,
            "patient_id": patient_id,
            "kit_id": kit_id,
            "kit_name": kit_name,
            "message": f"❌ 患者ID '{patient_id}' が登録されていません",
        }

    allowed_kits = VALID_COMBINATIONS[patient_id]
    if kit_id in allowed_kits:
        return {
            "ok": True,
            "patient_id": patient_id,
            "kit_id": kit_id,
            "kit_name": kit_name,
            "message": f"✅ 照合OK：{kit_name} を {patient_id} に配送します",
        }
    else:
        return {
            "ok": False,
            "patient_id": patient_id,
            "kit_id": kit_id,
            "kit_name": kit_name,
            "message": f"❌ 照合NG：{kit_name} は {patient_id} に対応していません",
        }


def print_result(result: dict):
    print(f"  患者ID : {result['patient_id']}")
    print(f"  キットID: {result['kit_id']} ({result['kit_name']})")
    print(f"  結果   : {result['message']}")
    print()


if __name__ == "__main__":
    print("=== 患者ID・キットID 照合テスト ===\n")

    test_cases = [
        ("PATIENT_A_ROOM_203", "KIT_TOILETING_A"),   # ✅ OK
        ("PATIENT_A_ROOM_203", "KIT_IV_ALERT"),       # ❌ NG（対応外）
        ("PATIENT_B_ROOM_204", "KIT_WATER"),           # ✅ OK
        ("PATIENT_B_ROOM_204", "KIT_TOILETING_A"),     # ❌ NG（対応外）
        ("PATIENT_UNKNOWN",    "KIT_WATER"),           # ❌ NG（患者不明）
    ]

    for patient_id, kit_id in test_cases:
        result = verify(patient_id, kit_id)
        print_result(result)
