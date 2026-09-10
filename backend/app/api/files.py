import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.machine import Machine
from ..models.user import User
from .deps import ok, current_user, audit
from ..services.files.manager import list_dir, read_text, write_text, mkdir_rm_rename
from ..services.ssh.client import build_connect_kwargs
from ..services.ssh.errors import map_error
from ..core.config import get_settings
import asyncssh

router = APIRouter(prefix="/api/machines", tags=["files"])

CHUNK_MAX_BYTES = 32 * 1024 * 1024  # 1 chunk request tối đa 32MB (client gửi 8MB/chunk)
_STREAM_BUF = 8 * 1024 * 1024  # đọc/ghi stream từng 8MB — RAM hằng số, SpooledTemporaryFile threshold
_MULTIPART_SLACK = 2 * 1024 * 1024  # trừ hao header multipart khi so Content-Length


def _reject_if_body_too_big(request: Request, limit: int):
    """Từ chối sớm nếu Content-Length vượt giới hạn (chưa đọc body).

    Không tin tuyệt đối (client có thể nói dối/thiếu header) nên vòng stream
    vẫn đếm bytes và cắt khi vượt — đây chỉ là lớp rẻ nhất chặn RAM-DoS.
    """
    try:
        cl = request.headers.get("content-length")
        if cl and int(cl) > limit + _MULTIPART_SLACK:
            raise HTTPException(413, "Tệp quá lớn")
    except ValueError:
        pass


@router.get("/{mid}/files")
async def files_list(mid: int, path: str = "/", db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        entries = await list_dir(m, path)
        return ok({"path": path, "entries": entries})
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502) if not isinstance(e, ValueError) else 400, str(e))


@router.get("/{mid}/files/read")
async def files_read(mid: int, path: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        text = await read_text(m, path)
        return ok({"path": path, "content": text})
    except Exception as e:
        raise HTTPException(400 if isinstance(e, ValueError) else getattr(e, "code", 502), str(e))


@router.post("/{mid}/files/write")
async def files_write(mid: int, body: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        await write_text(m, body.get("path", ""), body.get("content", ""))
        audit(db, user.id, m.id, "FILE_WRITE", body.get("path", "")[:500], "success", "")
        return ok(message="Đã lưu tệp")
    except Exception as e:
        raise HTTPException(400 if isinstance(e, ValueError) else getattr(e, "code", 502), str(e))


@router.post("/{mid}/files/action")
async def files_action(mid: int, body: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        await mkdir_rm_rename(m, body.get("action", ""), body.get("path", ""), body.get("new_path", ""))
        audit(db, user.id, m.id, f"FILE_{str(body.get('action', '')).upper()}", body.get("path", "")[:500], "success", "")
        return ok(message="Xong")
    except Exception as e:
        raise HTTPException(400 if isinstance(e, ValueError) else getattr(e, "code", 502), str(e))


@router.post("/{mid}/files/upload")
async def files_upload(mid: int, remote_path: str, request: Request, f: UploadFile = File(...),
                       db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    limit = get_settings().FILE_UPLOAD_MAX_MB * 1024 * 1024
    _check_remote_path(remote_path)
    # Batch B: từ chối sớm bằng Content-Length (kẻ tấn công gửi header 10GB thì
    # rớt ngay, không tốn RAM/disk chờ đọc body). +2MB slack cho multipart overhead.
    _reject_if_body_too_big(request, limit)
    # Spool tạm file: sao chép content UploadFile vào SpooledTemporaryFile.
    # Lưu RAM cho đến khi vượt _STREAM_BUF, sau đó disk — tránh read() cả file vào RAM.
    spool = tempfile.SpooledTemporaryFile(maxsize=_STREAM_BUF)
    while True:
        chunk = await f.read(_STREAM_BUF)
        if not chunk:
            break
        spool.write(chunk)
    spool.seek(0)
    # Stream từng buf 1MB thẳng ra SFTP — RAM hằng số, không read() cả file.
    total = 0
    try:
        kw = build_connect_kwargs(m)
        async with asyncssh.connect(**kw) as conn:
            async with conn.start_sftp_client() as sftp:
                async with sftp.open(remote_path, "wb") as rf:
                    while True:
                        buf = await spool.read(_STREAM_BUF)
                        if not buf:
                            break
                        total += len(buf)
                        if total > limit:
                            raise HTTPException(413, f"Tệp quá lớn (giới hạn {get_settings().FILE_UPLOAD_MAX_MB}MB cho upload 1-request — dùng upload chunk cho tệp lớn)")
                        await rf.write(buf)
    except HTTPException as he:
        # Dọn file dở khi vượt giới hạn giữa chừng (best-effort).
        if he.status_code == 413 and total > 0:
            try:
                kw2 = build_connect_kwargs(m)
                async with asyncssh.connect(**kw2) as conn2:
                    async with conn2.start_sftp_client() as sftp2:
                        try:
                            await sftp2.remove(remote_path)
                        except Exception:
                            pass
            except Exception:
                pass
        raise
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502), str(e))
    finally:
        try:
            spool.close()
        except Exception:
            pass
        try:
            await f.close()
        except Exception:
            pass
    audit(db, user.id, m.id, "FILE_UPLOAD", remote_path[:500], "success", f"{total} bytes")
    return ok(message=f"Đã tải lên {total} bytes")


def _check_remote_path(remote_path: str):
    if not remote_path or "\x00" in remote_path:
        raise HTTPException(400, "Đường dẫn không hợp lệ")
    if not remote_path.startswith("/"):
        raise HTTPException(400, "Đường dẫn phải là tuyệt đối")
    # Strict: reject any ".." segment (normpath would resolve "/a/../../etc" -> "/etc")
    if ".." in remote_path.split("/"):
        raise HTTPException(400, "Đã chặn đường dẫn vượt phạm vi cho phép")


async def _remote_size(m: Machine, remote_path: str) -> int:
    """Kích thước file đích hiện tại (0 nếu chưa có)."""
    kw = build_connect_kwargs(m)
    try:
        async with asyncssh.connect(**kw) as conn:
            async with conn.start_sftp_client() as sftp:
                try:
                    attrs = await sftp.stat(remote_path)
                    return int(attrs.size or 0)
                except (FileNotFoundError, asyncssh.SFTPNoSuchFile):
                    return 0
    except (FileNotFoundError, asyncssh.SFTPNoSuchFile):
        return 0
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502), str(e))


