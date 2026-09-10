import logging
import os
import tempfile


def _log_dir() -> str:
    """Thư mục ghi log: ưu tiên LSM_LOG_DIR, rồi ./logs.
    Không bao giờ crash khi CWD read-only (VD chạy từ AppImage mount
    squashfs) — rớt xuống thư mục tạm vẫn chạy được."""
    for cand in (os.environ.get("LSM_LOG_DIR") or "", "logs"):
        if not cand:
            continue
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".writetest")
            with open(probe, "a"):
                pass
            try:
                os.remove(probe)
            except OSError:
                pass
            return cand
        except OSError:
            continue
    fb = os.path.join(tempfile.gettempdir(), "lan-ssh-manager-logs")
    os.makedirs(fb, exist_ok=True)
    return fb


LOG_DIR = _log_dir()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
# Never log secrets: filter helper
logger = logging.getLogger("lan-ssh-manager")
