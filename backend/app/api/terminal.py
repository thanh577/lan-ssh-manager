from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from ..db.database import get_session_factory
from ..models.machine import Machine
from ..core.security import decode_token
from ..models.user import User
from ..services.terminal.session import bridge

router = APIRouter(tags=["terminal"])


@router.websocket("/ws/terminal/{mid}")
async def terminal_ws(websocket: WebSocket, mid: int):
    # token via query ?token=... (xterm JS cannot set headers)
    token = websocket.query_params.get("token", "")
    username = decode_token(token) if token else None
    if not username:
        await websocket.close(code=4401)
        return
    Session = get_session_factory()
    db = Session()
    try:
        u = db.query(User).filter(User.username == username).first()
        m = db.query(Machine).filter(Machine.id == mid).first()
        if not u or not u.is_active or not m:
            await websocket.close(code=4404)
            return
        cols = int(websocket.query_params.get("cols", 120))
        rows = int(websocket.query_params.get("rows", 32))
        await bridge(websocket, m, cols=cols, rows=rows)
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
