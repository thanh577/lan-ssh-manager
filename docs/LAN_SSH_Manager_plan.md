# LAN SSH Manager --- Kế hoạch xây dựng ứng dụng Web quản lý máy LAN qua SSH

> Phiên bản: 1.0\
> Ngày: 2026-09-05\
> Mục tiêu: Xây dựng một web app chạy nội bộ trong LAN, cho phép quản lý
> nhiều máy Linux/Ubuntu thông qua SSH mà không cần cài agent trên máy
> đích.

------------------------------------------------------------------------

## 1. Mục tiêu dự án

LAN SSH Manager là một ứng dụng web self-hosted dùng để quản lý các máy
chủ/máy tính trong mạng LAN thông qua SSH.

Ứng dụng được triển khai trên một máy trong LAN. Người quản trị truy cập
bằng trình duyệt:

``` text
Browser
   |
   | HTTP / WebSocket
   v
LAN SSH Manager
   |
   | SSH
   +--------> Server 01
   +--------> Server 02
   +--------> Server 03
   +--------> Server 04
```

### Nguyên tắc chính

-   Chạy hoàn toàn trong LAN.
-   Không yêu cầu Internet khi hệ thống đã cài đặt xong.
-   Không cần cài agent trên các máy đích.
-   SSH là phương thức quản lý chính.
-   Ưu tiên SSH key thay vì password.
-   Credential phải được mã hóa khi lưu.
-   Có web terminal tương tác realtime.
-   Có dashboard theo dõi trạng thái máy.
-   Có khả năng chạy command trên một hoặc nhiều máy.
-   Có audit log cho các thao tác quan trọng.
-   Kiến trúc đơn giản, dễ bảo trì.
-   Không triển khai microservice ở giai đoạn đầu.

------------------------------------------------------------------------

# 2. Phạm vi chức năng

## Phase 1 --- MVP

Bắt buộc hoàn thành:

-   Đăng nhập.
-   Dashboard.
-   Quản lý máy.
-   Thêm/sửa/xóa máy.
-   Test SSH.
-   Hiển thị Online/Offline.
-   Web terminal realtime.
-   Quản lý SSH credential cơ bản.

## Phase 2 --- System Management

-   CPU.
-   RAM.
-   Disk.
-   Uptime.
-   Load average.
-   OS.
-   Kernel.
-   Network.
-   Process.
-   Service systemd.
-   Xem log.
-   Chạy command.

## Phase 3 --- Advanced Management

-   File Manager.
-   Upload.
-   Download.
-   Rename.
-   Delete.
-   Tạo thư mục.
-   Chỉnh sửa file text.
-   Batch command.
-   Nhóm server.
-   Audit log.
-   Backup.

## Phase 4 --- Extension

-   Docker management.
-   Cron management.
-   Network tools.
-   Notification.
-   Role/Permission.
-   PostgreSQL.
-   Task queue nếu thực sự cần.
-   Plugin/module system.

------------------------------------------------------------------------

# 3. Công nghệ

## Backend

Sử dụng:

-   Python
-   FastAPI
-   AsyncSSH
-   SQLAlchemy
-   Pydantic
-   SQLite
-   WebSocket

Lý do:

FastAPI phù hợp để xây REST API và WebSocket.

AsyncSSH phù hợp với ứng dụng phải quản lý nhiều SSH session đồng thời.

SQLite đủ cho hệ thống LAN nhỏ và trung bình.

------------------------------------------------------------------------

# 4. Frontend

Sử dụng:

-   React
-   TypeScript
-   Vite
-   Tailwind CSS
-   xterm.js

### xterm.js

Dùng để xây terminal trong trình duyệt.

Luồng:

``` text
Browser
   |
   | WebSocket
   v
FastAPI
   |
   | AsyncSSH
   v
Remote SSH Server
```

------------------------------------------------------------------------

# 5. Database

Giai đoạn đầu dùng SQLite.

Database dự kiến:

``` text
data/
└── lan_ssh_manager.db
```

## Bảng users

``` text
users
-----
id
username
password_hash
is_active
created_at
updated_at
```

## Bảng machines

``` text
machines
--------
id
name
hostname
port
username
auth_type
credential_encrypted
group_id
description
enabled
created_at
updated_at
last_seen
```

