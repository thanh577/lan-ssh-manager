"""OS user management on remote machines. All commands are server-built;
frontend only sends validated fields. Passwords are hashed locally with
SHA-512 crypt ($6$, via passlib — cross-platform) and never appear in
commands, logs or audit in plaintext."""
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.machine import Machine
from ..models.user import User
from .deps import ok, current_user, audit
from ..services.ssh.manager import run_command

router = APIRouter(prefix="/api/machines", tags=["users"])

USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
NEED_PRIV_HINT = ("cần quyền root (thêm máy bằng user SSH 'root' "
                  "hoặc cấu hình sudo NOPASSWD cho user SSH)")


def _priv(m: Machine, cmd: str) -> str:
    """Prefix sudo -n when the SSH user is not root."""
    if (m.username or "") == "root":
        return cmd
    return f"sudo -n {cmd}"


def _check(r: dict, m: Machine):
    """Raise a meaningful error when a privileged command failed."""
    if r.get("exit_code", 0) == 0:
        return r.get("stdout") or ""
    err = ((r.get("stderr") or "") + "\n" + (r.get("stdout") or "")).strip()
    low = err.lower()
    if ("a password is required" in low or "interactive authentication" in low
            or "no tty present" in low or "not in the sudoers" in low):
        raise HTTPException(502, f"User SSH '{m.username}' {NEED_PRIV_HINT}")
    if "permission denied" in low:
        raise HTTPException(502, f"Truy cập bị từ chối — {NEED_PRIV_HINT}")
    raise HTTPException(502, err[:1000] or "Lệnh remote thất bại")


async def _exec(m: Machine, cmd: str, timeout: int = 20, priv: bool = False) -> str:
    """priv=True (add/del/passwd/lock) thì sudo -n khi SSH user khác root.
    Lệnh đọc (getent) chạy trực tiếp, không cần quyền."""
    try:
        r = await run_command(m, _priv(m, cmd) if priv else cmd, timeout=timeout)
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502), str(e))
    return _check(r, m)


def _parse_passwd(out: str) -> list[dict]:
    users = []
    for line in (out or "").splitlines():
        p = line.split(":")
        if len(p) != 7:
            continue
        name, _, uid, gid, _, home, shell = p
        if not USER_RE.match(name):
            continue
        try:
            uidn = int(uid)
        except ValueError:
            continue
        if uidn == 0 or uidn >= 1000:
            users.append({"name": name, "uid": uidn, "gid": int(gid) if gid.isdigit() else gid,
                          "home": home, "shell": shell, "status": "unknown"})
    return users


