"""Command executor with timeout + audit hook. Single place for exec logic."""
from ..ssh.manager import run_command as _ssh_run


async def execute(machine, command: str, timeout: int = 30) -> dict:
    command = (command or "").strip()
    if not command:
        raise ValueError("Lệnh rỗng")
    if len(command) > 8000:
        raise ValueError("Lệnh quá dài")
    return await _ssh_run(machine, command, timeout=timeout)


async def execute_batch(machines: list, command: str, timeout: int = 30) -> list[dict]:
    import asyncio
    from ...core.config import get_settings
    sem = asyncio.Semaphore(get_settings().MAX_CONCURRENT_SSH)

    async def _one(m):
        async with sem:
            try:
                r = await _ssh_run(m, command, timeout=timeout)
                return {"machine_id": m.id, "machine_name": m.name,
                        "success": r["exit_code"] == 0, **r}
            except Exception as e:
                return {"machine_id": m.id, "machine_name": m.name,
                        "success": False, "exit_code": -1,
                        "stdout": "", "stderr": str(e), "duration_ms": 0}

    return await asyncio.gather(*[_one(m) for m in machines])