## Bảng groups

``` text
groups
------
id
name
description
created_at
updated_at
```

## Bảng audit_logs

``` text
audit_logs
----------
id
user_id
machine_id
action
command
status
output_summary
created_at
```

## Bảng sessions

Chỉ dùng nếu cần quản lý session ở server:

``` text
sessions
--------
id
user_id
machine_id
session_type
created_at
expires_at
```

Không lưu private key hoặc password SSH dạng plaintext.

------------------------------------------------------------------------

# 6. Kiến trúc thư mục

``` text
lan-ssh-manager/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── machines.py
│   │   │   ├── terminal.py
│   │   │   ├── system.py
│   │   │   ├── commands.py
│   │   │   ├── files.py
│   │   │   └── logs.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   │
│   │   ├── db/
│   │   │   ├── database.py
│   │   │   └── migrations/
│   │   │
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── machine.py
│   │   │   ├── group.py
│   │   │   └── audit.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── machine.py
│   │   │   └── command.py
│   │   │
│   │   ├── services/
│   │   │   ├── ssh/
│   │   │   │   ├── client.py
│   │   │   │   ├── connection.py
│   │   │   │   └── manager.py
│   │   │   │
│   │   │   ├── terminal/
│   │   │   │   └── session.py
│   │   │   │
│   │   │   ├── monitoring/
│   │   │   │   └── system_info.py
│   │   │   │
│   │   │   ├── commands/
│   │   │   │   └── executor.py
│   │   │   │
│   │   │   └── files/
│   │   │       └── manager.py
│   │   │
│   │   └── main.py
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   ├── utils/
│   │   ├── App.tsx
│   │   └── main.tsx
│   │
│   ├── package.json
│   └── vite.config.ts
│
├── data/
│   └── .gitkeep
│
├── scripts/
│   ├── install.sh
│   ├── run.sh
│   ├── stop.sh
│   ├── backup.sh
│   └── clean.sh
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── security.md
│
├── .env.example
├── .gitignore
├── README.md
├── SKILL.md
└── docker-compose.yml
```

------------------------------------------------------------------------

# 7. Giai đoạn 0 --- Chuẩn bị môi trường

## 7.1 Backend

Cài Python 3 và virtual environment.

``` bash
python3 --version
python3 -m venv backend/venv
source backend/venv/bin/activate
```

Cài dependency:

``` bash
pip install fastapi uvicorn asyncssh sqlalchemy pydantic pydantic-settings
```

Các dependency bổ sung sẽ được thêm khi chức năng tương ứng được triển
khai.

## 7.2 Frontend

Cài Node.js phiên bản LTS.

Tạo frontend:

``` bash
npm create vite@latest frontend -- --template react-ts
```

Cài:

``` bash
cd frontend
npm install
npm install xterm @xterm/xterm
```

Tailwind CSS được cấu hình sau khi skeleton frontend hoạt động.

------------------------------------------------------------------------

# 8. Giai đoạn 1 --- Tạo Backend skeleton

Tạo:

``` text
backend/app/main.py
backend/app/core/
backend/app/api/
backend/app/services/
backend/app/models/
backend/app/schemas/
```

FastAPI phải chạy được trước khi viết chức năng.

Test:

``` bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Kiểm tra:

``` text
http://SERVER_IP:8000
```

Swagger:

``` text
http://SERVER_IP:8000/docs
```

------------------------------------------------------------------------

# 9. Giai đoạn 2 --- Database

Tạo SQLAlchemy models.

Thứ tự:

1.  User.
2.  Machine.
3.  Group.
4.  AuditLog.

Sau đó tạo database initialization.

Yêu cầu:

-   Không hard-code database path.
-   Database path lấy từ `.env`.
-   Migration phải có khả năng mở rộng.
-   Không xóa dữ liệu khi khởi động app.

------------------------------------------------------------------------

# 10. Giai đoạn 3 --- Authentication

Tạo:

``` text
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

Mật khẩu người dùng phải được hash.

Không lưu:

``` text
password = "123456"
```

Phải lưu password hash.

Session/token phải có thời hạn.

MVP có thể dùng JWT hoặc session cookie.

