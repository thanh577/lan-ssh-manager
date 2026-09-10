from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.group import Group
from ..models.user import User
from .deps import ok, current_user

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("")
def list_groups(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return ok([{"id": g.id, "name": g.name, "description": g.description or ""}
               for g in db.query(Group).order_by(Group.id).all()])


@router.post("", status_code=201)
def create_group(body: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Cần nhập tên")
    if db.query(Group).filter(Group.name == name).first():
        raise HTTPException(409, "Nhóm đã tồn tại")
    g = Group(name=name, description=body.get("description") or "")
    db.add(g)
    db.commit()
    db.refresh(g)
    return ok({"id": g.id, "name": g.name, "description": g.description}, "Đã tạo nhóm")


@router.delete("/{gid}")
def delete_group(gid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    g = db.query(Group).filter(Group.id == gid).first()
    if not g:
        raise HTTPException(404, "Không tìm thấy nhóm")
    db.delete(g)
    db.commit()
    return ok(message="Đã xóa nhóm")
