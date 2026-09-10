#!/usr/bin/env python3
"""Panel điều khiển LAN SSH Manager cho Windows — đóng thành 1 file .exe độc lập.

Khác gui/control.py (bản Linux, start server bằng tiến trình con):
- Server uvicorn chạy NGAY TRONG exe (thread riêng) → máy đích KHÔNG cần
  cài Python, tắt exe là server dừng theo, không bao giờ sót process.
- Chỉ dùng stdlib + thư viện backend (đóng gói hết vào exe bằng PyInstaller).

Nút: Khởi động / Dừng / Làm mới / Mở Web / Ẩn / Thoát + trạng thái + log.

Chạy từ source (dev):
    python gui/app_win.py [--port 8000]

Tạo exe (chạy trên máy Windows, xem scripts/build_exe.bat):
    build_exe.bat   → ssh_manager/LAN-SSH-Manager-win64-<VER>.exe

Test không cần màn hình:
    python gui/app_win.py --selftest-headless [--port PORT]
"""
import logging
import os
import queue
import shutil
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser

PORT = int(os.environ.get("PORT", "8000"))


# Exe --windowed không có console: sys.stdout/stderr là None → nhiều thư viện
# crash ngay khi chạm vào (VD uvicorn logging gọi sys.stdout.isatty() lúc
# Config → "Unable to configure formatter 'default'"). Chặn bằng dummy.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")


# Console Windows mặc định cp1252/cp437 không in được tiếng Việt →
# ép stdout/stderr UTF-8 ngay từ đầu (Linux không ảnh hưởng).
for _s in (sys.stdout, sys.stderr):
    try:
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
del _s


def app_root():
    """Thư mục gốc chứa backend/ + frontend/ (chạy source hay exe đều đúng)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # PyInstaller onefile giải nén vào đây
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir():
    """Thư mục ghi DB/log/config trên máy chạy (ngoài exe)."""
    d = os.environ.get("LAN_SSH_DATA")
    if not d:
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
        d = os.path.join(base, "lan-ssh-manager")
    os.makedirs(d, exist_ok=True)
    return d


def load_dotenv(path):
    """Nạp file .env đơn giản (KEY=VALUE, bỏ comment) vào environ."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except OSError:
        pass


def prepare_env():
    """Dựng DATA (DB/log/.env) + trả về APP_ROOT. Gọi TRƯỚC khi import backend."""
    root = app_root()
    data = data_dir()
    os.makedirs(os.path.join(data, "logs"), exist_ok=True)
    env_file = os.path.join(data, ".env")
    if not os.path.isfile(env_file):
        tpl = os.path.join(root, ".env.example")
        if os.path.isfile(tpl):
            shutil.copyfile(tpl, env_file)
    load_dotenv(env_file)
    # DATABASE_URL phải là đường dẫn TUYỆT ĐỐI trong DATA (file .env mẫu chỉ
    # chứa path tương đối "./data/..." — chạy exe từ CWD nào cũng đúng).
    db_abs = "sqlite:///" + os.path.join(data, "lan_ssh_manager.db").replace("\\", "/")
    os.environ["DATABASE_URL"] = db_abs
    os.environ.setdefault("LSM_LOG_DIR", os.path.join(data, "logs"))
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # UDP connect không gửi packet
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "localhost"


def lan_url(port=PORT):
    return f"http://{lan_ip()}:{port}"


def health_ok(port=PORT, timeout=2):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


class QueueHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.q = q

    def emit(self, record):
        try:
            self.q.put_nowait(self.format(record))
        except queue.Full:
            pass