Nếu app chỉ chạy LAN, vẫn phải có authentication.

------------------------------------------------------------------------

# 11. Giai đoạn 4 --- Machine Management

API:

``` text
GET    /api/machines
GET    /api/machines/{id}
POST   /api/machines
PUT    /api/machines/{id}
DELETE /api/machines/{id}
POST   /api/machines/{id}/test
```

Thông tin máy:

``` json
{
  "name": "server01",
  "hostname": "192.168.1.10",
  "port": 22,
  "username": "admin",
  "auth_type": "key",
  "description": "Ubuntu Server"
}
```

Frontend cần có:

-   Machine list.
-   Add machine dialog.
-   Edit machine.
-   Delete confirmation.
-   Test connection.
-   Status indicator.

------------------------------------------------------------------------

# 12. Giai đoạn 5 --- SSH Service

Đây là thành phần lõi.

Tạo:

``` text
services/ssh/client.py
services/ssh/connection.py
services/ssh/manager.py
```

## SSH Manager chịu trách nhiệm

-   Connect.
-   Disconnect.
-   Execute command.
-   Open interactive shell.
-   Upload.
-   Download.
-   Check connection.
-   Handle timeout.
-   Handle authentication error.
-   Handle connection error.

Không để API route tự xử lý SSH trực tiếp.

Sai:

``` text
API route
   ↓
AsyncSSH
```

Đúng:

``` text
API route
   ↓
SSH Manager
   ↓
SSH Connection
   ↓
AsyncSSH
```

------------------------------------------------------------------------

# 13. Giai đoạn 6 --- Test SSH

Khi người dùng bấm:

``` text
Test Connection
```

Backend:

``` text
API
 ↓
SSH Manager
 ↓
Connect
 ↓
Execute: echo OK
 ↓
Disconnect
```

Kết quả:

``` json
{
  "success": true,
  "message": "SSH connection successful"
}
```

Các lỗi phải phân biệt:

-   Timeout.
-   Connection refused.
-   Host unreachable.
-   Authentication failed.
-   Invalid key.
-   Permission denied.
-   Unknown host.

------------------------------------------------------------------------

# 14. Giai đoạn 7 --- Dashboard

Dashboard hiển thị:

``` text
Total Machines
Online
Offline
Unknown
```

Danh sách:

``` text
Machine     Status     CPU     RAM     Disk     Uptime
--------------------------------------------------------
server01    Online     21%     42%     61%      12d
server02    Online     63%     78%     83%       4d
server03    Offline    --      --      --        --
```

Không refresh toàn bộ trang.

Frontend gọi API định kỳ hoặc sử dụng WebSocket khi phù hợp.

------------------------------------------------------------------------

# 15. Giai đoạn 8 --- System Monitoring

Không cần agent.

Có thể lấy thông tin bằng command SSH.

Ví dụ:

``` bash
uname -a
```

CPU:

``` bash
nproc
uptime
```

Memory:

``` bash
free -m
```

Disk:

``` bash
df -h
```

OS:

``` bash
cat /etc/os-release
```

Hostname:

``` bash
hostname
```

Network:

``` bash
ip -brief address
```

Backend tạo một service:

``` text
SystemInfoService
```

Không để frontend tự chạy command.

------------------------------------------------------------------------

# 16. Giai đoạn 9 --- Web Terminal

Đây là chức năng quan trọng nhất.

Frontend:

``` text
xterm.js
```

Backend:

``` text
FastAPI WebSocket
```

SSH:

``` text
AsyncSSH interactive shell
```

Luồng:

``` text
xterm.js
   |
   | WebSocket
   v
FastAPI
   |
   | SSH interactive shell
   v
Remote machine
```

Ví dụ endpoint:

``` text
/ws/terminal/{machine_id}
```

Khi mở terminal:

1.  Xác thực user.
2.  Kiểm tra machine.
3.  Tạo SSH connection.
4.  Tạo interactive shell.
5.  Forward input từ browser → SSH.
6.  Forward output từ SSH → browser.
7.  Khi đóng browser → đóng SSH session.

Phải xử lý:

-   Resize terminal.
-   Ctrl+C.
-   Ctrl+D.
-   Arrow keys.
-   ANSI color.
-   Unicode.
-   Vietnamese text.
-   Connection lost.
-   Reconnect.

