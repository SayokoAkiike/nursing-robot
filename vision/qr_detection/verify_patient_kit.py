from robot_control.config import PATIENTS, KIT_NAMES

def verify(patient_id: str, kit_id: str) -> dict:
    kit_name = KIT_NAMES.get(kit_id, kit_id)
    if patient_id not in PATIENTS:
        return {"ok": False, "patient_id": patient_id, "kit_id": kit_id,
                "kit_name": kit_name, "message": f"患者ID '{patient_id}' が登録されていません"}
    allowed = PATIENTS[patient_id]["allowed_kits"]
    if kit_id in allowed:
        return {"ok": True, "patient_id": patient_id, "kit_id": kit_id,
                "kit_name": kit_name, "message": f"照合OK：{kit_name} を {patient_id} に配送します"}
    return {"ok": False, "patient_id": patient_id, "kit_id": kit_id,
            "kit_name": kit_name, "message": f"照合NG：{kit_name} は {patient_id} に対応していません"}
