# Hướng dẫn sử dụng LAN SSH Manager

Web app quản lý máy Linux trong mạng LAN qua SSH, không cần cài agent trên máy đích.
Chạy hoàn toàn offline trong LAN sau khi cài đặt.

## 1. Chạy app

```bash
bash run.sh
```

Mở trình duyệt: `http://<IP-máy-chạy-app>:8000`

- Đăng nhập mặc định: `admin / admin123`
- Đổi password admin trong file `.env` (`ADMIN_PASSWORD`). Chỉ áp dụng lần đầu
  (khi database chưa có user). Muốn đổi sau đó thì sửa trực tiếp trong database
  hoặc xóa `data/lan_ssh_manager.db` để tạo lại từ đầu (mất hết máy đã thêm).
- Tài liệu API tự động: `http://<IP>:8000/docs`

> Sau mỗi lần cập nhật code: chạy lại `run.sh` + tải lại trang bằng
> **Ctrl+F5** (xóa cache JS cũ).

## 2. Tổng quan các màn hình

| Menu | Chức năng |
|------|-----------|
| Dashboard | Tổng số máy, Online/Offline, bảng trạng thái (tự check SSH khi mở) |
| Machines | Thêm/sửa/xóa máy, Test kết nối SSH |
| Commands | Chạy 1 lệnh trên nhiều máy cùng lúc (batch) |
| Audit | Nhật ký thao tác: login, thêm/xóa máy, chạy lệnh, up file, quản lý user... |
| Groups | Nhóm máy để phân loại |

Trong mỗi máy có các tab: `overview` (CPU/RAM/disk/OS...), `terminal`,
`command`, `files`, `users`, `services`, `logs`.

## 3. Thêm máy (Machines)

Vào **Machines → + Thêm máy**, nhập:

- **Tên**: tên gợi nhớ (vd `Máy 01`)
- **Hostname/IP + Port**: vd `192.168.1.51`, port `22`
- **SSH user**: user đăng nhập trên máy đích (vd `tha`, `root`)
- **Auth**: `Password` (mật khẩu SSH) hoặc `SSH Key` (dán nội dung private key)
- **Group**: nhóm (tùy chọn), **Mô tả**: ghi chú

Bấm **Test** để kiểm tra. Lỗi thường gặp:

| Báo lỗi | Nghĩa |
|---------|-------|
| authentication failed | Sai user/password/key |
| timeout | Máy tắt, sai IP, hoặc firewall chặn port 22 |
| refused | Máy mở nhưng chưa bật SSH (`sudo systemctl start ssh`) |

> Thêm máy **không cần** SSH thành công — cứ thêm trước, Test sau.
> Credential được mã hóa (Fernet) trong database, không lưu plaintext.

## 4. Terminal realtime

Tab `terminal` của máy: gõ lệnh như ngồi trực tiếp trên máy.

- Hỗ trợ Ctrl+C/D, phím mũi tên, màu ANSI, resize tự động.
- Mất con trỏ: bấm chuột vào khung đen để focus lại.
- Đóng session: nút **Đóng session** hoặc chuyển tab khác.

## 5. Chạy lệnh (Command + Batch)

- Tab `command`: chạy 1 lệnh trên 1 máy, có timeout, hiện exit code/stdout/stderr.
- Menu **Commands**: tick nhiều máy → chạy 1 lệnh đồng loạt (giới hạn song song
  theo `MAX_CONCURRENT_SSH`). Lệnh nguy hiểm sẽ hỏi xác nhận.

## 6. Quản lý file (tab files)

- Ô **đường dẫn** + **List**: duyệt file. Mặc định mở home của user SSH
  (`/root` nếu là root, `/home/<user>` nếu là user thường) vì user thường
  không có quyền đọc `/root`.
- **Editor**: đọc/lưu file text ≤512KB.
- **+ Thư mục / Rename / Xóa**: quản lý cơ bản (xóa hỏi xác nhận).
- **Upload**:
  - Chọn 1 hoặc nhiều file → ô đích để trống = upload vào thư mục đang xem,
    hoặc bấm **Chọn...** để duyệt cây thư mục trên máy SSH rồi chốt
    **Dùng thư mục này**, hoặc gõ tay đường dẫn.
  - File ≤16MB gửi 1 lần; file lớn tự chia **chunk 8MB**, hiện % tiến trình,
    có nút **Hủy**. Đứt mạng thì bấm Upload lại để **resume** tiếp từ chỗ dở.
  - Giới hạn: upload 1 lần tối đa `FILE_UPLOAD_MAX_MB` (mặc định 50MB);
    upload chunk tổng tối đa `FILE_UPLOAD_MAX_TOTAL_MB` (mặc định 10GB).
    Đổi trong `.env` rồi restart app.

