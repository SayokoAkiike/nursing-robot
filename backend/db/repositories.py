"""Persistence facade used by the services layer.
 
Backed by the existing JSON file storage (`backend/storage.py`) for now.
PR2 replaces the *inside* of this module with SQLAlchemy-backed
implementations; callers (the services layer) do not change, because they
only depend on the functions below, never on `backend/storage.py` directly.
 
This repo still only tracks a single in-flight request at a time (see
`backend/storage.py`'s `load_state`/`save_state`) -- that is a real
constraint of the current JSON storage, not an artifact of this facade. PR3
("Task resource model") is what actually introduces multiple concurrent
`robot_tasks` rows; until then, `list_requests()` will keep returning at most
one item.
"""
from backend import storage
 
 
def load_state() -> dict:
    return storage.load_state()
 
 
def save_state(state: dict) -> None:
    storage.save_state(state)
 
 
def load_logs() -> list:
    return storage.load_logs()
 
 
def append_log_entry(entry: dict) -> None:
    storage.append_log_entry(entry)
 
 
def list_requests() -> list:
    return storage.load_requests()
 
 
def get_request(request_id: str):
    return storage.get_request(request_id)
 
