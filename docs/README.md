# LAN SSH Manager — App chạy ngay (MVP)

Web app quản lý máy LAN qua SSH, **không cần agent**, chạy hoàn toàn trong LAN.

📖 **Hướng dẫn sử dụng chi tiết: [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md)**
💻 **Máy không có trình duyệt: dùng console client `lsm` — [CONSOLE.md](CONSOLE.md)** (`bash scripts/install-console.sh`, rồi `lsm login ... && lsm menu`)
🔌 **Máy chưa có OS: cài qua cổng console vật lý (menu Console / `lsm console attach`) — [CONSOLE.md](CONSOLE.md)**
🖥️ **Bản AppImage (≥1.2.0): mở là có panel điều khiển (Start/Stop/Restart, trạng thái, Mở Web, Ẩn, Thoát); máy không màn hình thì tự chạy headless.**

## Chạy ngay (1 lệnh)

```bash
bash run.sh
# mở http://<LAN-IP>:8000  (login mặc định: admin / admin123)
# Swagger: http://<LAN-IP>:8000/docs
```

Đổi password admin mặc định trong `.env` (`ADMIN_PASSWORD`, chỉ áp dụng lần đầu khi DB chưa có user).

## Kiến trúc (gọn so với plan để chạy ngay single-port)

```
Browser (static HTML + xterm.js)
   | HTTP / WebSocket (cùng port 8000)
FastAPI (backend/app)
   |── REST: /api/auth, /machines, /groups, /dashboard, /system, /commands, /files, /logs, /audit
   |── WS: /ws/terminal/{id}
   |── SSH Manager (services/ssh/) → AsyncSSH → Server LAN
SQLite (data/lan_ssh_manager.db)
```

> Plan gốc đề xuất React+Vite. Bản MVP này dùng **static frontend** do backend serve luôn
> để **chạy ngay không cần `npm build`**, vẫn đầy đủ: login, dashboard online/offline,
> CRUD máy, test SSH, web terminal realtime (xterm.js), system info, command + batch
> (concurrency limit), services whitelist, logs, file manager SFTP, audit log.
> Khi cần có thể thay `frontend/` bằng bản React build mà không đổi API.

## Tính năng

- Đăng nhập JWT (hash bcrypt, token hết hạn), WebSocket cũng yêu cầu token
- Dashboard: total/online/offline (check SSH song song, timeout ngắn)
- Machines CRUD + Test SSH (phân biệt timeout/auth/refused/unreachable)
- Terminal realtime: xterm.js ↔ WebSocket ↔ AsyncSSH shell (resize, Ctrl+C/D, ANSI, Unicode)
- Overview: OS/kernel/uptime/load/RAM/disk/network (predefined commands)
- Command đơn + batch (timeout, exit code, audit, MAX_CONCURRENT_SSH=10)
- Services: start/stop/restart/status (whitelist, validate tên)
- Logs: journalctl/service + syslog
- Files SFTP: list/mkdir/rename/delete/đọc-ghi text/upload (chặn path traversal, giới hạn size)
- Audit log mọi thao tác quan trọng; credential SSH mã hóa Fernet, không log secret

## API chính

```
POST /api/auth/login  GET /api/auth/me
GET/POST /api/machines  PUT/DELETE /api/machines/{id}  POST /api/machines/{id}/test
GET /api/dashboard
GET /api/machines/{id}/system
POST /api/machines/{id}/command   POST /api/commands/batch
GET /api/machines/{id}/services   POST /api/machines/{id}/services/{name}/{action}
POST /api/machines/{id}/logs
GET /api/machines/{id}/files  .../read .../write .../action .../upload
GET /api/groups  POST /api/groups
GET /api/audit
WS  /ws/terminal/{id}?token=...
```

## Cấu hình (.env)

```
APP_SECRET_KEY / APP_ENCRYPTION_KEY / DATABASE_URL / JWT_EXPIRE_MINUTES
SSH_TIMEOUT / SSH_COMMAND_TIMEOUT / MAX_CONCURRENT_SSH / FILE_UPLOAD_MAX_MB
ADMIN_USERNAME / ADMIN_PASSWORD
```
