from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.user import User
from ..core.security import decode_token

bearer = HTTPBearer(auto_error=False)


def ok(data=None, message=None):
    return {"success": True, "data": data, "message": message}


def fail(message, data=None):
    return {"success": False, "data": data, "message": message}


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(401, "Chưa đăng nhập")
    username = decode_token(creds.credentials)
    if not username:
        raise HTTPException(401, "Phiên đăng nhập hết hạn hoặc không hợp lệ")
    u = db.query(User).filter(User.username == username).first()
    if not u or not u.is_active:
        raise HTTPException(401, "Tài khoản đã bị vô hiệu hóa")
    return u


def audit(db: Session, user_id, machine_id, action, command="", status="", summary=""):
    from ..models.audit import AuditLog
    db.add(AuditLog(user_id=user_id, machine_id=machine_id, action=action,
                    command=(command or "")[:2000], status=status or "",
                    output_summary=(summary or "")[:1000]))
    try:
        db.commit()
    except Exception:
        db.rollback()
