from pydantic import BaseModel, Field


class MachineIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=128)
    auth_type: str = Field(default="password", pattern="^(password|key)$")
    credential: str = ""  # plaintext password OR private key content; encrypted server-side
    group_id: int | None = None
    description: str = ""
    enabled: bool = True


class MachineUpdate(MachineIn):
    credential: str = ""  # empty = keep old
