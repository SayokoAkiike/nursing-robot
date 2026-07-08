from fastapi import APIRouter
 
from backend.db import repositories
 
router = APIRouter(tags=["logs"])
 
 
@router.get("/logs")
def get_logs():
    return repositories.load_logs()
 
