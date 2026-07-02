import backend.storage as storage


def test_json_decode_error_returns_idle(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("NOT JSON", encoding="utf-8")
    orig = storage.STATE_FILE
    storage.STATE_FILE = broken
    result = storage.load_state()
    storage.STATE_FILE = orig
    assert result == {"request": None, "robot_state": "IDLE"}
