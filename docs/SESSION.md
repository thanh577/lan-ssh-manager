# Phiên làm việc — điểm tiếp tục

> File này để hôm sau mở lại là bắt tay ngay, không bàn lại từ đầu.
> Chi tiết từng thay đổi xem `docs/CHANGELOG.md`. Hướng dẫn dùng app xem
> `docs/HUONG_DAN_SU_DUNG.md`. Câu copy-paste để tiếp tục ở cuối file.

## Trạng thái cuối ngày 2026-09-15 (đã push GitHub, chờ session mới)

- Repo `thanh577/lan-ssh-manager` nhánh `main` (local sạch, đã push).
  Secret/binary/venv/db/log đều chặn khỏi git; binary phát hành qua
  GitHub Releases/Artifacts.
- Đóng gói 1.2.5: `.deb` + `.AppImage` build OK, `apt install` + service
  health + login OK. Frontend có favicon inline.
- Exe Windows chạy OK (user xác nhận): `gui/app_win.py` + workflow
  Actions `Build Windows exe` (test headless rồi build, tải ở Artifacts).
  Token GitHub cần scope `repo` + `workflow`.
- Tab Giải trí: Dailymotion + YouTube (`api/youtube.py`, `youtube.js`),
  tìm kiếm toàn cục ở tab Xem, mini player phát nền khi chuyển tab.
- Batch B (Upload RAM-DoS) xong từ 09-09.
- Máy này đã có sudo không mật khẩu (`/etc/sudoers.d/thanhnv`).
- Máy 01 (192.168.1.51, user `tha`): sudo NOPASSWD cho
  useradd/userdel/usermod/passwd (`/etc/sudoers.d/lan-ssh-manager`, verified).
- Lưu ý: `passlib` thay `crypt` cho hash password user Linux (chạy được
  cả Windows, cùng hash `$6$`); `main.py` version vẫn `1.1.0` trong khi
  gói đã `1.2.5` (chưa đồng bộ).

## Còn pending (làm tiếp theo thứ tự)

1. **Batch C — Auth/WS/CORS** (`main.py:13` CORS `*` + credentials; `terminal.py:28`
   `int(cols)` crash khi query rác, thiếu check `m.enabled`, thiếu audit
   connect/disconnect + idle-timeout; `auth.py:12` login không rate-limit, JWT 480p).
2. Automated testing (unit + integration với SSH thật).
3. Backup + Restore (`restore.sh` + diễn tập khôi phục thật).
4. Production deploy (dừng `run.sh` → `sudo systemctl enable --now lan-ssh-manager`
   + nginx + docs vận hành).

## Hôm sau bắt đầu bằng câu này (copy-paste)

```
Tiếp tục session theo docs/SESSION.md — làm mục pending tiếp theo.
```
