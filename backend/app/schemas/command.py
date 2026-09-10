from pydantic import BaseModel


class CommandIn(BaseModel):
    command: str
    timeout: int = 30


class BatchIn(BaseModel):
    machine_ids: list[int]
    command: str
    timeout: int = 30


class LogIn(BaseModel):
    service: str = ""
    lines: int = 100