@router.get("/{mid}/files/upload/status")
async def upload_status(mid: int, remote_path: str, db: Session = Depends(get_db),
                        user: User = Depends(current_user)):
    """Cho client resume: đã nhận được bao nhiêu bytes."""
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    _check_remote_path(remote_path)
    return ok({"remote_path": remote_path, "size": await _remote_size(m, remote_path)})


@router.post("/{mid}/files/upload/chunk")
async def upload_chunk(mid: int, remote_path: str, offset: int, request: Request, f: UploadFile = File(...),
                       db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Nối 1 chunk vào cuối file. offset phải khớp kích thước hiện tại (chống ghi lệch)."""
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    _check_remote_path(remote_path)
    if offset < 0:
        raise HTTPException(400, "Offset không hợp lệ")
    # Batch B: từ chối sớm chunk quá khổ + stream từng 1MB (không read() cả chunk).
    _reject_if_body_too_big(request, CHUNK_MAX_BYTES)
    cap = get_settings().FILE_UPLOAD_MAX_TOTAL_MB * 1024 * 1024
    try:
        kw = build_connect_kwargs(m)
        async with asyncssh.connect(**kw) as conn:
            async with conn.start_sftp_client() as sftp:
                try:
                    cur = int((await sftp.stat(remote_path)).size or 0)
                except (FileNotFoundError, asyncssh.SFTPNoSuchFile):
                    cur = 0
                if offset != cur:
                    raise HTTPException(409, f"Offset lệch (server đang có {cur} bytes)")
                if cur >= cap:
                    raise HTTPException(400, "Vượt giới hạn FILE_UPLOAD_MAX_TOTAL_MB")
                written = 0
                try:
                    async with sftp.open(remote_path, "ab") as rf:
                        while True:
                            buf = await f.read(_STREAM_BUF)
                            if not buf:
                                break
                            written += len(buf)
                            if written > CHUNK_MAX_BYTES:
                                raise HTTPException(413, "Chunk quá lớn (tối đa 32MB)")
                            if cur + written > cap:
                                raise HTTPException(400, "Vượt giới hạn FILE_UPLOAD_MAX_TOTAL_MB")
                            await rf.write(buf)
                except HTTPException:
                    # Cắt phần đã nối dở về đúng cur để resume tiếp được sạch.
                    try:
                        async with sftp.open(remote_path, "r+b") as rf2:
                            try:
                                await rf2.truncate(cur)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    raise
                return ok({"remote_path": remote_path, "size": cur + written})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(getattr(e, "code", 502), str(e))
    finally:
        try:
            await f.close()
        except Exception:
            pass


@router.post("/{mid}/files/upload/complete")
async def upload_complete(mid: int, body: dict, db: Session = Depends(get_db),
                          user: User = Depends(current_user)):
    """Xác nhận file đủ size + ghi audit (1 dòng cho cả file lớn)."""
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    remote_path = body.get("remote_path", "")
    total = int(body.get("total_size") or 0)
    _check_remote_path(remote_path)
    cur = await _remote_size(m, remote_path)
    if total > 0 and cur != total:
        raise HTTPException(409, f"Tệp chưa đủ (có {cur}/{total} bytes) — hãy resume")
    audit(db, user.id, m.id, "FILE_UPLOAD", remote_path[:500], "success", f"{cur} bytes (chunked)")
    return ok({"remote_path": remote_path, "size": cur}, f"Đã tải lên xong {cur} bytes")
