"""Bridge FastAPI WebSocket <-> asyncssh interactive shell."""
import asyncio
import asyncssh
from fastapi import WebSocket


def _clamp(v, lo, hi, default):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


async def bridge(websocket: WebSocket, machine, cols: int = 120, rows: int = 32):
    await websocket.accept()
    cols = _clamp(cols, 20, 300, 120)
    rows = _clamp(rows, 5, 100, 32)
    from ..ssh.client import build_connect_kwargs
    kw = build_connect_kwargs(machine)
    # connect with timeout so browser never hangs on black screen
    try:
        conn = await asyncio.wait_for(asyncssh.connect(**kw), timeout=kw.get("connect_timeout", 10) + 5)
    except Exception as e:
        try:
            await websocket.send_text(f"\r\n[Kết nối SSH thất bại] {e}\r\n")
        finally:
            try:
                await websocket.close(code=4411)
            except Exception:
                pass
        return
    try:
        proc = await conn.create_process(
            term_type="xterm-256color",
            term_size=(cols, rows),
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        try:
            await websocket.send_text(f"\r\n[Mở shell thất bại] {e}\r\n")
        finally:
            try:
                await websocket.close(code=4412)
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass
        return

    async def forward(stream, tag=""):
        try:
            while not stream.at_eof():
                # read() trả ngay khi có dữ liệu (kể cả chưa có \n),
                # khác với `async for` đọc theo dòng làm echo gõ phím bị dồn tới khi Enter
                data = await stream.read(4096)
                if not data:
                    break
                if isinstance(data, bytes):
                    data = data.decode("utf-8", "replace")
                await websocket.send_text(data)
        except Exception:
            pass

    async def ssh_to_ws():
        await asyncio.gather(
            forward(proc.stdout),
            forward(proc.stderr) if proc.stderr is not None else asyncio.sleep(0),
        )
        # shell exited: report status then close
        try:
            code = proc.get_exit_status()
        except Exception:
            code = None
        try:
            await websocket.send_text(f"\r\n[shell đã thoát {code}]\r\n")
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass

    async def ws_to_ssh():
        try:
            while True:
                msg = await websocket.receive_text()
                # control protocol: JSON {"resize":[cols,rows]} else raw input
                if msg.startswith('{"resize"'):
                    try:
                        import json
                        d = json.loads(msg)
                        c, r = d.get("resize", [cols, rows])
                        proc.change_terminal_size(_clamp(c, 20, 300, cols),
                                                  _clamp(r, 5, 100, rows))
                    except Exception:
                        pass
                    continue
                try:
                    proc.stdin.write(msg)
                except Exception:
                    pass
        except Exception:
            pass

    t = asyncio.create_task(ssh_to_ws())
    try:
        await ws_to_ssh()
    finally:
        t.cancel()
        try:
            proc.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
