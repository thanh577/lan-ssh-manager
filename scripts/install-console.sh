#!/bin/bash
# Cài console client `lsm` cho máy headless / không có trình duyệt.
# Chỉ cần python3 (không pip, không venv, không root bắt buộc).
#
#   bash scripts/install-console.sh                 # cài cho user hiện tại
#   sudo bash scripts/install-console.sh --system   # cài chung /usr/local/bin
set -e
cd "$(dirname "$0")/.."
SRC="$PWD/console/lsm.py"
[ -f "$SRC" ] || { echo "!! Không thấy $SRC"; exit 1; }
python3 -m py_compile "$SRC" && echo "==> py_compile OK"

DEST=""
if [ "${1:-}" = "--system" ]; then
  DEST="/usr/local/bin/lsm"
  cp "$SRC" "$DEST" && chmod +x "$DEST"
else
  DEST="$HOME/.local/bin/lsm"
  mkdir -p "$HOME/.local/bin"
  cp "$SRC" "$DEST" && chmod +x "$DEST"
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "!! Thêm vào ~/.bashrc: export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
  esac
fi
echo "==> Đã cài: $DEST"
"$DEST" --help | head -8
echo "==> Dùng: lsm login --url http://<IP-server>:8000 -u admin && lsm menu"
