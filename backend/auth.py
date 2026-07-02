import os
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

NURSE_TOKEN = os.getenv("NURSE_TOKEN")
if not NURSE_TOKEN:
    raise RuntimeError("NURSE_TOKEN is not set. Please define it in your .env file.")

def require_nurse(x_nurse_token: str = Header(default="")):
    if x_nurse_token != NURSE_TOKEN:
        raise HTTPException(status_code=401, detail="Nurse token required")
