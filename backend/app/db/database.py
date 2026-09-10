from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

from ..core.config import get_settings

Base = declarative_base()
_engine = None
_SessionLocal = None


def _db_path_from_url(url: str) -> str | None:
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    return None


def get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        connect_args = {"check_same_thread": False} if s.DATABASE_URL.startswith("sqlite") else {}
        p = _db_path_from_url(s.DATABASE_URL)
        if p:
            d = os.path.dirname(os.path.abspath(p))
            if d:
                os.makedirs(d, exist_ok=True)
        _engine = create_engine(s.DATABASE_URL, connect_args=connect_args, future=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal


def get_db():
    Session = get_session_factory()
    db = Session()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # import models so tables register
    from ..models import user, machine, group, audit, console  # noqa
    Base.metadata.create_all(bind=get_engine())
    # seed admin
    from ..models.user import User
    from ..core.security import hash_password
    from ..core.config import get_settings as gs
    Session = get_session_factory()
    db = Session()
    try:
        if not db.query(User).filter(User.username == gs().ADMIN_USERNAME).first():
            db.add(User(username=gs().ADMIN_USERNAME,
                        password_hash=hash_password(gs().ADMIN_PASSWORD),
                        is_active=True))
            db.commit()
    finally:
        db.close()
