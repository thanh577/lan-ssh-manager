from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.machine import Machine
from ..models.user import User
from .deps import ok, current_user, audit
from ..services.monitoring.system_info import collect

router = APIRouter(prefix="/api/machines", tags=["system"])


@router.get("/{mid}/system")
async def system_info(mid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        info = await collect(m)
        return ok(info)
    except Exception as e:
        raise HTTPException(502, f"Lấy thông tin hệ thống thất bại: {e}")
