# Nhật ký thay đổi LAN SSH Manager

> Quy ước: mỗi lần sửa app (tính năng, fix bug, đổi config mặc định) đều ghi thêm
> mục mới **lên đầu** file này, ghi ngày + nội dung + file liên quan.

## 2026-09-09 — Batch B RAM-DoS + font/zoom terminal + sshman hiểu systemd

- Batch B (`backend/app/api/files.py`): upload 1-request spool qua
  `SpooledTemporaryFile` (threshold 8MB, tràn ra disk), stream 8MB/chunk ra
  SFTP, giữ check `Content-Length` sớm + giới hạn 50MB/10GB. `_STREAM_BUF`
  1MB → 8MB. `python3 -m py_compile` OK.
- Terminal font `14 → 18` (monospace + lineHeight 1.35) cho cả SSH lẫn console;
  toàn app: body 16px, bảng 15px, `pre.out` 14px (`frontend/app.js`,
  `frontend/styles.css`). Thêm nút **A−/A+** zoom 12–30px (bước 2px), lưu
  `localStorage`, áp dụng live qua `setOption` + `fit()` + resize pty, không
  rớt session. `node --check` OK.
- `scripts/sshman.sh`: `stop`/`start` qua `systemctl` khi unit
  `lan-ssh-manager` tồn tại (fix bệnh kill PID bị `Restart=on-failure` dựng
  lại → "Port 8000 vẫn mở"); `status` báo `(systemd)`. `bash -n` OK.
- Vận hành: `~/.local/bin` đã vào PATH (`~/.bashrc`); service sửa bind
  `127.0.0.1` → `0.0.0.0` (file unit + `daemon-reload`), health + LAN OK.
  Frontend đã sync `/opt/lan-ssh-manager/frontend/` + restart service.
  Cuối phiên: `systemctl stop`, port 8000 đóng, sạch tiến trình/pidfile.

## 2026-09-07 — Sửa 2 lỗi GUI từ log user gửi + Stop không giết nhầm server (gói 1.2.3)

- Log user dán cho thấy bệnh thật: backend crash `OSError: Read-only file
  system: 'logs'` vì panel chạy server với CWD=APP_ROOT (mount AppImage
  read-only), trong khi bản headless cũ `cd` sang DATA nên thoát. Sửa:
  `logging_conf.py` không crash khi CWD read-only (thử `LSM_LOG_DIR` →
  `./logs` → fallback `/tmp/lan-ssh-manager-logs`); panel chạy server với
  `cwd=DATA` + chèn `APP_ROOT` vào `PYTHONPATH` của tiến trình con.
- Chuột phải trên khung log: menu Copy đoạn đã chọn / Copy tất cả / Xóa
  (+ Ctrl+C). Lý do start thất bại giờ lấy từ dòng lỗi thật của tiến trình
  con (thiếu thư viện / read-only / port bận) thay vì đoán mò.
- Bug nghiêm trọng lòi ra khi đọc log: nút **Stop đã giết nhầm server chính**
  của máy (cùng port 8000, khác DATA) qua `_kill_strays`. Sửa: tiến trình con
  đánh dấu `LAN_SSH_DATA` vào environ, Stop mặc định chỉ dọn cùng DATA;
  gặp server lạ thì hỏi xác nhận (Yes/No) mới dừng; không xác nhận trả về
  `foreign-running`. Có test hồi quy trong `--selftest`.
- Verify: fallback log từ CWD read-only PASS; selftest Xvfb (system python,
  assert cwd con == DATA + copy handler + foreign còn sống sau Stop) PASS;
  AppImage 1.2.3 nhánh headless + GUI đều lên, payload md5 khớp repo;
  `dpkg -i` 1.2.3 OK. Hậu quả đã khắc phục: start lại server chính bằng
  `sshman` (health OK). Không động vào phiên AppImage user đang mở.

## 2026-09-07 — Đóng gói tự xóa bản cũ, chỉ giữ bản mới nhất

