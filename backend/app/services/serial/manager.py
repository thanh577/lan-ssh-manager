"""Serial console service: truy cập cổng console vật lý (/dev/ttyUSB0, ...)
để điều khiển máy chưa có OS (BIOS/bootloader/bộ cài OS).

Một cổng serial chỉ mở được bởi 1 session tại 1 thời điểm nên module giữ
registry chiếm-giữ loại trừ (WS bridge hoặc polling session của CLI)."""
import asyncio
import re
import threading
import time
from collections import deque

BAUDS = {1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600}
DEVICE_RE = re.compile(r"^/dev/[A-Za-z0-9_.\-/]{1,100}$")
POLL_IDLE_S = 90
POLL_BUF = 500

_lock = threading.Lock()
_holders: dict[str, dict] = {}      # device -> {"kind": "ws"|"poll", "label": str}
_poll: dict[int, "_PollState"] = {}  # console_id -> state


def valid_device(path: str) -> bool:
    if not path or not isinstance(path, str):
        return False
    if ".." in path or "\x00" in path:
        return False
    return bool(DEVICE_RE.match(path))


def valid_baud(b) -> bool:
    try:
        return int(b) in BAUDS
    except (TypeError, ValueError):
        return False


def holder_of(device: str):
    with _lock:
        h = _holders.get(device)
        return dict(h) if h else None


def acquire(device: str, kind: str, label: str = "") -> bool:
    with _lock:
        if device in _holders:
            return False
        _holders[device] = {"kind": kind, "label": label or kind}
        return True


def release(device: str):
    with _lock:
        _holders.pop(device, None)


def system_ports():
    """Cổng serial đang thấy trên máy chủ app (để gợi ý khi khai báo)."""
    try:
        from serial.tools import list_ports
        return [{"device": p.device, "description": p.description or ""}
                for p in list_ports.comports()]
    except Exception:
        return []


def open_serial(device: str, baudrate: int):
    import serial
    return serial.Serial(port=device, baudrate=int(baudrate), timeout=0.2)


async def bridge_console(websocket, device: str, baudrate: int):
    """Bridge FastAPI WebSocket <-> cổng serial (dùng cho xterm trên web)."""
    await websocket.accept()
    if not acquire(device, "ws", "web"):
        await websocket.send_text("\r\n[Cổng đang được session khác dùng — "
                                  "đóng session kia hoặc bấm 'Giải phóng kẹt']\r\n")
        try:
            await websocket.close(code=4409)
        except Exception:
            pass
        return
    try:
        ser = await asyncio.to_thread(open_serial, device, baudrate)
    except Exception as e:
        release(device)
        try:
            await websocket.send_text(f"\r\n[Mở cổng serial thất bại] {e}\r\n")
        finally:
            try:
                await websocket.close(code=4413)
            except Exception:
                pass
        return
    try:
        await websocket.send_text(f"\r\n[đã nối {device} @ {baudrate} baud — "
                                  f"màn hình cài OS/BIOS của máy đích]\r\n")

        async def serial_to_ws():
            try:
                while True:
                    data = await asyncio.to_thread(ser.read, 4096)
                    if data:
                        await websocket.send_text(data.decode("utf-8", "replace"))
            except Exception:
                pass

        async def ws_to_serial():
            try:
                while True:
                    msg = await websocket.receive_text()
                    if msg.startswith('{"break"'):
                        try:
                            await asyncio.to_thread(ser.send_break)
                            await websocket.send_text("\r\n[đã gửi BREAK]\r\n")
                        except Exception:
                            pass
                        continue
                    if msg:
                        try:
                            await asyncio.to_thread(ser.write, msg.encode("utf-8"))
                        except Exception:
                            pass
            except Exception:
                pass

        t = asyncio.create_task(serial_to_ws())
        try:
            await ws_to_serial()
        finally:
            t.cancel()
    finally:
        try:
            await asyncio.to_thread(ser.close)
        except Exception:
            pass
        release(device)


class _PollState:
    """Session polling cho CLI (lsm console attach): reader nền bơm dữ liệu
    serial vào buffer, CLI đọc qua REST, ghi qua REST."""

    def __init__(self, console_id: int, device: str, ser):
        self.console_id = console_id
        self.device = device
        self.ser = ser
        self.buf: deque = deque(maxlen=POLL_BUF)
        self.seq = 0
        self.last = time.monotonic()
        self.task = None
        self.bloc = threading.Lock()
        self.opened = asyncio.Event()


async def _poll_reader(st: _PollState):
    try:
        while True:
            try:
                data = await asyncio.to_thread(st.ser.read, 4096)
            except Exception:
                break
            if data:
                txt = data.decode("utf-8", "replace")
                with st.bloc:
                    st.seq += 1
                    st.buf.append({"seq": st.seq, "data": txt})
            if time.monotonic() - st.last > POLL_IDLE_S:
                break
            if not data:
                await asyncio.sleep(0.05)
    finally:
        with _lock:
            if _poll.get(st.console_id) is st:
                _poll.pop(st.console_id, None)
        try:
            await asyncio.to_thread(st.ser.close)
        except Exception:
            pass
        release(st.device)


async def poll_ensure(console_id: int, device: str, baudrate: int) -> _PollState:
    """Mở (nếu chưa) và trả về polling session. 409 nếu cổng đang bận.

    Toàn bộ check→acquire→đặt chỗ giữ trong MỘT lock để 2 thread cùng mở
    (poller + writer của `lsm console attach`) không tranh nhau 409 oan."""
    with _lock:
        st = _poll.get(console_id)
        if st is None:
            h = _holders.get(device)
            if h is not None:
                err = RuntimeError("Cổng đang được session khác dùng"
                                   + (f" ({h['label']})" if h else ""))
                err.code = 409
                raise err
            _holders[device] = {"kind": "poll", "label": "cli"}
            st = _PollState(console_id, device, None)
            _poll[console_id] = st
            fresh = True
        else:
            fresh = False
    if not fresh:
        await st.opened.wait()
        if st.ser is None:
            err = RuntimeError("Mở cổng serial thất bại — thử lại")
            err.code = 502
            raise err
        st.last = time.monotonic()
        return st
    try:
        st.ser = await asyncio.to_thread(open_serial, device, baudrate)
    except Exception as e:
        st.ser = None
        st.opened.set()
        with _lock:
            if _poll.get(console_id) is st:
                _poll.pop(console_id, None)
        release(device)
        e.code = 502
        raise
    st.task = asyncio.create_task(_poll_reader(st))
    st.opened.set()
    return st


def poll_close(console_id: int):
    with _lock:
        st = _poll.pop(console_id, None)
    if st and st.task:
        st.task.cancel()
    if st:
        try:
            st.ser.close()
        except Exception:
            pass
        release(st.device)
