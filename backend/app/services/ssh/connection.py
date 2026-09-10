"""Single SSH connection wrapper."""
import asyncssh
import time
from .client import build_connect_kwargs
from .errors import map_error


class SSHConnection:
    def __init__(self, machine):
        self.machine = machine
        self.conn: asyncssh.SSHClientConnection | None = None

    async def connect(self):
        try:
            kw = build_connect_kwargs(self.machine)
            self.conn = await asyncssh.connect(**kw)
            return self.conn
        except Exception as e:
            raise map_error(e)

    async def run(self, command: str, timeout: int = 30) -> dict:
        if self.conn is None:
            await self.connect()
        t0 = time.time()
        try:
            result = await asyncio_wait_run(self.conn, command, timeout)
            return {
                "exit_code": result.exit_status,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "duration_ms": int((time.time() - t0) * 1000),
            }
        except Exception as e:
            raise map_error(e)

    async def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None


async def asyncio_wait_run(conn, command: str, timeout: int):
    import asyncio
    return await asyncio.wait_for(conn.run(command), timeout=timeout)
