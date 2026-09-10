from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from ..db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    action = Column(String(64), nullable=False)
    command = Column(String(2048), default="")
    status = Column(String(32), default="")
    output_summary = Column(String(1024), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
