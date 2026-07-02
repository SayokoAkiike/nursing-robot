from vision.qr_detection.verify_patient_kit import verify


def test_verify_ok_toileting():
    assert verify("PATIENT_A_ROOM_203", "KIT_TOILETING_A")["ok"] is True

def test_verify_ok_water():
    assert verify("PATIENT_B_ROOM_204", "KIT_WATER")["ok"] is True

def test_verify_ok_nurse_check():
    assert verify("PATIENT_A_ROOM_203", "ALERT_NURSE_ONLY")["ok"] is True

def test_verify_ng_wrong_kit():
    assert verify("PATIENT_A_ROOM_203", "KIT_UNKNOWN")["ok"] is False

def test_verify_ng_unknown_patient():
    assert verify("PATIENT_UNKNOWN", "KIT_WATER")["ok"] is False
