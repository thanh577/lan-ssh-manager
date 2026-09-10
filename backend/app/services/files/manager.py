"""SFTP file manager with path-traversal guard."""
import asyncssh
import asyncio
import posixpath
from ..ssh.client import build_connect_kwargs
from ..ssh.errors import map_error

MAX_TEXT_BYTES = 512 * 1024


DENY_DELETE_EXACT = frozenset({
    "/", "/bin", "/sbin", "/usr", "/boot", "/proc", "/sys", "/dev",
    "/etc", "/root", "/home", "/var",
})


def _safe_remote_path(base: str, name: str = "") -> str:
    base = base or "/"
    for part in (base, name):
        if "\x00" in (part or ""):
            raise ValueError("Đường dẫn không hợp lệ (ký tự null)")
    if not base.startswith("/"):
        raise ValueError("Đường dẫn phải là tuyệt đối")
    # Strict: reject any ".." segment in user input BEFORE normpath
    # (normpath would silently resolve "/a/../../etc" -> "/etc")
    raw = posixpath.join(base, name) if name else base
    if ".." in [seg for seg in raw.split("/")]:
        raise ValueError("Đã chặn đường dẫn vượt phạm vi cho phép")
    norm = posixpath.normpath(raw)
    if not norm.startswith("/"):
        raise ValueError("Đường dẫn phải là tuyệt đối")
    if ".." in norm.split("/"):
        raise ValueError("Đã chặn đường dẫn vượt phạm vi cho phép")
    return norm


def _deny_destructive(path: str):
    if path in DENY_DELETE_EXACT:
        raise ValueError(f"Từ chối xóa đường dẫn hệ thống được bảo vệ: {path}")


async def _sftp_conn(machine):
    kw = build_connect_kwargs(machine)
    conn = await asyncssh.connect(**kw)
    sftp = await conn.start_sftp_client()
    return conn, sftp


async def list_dir(machine, path: str = "/") -> list[dict]:
    path = _safe_remote_path(path or "/")
    conn, sftp = None, None
    try:
        conn, sftp = await _sftp_conn(machine)
        entries = []
        for name in await sftp.listdir(path):
            try:
                attrs = await sftp.stat(posixpath.join(path, name))
                import stat as statm
                is_dir = statm.S_ISDIR(attrs.permissions) if attrs.permissions else False
                entries.append({"name": name, "size": attrs.size, "is_dir": bool(is_dir),
                                "mtime": int(attrs.mtime or 0), "permissions": oct(attrs.permissions) if attrs.permissions else ""})
            except Exception:
                entries.append({"name": name, "size": 0, "is_dir": False, "mtime": 0, "permissions": ""})
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return entries
    except Exception as e:
        raise map_error(e)
    finally:
        try:
            if sftp: sftp.exit()
        except Exception: pass
        try:
            if conn: conn.close()
        except Exception: pass


async def read_text(machine, path: str) -> str:
    path = _safe_remote_path(path)
    conn, sftp = None, None
    try:
        conn, sftp = await _sftp_conn(machine)
        async with sftp.open(path, "r") as f:
            data = await f.read(MAX_TEXT_BYTES + 1)
        if isinstance(data, bytes):
            text = data.decode("utf-8", errors="replace")
        else:
            text = data or ""
        if len(text.encode("utf-8", errors="ignore")) > MAX_TEXT_BYTES:
            raise ValueError("Tệp quá lớn để sửa (>512KB)")
        return text
    except Exception as e:
        raise map_error(e) if not isinstance(e, ValueError) else e
    finally:
        try:
            if sftp: sftp.exit()
        except Exception: pass
        try:
            if conn: conn.close()
        except Exception: pass


async def write_text(machine, path: str, content: str):
    path = _safe_remote_path(path)
    if len((content or "").encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("Nội dung quá lớn (>2MB)")
    conn, sftp = None, None
    try:
        conn, sftp = await _sftp_conn(machine)
        async with sftp.open(path, "w") as f:
            await f.write(content or "")
    except Exception as e:
        raise map_error(e) if not isinstance(e, ValueError) else e
    finally:
        try:
            if sftp: sftp.exit()
        except Exception: pass
        try:
            if conn: conn.close()
        except Exception: pass


async def mkdir_rm_rename(machine, action: str, path: str, new_path: str = ""):
    path = _safe_remote_path(path)
    if action == "delete":
        _deny_destructive(path)
    conn, sftp = None, None
    try:
        conn, sftp = await _sftp_conn(machine)
        if action == "mkdir":
            await sftp.mkdir(path)
        elif action == "delete":
            try:
                await sftp.remove(path)
            except Exception:
                await sftp.rmdir(path)
        elif action == "rename":
            np = _safe_remote_path(new_path)
            await sftp.rename(path, np)
        else:
            raise ValueError("Hành động không xác định")
    except Exception as e:
        raise map_error(e) if not isinstance(e, ValueError) else e
    finally:
        try:
            if sftp: sftp.exit()
        except Exception: pass
        try:
            if conn: conn.close()
        except Exception: pass
