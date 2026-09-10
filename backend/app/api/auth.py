from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.user import User
from ..schemas.auth import LoginIn
from ..core.security import verify_password, create_token
from .deps import ok, current_user, audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == body.username).first()
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    token = create_token(u.username)
    audit(db, u.id, None, "LOGIN", "", "success", f"user {u.username} login")
    return ok({"token": token, "username": u.username}, "Đăng nhập thành công")


@router.post("/logout")
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    audit(db, user.id, None, "LOGOUT", "", "success", f"user {user.username} logout")
    return ok(message="Đã đăng xuất")


@router.get("/me")
def me(user: User = Depends(current_user)):
    return ok({"username": user.username, "id": user.id})
