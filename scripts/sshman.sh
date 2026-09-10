#!/bin/bash
# sshman — gõ ở BẤT CỨ ĐÂU để điều khiển LAN SSH Manager.
#
#   sshman              → menu tương tác: 1.Start  2.Stop  3.Restart  4.Status  5.Logs
#   sshman start        → khởi động app (chạy nền) + mở web
#   sshman stop         → dừng app (kể cả server start thủ công)
#   sshman restart      → khởi động lại + mở web
#   sshman status       → xem app đang chạy hay không
#   sshman logs         → xem log app (tail -f)
#   sshman --install    → tạo lệnh `sshman` trong ~/.local/bin (chỉ cần làm 1 lần)
#
# Đổi port: PORT=9000 sshman
#
# 2 chế độ tự nhận diện:
#  - repo: chạy từ source clone (venv ở backend/venv, config .env tại root)
#  - deb:  cài từ gói .deb (code ở /opt/lan-ssh-manager, config dùng
#          /etc/lan-ssh-manager/.env, data ở /var/lib/... hoặc ~/.local/share/...)
set -e

# Tìm đúng thư mục project kể cả khi được gọi qua symlink ~/.local/bin/sshman
SRC="${BASH_SOURCE[0]}"
while [ -L "$SRC" ]; do SRC="$(readlink "$SRC")"; done
SCRIPT="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"
ROOT="$(cd "$(dirname "$SCRIPT")/.." && pwd)"

MODE="repo"
if [ ! -f "$ROOT/backend/requirements.txt" ] && [ -d /opt/lan-ssh-manager/backend/app ]; then
  MODE="deb"; ROOT="/opt/lan-ssh-manager"
fi

if [ "$MODE" = deb ]; then
  export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
  if [ -d /var/lib/lan-ssh-manager ] && [ -w /var/lib/lan-ssh-manager ]; then
    WORKDIR=/var/lib/lan-ssh-manager
  else
    WORKDIR="$HOME/.local/share/lan-ssh-manager"
  fi
  APPCD="$WORKDIR"
  LOGFILE="$WORKDIR/logs/sshman.log"
else
  APPCD="$ROOT"
  LOGFILE="$ROOT/logs/sshman.log"
fi
PYBIN="$ROOT/backend/venv/bin/python"

PORT="${PORT:-8000}"
PIDFILE="/tmp/sshman-${PORT}.pid"

lan_ip() { hostname -I 2>/dev/null | awk '{print $1}'; }
url() { echo "http://$(lan_ip || echo localhost):${PORT}"; }

is_running() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

# Service systemd (gói .deb) chạy cố định ở port 8000, có Restart=on-failure:
# giết PID thủ công sẽ bị systemd dựng lại ngay, nên phải stop/start qua systemctl.
svc_unit_exists() {
  [ "${PORT}" = "8000" ] && systemctl list-unit-files lan-ssh-manager.service 2>/dev/null | grep -q "lan-ssh-manager.service"
}
svc_active() {
  svc_unit_exists && systemctl is-active --quiet lan-ssh-manager 2>/dev/null
}

port_open() {
  curl -s -m 2 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null | grep -q '"status":"ok"'
}

open_web() {
  local u; u="$(url)"
  echo "==> Mở web: $u"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$u" >/dev/null 2>&1 &
  else
    echo "(không tìm thấy xdg-open — tự mở trình duyệt với địa chỉ trên)"
  fi
}

do_start() {
  if is_running || port_open; then
    echo "==> App đã chạy (port ${PORT})."
    open_web
    return 0
  fi
  # Nếu có service systemd (port 8000 mặc định): start qua service để 1 đầu mối quản lý.
  if svc_unit_exists; then
    echo "==> Khởi động qua systemd (lan-ssh-manager)..."
    sudo systemctl start lan-ssh-manager || { echo "!! Không start được service — xem: sudo systemctl status lan-ssh-manager"; return 1; }
    local i=0
    while [ $i -lt 25 ]; do
      if port_open; then break; fi
      sleep 1; i=$((i + 1))
    done
    if port_open; then
      echo "==> App đã chạy (systemd). Tài khoản mặc định: admin/admin123"
      open_web
    else
      echo "!! App chưa lên sau 25s — xem: sudo journalctl -u lan-ssh-manager -n 50"
      return 1
    fi
    return 0
  fi
  cd "$APPCD"
  mkdir -p data logs
  if [ "$MODE" = deb ]; then
    if [ ! -f .env ]; then
      if [ -r /etc/lan-ssh-manager/.env ]; then
        cp /etc/lan-ssh-manager/.env .env && chmod 600 .env
      else
        cp "$ROOT/.env.example" .env
      fi
      echo "==> Config: $APPCD/.env"
    fi
  else
    [ -f .env ] || cp .env.example .env
  fi
  if [ ! -x "$PYBIN" ]; then
    if [ "$MODE" = deb ]; then
      echo "!! Chưa có venv $PYBIN — cài lại gói .deb (postinst sẽ dựng venv)."
      return 1
    fi
    echo "==> Tạo venv lần đầu..."
    python3 -m venv backend/venv
  fi
  if [ -w "$ROOT" ]; then
    echo "==> Kiểm tra thư viện..."
    "$PYBIN" -m pip install -q -r "$ROOT/backend/requirements.txt"
  else
    echo "==> Dùng venv sẵn của gói .deb (không pip vì $ROOT chỉ đọc)."
  fi
  echo "==> Khởi động app (log: $LOGFILE)..."
  # shellcheck disable=SC2086
  nohup bash -c "cd '$APPCD' && exec '$PYBIN' -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT" >>"$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  local i=0
  while [ $i -lt 25 ]; do
    if port_open; then break; fi
    sleep 1; i=$((i + 1))
  done
  if port_open; then
    echo "==> App đã chạy (PID $(cat "$PIDFILE")). Tài khoản mặc định: admin/admin123"
    open_web
  else
    echo "!! App chưa lên sau 25s — xem log: tail -50 $LOGFILE"
    return 1
  fi
}

