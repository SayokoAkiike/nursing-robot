import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
NURSE_TOKEN  = os.getenv("NURSE_TOKEN", "")
_TIMEOUT = 5

def _nurse_headers():
    return {"x-nurse-token": NURSE_TOKEN}

def get_requests():
    r = requests.get(f"{API_BASE_URL}/requests", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

def create_request(patient_id, request_type):
    r = requests.post(f"{API_BASE_URL}/requests",
        json={"patient_id": patient_id, "request_type": request_type}, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

def cancel_request(request_id):
    r = requests.post(f"{API_BASE_URL}/requests/{request_id}/cancel", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

def transition_task(request_id, next_state):
    r = requests.post(f"{API_BASE_URL}/tasks/{request_id}/transition",
        headers=_nurse_headers(), json={"next_state": next_state}, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

def verify_task(request_id, patient_id, kit_id):
    r = requests.post(f"{API_BASE_URL}/tasks/{request_id}/verify",
        headers=_nurse_headers(), json={"patient_id": patient_id, "kit_id": kit_id}, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

def emergency_stop(request_id):
    r = requests.post(f"{API_BASE_URL}/tasks/{request_id}/emergency-stop",
        headers=_nurse_headers(), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

def reset_task(request_id):
    r = requests.post(f"{API_BASE_URL}/tasks/{request_id}/reset",
        headers=_nurse_headers(), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

def nurse_cancel(request_id):
    r = requests.post(f"{API_BASE_URL}/cancel",
        headers=_nurse_headers(), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

def get_logs():
    r = requests.get(f"{API_BASE_URL}/logs", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()