- `scripts/package.sh`: sau khi build xong cả `.deb` + `.AppImage` mới tự
  xóa bản cũ trong `ssh_manager/` (chỉ giữ đúng VER vừa build; build lỗi thì
  không xóa gì). Dọn tay hiện tại: chỉ còn 1.2.1 (xóa 1.2.0).

## 2026-09-07 — Sửa lỗi GUI không start được server + resize/copy log (gói 1.2.1)

- Nguyên nhân start thất bại: panel chạy bằng system `python3` (không có
  deps), còn thư viện chỉ nằm trong `backend/venv` → tiến trình server chết
  ngay, panel chỉ hiện "failed" chung chung. Sửa `gui/control.py`:
  `find_server_python()` ưu tiên venv của app (kiểm tra import thật),
  log ghi rõ đang dùng python nào, thất bại thì hiện lý do + popup lỗi.
- Cửa sổ cho resize tự do (`minsize` giữ), khung log thêm nút **📋 Copy log**
  (vào clipboard) và **🗑 Xóa**.
- Verify: selftest Xvfb chạy bằng system python (không deps) PASS qua venv
  fallback; đường lỗi cưỡng bức cũng trả lý do rõ ràng. Rebuild
  `lan-ssh-manager_1.2.1_amd64.deb` + `LAN-SSH-Manager-1.2.1-x86_64.AppImage`,
  AppImage nhánh headless + GUI đều lên, `dpkg -i` OK (md5 gui khớp repo).
- Phát hiện khi verify: audit có 2 `DELETE_MACHINE` lúc ~14:45 (Máy 02, 03 —
  không phải do trợ lý làm, các lệnh test chỉ đụng bảng consoles). Hiện DB
  còn 1 máy. Chưa có backup nào (`backup/` trống) nên không khôi phục được —
  nên chạy `bash scripts/backup.sh` định kỳ.

## 2026-09-07 — AppImage 1.2.0 có panel GUI (Start/Stop/Restart/Trạng thái/Ẩn/Thoát)

- Mới `gui/control.py` (tkinter, stdlib-only): các nút Start/Stop/Restart/Mở
  Web/Ẩn (minimize taskbar)/Thoát, đèn trạng thái 🟢/🔴 + URL, khung log
  server, notify desktop; tự dọn tiến trình start tay cùng port khi Stop.
  `AppRun` mở GUI khi có màn hình + tkinter, ngược lại chạy headless như cũ.
- `scripts/package.sh` VER mặc định 1.2.0, payload thêm `gui/`. File mới:
  `lan-ssh-manager_1.2.0_amd64.deb` (95KB), `LAN-SSH-Manager-1.2.0-x86_64.AppImage`.
- Verify: logic start/stop headless PASS; GUI `--selftest` dưới Xvfb PASS;
  AppImage thật: nhánh headless (không DISPLAY) lên + health OK, nhánh GUI
  (xvfb) hiện đúng `gui/control.py` từ payload (md5 khớp repo); `dpkg -i`
  1.2.0 OK, service vẫn inactive (không đụng port 8000). Dọn sạch test.
- Sự cố giữa chừng: server dev 8000 tắt bất thường + sót con uvicorn AppImage
  ở port test (cha chết con sống) — đã dọn và start lại bằng `sshman`
  (PID 68989, health OK).

## 2026-09-07 — `sshman` thành menu tương tác (Start/Stop/Restart)

- `sshman` không tham số giờ mở menu: 1.Start 2.Stop 3.Restart 4.Status
  5.Logs 0.Thoát (lệnh cũ `sshman start/stop/...` vẫn dùng được).
- `stop` giờ dọn được cả server start thủ công (setsid/`run.sh` foreground,
  không có pidfile) bằng cách tìm tiến trình `uvicorn backend.app.main`
  đúng port; tách hàm `do_status` dùng chung cho menu.
