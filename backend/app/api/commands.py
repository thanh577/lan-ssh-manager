from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.machine import Machine
from ..models.user import User
from ..schemas.command import CommandIn, BatchIn
from .deps import ok, current_user, audit
from ..services.commands.executor import execute, execute_batch

router = APIRouter(tags=["commands"])


@router.post("/api/machines/{mid}/command")
async def run_single(mid: int, body: CommandIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.query(Machine).filter(Machine.id == mid).first()
    if not m:
        raise HTTPException(404, "Không tìm thấy máy")
    try:
        r = await execute(m, body.command, timeout=body.timeout)
        audit(db, user.id, m.id, "COMMAND", body.command[:2000],
              "success" if r["exit_code"] == 0 else f"exit={r['exit_code']}",
              (r.get("stdout") or "")[:500])
        return ok(r)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        audit(db, user.id, m.id, "COMMAND", body.command[:2000], "failed", str(e)[:1000])
        msg = str(e)
        code = getattr(e, "code", 502)
        raise HTTPException(code, msg)


@router.post("/api/commands/batch")
async def run_batch(body: BatchIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not body.machine_ids:
        raise HTTPException(400, "Chưa chọn máy nào")
    machines = db.query(Machine).filter(Machine.id.in_(body.machine_ids)).all()
    if not machines:
        raise HTTPException(404, "Không tìm thấy máy nào")
    results = await execute_batch(machines, body.command, timeout=body.timeout)
    ok_count = sum(1 for r in results if r["success"])
    audit(db, user.id, None, "BATCH_COMMAND", body.command[:2000],
          f"{ok_count}/{len(results)} ok", f"targets={[m.name for m in machines]}"[:1000])
    return ok({"results": results, "summary": {"total": len(results), "ok": ok_count,
                                              "failed": len(results) - ok_count}})
