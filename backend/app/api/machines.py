from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.machine import Machine
from ..models.user import User
from ..schemas.machine import MachineIn, MachineUpdate
from ..core.security import encrypt_secret
from .deps import ok, current_user, audit
from ..services.ssh.manager import test_connection

router = APIRouter(prefix="/api/machines", tags=["machines"])


def _public(m: Machine) -> dict:
    return {"id": m.id, "name": m.name, "hostname": m.hostname, "port": m.port,
            "username": m.username, "auth_type": m.auth_type, "group_id": m.group_id,
            "description": m.description or "", "enabled": m.enabled,
            "last_seen": m.last_seen.isoformat() if m.last_seen else None,
            "has_credential": bool(m.credential_encrypted)}


@router.get("")
def list_machines(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Machine).order_by(Machine.id).all()
    return ok([_public(m) for m in rows])


@router.get("/{mid}")
def get_machine(mid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    return ok(_public(m))


@router.post("", status_code=201)
def create_machine(body: MachineIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = Machine(name=body.name.strip(), hostname=body.hostname.strip(), port=body.port,
                username=body.username.strip(), auth_type=body.auth_type,
                credential_encrypted=encrypt_secret(body.credential or ""),
                group_id=body.group_id, description=body.description or "",
                enabled=body.enabled)
    db.add(m)
    db.commit()
    db.refresh(m)
    audit(db, user.id, m.id, "ADD_MACHINE", "", "success", f"add {m.name}")
    return ok(_public(m), "Đã thêm máy")


@router.put("/{mid}")
def update_machine(mid: int, body: MachineUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    m.name = body.name.strip()
    m.hostname = body.hostname.strip()
    m.port = body.port
    m.username = body.username.strip()
    m.auth_type = body.auth_type
    if body.credential:
        m.credential_encrypted = encrypt_secret(body.credential)
    m.group_id = body.group_id
    m.description = body.description or ""
    m.enabled = body.enabled
    db.commit()
    db.refresh(m)
    audit(db, user.id, m.id, "UPDATE_MACHINE", "", "success", f"update {m.name}")
    return ok(_public(m), "Đã cập nhật máy")


@router.delete("/{mid}")
def delete_machine(mid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    name = m.name
    db.delete(m)
    db.commit()
    audit(db, user.id, None, "DELETE_MACHINE", "", "success", f"delete {name}")
    return ok(message=f"Đã xóa {name}")


@router.post("/{mid}/test")
async def test_machine(mid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    res = await test_connection(m)
    from datetime import datetime, timezone
    if res["success"]:
        m.last_seen = datetime.now(timezone.utc)
        db.commit()
    audit(db, user.id, m.id, "TEST_SSH", "", "success" if res["success"] else "failed", res["message"][:1000])
    status = 200 if res["success"] else 502
    if status != 200:
        raise HTTPException(status, res["message"])
    return ok(res, res["message"])
