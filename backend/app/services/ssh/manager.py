"""SSH Manager: only layer allowed to use asyncssh. Handles concurrency limit."""
import asyncio
import time
import asyncssh
from .client import build_connect_kwargs
from .errors import map_error
from ...core.config import get_settings

_sem: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(get_settings().MAX_CONCURRENT_SSH)
    return _sem


async def test_connection(machine) -> dict:
    """Connect, run echo OK, disconnect. Returns {success, message}."""
    t0 = time.time()
    async with _semaphore():
        try:
            kw = build_connect_kwargs(machine)
            async with asyncssh.connect(**kw) as conn:
                r = await asyncio.wait_for(conn.run("echo OK"), timeout=get_settings().SSH_TIMEOUT)
                ok = (r.stdout or "").strip() == "OK"
                ms = int((time.time() - t0) * 1000)
                if ok:
                    return {"success": True, "message": f"Kết nối SSH thành công ({ms}ms)"}
                return {"success": False, "message": f"Kết quả kiểm tra bất thường: {r.stdout!r}"}
        except Exception as e:
            mapped = map_error(e)
            return {"success": False, "message": str(mapped)}


async def run_command(machine, command: str, timeout: int | None = None) -> dict:
    timeout = timeout or get_settings().SSH_COMMAND_TIMEOUT
    timeout = max(1, min(timeout, 300))
    t0 = time.time()
    async with _semaphore():
        conn = None
        try:
            kw = build_connect_kwargs(machine)
            conn = await asyncssh.connect(**kw)
            try:
                r = await asyncio.wait_for(conn.run(command), timeout=timeout)
                return {
                    "success": True,
                    "exit_code": r.exit_status,
                    "stdout": r.stdout or "",
                    "stderr": r.stderr or "",
                    "duration_ms": int((time.time() - t0) * 1000),
                }
            finally:
                conn.close()
        except Exception as e:
            mapped = map_error(e)
            raise mapped


async def quick_status(machine) -> str:
    """Return online|offline without raising."""
    try:
        kw = build_connect_kwargs(machine)
        kw["connect_timeout"] = 4
        async with _semaphore():
            async with asyncssh.connect(**kw) as conn:
                await asyncio.wait_for(conn.run("echo OK"), timeout=5)
        return "online"
    except Exception:
        return "offline"