@router.get("/{mid}/users")
async def list_users(mid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        out = await _exec(m, "getent passwd", timeout=15)
    except Exception as e:
        raise e
    users = _parse_passwd(out)
    # lock status needs root; best-effort (sudo when available), never fatal
    try:
        st = await _exec(m, "passwd -Sa 2>/dev/null", timeout=15, priv=True)
        status = {}
        for line in st.splitlines():
            p = line.split()
            if len(p) >= 2:
                status[p[0]] = {"L": "locked", "P": "active", "NP": "no-password"}.get(p[1], p[1])
        for u in users:
            u["status"] = status.get(u["name"], "unknown")
    except HTTPException:
        pass
    return ok(users)


@router.post("/{mid}/users", status_code=201)
async def add_user(mid: int, body: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    name = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not USER_RE.match(name):
        raise HTTPException(400, "Tên người dùng không hợp lệ (a-z, 0-9, _, -, max 32, bắt đầu bằng chữ thường hoặc _)")
    if name == "root":
        raise HTTPException(400, "Không tạo người dùng 'root' từ đây")
    if password and len(password) < 4:
        raise HTTPException(400, "Mật khẩu tối thiểu 4 ký tự")
    try:
        await _exec(m, f"useradd -m -s /bin/bash {name}", timeout=20, priv=True)
        if password:
            await _exec(m, f"usermod -p '{_hash(password)}' {name}", timeout=20, priv=True)
        audit(db, user.id, m.id, "OS_USER_ADD", "", "success", f"add {name}")
        return ok({"name": name}, f"Đã tạo user {name}")
    except Exception as e:
        audit(db, user.id, m.id, "OS_USER_ADD", "", "failed", str(e)[:500])
        raise


@router.delete("/{mid}/users/{name}")
async def del_user(mid: int, name: str, remove_home: bool = False,
                   db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    if not USER_RE.match(name or ""):
        raise HTTPException(400, "Tên người dùng không hợp lệ")
    if name in ("root", m.username):
        raise HTTPException(400, f"Không được xóa '{name}' (root hoặc user SSH đang dùng)")
    try:
        out = await _exec(m, f"getent passwd {name}", timeout=15)
        p = out.strip().split(":")
        uid = int(p[2]) if len(p) == 7 and p[2].isdigit() else 10**9
        if uid < 1000 or uid > 60000:
            raise HTTPException(400, f"Không xóa user hệ thống '{name}' (uid={uid})")
        flag = " -r" if remove_home else ""
        await _exec(m, f"userdel{flag} {name}", timeout=20, priv=True)
        audit(db, user.id, m.id, "OS_USER_DEL", "", "success", f"delete {name}")
        return ok(message=f"Đã xóa user {name}")
    except HTTPException as e:
        if e.status_code not in (400,):
            audit(db, user.id, m.id, "OS_USER_DEL", "", "failed", str(e.detail)[:500])
        raise
    except Exception as e:
        audit(db, user.id, m.id, "OS_USER_DEL", "", "failed", str(e)[:500])
        raise HTTPException(502, str(e))


@router.post("/{mid}/users/{name}/password")
async def set_password(mid: int, name: str, body: dict,
                       db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    if not USER_RE.match(name or ""):
        raise HTTPException(400, "Tên người dùng không hợp lệ")
    password = body.get("password") or ""
    if len(password) < 4:
        raise HTTPException(400, "Mật khẩu tối thiểu 4 ký tự")
    try:
        await _exec(m, f"getent passwd {name} >/dev/null", timeout=15)
        await _exec(m, f"usermod -p '{_hash(password)}' {name}", timeout=20, priv=True)
        audit(db, user.id, m.id, "OS_USER_PASSWD", "", "success", f"passwd {name}")
        return ok(message=f"Đã đổi password cho {name}")
    except Exception as e:
        audit(db, user.id, m.id, "OS_USER_PASSWD", "", "failed", str(getattr(e, "detail", e))[:500])
        raise


@router.post("/{mid}/users/{name}/{action}")
async def lock_user(mid: int, name: str, action: str,
                    db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    if action not in ("lock", "unlock"):
        raise HTTPException(400, "Hành động phải là lock/unlock")
    if not USER_RE.match(name or ""):
        raise HTTPException(400, "Tên người dùng không hợp lệ")
    if name in ("root", m.username):
        raise HTTPException(400, f"Không được khóa '{name}'")
    try:
        await _exec(m, f"passwd -{'l' if action == 'lock' else 'u'} {name}", timeout=20, priv=True)
        audit(db, user.id, m.id, f"OS_USER_{action.upper()}", "", "success", name)
        return ok(message=f"Đã {action} user {name}")
    except Exception as e:
        audit(db, user.id, m.id, f"OS_USER_{action.upper()}", "", "failed", str(e)[:500])
        raise


def _hash(password: str) -> str:
    # SHA-512 crypt ($6$) — máy Linux đích hiểu trực tiếp. Dùng passlib
    # (thuần Python, chạy cả Windows) thay vì module crypt của Unix.
    try:
        from passlib.hash import sha512_crypt
        h = sha512_crypt.using(rounds=5000).hash(password)
    except Exception:
        import crypt  # fallback Unix khi thiếu passlib
        h = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    if "'" in h or len(h) > 256:
        raise HTTPException(500, "Băm mật khẩu thất bại")
    return h