## 7. Quản lý user Linux (tab users)

Liệt kê user trên máy (uid 0 và uid ≥ 1000), thêm/xóa user, đổi password,
lock/unlock. Cấm xóa `root`, user SSH đang dùng và user hệ thống.

> Thao tác thêm/xóa/đổi pass/lock **cần quyền root**. Nếu máy dùng user SSH
> thường (vd `tha`), cấu hình sudo NOPASSWD cho 4 lệnh trên máy đích:
>
> ```bash
> sudo visudo   # hoặc: sudo nano /etc/sudoers.d/lan-ssh-manager
> ```
>
> Thêm dòng (thay `tha` bằng user SSH của bạn):
>
> ```
> tha ALL=(ALL) NOPASSWD: /usr/sbin/useradd, /usr/sbin/userdel, /usr/sbin/usermod, /usr/bin/passwd
> ```
>
> Lưu file, kiểm tra: `sudo visudo -c` phải báo `parsed OK`,
> `sudo -n useradd --help` phải chạy được không hỏi password.
> Nếu thiếu quyền, app báo rõ `cần quyền root...` thay vì lỗi chung chung.

## 8. Services & Logs

- Tab `services`: xem service đang chạy; start/stop/restart/status/enable/disable
  service hệ thống (tên service được kiểm tra, thao tác nguy hiểm hỏi xác nhận).
- Tab `logs`: xem log hệ thống hoặc log của 1 service (`journalctl`, N dòng gần nhất).

> 2 tab này cũng cần user SSH có quyền tương ứng (root hoặc sudo).

## 9. Cấu hình (.env)

| Biến | Mặc định | Nghĩa |
|------|----------|-------|
| ADMIN_USERNAME / ADMIN_PASSWORD | admin / admin123 | Login lần đầu |
| SSH_TIMEOUT | 10 | Timeout kết nối SSH (giây) |
| SSH_COMMAND_TIMEOUT | 30 | Timeout chạy lệnh (giây) |
| MAX_CONCURRENT_SSH | 10 | Số SSH song song tối đa |
| FILE_UPLOAD_MAX_MB | 50 | Upload 1-request tối đa |
| FILE_UPLOAD_MAX_TOTAL_MB | 10240 | Upload chunk tổng tối đa |
| JWT_EXPIRE_MINUTES | 480 | Token login hết hạn |
| APP_SECRET_KEY / APP_ENCRYPTION_KEY | — | **Tuyệt đối không commit/publish** |

## 10. Backup & dọn dẹp

```bash
bash scripts/backup.sh   # backup database + config (có timestamp)
bash scripts/clean.sh    # xóa file tạm, cache (không xóa data/.env)
```

## 11. Xử lý sự cố nhanh

| Hiện tượng | Cách xử |
|------------|---------|
| Nút bấm không phản hồi | Ctrl+F5 (cache JS cũ) |
| Terminal đen, chỉ có con trỏ | Đợi 2–3s hiện banner login; bấm vào khung đen để focus |
| Gõ terminal không hiện chữ | Gõ xong Enter vẫn chạy là bình thường ở bản cũ; bản mới echo ngay từng ký tự |
| Tab files báo Permission denied | Đang mở thư mục user SSH không có quyền (vd `/root`) → chuyển về home |
| Tab users báo cần quyền root | Làm theo mục 7 |
| Quên password admin | Xóa `data/lan_ssh_manager.db` rồi chạy lại (mất danh sách máy) |
| Xem log backend | `logs/app.log`, `logs/error.log` |

## 12. Console vật lý — cài OS cho máy chưa có hệ điều hành

Máy chưa có OS thì chưa SSH được. Cắm cáp serial từ máy chủ app tới cổng
console của máy đích, bật console redirection trong BIOS (115200), rồi vào
menu **Console** → **+ Thêm cổng** (`/dev/ttyUSB0`...) → **Mở** để thao tác
BIOS/bootloader/bộ cài OS. Chi tiết phần cứng + CLI (`lsm console attach`):
xem `docs/CONSOLE.md`.
