import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "shared_state.json"
LOG_FILE   = DATA_DIR / "robot_log.json"

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # ファイル破損時はIDLEにフォールバック
            return {"request": None, "robot_state": "IDLE"}
    return {"request": None, "robot_state": "IDLE"}

def save_state(state: dict):
    try:
        tmp = STATE_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        tmp.replace(STATE_FILE)
    except OSError as e:
        print(f"[WARN] 状態保存失敗: {e}")
        raise

def load_logs() -> list:
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []

def append_log_entry(entry: dict):
    try:
        logs = load_logs()
        logs.append(entry)
        tmp = LOG_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        tmp.replace(LOG_FILE)
    except OSError as e:
        print(f"[WARN] ログ保存失敗: {e}")