------------------------------------------------------------------------

# 17. Giai đoạn 10 --- Command Executor

API:

``` text
POST /api/machines/{id}/command
```

Request:

``` json
{
  "command": "uptime"
}
```

Response:

``` json
{
  "success": true,
  "exit_code": 0,
  "stdout": "...",
  "stderr": ""
}
```

Command executor phải có:

-   Timeout.
-   Exit code.
-   stdout.
-   stderr.
-   Execution time.
-   Audit log.

Không chạy command trực tiếp từ frontend.

------------------------------------------------------------------------

# 18. Giai đoạn 11 --- Batch Command

Cho phép chọn nhiều máy:

``` text
☑ server01
☑ server02
☑ server03
☑ server04
```

Command:

``` bash
uptime
```

Backend thực hiện song song có giới hạn concurrency.

Kết quả:

``` text
server01  SUCCESS
server02  SUCCESS
server03  FAILED
server04  SUCCESS
```

Không tạo vô hạn SSH connection.

Phải có concurrency limit.

Ví dụ:

``` text
MAX_CONCURRENT_SSH = 10
```

Giá trị này đưa vào config.

------------------------------------------------------------------------

# 19. Giai đoạn 12 --- Service Management

Hiển thị service:

``` text
nginx
docker
ssh
cron
```

API:

``` text
GET  /api/machines/{id}/services
POST /api/machines/{id}/services/{name}/start
POST /api/machines/{id}/services/{name}/stop
POST /api/machines/{id}/services/{name}/restart
```

Không cho phép frontend tự ghép command nguy hiểm.

Backend nên dùng command builder có whitelist.

Ví dụ:

``` text
allowed actions:

start
stop
restart
status
```

------------------------------------------------------------------------

# 20. Giai đoạn 13 --- Logs

Cho phép xem:

``` text
journalctl
syslog
auth.log
nginx logs
docker logs
```

MVP chỉ cần command-based log viewer.

Ví dụ:

``` bash
journalctl -u nginx --no-pager -n 100
```

Sau đó có thể bổ sung realtime log streaming.

------------------------------------------------------------------------

# 21. Giai đoạn 14 --- File Manager

File Manager dùng SFTP/SSH.

Chức năng:

-   List directory.
-   Create directory.
-   Rename.
-   Delete.
-   Upload.
-   Download.
-   Edit text file.

Không cho phép path traversal.

Phải kiểm tra:

``` text
../../etc/passwd
```

và các biến thể tương tự.

MVP nên giới hạn file editor vào text file.

Không cố gắng xây một IDE hoàn chỉnh.

------------------------------------------------------------------------

# 22. Giai đoạn 15 --- Credential Security

Ưu tiên authentication:

``` text
1. SSH Key
2. Password
```

Private key hoặc password phải được mã hóa trước khi lưu database.

Encryption key lấy từ environment:

``` text
APP_ENCRYPTION_KEY
```

Không commit key vào Git.

`.env`:

``` text
APP_SECRET_KEY=
APP_ENCRYPTION_KEY=
DATABASE_URL=
```

`.gitignore`:

``` text
.env
*.db
*.sqlite
*.sqlite3
backend/venv/
frontend/node_modules/
__pycache__/
```

------------------------------------------------------------------------

# 23. Giai đoạn 16 --- Audit Log

Ghi lại:

-   Login.
-   Logout.
-   Add machine.
-   Delete machine.
-   Test SSH.
-   Execute command.
-   Start service.
-   Stop service.
-   Restart service.
-   File upload.
-   File download.
-   File delete.

Ví dụ:

``` text
Time                 User     Machine    Action
-------------------------------------------------------
2026-09-05 08:20     admin    server01   SSH_CONNECT
2026-09-05 08:21     admin    server01   COMMAND
2026-09-05 08:22     admin    server01   SERVICE_RESTART
```

Không nhất thiết lưu toàn bộ output command nếu output có thể chứa dữ
liệu nhạy cảm.

------------------------------------------------------------------------

# 24. Giai đoạn 17 --- Frontend UI

Layout:

