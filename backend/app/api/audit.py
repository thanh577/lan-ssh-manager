from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.audit import AuditLog
from ..models.user import User
from .deps import ok, current_user

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(current_user)):
    limit = max(1, min(limit, 500))
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return ok([{"id": r.id, "user_id": r.user_id, "machine_id": r.machine_id,
                "action": r.action, "command": r.command or "", "status": r.status or "",
                "output_summary": r.output_summary or "",
                "created_at": r.created_at.isoformat() if r.created_at else None}
               for r in rows])
