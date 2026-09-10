# Console: cổng serial vật lý (máy chưa có OS) + client `lsm`

Hai thứ khác nhau, cùng phục vụ máy không có màn hình/trình duyệt:

1. **Serial Console** — điều khiển máy chưa có OS qua cổng console vật lý
   (cắm cáp serial từ máy chủ app tới máy đích, thao tác BIOS/bootloader/
   bộ cài OS như ngồi trực tiếp). SSH chưa dùng được ở giai đoạn này.
2. **Client `lsm`** — điều khiển app qua dòng lệnh từ bất kỳ máy nào trong LAN.

## 1. Serial Console — cài OS cho máy chưa có hệ điều hành

### Phần cứng cần chuẩn bị (người dùng tự đấu nối)

- Máy chủ chạy app phải có cổng serial tới máy đích: USB-RS232, PCIe serial,
  hoặc console server. Kiểm tra trên máy chủ: `ls /dev/ttyUSB*`.
- Máy đích bật console redirection trong BIOS (tốc độ 115200) hoặc dùng cổng
  console mặc định của mainboard.
- Cài OS thì boot máy đích từ USB/DVD/ISO (người dùng tự triển khai PXE —
  app không can thiệp DHCP/TFTP).

### Khai báo cổng trên web (menu Console)

Vào **Console → + Thêm cổng**: tên gợi nhớ, thiết bị (vd `/dev/ttyUSB0`,
gợi ý từ cổng đang thấy), baudrate (BIOS/console thường 115200), liên kết
máy (tùy chọn). Bấm **Mở** để vào phiên xterm tương tác.

- 1 cổng chỉ 1 người dùng tại 1 thời điểm (web hoặc CLI).
  Cổng bận sẽ báo rõ; session kẹt (rớt mạng quên đóng) thì bấm **Giải phóng kẹt**.
- Nút **Gửi BREAK**: ngắt vào bootloader/BIOS khi cần.

### Dùng qua CLI

```bash
lsm console ls                                   # liệt kê cổng + trạng thái
lsm console add --name "Máy 04 - console" --device /dev/ttyUSB0 --baud 115200
lsm console attach 1                            # gõ trực tiếp từng phím, thoát: Ctrl+]
lsm console break 1                             # gửi BREAK ngoài phiên
lsm console release 1                           # gỡ session kẹt
```

### API (cho script tự động)

```
GET/POST /api/consoles  PUT/DELETE /api/consoles/{id}
POST /api/consoles/{id}/write {data}     GET /api/consoles/{id}/read?since=N
POST /api/consoles/{id}/break            POST /api/consoles/{id}/release
WS   /ws/console/{id}?token=...
```

## 2. Client `lsm` (máy không có trình duyệt / headless)

`lsm` là client điều khiển LAN SSH Manager qua dòng lệnh, nói chuyện với
cùng backend API như web. Chỉ cần **python3 có sẵn** — không pip, không venv,
không cài thêm gì.

## Cài đặt

Từ máy cần điều khiển (chỉ cần copy 1 file):

```bash
# trong thư mục repo:
bash scripts/install-console.sh
# cài chung cả máy:
sudo bash scripts/install-console.sh --system

# máy khác không có repo: copy file rồi chạy
scp console/lsm.py user@may-khac:/tmp/lsm && ssh user@may-khac \
  "mkdir -p ~/.local/bin && cp /tmp/lsm ~/.local/bin/lsm && chmod +x ~/.local/bin/lsm"
```

## Dùng

```bash
lsm login --url http://192.168.1.10:8000 -u admin   # hỏi mật khẩu, lưu token
lsm menu          # menu số tương tác (hợp console thuần qua SSH)
lsm status        # tổng quan online/offline
lsm ls            # danh sách máy
lsm info 1        # CPU/RAM/disk/OS máy #1
lsm exec 1 "uptime"
lsm batch -i 1,2 "uptime"
lsm svc 1 ls                    # service đang chạy
lsm svc 1 restart nginx         # hỏi xác nhận với stop/restart
lsm logs 1 --service nginx -n 50
lsm files 1 /home/tha
lsm users 1
lsm test 2        # kiểm tra SSH
lsm terminal 1    # nhảy vào SSH bằng lệnh `ssh` của hệ thống
lsm audit -n 50
```

Ghi chú:

- Token lưu ở `~/.config/lan-ssh-manager/config.json` (mode 600).
- Ghi đè nhanh bằng env: `LSM_URL`, `LSM_TOKEN`, `LSM_USER`, `LSM_PASS`.
- Mọi lệnh đọc đều có `--json` để viết script (`lsm ls --json | jq ...`).
- `terminal` dùng OpenSSH của máy (`ssh -p ... user@host`), không qua WebSocket.