- Verify: menu chọn 4→0 OK; chọn 2 dừng đúng server thủ công (PID 65390,
  port đóng); `start` lên lại PID mới + health OK + status thấy.
- File: `scripts/sshman.sh`.

## 2026-09-07 — Đóng gói 1.1.0 (Serial Console) `.deb` + `.AppImage`

- `scripts/package.sh` (VER mặc định 1.1.0): payload tự gồm code console mới
  (`api/consoles.py`, `services/serial/`, `models/console.py`, `app.js`,
  `requirements.txt` có pyserial). Service unit thêm `PrivateDevices=no` +
  `SupplementaryGroups=dialout` + `DeviceAllow` ttyUSB/ACM/S* + pts để bản
  .deb chạm được cổng serial (user động mặc định không thấy /dev/ttyUSB*).
- File mới trong `ssh_manager/`: `lan-ssh-manager_1.1.0_amd64.deb` (92KB),
  `LAN-SSH-Manager-1.1.0-x86_64.AppImage` (24.8MB). Bản 1.0.0 giữ nguyên.
- Verify: deb chứa đủ file console + pyserial; `dpkg -i` 1.1.0 OK (postinst
  dựng pyserial vào /opt venv, import module console OK),
  `systemd-analyze verify` sạch, service KHÔNG start (tránh đụng port 8000
  của server working tree đang chạy); AppImage chạy thật port 8129 —
  health + login + `/api/consoles` trả baudrates/system_ports (pyserial OK).
  Dọn sạch tiến trình/file test, DB không còn cổng console test.
- Lưu ý: gói .deb KHÔNG gồm `lsm` CLI (lấy từ repo: `bash
  scripts/install-console.sh` hoặc `scp console/lsm.py`).

## 2026-09-07 — Serial Console: cài OS cho máy chưa có hệ điều hành

- Máy chưa có OS không SSH được → thêm điều khiển qua **cổng console vật lý**:
  cắm cáp serial từ máy chủ app tới máy đích, mở console tương tác (BIOS/
  bootloader/bộ cài OS) trên web hoặc CLI. Hạ tầng PXE/DHCP người dùng tự lo.
- Backend mới: `models/console.py` (bảng `serial_consoles`, tự tạo qua
  `create_all`), `services/serial/manager.py` (pyserial, chiếm-giữ loại trừ
  1 cổng/1 session, WS bridge, polling session cho CLI), `api/consoles.py`
  (CRUD + `write`/`read` polling + `break` + `release` + WS `/ws/console/{id}`).
  Validate device (chặn `..`, bắt buộc `/dev/...`) + baud whitelist + audit
  CONNECT/DISCONNECT/ADD/DELETE/BREAK/RELEASE.
- Frontend: menu **Console** (`index.html`, `app.js` `viewConsoles`): bảng cổng
  (rảnh/đang dùng), xterm qua WS, Gửi BREAK, Giải phóng kẹt, modal thêm/sửa.
- CLI: `lsm console ls/add/del/attach/release/break` (`console/lsm.py`,
  attach raw-mode từng phím, thoát Ctrl+], pipe-mode cho script).
- Thêm `pyserial>=3.5` vào `backend/requirements.txt`; docs `docs/CONSOLE.md`.
- Verify (không có máy thật → cặp PTY ảo + máy đích giả, 13/13 PASS): chặn
  traversal/baud lạ, trùng cổng 409, polling write/read thấy banner+echo,
  WS 4409 khi bận, WS nối+echo phím, break, xóa sạch. CLI pipe attach 3 lần OK.
- Bug lòi ra khi test và đã sửa:
  - `APIRouter(prefix=...)` áp cả vào ws route → WS 403. Tách `router_ws`
    riêng không prefix (`api/consoles.py`, `main.py`).
  - Race poller+writer cùng mở session polling → 409 oan. `poll_ensure` giờ
    check→acquire→đặt chỗ trong 1 lock + `asyncio.Event` chờ mở xong.
