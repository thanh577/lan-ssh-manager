"""Quản lý cổng console vật lý cho máy chưa có OS.

- CRUD ánh xạ cổng serial (/dev/ttyUSB0...) <-> máy đích.
- WS /ws/console/{id}: console tương tác trên web (xterm).
- REST read/write polling: cho CLI `lsm console attach` (stdlib-only).
"""
import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..db.database import get_db, get_session_factory
from ..models.console import SerialConsole
from ..models.machine import Machine
from ..models.user import User
from ..core.security import decode_token
from .deps import ok, current_user, audit
from ..services.serial import manager as serm
from ..services.serial.manager import bridge_console

router = APIRouter(prefix="/api/consoles", tags=["consoles"])
# WebSocket phải dùng router riêng KHÔNG prefix (APIRouter prefix áp dụng
# cho cả ws route — để chung prefix sẽ thành /api/consoles/ws/... và 403).
router_ws = APIRouter(tags=["consoles"])


def _public(c: SerialConsole, machine_name: str = "") -> dict:
    return {"id": c.id, "name": c.name, "device": c.device,
            "baudrate": c.baudrate, "machine_id": c.machine_id,
            "machine_name": machine_name,
            "description": c.description or "", "enabled": c.enabled,
            "in_use": bool(serm.holder_of(c.device))}


def _get_or_404(db: Session, cid: int) -> SerialConsole:
    c = db.query(SerialConsole).filter(SerialConsole.id == cid).first()
    if not c:
        raise HTTPException(404, "Không tìm thấy cổng console")
    return c


def _check_body(body: dict, partial=False):
    name = (body.get("name") or "").strip()
    device = (body.get("device") or "").strip()
    baud = body.get("baudrate", 115200)
    if not partial or "name" in body:
        if not name:
            raise HTTPException(400, "Cần nhập tên cổng console")
    if not partial or "device" in body:
        if not serm.valid_device(device):
            raise HTTPException(400, "Đường dẫn thiết bị không hợp lệ (vd /dev/ttyUSB0)")
    if not partial or "baudrate" in body:
        if not serm.valid_baud(baud):
            raise HTTPException(400, f"Baudrate không hỗ trợ (chọn trong {sorted(serm.BAUDS)})")
    return name, device, int(baud)


@router.get("")
def list_consoles(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(SerialConsole).order_by(SerialConsole.id).all()
    mids = {c.machine_id for c in rows if c.machine_id}
    names = {m.id: m.name for m in db.query(Machine).filter(Machine.id.in_(mids)).all()} if mids else {}
    return ok({"consoles": [_public(c, names.get(c.machine_id or -1, "")) for c in rows],
               "system_ports": serm.system_ports(),
               "baudrates": sorted(serm.BAUDS)})


@router.post("", status_code=201)
def create_console(body: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    name, device, baud = _check_body(body)
    if db.query(SerialConsole).filter(SerialConsole.device == device).first():
        raise HTTPException(409, "Cổng này đã được khai báo")
    mid = body.get("machine_id")
    if mid is not None and not db.query(Machine).filter(Machine.id == mid).first():
        raise HTTPException(404, "Không tìm thấy máy liên kết")
    c = SerialConsole(name=name, device=device, baudrate=baud, machine_id=mid,
                      description=body.get("description") or "",
                      enabled=body.get("enabled", True))
    db.add(c)
    db.commit()
    db.refresh(c)
    audit(db, user.id, mid, "CONSOLE_ADD", "", "success", f"add console {name} {device}")
    return ok(_public(c), "Đã thêm cổng console")


@router.put("/{cid}")
def update_console(cid: int, body: dict, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    c = _get_or_404(db, cid)
    if serm.holder_of(c.device):
        raise HTTPException(409, "Cổng đang có session — ngắt kết nối trước khi sửa")
    name, device, baud = _check_body(body, partial=True)
    if "name" in body:
        c.name = name
    if "device" in body:
        dup = db.query(SerialConsole).filter(
            SerialConsole.device == device, SerialConsole.id != cid).first()
        if dup:
            raise HTTPException(409, "Cổng này đã được khai báo ở mục khác")
        c.device = device
    if "baudrate" in body:
        c.baudrate = baud
    if "machine_id" in body:
        mid = body.get("machine_id")
        if mid is not None and not db.query(Machine).filter(Machine.id == mid).first():
            raise HTTPException(404, "Không tìm thấy máy liên kết")
        c.machine_id = mid
    if "description" in body:
        c.description = body.get("description") or ""
    if "enabled" in body:
        c.enabled = bool(body.get("enabled"))
    db.commit()
    db.refresh(c)
    return ok(_public(c), "Đã cập nhật cổng console")


@router.delete("/{cid}")
def delete_console(cid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = _get_or_404(db, cid)
    if serm.holder_of(c.device):
        raise HTTPException(409, "Cổng đang có session — ngắt kết nối trước khi xóa")
    name = c.name
    db.delete(c)
    db.commit()
    audit(db, user.id, None, "CONSOLE_DELETE", "", "success", f"delete console {name}")
    return ok(message=f"Đã xóa {name}")


@router.post("/{cid}/write")
async def console_write(cid: int, body: dict, db: Session = Depends(get_db),
                        user: User = Depends(current_user)):
    c = _get_or_404(db, cid)
    if not c.enabled:
        raise HTTPException(400, "Cổng console đang tắt")
    data = body.get("data", "")
    if not isinstance(data, str) or not data:
        raise HTTPException(400, "Chưa có dữ liệu gửi")
    try:
        st = await serm.poll_ensure(cid, c.device, c.baudrate)
    except RuntimeError as e:
        raise HTTPException(getattr(e, "code", 409), str(e))
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502), f"Mở cổng serial thất bại: {e}")
    try:
        await asyncio.to_thread(st.ser.write, data.encode("utf-8"))
    except Exception as e:
        raise HTTPException(502, f"Ghi serial thất bại: {e}")
    st.last = time.monotonic()
    return ok({"seq": st.seq})


@router.get("/{cid}/read")
async def console_read(cid: int, since: int = 0, db: Session = Depends(get_db),
                       user: User = Depends(current_user)):
    c = _get_or_404(db, cid)
    if not c.enabled:
        raise HTTPException(400, "Cổng console đang tắt")
    try:
        st = await serm.poll_ensure(cid, c.device, c.baudrate)
    except RuntimeError as e:
        raise HTTPException(getattr(e, "code", 409), str(e))
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502), f"Mở cổng serial thất bại: {e}")
    st.last = time.monotonic()
    with st.bloc:
        entries = [e for e in st.buf if e["seq"] > since][-200:]
        cur = st.seq
    return ok({"entries": entries, "next": cur})


