from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import asyncio
from ..db.database import get_db
from ..models.machine import Machine
from ..models.user import User
from .deps import ok, current_user
from ..services.ssh.manager import quick_status

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    machines = db.query(Machine).all()
    statuses = await asyncio.gather(*[quick_status(m) if m.enabled else asyncio.sleep(0, result="disabled") for m in machines])
    total = len(machines)
    online = sum(1 for s in statuses if s == "online")
    offline = sum(1 for s in statuses if s == "offline")
    disabled = sum(1 for s in statuses if s == "disabled")
    rows = []
    for m, s in zip(machines, statuses):
        rows.append({"id": m.id, "name": m.name, "hostname": m.hostname,
                     "status": "unknown" if s == "disabled" else s, "enabled": m.enabled})
    return ok({"total": total, "online": online, "offline": offline,
               "disabled": disabled, "unknown": disabled, "machines": rows})