- Lưu ý vận hành: đã `stop lan-ssh-manager.service` (.deb serving code cũ,
  chiếm port) và chạy lại server từ working tree trên `0.0.0.0:8000`
  (detached, log `logs/uvicorn.log`) để LAN truy cập lại + có tính năng mới.

## 2026-09-07 — Console client `lsm` cho máy headless/không trình duyệt

- Mới `console/lsm.py` (1 file, chỉ dùng stdlib python3, không cần pip/venv):
  login/logout, status, ls/show/add/del/test, info, exec, batch, svc, logs,
  files, users, audit, groups, terminal (nhảy SSH bằng `ssh` hệ thống),
  menu tương tác số, `--json` cho mọi lệnh đọc, token ở
  `~/.config/lan-ssh-manager/config.json` (600), env `LSM_URL/LSM_TOKEN/...`.
- Mới `scripts/install-console.sh` (user hoặc `--system`) + `docs/CONSOLE.md`.
- Verify: chạy thật với server local — login/status/ls/audit/info/exec/files/
  svc/groups/batch/logs/users OK trên Máy 01, `lsm` gọi từ PATH được.

## 2026-09-07 — Đóng gói AppImage + .deb vào `ssh_manager/`

- Mới `scripts/package.sh` (build lại 1 lệnh): payload loại venv/db/log/pycache.
- `lan-ssh-manager_1.0.0_amd64.deb` (87KB): code vào `/opt/lan-ssh-manager`,
  config `/etc/lan-ssh-manager/.env` (600, conffiles), launcher `/usr/bin/`,
  service systemd `DynamicUser` + `StateDirectory` (DB ở `/var/lib/...`),
  postinst tự dựng venv + pip. Cài: `sudo dpkg -i ...deb` rồi
  `sudo systemctl enable --now lan-ssh-manager`.
- `LAN-SSH-Manager-1.0.0-x86_64.AppImage` (24.6MB): bundle sẵn deps pip
  (python3.12), DB tách ra `~/.local/share/lan-ssh-manager`, chạy là tự mở web.
- Verify: deb không rò venv/db/pycache, postinst/prerm `bash -n` OK;
  AppImage `--appimage-extract` + chạy thật (health + login OK).
  Chưa test `dpkg -i` (máy build không có passwordless sudo).

## 2026-09-07 — Test cài .deb thật OK (sau khi cấp passwordless sudo)

- `sudo dpkg -i lan-ssh-manager_1.0.0_amd64.deb`: postinst dựng venv + pip xong,
  file đúng vị trí (`/opt`, `/etc` 600, service systemd), venv import app OK.
- Bản đã cài chạy thật (port test 8129): `/api/health` OK. Không start service
  8000 để khỏi đụng app đang chạy của user. Dọn sạch tiến trình/file test.

## 2026-09-07 — Tab Tổng quan có màu sắc

- 4 thẻ gradient (xanh tổng số, lục trực tuyến, đỏ ngoại tuyến, xám tắt/không rõ),
  donut % trực tuyến + thanh sức khỏe, badge trạng thái pill (● Trực tuyến/Ngoại tuyến/
  Không rõ), hostname dạng mono, bảng có hover.
- File: `frontend/app.js` (`viewDashboard`), `frontend/styles.css`
  (`.stat`, `.donut`, `.healthbar`, `.pill`). Backend/API không đổi.

## 2026-09-07 — Lệnh `sshman`: gõ ở đâu cũng chạy app + tự mở web

- Mới `scripts/sshman.sh`: `start` (mặc định, chạy nền + chờ health + `xdg-open`),
  `stop`/`restart`/`status`/`logs`, `PORT=...` đổi port, nhận diện cả app đang chạy
  sẵn bằng `run.sh` (qua health-check port, không chỉ pidfile).
- `sshman --install` tạo symlink `~/.local/bin/sshman` (đã cài cho máy này).
- Verify: chu trình start→health→status→stop→đóng port OK trên port test 8127,
  gọi từ `/tmp` và `$HOME` đều được; `sshman status` thấy đúng app thật ở 8000.