@router.post("/{cid}/break")
async def console_break(cid: int, db: Session = Depends(get_db),
                        user: User = Depends(current_user)):
    """Gửi tín hiệu BREAK (hữu ích để ngắt vào bootloader/BIOS)."""
    c = _get_or_404(db, cid)
    h = serm.holder_of(c.device)
    if h:
        raise HTTPException(409, "Cổng đang có session — gửi BREAK từ trong session đó")
    try:
        ser = await asyncio.to_thread(serm.open_serial, c.device, c.baudrate)
    except Exception as e:
        raise HTTPException(502, f"Mở cổng serial thất bại: {e}")
    try:
        await asyncio.to_thread(ser.send_break)
    finally:
        try:
            ser.close()
        except Exception:
            pass
    audit(db, user.id, c.machine_id, "CONSOLE_BREAK", c.device, "success", "")
    return ok(message="Đã gửi BREAK")


@router.post("/{cid}/release")
async def console_release(cid: int, db: Session = Depends(get_db),
                          user: User = Depends(current_user)):
    """Cưỡng chế giải phóng session kẹt (WS rớt không đóng / CLI quên thoát)."""
    c = _get_or_404(db, cid)
    h = serm.holder_of(c.device)
    serm.poll_close(cid)
    serm.release(c.device)
    audit(db, user.id, c.machine_id, "CONSOLE_RELEASE", c.device, "success",
          f"gỡ {h['kind']}/{h['label']}" if h else "không có session")
    return ok(message="Đã giải phóng" if h else "Cổng vốn đang rảnh")


@router_ws.websocket("/ws/console/{cid}")
async def console_ws(websocket: WebSocket, cid: int):
    token = websocket.query_params.get("token", "")
    username = decode_token(token) if token else None
    if not username:
        await websocket.close(code=4401)
        return
    Session = get_session_factory()
    db = Session()
    try:
        u = db.query(User).filter(User.username == username).first()
        c = db.query(SerialConsole).filter(SerialConsole.id == cid).first()
        if not u or not u.is_active or not c:
            await websocket.close(code=4404)
            return
        if not c.enabled:
            await websocket.close(code=4404)
            return
        audit(db, u.id, c.machine_id, "CONSOLE_CONNECT", c.device, "success", c.name)
        try:
            await bridge_console(websocket, c.device, c.baudrate)
        except WebSocketDisconnect:
            pass
        audit(db, u.id, c.machine_id, "CONSOLE_DISCONNECT", c.device, "success", c.name)
    finally:
        db.close()