``` text
┌───────────────────────────────────────────────┐
│ LAN SSH Manager                    User       │
├──────────────┬────────────────────────────────┤
│ Dashboard    │                                │
│ Machines     │           Content              │
│ Terminal     │                                │
│ Commands     │                                │
│ Logs         │                                │
│ Settings     │                                │
└──────────────┴────────────────────────────────┘
```

## Pages

``` text
/login
/
/machines
/machines/:id
/machines/:id/terminal
/machines/:id/files
/machines/:id/logs
/commands
/audit
/settings
```

------------------------------------------------------------------------

# 25. Giai đoạn 18 --- UX

Trạng thái phải rõ ràng:

``` text
● Online
● Offline
● Connecting
● Error
● Unknown
```

Các thao tác nguy hiểm phải có confirmation:

``` text
Delete machine
Stop service
Restart service
Delete file
Run command
```

Ví dụ:

``` text
Are you sure?

Restart nginx on server01?

[Cancel] [Restart]
```

------------------------------------------------------------------------

# 26. Giai đoạn 19 --- API Design

API nên thống nhất:

``` text
/api/auth/*
/api/machines/*
/api/groups/*
/api/system/*
/api/commands/*
/api/files/*
/api/logs/*
/api/audit/*
```

HTTP status:

``` text
200 OK
201 Created
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Validation Error
500 Internal Server Error
502 SSH Error
504 SSH Timeout
```

Response format thống nhất:

``` json
{
  "success": true,
  "data": {},
  "message": null
}
```

Error:

``` json
{
  "success": false,
  "data": null,
  "message": "SSH authentication failed"
}
```

------------------------------------------------------------------------

# 27. Giai đoạn 20 --- Error Handling

Không để exception backend trả stack trace cho frontend production.

Các lỗi phải được chuyển thành lỗi có nghĩa:

``` text
SSHConnectionError
SSHAuthenticationError
SSHTimeoutError
SSHCommandError
SSHFileError
MachineNotFoundError
CredentialError
```

Frontend hiển thị thông báo dễ hiểu.

------------------------------------------------------------------------

# 28. Giai đoạn 21 --- Logging

Backend log:

``` text
logs/
├── app.log
└── error.log
```

Không ghi:

-   Password.
-   Private key.
-   Encryption key.
-   Token.
-   Cookie.
-   Secret.

------------------------------------------------------------------------

# 29. Giai đoạn 22 --- Testing

## Unit test

Test:

-   Credential encryption.
-   Machine validation.
-   Command validation.
-   Authentication.
-   SSH error mapping.

## Integration test

Test:

``` text
API
 ↓
SSH service
 ↓
Test SSH server
```

## Frontend test

Test:

-   Login.
-   Add machine.
-   Test connection.
-   Terminal.
-   Delete machine.

## Manual test

Phải test tối thiểu:

``` text
Ubuntu → Ubuntu
Ubuntu → Debian
Ubuntu → server LAN
SSH key
SSH password
Wrong password
Wrong port
Offline server
Network timeout
```

------------------------------------------------------------------------

# 30. Giai đoạn 23 --- Security Checklist

Trước khi dùng thực tế:

-   [ ] Authentication bật.
-   [ ] Password được hash.
-   [ ] SSH credentials được mã hóa.
-   [ ] Secret nằm trong `.env`.
-   [ ] `.env` không commit.
-   [ ] WebSocket yêu cầu authentication.
-   [ ] API yêu cầu authentication.
-   [ ] Command có timeout.
-   [ ] SSH connection có timeout.
-   [ ] Batch command có concurrency limit.
-   [ ] Path traversal được chặn.
-   [ ] File upload có giới hạn.
-   [ ] Audit log hoạt động.
-   [ ] Không log credential.
-   [ ] Không expose SSH private key.
-   [ ] Không chạy frontend với quyền root.
-   [ ] Không chạy backend bằng root nếu không cần.
-   [ ] Firewall giới hạn truy cập vào LAN.

------------------------------------------------------------------------

# 31. Giai đoạn 24 --- Chạy Production trong LAN

Có thể chạy:

``` text
Browser
   |
   | :80
   v
Nginx
   |
   | :8000
   v
FastAPI
```

Frontend được build:

``` bash
npm run build
```

