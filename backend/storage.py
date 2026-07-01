import json
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "shared_state.json"
LOG_FILE   = DATA_DIR / "robot_log.json"

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"request": None, "robot_state": "IDLE"}

def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_logs() -> list:
    if LOG_FILE.exists():
        with open(LOG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def append_log_entry(entry: dict):
    logs = load_logs()
    logs.append(entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
