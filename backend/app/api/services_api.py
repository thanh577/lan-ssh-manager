"""Service control with whitelist. Frontend sends only action, backend builds command."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.machine import Machine
from ..models.user import User
from .deps import ok, current_user, audit
from ..services.ssh.manager import run_command
import re

router = APIRouter(prefix="/api/machines", tags=["services"])

ALLOWED_ACTIONS = {"start", "stop", "restart", "status", "enable", "disable"}
NAME_RE = re.compile(r"^[A-Za-z0-9@_:.\-]{1,128}$")


def _build(action: str, name: str) -> str:
    if action not in ALLOWED_ACTIONS:
        raise ValueError("Hành động không được phép")
    if not NAME_RE.match(name or ""):
        raise ValueError("Tên dịch vụ không hợp lệ")
    return f"systemctl {action} {name} --no-pager 2>&1; echo EXIT:$?"


@router.get("/{mid}/services")
async def list_services(mid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        r = await run_command(m, "systemctl list-units --type=service --state=running --no-pager --no-legend | head -50", timeout=20)
        return ok({"running": r["stdout"]})
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502), str(e))


@router.post("/{mid}/services/{name}/{action}")
async def control(mid: int, name: str, action: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        cmd = _build(action, name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        r = await run_command(m, cmd, timeout=30)
        audit(db, user.id, m.id, f"SERVICE_{action.upper()}", f"systemctl {action} {name}",
              "success", (r.get("stdout") or "")[:500])
        return ok(r)
    except Exception as e:
        audit(db, user.id, m.id, f"SERVICE_{action.upper()}", f"systemctl {action} {name}", "failed", str(e)[:500])
        raise HTTPException(getattr(e, "code", 502), str(e))