do_stop() {
  # Dừng service systemd trước (nếu đang active): giết PID thủ công sẽ bị Restart=on-failure dựng lại.
  if svc_active; then
    echo "==> Dừng service systemd (lan-ssh-manager)..."
    sudo systemctl stop lan-ssh-manager || true
    sleep 2
  fi
  if is_running; then
    echo "==> Dừng app (PID $(cat "$PIDFILE"))..."
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    sleep 2
    if is_running; then kill -9 "$(cat "$PIDFILE")" 2>/dev/null || true; fi
    rm -f "$PIDFILE"
  else
    rm -f "$PIDFILE"
  fi
  # Dọn cả server start thủ công (setsid/run.sh foreground) không có pidfile
  local stray
  stray="$(pgrep -f "uvicorn backend.app.main:app.*--port ${PORT}" 2>/dev/null || true)"
  if [ -n "$stray" ]; then
    echo "==> Dừng tiến trình sót: $stray"
    # shellcheck disable=SC2086
    kill $stray 2>/dev/null || true
    sleep 2
    stray="$(pgrep -f "uvicorn backend.app.main:app.*--port ${PORT}" 2>/dev/null || true)"
    [ -n "$stray" ] && kill -9 $stray 2>/dev/null || true
  fi
  if port_open; then
    echo "!! Port ${PORT} vẫn mở — kiểm tra tiến trình khác đang giữ port."
    return 1
  fi
  echo "==> Đã dừng."
}

do_status() {
  if svc_active; then echo "App ĐANG CHẠY (systemd) — $(url)";
  elif is_running || port_open; then echo "App ĐANG CHẠY — $(url)"; else echo "App CHƯA chạy. Gõ: sshman"; fi
}

show_menu() {
  while true; do
    echo ""
    echo "=== LAN SSH Manager — $(url) ==="
    do_status
    echo " 1. Start server"
    echo " 2. Stop server"
    echo " 3. Restart server"
    echo " 4. Status"
    echo " 5. Xem logs"
    echo " 0. Thoát"
    read -rp "Chọn [0-5]: " c
    case "$c" in
      1) do_start ;;
      2) do_stop ;;
      3) do_stop; do_start ;;
      4) do_status ;;
      5) tail -f "$LOGFILE" ;;
      0|q|quit|exit) break ;;
      *) echo "Chọn số 0-5." ;;
    esac
  done
}

do_install() {
  if [ "$MODE" = deb ]; then
    echo "==> Chế độ deb: lệnh \`sshman\` đã có sẵn tại /usr/bin/sshman từ gói .deb."
    return 0
  fi
  mkdir -p "$HOME/.local/bin"
  ln -sf "$SCRIPT" "$HOME/.local/bin/sshman"
  echo "==> Đã tạo lệnh \`sshman\` → $SCRIPT"
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) echo "==> ~/.local/bin đã có trong PATH — mở terminal mới và gõ: sshman" ;;
    *) echo "!! ~/.local/bin CHƯA có trong PATH — thêm dòng này vào ~/.bashrc rồi mở terminal mới:"
       echo "   export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
  esac
}

case "${1:-}" in
  "")           show_menu ;;
  start)        do_start ;;
  stop)         do_stop ;;
  restart)      do_stop; do_start ;;
  status)       do_status ;;
  logs)         tail -f "$LOGFILE" ;;
  --install|-i) do_install ;;
  *) echo "Dùng: sshman [start|stop|restart|status|logs|--install] (không tham số = menu)"; exit 1 ;;
esac
