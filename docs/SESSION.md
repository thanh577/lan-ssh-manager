# Phiên làm việc — điểm tiếp tục

> File này để hôm sau mở lại là bắt tay ngay, không bàn lại từ đầu.
> Chi tiết từng thay đổi xem `docs/CHANGELOG.md`. Hướng dẫn dùng app xem
> `docs/HUONG_DAN_SU_DUNG.md`. Câu copy-paste để tiếp tục ở cuối file.

## Trạng thái cuối ngày 2026-09-09 (đã TẮT hết, chờ session mới)

- Service `lan-ssh-manager` đang `inactive`, port 8000 đã đóng, không còn
  tiến trình uvicorn app nào, `/tmp/sshman-8000.pid` đã xóa.
- Đã xong trong ngày:
  - Batch B Upload RAM-DoS (`backend/app/api/files.py`): `SpooledTemporaryFile`
    threshold 8MB + stream 8MB/chunk + check `Content-Length` sớm. Đã verify syntax.
  - `sshman`: đã `--install` + thêm `~/.local/bin` vào PATH trong `~/.bashrc`
    (mở terminal mới là gõ được ở mọi nơi).
  - Service `.deb` sửa bind `127.0.0.1` → `0.0.0.0` (`/usr/lib/systemd/system/
    lan-ssh-manager.service`) + `daemon-reload`; web vào được từ LAN.
  - Terminal: font `14 → 18` (+ monospace, giãn dòng 1.35); thêm nút **A−/A+**
    zoom 12–30px, nhớ cỡ chữ vào localStorage, áp dụng live không rớt SSH.
    Frontend đã sync sang `/opt/lan-ssh-manager/frontend/`.
  - `scripts/sshman.sh`: `stop`/`start` đi qua `systemctl` khi service tồn tại
    (trước đây kill PID bị `Restart=on-failure` dựng lại → "port vẫn mở").
    `status` hiện rõ `(systemd)`. Đã `bash -n` OK.
- Lưu ý cho session mới: code chạy là bản `/opt` (service .deb), sửa repo xong
  nhớ `sudo cp frontend/... /opt/lan-ssh-manager/frontend/` + restart service.
  DB hiện có máy test `test`/`test02`/`test03` (thêm khi smoke-test API).
- Máy 01 (192.168.1.51, user `tha`) — xem lại log nếu cần test SSH thật.

- App đang chạy bằng `bash scripts/run.sh` (port 8000). Chưa chuyển sang service .deb.
- Đã xong trong ngày: Feature Audit Batch A (path traversal + XSS, đã verify),
  terminal giữ session khi chuyển tab, Việt hóa toàn app, terminal full cao/rộng,
  lệnh `sshman` (đã cài `~/.local/bin`), Tổng quan có màu sắc,
  đóng gói `.deb` + `.AppImage` trong `ssh_manager/` (`scripts/package.sh`).
- Máy này đã có sudo không mật khẩu (`/etc/sudoers.d/thanhnv`).
- Gói `.deb` 1.0.0 đã `dpkg -i` thành công + chạy thử OK, nhưng service
  `lan-ssh-manager` CHƯA enable/start (tránh đụng port 8000 của `run.sh`).
- Máy 01 (192.168.1.51, user `tha`): sudo NOPASSWD cho
  useradd/userdel/usermod/passwd (`/etc/sudoers.d/lan-ssh-manager`, verified).
- Không còn tiến trình/file/user test nào (port test 8123–8129 đã đóng,
  `/tmp/ai-test`, `/tmp/deb-test`, `squashfs-root` đã xóa; Máy 01 sạch
  `lsmtest`, `bigtest.bin`, `uptest.*`).
- Dự án chưa phải git repo; mọi thay đổi nằm trong file working tree.

## Còn pending (làm tiếp theo thứ tự)

1. **Batch B — Upload RAM-DoS** (`backend/app/api/files.py:73-74,137`): `await f.read()`
   đọc cả file vào RAM rồi mới check size. Sửa: check `Content-Length` trước,
   stream/spool (`SpooledTemporaryFile`), chunked 8MB làm đường mặc định, hạ
   `FILE_UPLOAD_MAX_TOTAL_MB=10240`.
2. **Batch C — Auth/WS/CORS** (`main.py:13` CORS `*` + credentials; `terminal.py:28`
   `int(cols)` crash khi query rác, thiếu check `m.enabled`, thiếu audit
   connect/disconnect + idle-timeout; `auth.py:12` login không rate-limit, JWT 480p).
3. Automated testing (unit + integration với SSH thật).
4. Backup + Restore (`restore.sh` + diễn tập khôi phục thật).
5. Production deploy (dừng `run.sh` → `sudo systemctl enable --now lan-ssh-manager`
   + nginx + docs vận hành) → v1.0.

## Hôm sau bắt đầu bằng câu này (copy-paste)

```
Tiếp tục session theo docs/SESSION.md — làm mục pending tiếp theo.
```
