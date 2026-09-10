from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.machine import Machine
from ..models.user import User
from ..schemas.command import LogIn
from .deps import ok, current_user
from ..services.ssh.manager import run_command
import re

router = APIRouter(prefix="/api/machines", tags=["logs"])

SAFE_SERVICE = re.compile(r"^[A-Za-z0-9@_:.\-]{0,128}$")


@router.post("/{mid}/logs")
async def view_logs(mid: int, body: LogIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    svc = (body.service or "").strip()
    if not SAFE_SERVICE.match(svc):
        raise HTTPException(400, "Tên dịch vụ không hợp lệ")
    lines = max(10, min(body.lines or 100, 1000))
    if svc:
        cmd = f"journalctl -u {svc} --no-pager -n {lines} 2>&1 || tail -n {lines} /var/log/syslog 2>&1"
    else:
        cmd = f"journalctl --no-pager -n {lines} 2>&1 | tail -n {lines} || tail -n {lines} /var/log/syslog 2>&1"
    try:
        r = await run_command(m, cmd, timeout=20)
        return ok({"service": svc, "lines": lines, "output": r["stdout"], "stderr": r["stderr"]})
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502), str(e))