## 2026-09-07 — Terminal to hơn: full chiều cao + full chiều rộng

- Khung terminal (`.term-box`) cao `calc(100vh - 320px)`, tối thiểu 420px thay vì
  480px cố định (quy tắc `#term` cũ đã không còn ăn từ lúc giữ-session).
- Tab terminal dùng full chiều rộng (`.content.wide` bỏ `max-width:1200px`), các tab
  khác giữ nguyên. `fit()` tự nới số dòng/cột theo khung mới.
- File: `frontend/styles.css`, `frontend/app.js` (`term-box`, toggle `wide`).

## 2026-09-07 — Việt hóa toàn bộ app

- Frontend (`index.html`, `app.js`): nav/tabs/bảng/nút/placeholder/confirm/prompt sang
  tiếng Việt (Máy, Tổng quan, Lệnh, Tệp tin, Người dùng, Dịch vụ, Nhật ký, Đăng xuất...).
- Backend: mọi message trả về client sang tiếng Việt (login, CRUD máy, files,
  users, services, logs, SSH errors, terminal `[đã kết nối]`...).
- Giữ tiếng Anh cho thuật ngữ kỹ thuật: SSH, Terminal, WebSocket, xterm.js, IP,
  hostname, UID, chunk, resume, sudo, private key, systemctl actions, CPU/RAM...
- Verify: `node --check` OK, smoke test message VI (sai pass, login OK,
  máy 404, traversal 400).

## 2026-09-07 — Terminal giữ session khi chuyển tab

- Trước đây `setTab` chủ động `ws.close()` mỗi lần rời tab terminal, quay lại là
  session SSH mới (mất hết trạng thái đang làm).
- Giờ cache 1 session/máy (`window._terms` trong `frontend/app.js`): chuyển tab chỉ
  di chuyển DOM node xterm, WebSocket + shell SSH + scrollback giữ nguyên; quay lại
  thì gắn khung cũ vào, `fit()` + gửi `resize` + focus lại.
- Thêm nút **Kết nối lại** (mở session mới khi rớt mạng/token hết hạn), **Đóng session**
  kill đúng WS của máy đó; logout đóng hết session tránh SSH mồ côi. Backend không đổi.
- Verify: `node --check` OK, WS token rác vẫn bị từ chối (auth enforced).
- Lưu ý: idle-timeout phía server (Batch C) sau này sẽ ngắt session ẩn lâu — khi đó
  bấm Kết nối lại.

## 2026-09-07 — Feature Audit Batch A: vá path traversal + XSS

- `_safe_remote_path` (`backend/app/services/files/manager.py`) viết lại: chặn mọi
  segment `..` trong input thô TRƯỚC `normpath` (trước đây `pass` không làm gì nên
  `/a/../../etc` lọt thành `/etc`), chặn null byte, bắt buộc absolute. Thêm
  `DENY_DELETE_EXACT` (`/`, `/etc`, `/root`, `/home`, `/bin`, `/usr`, ...) —
  `delete` các path này bị từ chối server-side.
- `_check_remote_path` (`backend/app/api/files.py`) siết tương tự (absolute + `..`
  theo segment + null byte); `files_upload` giờ validate TRƯỚC khi đọc body.
- XSS stored qua tên file/user (`frontend/app.js`): `esc()` thêm `'`/backtick;
  list files + list OS users chuyển từ `onclick="fn('${esc(...)}')` sang
  `data-*` + `onclick` gán qua JS (không còn nối chuỗi vào HTML).
- Verify: unit check `_safe_remote_path` 6 case + delete-deny 4 case OK,
  `node --check` OK, smoke test server thật: `/tmp/../../etc` → 400
  "Path traversal blocked", `delete /` → 400 "Refusing to delete protected path".
