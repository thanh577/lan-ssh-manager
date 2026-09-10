from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from ..db.database import Base


class Machine(Base):
    __tablename__ = "machines"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    hostname = Column(String(255), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(128), nullable=False)
    auth_type = Column(String(16), default="password")  # password | key
    credential_encrypted = Column(String(4096), default="")
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    description = Column(String(512), default="")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=True)
