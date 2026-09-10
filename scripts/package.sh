#!/bin/bash
# Đóng gói LAN SSH Manager → ssh_manager/lan-ssh-manager_*.deb + *.AppImage
#   bash scripts/package.sh
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/ssh_manager"
VER="${VER:-1.2.4}"
ARCH_DEB="amd64"

mkdir -p "$OUT"
echo "==> Version: $VER | Out: $OUT"

# ---- payload chung: code + frontend (loại venv/db/log/cache) ----
stage_payload() { # $1 = dest dir
  local d="$1"
  mkdir -p "$d"
  tar -C "$ROOT" \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='backend/venv' \
    -cf - backend/app backend/requirements.txt frontend gui .env.example \
    | tar -xf - -C "$d"
}

# ============================== .deb ==============================
build_deb() {
  echo "==> Build .deb..."
  local pkg=/tmp/lsm-deb-pkg
  rm -rf "$pkg"
  mkdir -p "$pkg/DEBIAN" "$pkg/opt/lan-ssh-manager" \
           "$pkg/usr/bin" "$pkg/etc/lan-ssh-manager" \
           "$pkg/lib/systemd/system"

  stage_payload "$pkg/opt/lan-ssh-manager"

  # config mẫu -> /etc (giữ quyền 600, khai báo conffiles)
  cp "$ROOT/.env.example" "$pkg/etc/lan-ssh-manager/.env"
  chmod 600 "$pkg/etc/lan-ssh-manager/.env"

  cat > "$pkg/DEBIAN/control" <<EOF
Package: lan-ssh-manager
Version: $VER
Section: net
Priority: optional
Architecture: $ARCH_DEB
Depends: python3 (>= 3.10), python3-venv, python3-pip, curl
Maintainer: LAN SSH Manager <admin@lan>
Description: Quan ly may LAN qua SSH (khong can agent)
 Web app tu host trong LAN: quan ly may qua SSH, web terminal
 realtime, command/batch, files SFTP, services, logs, audit,
 serial console cai OS cho may chua co he dieu hanh.
 Chay 1 port duy nhat (mac dinh 8000) + systemd service.
EOF
  echo "/etc/lan-ssh-manager/.env" > "$pkg/DEBIAN/conffiles"

  cat > "$pkg/DEBIAN/postinst" <<'EOF'
#!/bin/bash
set -e
APP=/opt/lan-ssh-manager
if [ ! -x "$APP/venv/bin/python" ]; then
  python3 -m venv "$APP/venv"
fi
"$APP/venv/bin/pip" install -q -r "$APP/backend/requirements.txt"
chmod 600 /etc/lan-ssh-manager/.env || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload || true
fi
echo "------------------------------------------------------------------"
echo " lan-ssh-manager da cai xong."
echo " 1) Sua cau hinh:  sudo nano /etc/lan-ssh-manager/.env"
echo "    (doi APP_SECRET_KEY, APP_ENCRYPTION_KEY, ADMIN_PASSWORD)"
echo " 2) Chay service:  sudo systemctl enable --now lan-ssh-manager"
echo "    Mo: http://<LAN-IP>:8000"
echo "------------------------------------------------------------------"
EOF
  cat > "$pkg/DEBIAN/prerm" <<'EOF'
#!/bin/bash
set -e
if [ "$1" = remove ] && command -v systemctl >/dev/null 2>&1; then
  systemctl stop lan-ssh-manager || true
  systemctl disable lan-ssh-manager || true
fi
EOF
  chmod 755 "$pkg/DEBIAN/postinst" "$pkg/DEBIAN/prerm"

  # launcher chay tay
  cat > "$pkg/usr/bin/lan-ssh-manager" <<'EOF'
#!/bin/bash
# Chay thu LAN SSH Manager (foreground). Service chinh: systemd lan-ssh-manager.
set -e
APP=/opt/lan-ssh-manager
exec "$APP/venv/bin/python" -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
EOF
  chmod 755 "$pkg/usr/bin/lan-ssh-manager"

  # sshman: menu Start/Stop/Restart/Status/Logs (tự nhận chế độ deb khi ở /usr/bin)
  cp "$ROOT/scripts/sshman.sh" "$pkg/usr/bin/sshman"
  chmod 755 "$pkg/usr/bin/sshman"

  # systemd service (DynamicUser: khong can tao user tay)
  # Serial console can cham /dev/ttyUSB*... nen mo PrivateDevices + nhom dialout.
  cat > "$pkg/lib/systemd/system/lan-ssh-manager.service" <<'EOF'
[Unit]
Description=LAN SSH Manager (quan ly may LAN qua SSH)
After=network.target

[Service]
Type=simple
DynamicUser=yes
StateDirectory=lan-ssh-manager
WorkingDirectory=/var/lib/lan-ssh-manager
Environment=PYTHONPATH=/opt/lan-ssh-manager
EnvironmentFile=-/etc/lan-ssh-manager/.env
ExecStart=/opt/lan-ssh-manager/venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3
# Cho phep serial console (cai OS may chua co HDH qua cong console vat ly)
PrivateDevices=no
SupplementaryGroups=dialout
DeviceAllow=/dev/ttyUSB* rw
DeviceAllow=/dev/ttyACM* rw
DeviceAllow=/dev/ttyS* rw
DeviceAllow=/dev/pts/* rw

[Install]
WantedBy=multi-user.target
EOF

  dpkg-deb --build "$pkg" "$OUT/lan-ssh-manager_${VER}_${ARCH_DEB}.deb"
  echo "==> Xong .deb: $OUT/lan-ssh-manager_${VER}_${ARCH_DEB}.deb"
}

# ============================ AppImage ============================
build_appimage() {
  echo "==> Build AppImage..."
  local work=/tmp/lsm-appimage
  rm -rf "$work"
  mkdir -p "$work/AppDir/usr/share/lan-ssh-manager" "$work/AppDir/usr/lib/pythonlibs"

  stage_payload "$work/AppDir/usr/share/lan-ssh-manager"

  echo "==> pip install --target (can mang)..."
  python3 -m pip install -q --break-system-packages \
    --target "$work/AppDir/usr/lib/pythonlibs" \
    -r "$ROOT/backend/requirements.txt"

  # icon PNG 256x256 (ve bang stdlib: nen toi + cua so terminal xanh)
  python3 - "$work/AppDir/lan-ssh-manager.png" <<'EOF'
import struct, sys, zlib
W = H = 256
px = bytearray()
for y in range(H):
    for x in range(W):
        r = x / (W - 1); rr = int(15 + 30 * r); gg = int(23 + 20 * r); bb = int(42 + 40 * r)
        in_win = 48 <= x < 208 and 64 <= y < 192
        title = 48 <= x < 208 and 64 <= y < 92
        if title: rr, gg, bb = 30, 58, 95
        elif in_win: rr, gg, bb = 2, 6, 18
        dot = None
        for i, dx in enumerate((66, 84, 102)):
            if (x - dx) ** 2 + (y - 78) ** 2 < 36: dot = [(239, 68, 68), (249, 115, 22), (34, 197, 94)][i]
        if dot: rr, gg, bb = dot
        prompt = 66 <= x < 120 and 118 <= y < 126
        cursor = 128 <= x < 142 and 118 <= y < 140
        if prompt or cursor: rr, gg, bb = 74, 222, 128
        px += bytes((rr, gg, bb))
raw = b"".join(b"\x00" + bytes(px[y * W * 3:(y + 1) * W * 3]) for y in range(H))
def chunk(t, d):
    c = t + d
    return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")
open(sys.argv[1], "wb").write(png)
print("icon ok")
EOF

  cat > "$work/AppDir/lan-ssh-manager.desktop" <<'EOF'
[Desktop Entry]
Name=LAN SSH Manager
Comment=Quan ly may LAN qua SSH (khong can agent)
Exec=lan-ssh-manager
Icon=lan-ssh-manager
Categories=Network;System;Utility;
Terminal=false
Type=Application
StartupNotify=false
EOF

  cat > "$work/AppDir/AppRun" <<'EOF'
#!/bin/bash
# LAN SSH Manager AppImage:
#  - Có màn hình (X/Wayland + tkinter): mở panel điều khiển GUI
#    (Start/Stop/Restart server, trạng thái, Mở Web, Ẩn, Thoát + log).
#  - Không màn hình: chạy server + tự mở trình duyệt như cũ. Ctrl+C để dừng.
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$HERE/usr/lib/pythonlibs:$HERE/usr/share/lan-ssh-manager"
DATA="${LAN_SSH_DATA:-$HOME/.local/share/lan-ssh-manager}"
mkdir -p "$DATA"
export LAN_SSH_DATA="$DATA"
export DATABASE_URL="sqlite:///$DATA/lan_ssh_manager.db"
PORT="${PORT:-8000}"
export PORT
GUI="$HERE/usr/share/lan-ssh-manager/gui/control.py"
if { [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; } && [ -f "$GUI" ] \
   && python3 -c "import tkinter" 2>/dev/null; then
  echo "==> Mở panel điều khiển LAN SSH Manager..."
  exec python3 "$GUI"
fi
echo "==> Không có màn hình/tkinter — chạy headless (log vẫn hiện ở terminal)."
cd "$DATA"
echo "==> LAN SSH Manager (AppImage) — data: $DATA"
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT" &
SRV=$!
cleanup() { kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; }
trap cleanup INT TERM
for i in $(seq 1 25); do
  curl -s -m 2 "http://127.0.0.1:${PORT}/api/health" 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 1
done
LANIP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "==> Mo web: http://${LANIP:-localhost}:${PORT}  (admin/admin123 lan dau)"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://${LANIP:-localhost}:${PORT}" >/dev/null 2>&1 &
fi
wait "$SRV"
EOF
  chmod +x "$work/AppDir/AppRun"

  local tool=/tmp/appimagetool-x86_64.AppImage
  if [ ! -x "$tool" ]; then
    echo "==> Tai appimagetool (can mang)..."
    curl -sSL -o "$tool" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$tool"
  fi
  (cd "$work" && ARCH=x86_64 "$tool" AppDir "$OUT/LAN-SSH-Manager-${VER}-x86_64.AppImage")
  chmod +x "$OUT/LAN-SSH-Manager-${VER}-x86_64.AppImage"
  echo "==> Xong AppImage: $OUT/LAN-SSH-Manager-${VER}-x86_64.AppImage"
}

build_deb
build_appimage
# Build xong cả 2 mới xóa bản cũ — chỉ giữ đúng VER vừa build.
clean_old() {
  local f keep=0
  for f in "$OUT"/lan-ssh-manager_*_"$ARCH_DEB".deb \
           "$OUT"/LAN-SSH-Manager-*-x86_64.AppImage; do
    [ -e "$f" ] || continue
    case "$f" in
      *"_${VER}_"*|*"-$VER-"*) keep=$((keep + 1)) ;;
      *) echo "==> Xóa bản cũ: $(basename "$f")"; rm -f "$f" ;;
    esac
  done
  [ "$keep" -ge 2 ] || { echo "!! Thiếu file bản $VER sau build — giữ nguyên bản cũ"; return 1; }
}
clean_old
echo "==> TAT CA XONG. File trong $OUT:"
rtk ls -la "$OUT"
