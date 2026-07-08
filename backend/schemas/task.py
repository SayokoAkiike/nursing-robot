from pydantic import BaseModel


class TransitionRequest(BaseModel):
    next_state: str