Backend:

``` bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Nginx phục vụ frontend và reverse proxy API/WebSocket.

------------------------------------------------------------------------

# 32. Giai đoạn 25 --- Systemd

Tạo service:

``` text
lan-ssh-manager.service
```

Service phải:

-   Tự khởi động.
-   Restart khi crash.
-   Chạy bằng user riêng.
-   Không chạy root.
-   Log qua journald.

------------------------------------------------------------------------

# 33. Giai đoạn 26 --- Backup

Backup tối thiểu:

``` text
database
.env/config cần thiết
application config
```

Không backup secret theo cách plaintext vào thư mục công khai.

Script:

``` bash
scripts/backup.sh
```

Ví dụ cấu trúc:

``` text
backup/
├── database/
└── config/
```

Backup phải có timestamp.

------------------------------------------------------------------------

# 34. Giai đoạn 27 --- Clean Script

`scripts/clean.sh` chỉ xóa file sinh ra an toàn:

``` text
__pycache__
*.pyc
frontend/dist
temporary files
test artifacts
```

Không được xóa:

``` text
data/
.env
database
SSH credentials
```

trừ khi người dùng xác nhận rõ ràng.

------------------------------------------------------------------------

# 35. Giai đoạn 28 --- Docker

Docker chỉ là tùy chọn.

Không bắt buộc ở MVP.

Nếu sử dụng:

``` text
docker-compose.yml

frontend/nginx
       |
backend
       |
SQLite
```

Không cần Redis hoặc Celery khi chưa có nhu cầu.

------------------------------------------------------------------------

# 36. Giai đoạn 29 --- Thứ tự triển khai bắt buộc

Không phát triển ngẫu nhiên.

Thực hiện theo thứ tự:

``` text
01. Project skeleton
        ↓
02. Backend startup
        ↓
03. Frontend startup
        ↓
04. Database
        ↓
05. Authentication
        ↓
06. Machine CRUD
        ↓
07. SSH connection
        ↓
08. Test SSH
        ↓
09. Dashboard
        ↓
10. System information
        ↓
11. Web Terminal
        ↓
12. Command executor
        ↓
13. Batch command
        ↓
14. Services
        ↓
15. Logs
        ↓
16. File Manager
        ↓
17. Audit
        ↓
18. Security hardening
        ↓
19. Testing
        ↓
20. Production deployment
```

------------------------------------------------------------------------

# 37. Definition of Done cho MVP

MVP chỉ được coi là hoàn thành khi:

-   [ ] Backend chạy ổn định.
-   [ ] Frontend chạy ổn định.
-   [ ] User đăng nhập được.
-   [ ] Thêm machine được.
-   [ ] Test SSH thành công.
-   [ ] Hiển thị online/offline.
-   [ ] Dashboard hoạt động.
-   [ ] Mở terminal SSH trên browser.
-   [ ] Terminal nhập command realtime.
-   [ ] Đóng terminal không để lại SSH session.
-   [ ] SSH timeout hoạt động.
-   [ ] SSH authentication error hoạt động.
-   [ ] Credential không lưu plaintext.
-   [ ] `.env` không commit.
-   [ ] Có logging cơ bản.
-   [ ] Có test cơ bản.
-   [ ] Có script chạy app.

------------------------------------------------------------------------

# 38. Nguyên tắc phát triển cho AI Coding Agent

AI coding agent phải tuân thủ:

## Không tự ý mở rộng phạm vi

Không tự thêm:

-   Redis.
-   Celery.
-   Kubernetes.
-   Microservice.
-   Message broker.
-   Agent trên server.
-   Cloud service.

nếu chưa có yêu cầu.

## Không phá kiến trúc

Service SSH phải nằm trong:

``` text
backend/app/services/ssh/
```

API chỉ gọi service.

Frontend chỉ gọi API.

## Không duplicate code

Nếu logic đã tồn tại:

``` text
services/ssh/
```

thì không viết lại SSH logic trong:

``` text
api/
```

## Không hard-code

Không hard-code:

-   IP.
-   Port.
-   Secret.
-   Password.
-   Database path.
-   Concurrency limit.

## Ưu tiên code nhỏ

Mỗi module chỉ chịu trách nhiệm một nhóm chức năng.

------------------------------------------------------------------------

# 39. Nguyên tắc command execution

Command từ người dùng là vùng nguy hiểm.

Mặc định:

``` text
Terminal:
    Cho phép interactive shell