class WinServer:
    """Server uvicorn chạy trong thread của chính exe."""

    def __init__(self, port=PORT):
        self.port = port
        self._server = None
        self._thread = None
        self._lock = threading.Lock()
        self.logq: queue.Queue = queue.Queue(maxsize=2000)
        self.last_error = ""

    def is_running(self):
        return health_ok(self.port)

    def _attach_logs(self):
        h = QueueHandler(self.logq)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
        for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "lan-ssh-manager"):
            try:
                logging.getLogger(name).addHandler(h)
            except Exception:
                pass

    def start(self):
        with self._lock:
            if self.is_running():
                return "already"
            if self._thread and self._thread.is_alive():
                return "already"
            self.last_error = ""
            self._attach_logs()
            try:
                prepare_env()
                import uvicorn  # noqa: E402
                from backend.app.main import app  # noqa: E402
            except Exception as e:
                tb = traceback.format_exc(limit=5)
                self.last_error = f"Không nạp được backend: {e}\n{tb[-1500:]}"
                return "failed"
            cfg = uvicorn.Config(app, host="0.0.0.0", port=self.port, log_level="info")
            self._server = uvicorn.Server(cfg)
            self._thread = threading.Thread(target=self._server.run, daemon=True)
            self._thread.start()
            for _ in range(50):  # đợi tối đa ~25s
                if self.is_running():
                    return "started"
                if not self._thread.is_alive():
                    self.last_error = "Tiến trình server dừng bất thường — xem log."
                    self._server = None
                    return "failed"
                time.sleep(0.5)
            self.last_error = "Hết 25s chờ mà server chưa lên — xem log."
            return "timeout"

    def stop(self):
        with self._lock:
            srv, th = self._server, self._thread
            self._server, self._thread = None, None
        if srv is not None:
            srv.should_exit = True
            if th is not None:
                th.join(timeout=10)
        for _ in range(10):
            if not self.is_running():
                return "stopped"
            time.sleep(0.5)
        if not self.is_running():
            return "stopped"
        return "timeout"

    def restart(self):
        self.stop()
        return self.start()


# ---------------- GUI ----------------

