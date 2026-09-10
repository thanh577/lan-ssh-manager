from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    success: bool = True
    data: dict = {}
    message: str | None = None
