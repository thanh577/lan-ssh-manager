from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from ..db.database import Base


class SerialConsole(Base):
    """Ánh xạ 1 cổng serial vật lý trên máy chủ app tới 1 máy đích
    (máy chưa có OS — điều khiển qua console để cài đặt)."""
    __tablename__ = "serial_consoles"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)          # tên gợi nhớ, vd "Máy 04 - console"
    device = Column(String(128), nullable=False)        # vd /dev/ttyUSB0
    baudrate = Column(Integer, default=115200)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    description = Column(String(512), default="")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