class Panel:
    def __init__(self, root, srv: WinServer):
        import tkinter as tk
        from tkinter import messagebox, scrolledtext
        self.tk = tk
        self.msgbox = messagebox
        self.root = root
        self.srv = srv
        self._checking = False  # health-check nền đang chạy?
        self._panel_log = os.path.join(data_dir(), "logs", "panel.log")
        root.title("LAN SSH Manager")
        root.geometry("480x500")
        root.minsize(450, 440)

        self.status_var = tk.StringVar(value="Đang kiểm tra...")
        tk.Label(root, text="LAN SSH Manager", font=("TkDefaultFont", 14, "bold")).pack(pady=(10, 2))
        self.status_lbl = tk.Label(root, textvariable=self.status_var, font=("TkDefaultFont", 11))
        self.status_lbl.pack()
        self.url_var = tk.StringVar(value="")
        tk.Label(root, textvariable=self.url_var, fg="blue").pack()
        tk.Label(root, text=f"Tài khoản mặc định: admin / admin123 (đổi trong {data_dir()}\\.env)",
                 font=("TkDefaultFont", 9)).pack()

        btns = tk.Frame(root)
        btns.pack(pady=8)
        tk.Button(btns, text="▶ Khởi động", width=14, command=self.on_start).grid(row=0, column=0, padx=4, pady=3)
        tk.Button(btns, text="⏹ Dừng", width=14, command=self.on_stop).grid(row=0, column=1, padx=4, pady=3)
        tk.Button(btns, text="↻ Làm mới", width=14, command=self.on_refresh).grid(row=1, column=0, padx=4, pady=3)
        tk.Button(btns, text="🌐 Mở Web", width=14, command=self.on_web).grid(row=1, column=1, padx=4, pady=3)
        tk.Button(btns, text="➖ Ẩn", width=14, command=self.on_hide).grid(row=2, column=0, padx=4, pady=3)
        tk.Button(btns, text="✖ Thoát", width=14, command=self.on_exit).grid(row=2, column=1, padx=4, pady=3)

        logbar = tk.Frame(root)
        logbar.pack(fill="x", padx=10)
        tk.Label(logbar, text="Log server:").pack(side="left")
        tk.Button(logbar, text="📋 Copy", command=self.on_copy_log).pack(side="right", padx=2)
        tk.Button(logbar, text="🗑 Xóa", command=self.on_clear_log).pack(side="right", padx=2)
        self.log = scrolledtext.ScrolledText(root, height=9, state="disabled", font=("TkFixedFont", 9))
        self.log.pack(fill="both", expand=True, padx=10, pady=(2, 10))

        self._log("Panel sẵn sàng. Bấm Khởi động để chạy server.")
        self.refresh_status()
        root.after(2000, self._tick)
        root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        try:
            with open(self._panel_log, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except OSError:
            pass

    def _tick(self):
        # Chỉ xả log (nhanh, không chặn). Health-check chạy ở luồng nền
        # để UI không bao giờ đơ.
        while True:
            try:
                self._log(self.srv.logq.get_nowait())
            except queue.Empty:
                break
        self.refresh_status()
        try:
            self.root.after(2000, self._tick)
        except Exception:
            pass

    def _check_status_bg(self):
        try:
            running = self.srv.is_running()
        except Exception:
            running = False
        url = lan_url(self.srv.port) if running else ""
        try:
            self.root.after(0, lambda: self._apply_status(running, url))
        except Exception:
            pass
        self._checking = False

    def _apply_status(self, running, url):
        try:
            if running:
                self.status_var.set("🟢 ĐANG CHẠY")
                self.status_lbl.configure(fg="green")
                self.url_var.set(url)
            else:
                self.status_var.set("🔴 ĐÃ DỪNG")
                self.status_lbl.configure(fg="red")
                self.url_var.set("")
        except Exception:
            pass

    def refresh_status(self):
        if not self._checking:
            self._checking = True
            threading.Thread(target=self._check_status_bg, daemon=True).start()

    def _run_bg(self, fn, done_msg):
        # Luồng worker CHỈ tính toán; mọi cập nhật UI dồn về main thread
        # (tkinter không thread-safe — đụng trực tiếp dễ treo trên Windows).
        def w():
            try:
                r = fn()
            except Exception as e:
                r = f"exception: {e}"
            try:
                self.root.after(0, lambda: self._on_done(r, done_msg))
            except Exception:
                pass
        threading.Thread(target=w, daemon=True).start()

    def _on_done(self, r, done_msg):
        while True:
            try:
                self._log(self.srv.logq.get_nowait())
            except queue.Empty:
                break
        self._log(f"{done_msg}: {r}")
        if isinstance(r, str) and r in ("failed", "timeout") and getattr(self.srv, "last_error", ""):
            self._log("LÝ DO: " + self.srv.last_error)
            try:
                self.msgbox.showerror("LAN SSH Manager", f"{done_msg} thất bại.\n\n{self.srv.last_error}")
            except Exception:
                pass
        self.refresh_status()

    def on_start(self):
        self._log("Đang khởi động server...")
        self._run_bg(self.srv.start, "Khởi động")

    def on_stop(self):
        self._log("Đang dừng server...")
        self._run_bg(self.srv.stop, "Dừng")

    def on_refresh(self):
        while True:
            try:
                self._log(self.srv.logq.get_nowait())
            except queue.Empty:
                break
        self.refresh_status()
        self._log("Đã làm mới trạng thái.")

    def on_web(self):
        url = lan_url(self.srv.port)
        self._log(f"Mở web: {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            self._log(f"Không mở được trình duyệt: {e}")

    def on_hide(self):
        self._log("Đã ẩn panel — bấm icon trên taskbar để mở lại.")
        self.root.iconify()

    def on_clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def on_copy_log(self):
        try:
            text = self.log.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._log("(đã copy log vào clipboard)")
        except Exception as e:
            self._log(f"Copy thất bại: {e}")

    def on_exit(self):
        # Server chạy trong exe → đóng exe là server dừng theo, hỏi rõ trước.
        # stop() có thể mất ~10s nên chạy nền, xong mới destroy (không đơ UI).
        try:
            running = self.srv.is_running()
        except Exception:
            running = False
        if running:
            try:
                ok = self.msgbox.askyesno("Thoát", "Server đang chạy.\nDừng server và thoát?")
            except Exception:
                ok = True
            if not ok:
                return
            self._log("Đang dừng server để thoát...")
            threading.Thread(target=self._exit_after_stop, daemon=True).start()
            return
        self.root.destroy()

    def _exit_after_stop(self):
        try:
            self.srv.stop()
        except Exception:
            pass
        try:
            self.root.after(0, self.root.destroy)
        except Exception:
            pass


def run_selftest_headless(port):
    """Test không GUI: start → health → stop. In SELFTEST-PASS nếu OK."""
    srv = WinServer(port=port)
    if srv.is_running():
        print("SELFTEST-FAIL: port bận trước khi test")
        return 1
    r = srv.start()
    assert r in ("started", "already"), f"start failed: {r} {srv.last_error}"
    assert srv.is_running(), "health failed sau start"
    print(f"server lên OK trên port {port}, thử API...")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as resp:
        assert resp.status == 200, "health API không 200"
    r = srv.stop()
    assert r == "stopped", f"stop failed: {r}"
    assert not srv.is_running(), "vẫn chạy sau stop"
    print("SELFTEST-PASS")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Panel điều khiển LAN SSH Manager (Windows)")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--selftest-headless", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest_headless:
        return run_selftest_headless(a.port)
    import tkinter as tk
    root = tk.Tk()
    Panel(root, WinServer(port=a.port))
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