- Batch tiếp theo (đã ghi vào `docs/SESSION.md`, chưa làm): Batch B upload
  RAM-DoS, Batch C auth/WS/CORS.

## 2026-09-05 — Upload: chọn thư mục đích bằng cửa sổ duyệt cây

- Nút **Chọn...** cạnh ô đích upload: mở modal duyệt cây thư mục trên máy SSH
  (từ thư mục đang xem, vào thư mục con, lên `..`), chốt bằng **Dùng thư mục này**.
- Chỉ dùng API list có sẵn, không thêm endpoint.
- File: `frontend/app.js` (`pickDestDir`, `renderPickDir`, `setDestDir`).

## 2026-09-05 — Upload file lớn >2GB: chia chunk, resume, progress

- File ≤16MB giữ đường upload 1-request cũ; file lớn tự cắt **chunk 8MB** gửi nối
  tiếp, retry 3 lần/chunk, thanh tiến trình %, nút Hủy.
- Resume: hỏi server đã nhận bao nhiêu byte rồi gửi tiếp; server kiểm tra offset
  khớp từng chunk (lệch trả 409 + số byte hiện tại).
- Backend mới trong `backend/app/api/files.py`: `GET .../upload/status`,
  `POST .../upload/chunk` (tối đa 32MB/chunk), `POST .../upload/complete`
  (xác nhận đủ size + ghi audit 1 dòng).
- Config mới `FILE_UPLOAD_MAX_TOTAL_MB=10240` (10GB) trong `.env`/`.env.example`/
  `config.py`. Giới hạn 50MB cũ chỉ còn áp cho upload 1-request.
- Test thật file 100MB lên Máy 01: 13 chunk, resume ở 24MB OK, md5 2 đầu khớp.
- Bug lòi ra khi test và đã sửa:
  - `SFTPNoSuchFile` không phải `FileNotFoundError` → crash cả server
    (bắt thêm `asyncssh.SFTPNoSuchFile` ở `_remote_size` và `upload_chunk`).

## 2026-09-05 — Sửa upload/editor ghi file 0 byte

- `SFTPClientFile.write` là coroutine nhưng code gọi không `await` → báo thành công
  giả, file rỗng. Thêm `await` ở `files_upload` (`backend/app/api/files.py`) và
  `write_text` (`backend/app/services/files/manager.py`).
- Upload binary lỗi `'bytes' object has no attribute 'encode'`: mở SFTP ở mode
  `"w"` (text) nhưng ghi bytes → đổi upload sang mode `"wb"`.
- Test: upload text + binary 200B, đọc lại khớp, editor sửa/đọc khớp, xóa dọn sạch.

## 2026-09-05 — Tab quản lý user Linux (mới)

- Backend mới `backend/app/api/users_api.py`, đăng ký trong `main.py`:
  list (`getent`, lọc uid 0 và ≥1000), add (`useradd -m`), delete (`userdel` ± `-r`),
  password và lock/unlock (`usermod`/`passwd`).
- Password hash bằng `crypt` (SHA-512) ngay ở backend, không lộ plaintext trong
  lệnh/log/audit. Validate tên user regex, cấm xóa root/user SSH đang dùng/user
  hệ thống (uid <1000 hoặc >60000), lệnh đọc chạy trực tiếp, lệnh ghi dùng
  `sudo -n` khi SSH user khác root + thông báo thiếu quyền rõ ràng.
- Frontend: tab `users` trong chi tiết máy (bảng, thêm, xóa có hỏi giữ/xóa home,
  đổi pass, lock/unlock, tải lại).
- Cấu hình sudo NOPASSWD trên Máy 01 (`/etc/sudoers.d/lan-ssh-manager`, mode 440,
  `visudo -c` parsed OK) cho 4 lệnh useradd/userdel/usermod/passwd.
- Sự cố giữa chừng: lần ghi đầu sai quoting tạo file sudoers lỗi cú pháp
  (`passwdn`, thiếu newline) → đã xóa và ghi lại đúng bằng base64, verify
  `sudo -n useradd --help` OK.
