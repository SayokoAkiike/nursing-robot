import os
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

NURSE_TOKEN = os.getenv("NURSE_TOKEN", "precare-dev-token-2026")

def require_nurse(x_nurse_token: str = Header(default="")):
    if x_nurse_token != NURSE_TOKEN:
        raise HTTPException(status_code=401, detail="Nurse token required")