Command API:
    Cho phép command execution nhưng phải audit + timeout

Service API:
    Chỉ whitelist action

System API:
    Chỉ dùng predefined commands
```

Không biến API thành endpoint kiểu:

``` text
POST /exec?cmd=...
```

mà không có authentication, authorization và audit.

------------------------------------------------------------------------

# 40. Khả năng mở rộng sau này

Kiến trúc phải cho phép thêm:

``` text
SSH
SFTP
Docker
Podman
Systemd
Cron
Logs
Monitoring
Backup
```

Mà không phải viết lại toàn bộ backend.

Có thể mở rộng:

``` text
services/
├── ssh/
├── docker/
├── systemd/
├── monitoring/
├── files/
└── backup/
```

------------------------------------------------------------------------

# 41. Kiến trúc cuối cùng

``` text
                         Browser
                            |
                    HTTP / WebSocket
                            |
                    +-------v-------+
                    |     Nginx     |
                    +-------+-------+
                            |
                    +-------v-------+
                    |    FastAPI    |
                    +-------+-------+
                            |
          +-----------------+-----------------+
          |                 |                 |
       Database         SSH Manager       Audit Log
          |                 |
        SQLite          AsyncSSH
                            |
             +--------------+--------------+
             |              |              |
          Server 01      Server 02      Server 03
             |              |              |
           Linux          Linux          Linux
```

------------------------------------------------------------------------

# 42. Mục tiêu cuối cùng

Sau khi hoàn thành, người dùng chỉ cần mở:

``` text
http://<LAN-SERVER-IP>
```

Sau đó có thể:

``` text
Login
  ↓
Dashboard
  ↓
Chọn server
  ↓
 ┌─────────────────────────────┐
 │ Overview                    │
 │ Terminal                    │
 │ Files                       │
 │ Services                    │
 │ Processes                   │
 │ Logs                        │
 │ Commands                    │
 └─────────────────────────────┘
```

Toàn bộ hệ thống hoạt động trong LAN và sử dụng SSH làm lớp quản lý máy.

------------------------------------------------------------------------

# 43. Roadmap đề xuất

## Milestone 1

``` text
Project skeleton
Backend
Frontend
Database
Authentication
```

## Milestone 2

``` text
Machine CRUD
SSH Manager
SSH Test
Dashboard
```

## Milestone 3

``` text
Web Terminal
System Information
Command Executor
```

## Milestone 4

``` text
Batch Command
Services
Logs
```

## Milestone 5

``` text
File Manager
Audit
Security hardening
```

## Milestone 6

``` text
Testing
Backup
Systemd
Production deployment
Documentation
```

## Milestone 7

``` text
Docker
Advanced monitoring
Docker management
Cron
Notification
RBAC
```

------------------------------------------------------------------------

# 44. Tiêu chí ưu tiên

Khi phải lựa chọn giữa nhiều giải pháp:

``` text
Security
   ↓
Stability
   ↓
Simplicity
   ↓
Maintainability
   ↓
Performance
   ↓
Extra features
```

Không hy sinh security/stability chỉ để thêm chức năng.

------------------------------------------------------------------------

# 45. Kết luận

LAN SSH Manager nên được xây dựng trước hết như một **SSH management
platform đơn giản, ổn định và an toàn**, thay vì cố gắng trở thành một
hệ thống DevOps toàn diện ngay từ đầu.

Stack chính:

``` text
Frontend:
React + TypeScript + Vite + Tailwind + xterm.js

Backend:
Python + FastAPI + AsyncSSH

Database:
SQLite

Communication:
REST API + WebSocket

Remote management:
SSH / SFTP

Deployment:
Linux + Nginx + systemd
```

MVP phải tập trung vào ba năng lực cốt lõi:

``` text
1. Quản lý máy
2. Kết nối SSH
3. Web Terminal
```

Sau khi ba phần này ổn định mới mở rộng sang monitoring, command
automation, service management, file manager và các chức năng nâng cao.