- Test toàn trình qua API: tạo `lsmtest` → đổi pass → lock → unlock → xóa cả home
  → list cuối sạch. Trạng thái lock lấy bằng `passwd -Sa` qua sudo nên hiện đúng
  (`tha: active`).

## 2026-09-05 — Sửa terminal gõ không echo (gõ mù, Enter mới hiện)

- Nguyên nhân: backend đọc output shell theo dòng (`async for`), ký tự echo chưa có
  `\n` bị giữ lại tới khi Enter.
- Đổi sang `stream.read(4096)` trả ngay khi có dữ liệu + forward cả stderr.
- File: `backend/app/services/terminal/session.py`. Test gửi từng ký tự echo về ngay.

## 2026-09-05 — Đồng bộ kích thước terminal, hiện trạng thái

- Sau khi WS mở 300ms: đo lại khung (`fit.fit()`), gửi `resize` cho server để pty
  khớp, `scrollToBottom()` + focus lại.
- Thêm dòng trạng thái dưới khung terminal (`terminal 136x29`, mã disconnect).
- Cursor dạng block + bấm vào khung đen để focus lại (xterm ẩn cursor khi mất focus).
- File: `frontend/app.js`.

## 2026-09-05 — Tab files mặc định mở home thay vì /root

- User SSH thường không có quyền đọc `/root` → 502 Permission denied gây hiểu lầm.
- Tab files giờ mặc định mở `/root` nếu là root, `/home/<user>` nếu user thường,
  kèm dòng ghi rõ user SSH đang dùng. Backend đổi default `/root` → `/`.
- File: `frontend/app.js`, `backend/app/api/files.py`, `manager.py`.
- Test: `/home/tha` 200 OK, `/root` 502 đúng quyền.

## 2026-09-05 — Sửa terminal đen màn hình (shell mở nhưng không có output)

- Nguyên nhân: `conn.create_process()` trả bytes, `send_text(bytes)` ném lỗi câm.
- Mở shell với `encoding="utf-8"`, decode bytes→str, clamp cols/rows, timeout kết
  nối, báo lỗi rõ (`[SSH connect failed]`/`[Shell open failed]`/`[shell exited]`).
- Frontend: `encodeURIComponent(token)`, chống crash `FitAddon`, hiện mã đóng WS,
  xử lý tin nhắn Blob.
- File: `backend/app/services/terminal/session.py`, `frontend/app.js`.
- Test WS thật với Máy 01: nhận banner Ubuntu + prompt `tha@bbi-tek:~$`, echo 2 chiều.

## 2026-09-05 — Terminal chạy offline (vendor xterm local)

- URL CDN cũ `xterm@5.5.0/lib/xterm.js` đã 404 (gói đổi tên) + phụ thuộc Internet,
  trái yêu cầu chạy offline trong LAN.
- Tải về `frontend/vendor/`: `xterm.js` 5.3.0 + `xterm-addon-fit.js` 0.8.0 +
  `xterm.css`; `index.html` load local; backend mount thêm `/vendor`.
- File: `frontend/index.html`, `frontend/vendor/*`, `backend/app/main.py`.

## 2026-09-05 — Sửa JS/CSS 404 (mọi nút bấm chết)

- Frontend mount ở `/static` nhưng `index.html` load `app.js`/`styles.css` tương đối
  → 404, JS không chạy, login và mọi nút đơ.
- Thêm route `/app.js`, `/styles.css` trong `backend/app/main.py` (giữ cả `/static/*`).
- Verify: login JWT OK, thêm/xóa máy 201/200.

## 2026-09-05 — Rà soát ban đầu

- App đã có đầy đủ (~1759 dòng: 11 router backend, SPA `index.html`+`app.js` 288 dòng,
  `run.sh`/`backup.sh`/`clean.sh`, DB SQLite). Chạy thử API OK, không phải dự án rỗng.
