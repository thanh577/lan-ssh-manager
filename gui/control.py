#!/usr/bin/env python3
"""Panel điều khiển GUI cho LAN SSH Manager (chạy trong AppImage).

Stdlib-only (tkinter có sẵn theo Python) — không cần pip thêm gì.

Nút: Start server / Stop server / Restart server / Mở Web / Ẩn / Thoát,
kèm dòng trạng thái (đang chạy + URL / đã dừng) và khung log server.

    python3 gui/control.py [--port 8000] [--selftest]

--selftest: tự bấm Start → đợi health → Stop → in SELFTEST-PASS (để test
dưới Xvfb trên máy không màn hình).
"""
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
# LSM_APP_ROOT để test/ghi đè; mặc định: thư mục chứa backend/ (payload) hoặc repo root
APP_ROOT = os.environ.get("LSM_APP_ROOT") or os.path.dirname(HERE)
DATA = os.environ.get("LAN_SSH_DATA",
                      os.path.join(os.path.expanduser("~"), ".local", "share", "lan-ssh-manager"))
PORT = int(os.environ.get("PORT", "8000"))


def base_url(port=PORT):
    return f"http://127.0.0.1:{port}"


def lan_url(port=PORT):
    return f"http://{lan_ip()}:{port}"


def lan_ip():
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5).stdout
        return (out.split() or ["localhost"])[0]
    except Exception:
        return "localhost"


def health_ok(port=PORT, timeout=2):
    try:
        with urllib.request.urlopen(base_url(port) + "/api/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def notify(msg):
    if shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", "LAN SSH Manager", msg], timeout=5,
                           capture_output=True)
        except Exception:
            pass


def find_server_python():
    """Chọn python chạy server: ưu tiên venv của app (đủ deps), rồi mới tới
    python đang chạy panel. Trả về (đường_dẫn, nguồn)."""
    cands = [
        (os.path.join(APP_ROOT, "backend", "venv", "bin", "python"), "venv của app"),
        (sys.executable, "python đang chạy panel"),
    ]
    seen = set()
    for py, src in cands:
        if not py or py in seen:
            continue
        seen.add(py)
        if not (os.path.isfile(py) and os.access(py, os.X_OK)):
            continue
        try:
            r = subprocess.run([py, "-c", "import uvicorn, fastapi"],
                               capture_output=True, timeout=15)
            if r.returncode == 0:
                return py, src
        except Exception:
            pass
    return sys.executable, "python đang chạy panel (thiếu deps?)"


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, ValueError, TypeError):
        return False


class ServerProc:
    """Nắm 1 tiến trình uvicorn do panel tự start (start/stop/restart)."""

    def __init__(self, port=PORT):
        self.port = port
        self.proc = None
        self.logq: queue.Queue = queue.Queue()
        self.recent: deque = deque(maxlen=20)  # dòng log cuối của tiến trình con
        self.last_error = ""

    def is_running(self):
        return health_ok(self.port)

    def start(self):
        if self.is_running():
            return "already"
        self.last_error = ""
        try:
            os.makedirs(DATA, exist_ok=True)
        except Exception as e:
            self.last_error = f"Không tạo được thư mục data {DATA}: {e}"
            return "failed"
        py, src = find_server_python()
        env = dict(os.environ)
        env["DATABASE_URL"] = f"sqlite:///{DATA}/lan_ssh_manager.db"
        env["LAN_SSH_DATA"] = DATA  # đánh dấu để Stop chỉ dọn đúng server của DATA này
        # Bổ sung APP_ROOT vào PYTHONPATH để chạy được từ thư mục DATA
        # (ghi được) thay vì APP_ROOT (có thể read-only như mount AppImage).
        pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = APP_ROOT + (os.pathsep + pp if pp else "")
        try:
            self.proc = subprocess.Popen(
                [py, "-m", "uvicorn", "backend.app.main:app",
                 "--host", "0.0.0.0", "--port", str(self.port)],
                cwd=DATA, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except Exception as e:
            self.last_error = f"Không chạy được {py}: {e}"
            return "failed"
        self._note(f"Dùng {src}: {py}")
        threading.Thread(target=self._drain, daemon=True).start()
        for _ in range(50):  # đợi tối đa ~25s
            if self.is_running():
                notify(f"Server đã chạy — {lan_url(self.port)}")
                return "started"
            if self.proc.poll() is not None:
                self.last_error = self._diagnose(self.proc.returncode)
                return "failed"
            time.sleep(0.5)
        self.last_error = "Hết 25s chờ mà server chưa lên — xem log bên dưới."
        return "timeout"

    def _note(self, msg):
        try:
            self.logq.put_nowait(msg)
        except queue.Full:
            pass

    def _drain(self):
        try:
            for line in self.proc.stdout:
                line = line.rstrip()
                self.recent.append(line)
                try:
                    self.logq.put_nowait(line)
                except queue.Full:
                    pass
        except Exception:
            pass

    def _diagnose(self, code):
        """Lý do lỗi từ dòng log cuối của tiến trình con (thay vì đoán mò)."""
        tail = ""
        for ln in reversed(self.recent):
            if ln.strip():
                tail = ln.strip()[:300]
                break
        blob = "\n".join(self.recent)
        if "No module named" in blob or "ModuleNotFoundError" in blob:
            hint = "thiếu thư viện Python"
        elif "Read-only file system" in blob or "Permission denied" in blob:
            hint = "không ghi được file (thư mục read-only/thiếu quyền)"
        elif "Address already in use" in blob:
            hint = f"port {self.port} đang bị tiến trình khác giữ"
        else:
            hint = "xem traceback trong log"
        msg = f"Tiến trình server thoát (mã {code}) — {hint}."
        if tail:
            msg += f" Lỗi cuối: {tail}"
        return msg

    def stop(self, pids=None):
        """Dừng server. Mặc định chỉ dừng con của panel + tiến trình sót
        CÙNG DATA (không bao giờ giết server của DATA khác chung port).
        Muốn dừng server lạ (khác DATA) phải truyền pids tường minh
        (GUI hỏi xác nhận trước)."""
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        targets = list(pids) if pids else self._stray_pids(same_data=True)
        for pid in targets:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, ValueError):
                pass
        for _ in range(10):
            alive = [pid for pid in targets if _alive(pid)]
            if not self.is_running() and not alive:
                notify("Server đã dừng")
                return "stopped"
            time.sleep(0.5)
        for pid in targets:
            if _alive(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, ValueError):
                    pass
        if not self.is_running():
            notify("Server đã dừng")
            return "stopped"
        if not targets:
            return "foreign-running"
        return "timeout"

    def foreign_pids(self):
        """Tiến trình server cùng port nhưng KHÁC DATA (của người khác)."""
        return self._stray_pids(same_data=False)

    def _stray_pids(self, same_data=True):
        if not shutil.which("pgrep"):
            return []
        try:
            out = subprocess.run(
                ["pgrep", "-f", f"uvicorn backend.app.main:app.*--port {self.port}"],
                capture_output=True, text=True, timeout=5).stdout
        except Exception:
            return []
        me = os.getpid()
        found = []
        for pid in out.split():
            try:
                pidn = int(pid)
            except ValueError:
                continue
            if pidn == me:
                continue
            if same_data and not self._same_data_dir(pidn):
                continue
            if not same_data and self._same_data_dir(pidn):
                continue
            found.append(pidn)
        return found

    def _same_data_dir(self, pid):
        """Tiến trình kia có dùng cùng DATA với panel không (đọc environ)."""
        try:
            with open(f"/proc/{pid}/environ", "rb") as f:
                entries = f.read().split(b"\0")
            return ("LAN_SSH_DATA=" + DATA).encode() in entries
        except (OSError, ValueError):
            return False

    def restart(self):
        self.stop()
        return self.start()


# ---------------- GUI ----------------

class Panel:
    def __init__(self, root, srv: ServerProc, selftest=False):
        import tkinter as tk
        from tkinter import scrolledtext
        self.tk = tk
        self.root = root
        self.srv = srv
        self.selftest = selftest
        root.title("LAN SSH Manager")
        root.geometry("460x470")
        root.minsize(440, 430)
        root.resizable(True, True)  # cho phép resize tự do

        self.status_var = tk.StringVar(value="Đang kiểm tra...")
        tk.Label(root, text="LAN SSH Manager", font=("TkDefaultFont", 14, "bold")).pack(pady=(10, 2))
        self.status_lbl = tk.Label(root, textvariable=self.status_var, font=("TkDefaultFont", 11))
        self.status_lbl.pack()
        self.url_var = tk.StringVar(value="")
        tk.Label(root, textvariable=self.url_var, fg="blue").pack()

        btns = tk.Frame(root)
        btns.pack(pady=8)
        self.b_start = tk.Button(btns, text="▶ Start server", width=14, command=self.on_start)
        self.b_stop = tk.Button(btns, text="⏹ Stop server", width=14, command=self.on_stop)
        self.b_restart = tk.Button(btns, text="↻ Restart server", width=14, command=self.on_restart)
        self.b_web = tk.Button(btns, text="🌐 Mở Web", width=14, command=self.on_web)
        self.b_hide = tk.Button(btns, text="➖ Ẩn", width=14, command=self.on_hide)
        self.b_exit = tk.Button(btns, text="✖ Thoát", width=14, command=self.on_exit)
        self.b_start.grid(row=0, column=0, padx=4, pady=3)
        self.b_stop.grid(row=0, column=1, padx=4, pady=3)
        self.b_restart.grid(row=1, column=0, padx=4, pady=3)
        self.b_web.grid(row=1, column=1, padx=4, pady=3)
        self.b_hide.grid(row=2, column=0, padx=4, pady=3)
        self.b_exit.grid(row=2, column=1, padx=4, pady=3)

        logbar = tk.Frame(root)
        logbar.pack(fill="x", padx=10)
        tk.Label(logbar, text="Log server:").pack(side="left")
        tk.Button(logbar, text="📋 Copy log", command=self.on_copy_log).pack(side="right", padx=2)
        tk.Button(logbar, text="🗑 Xóa", command=self.on_clear_log).pack(side="right", padx=2)
        self.log = scrolledtext.ScrolledText(root, height=9, state="disabled", font=("TkFixedFont", 9))
        self.log.pack(fill="both", expand=True, padx=10, pady=(2, 10))
        # Menu chuột phải: copy đoạn bôi đen / copy tất cả / xóa
        self.ctx = tk.Menu(root, tearoff=0)
        self.ctx.add_command(label="Copy đoạn đã chọn", command=self.on_copy_sel)
        self.ctx.add_command(label="Copy tất cả log", command=self.on_copy_log)
        self.ctx.add_command(label="Xóa log", command=self.on_clear_log)
        self.log.bind("<Button-3>", self._popup_ctx)
        self.log.bind("<Control-c>", lambda e: (self.on_copy_sel(), "break"))
        self.log.bind("<Control-C>", lambda e: (self.on_copy_sel(), "break"))

        self._log("Panel sẵn sàng. Bấm Start server để chạy.")
        self.refresh_status()
        root.after(2000, self._tick)
        root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _tick(self):
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

    def refresh_status(self):
        if self.srv.is_running():
            url = lan_url(self.srv.port)
            self.status_var.set("🟢 ĐANG CHẠY")
            self.status_lbl.configure(fg="green")
            self.url_var.set(url)
        else:
            self.status_var.set("🔴 ĐÃ DỪNG")
            self.status_lbl.configure(fg="red")
            self.url_var.set("")

    def _popup_ctx(self, event):
        try:
            self.ctx.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass
        return "break"

    def on_copy_sel(self):
        """Copy đoạn đang bôi đen (không có thì copy tất cả)."""
        try:
            try:
                text = self.log.get("sel.first", "sel.last")
            except Exception:
                text = self.log.get("1.0", "end-1c")
            if not text:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._log("(đã copy vào clipboard)")
        except Exception as e:
            self._log(f"Copy thất bại: {e}")

    def on_copy_log(self):
        try:
            text = self.log.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._log("(đã copy log vào clipboard)")
        except Exception as e:
            self._log(f"Copy thất bại: {e}")

    def on_clear_log(self):
        try:
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")
        except Exception:
            pass

    def _run_bg(self, fn, done_msg):
        def w():
            r = fn()
            self._flush_server_log()
            self._log(f"{done_msg}: {r}")
            if r in ("failed", "timeout") and getattr(self.srv, "last_error", ""):
                self._log("LÝ DO: " + self.srv.last_error)
                if not self.selftest:
                    try:
                        from tkinter import messagebox
                        messagebox.showerror("LAN SSH Manager",
                                             f"{done_msg} thất bại.\n\n{self.srv.last_error}")
                    except Exception:
                        pass
            self.refresh_status()
        threading.Thread(target=w, daemon=True).start()

    def _flush_server_log(self):
        while True:
            try:
                self._log(self.srv.logq.get_nowait())
            except queue.Empty:
                break

    def on_start(self):
        self._log("Đang start server...")
        self._run_bg(self.srv.start, "Start")

    def on_stop(self):
        # Server lạ (khác DATA, VD server chính của máy) thì hỏi trước,
        # không được tự ý giết.
        try:
            own_alive = self.srv.proc and self.srv.proc.poll() is None
        except Exception:
            own_alive = False
        if not own_alive and self.srv.is_running():
            foreign = self.srv.foreign_pids()
            if foreign:
                try:
                    from tkinter import messagebox
                    ok = messagebox.askyesno(
                        "Xác nhận dừng server lạ",
                        f"Server đang chạy bởi tiến trình khác\n(PID {', '.join(map(str, foreign))}, khác DATA của panel).\n\nDừng nó?")
                except Exception:
                    ok = False
                if not ok:
                    self._log("Giữ nguyên server của tiến trình khác.")
                    return
                self._log(f"Đang dừng server lạ PID {foreign} theo xác nhận...")
                self._run_bg(lambda: self.srv.stop(pids=foreign), "Stop server lạ")
                return
        self._log("Đang stop server...")
        self._run_bg(self.srv.stop, "Stop")

    def on_restart(self):
        self._log("Đang restart server...")
        self._run_bg(self.srv.restart, "Restart")

    def on_web(self):
        url = lan_url(self.srv.port)
        self._log(f"Mở web: {url}")
        try:
            subprocess.Popen(["xdg-open", url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self._log(f"Không mở được trình duyệt: {e}")

    def on_hide(self):
        self._log("Đã ẩn panel — bấm icon trên taskbar để mở lại.")
        notify("Panel đã ẩn — bấm icon taskbar để mở lại")
        self.root.iconify()

    def on_exit(self):
        self._log("Thoát: dừng server (nếu do panel start)...")
        try:
            if self.srv.proc and self.srv.proc.poll() is None:
                self.srv.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


def run_selftest(port):
    """Chạy GUI thật, tự bấm Start/Stop qua handler, không cần chạm tay."""
    import tkinter as tk
    srv = ServerProc(port=port)
    if srv.is_running():
        print("SELFTEST-FAIL: port bận trước khi test")
        return 1
    root = tk.Tk()
    root.withdraw()  # vẫn cần display (chạy dưới xvfb-run)
    p = Panel(root, srv, selftest=True)

    result = {}

    def step1():
        py, src = find_server_python()
        if os.path.isfile(os.path.join(APP_ROOT, "backend", "venv", "bin", "python")):
            assert "venv" in py, f"phải ưu tiên venv của app, got {py}"
        assert srv.start() in ("started", "already"), "start failed"
        assert srv.is_running(), "health failed sau start"
        # tiến trình con phải chạy từ thư mục DATA (ghi được), không phải
        # APP_ROOT (có thể read-only như mount AppImage)
        try:
            cw = os.readlink(f"/proc/{srv.proc.pid}/cwd")
            assert os.path.realpath(cw) == os.path.realpath(DATA), f"cwd sai: {cw}"
        except (OSError, AttributeError):
            pass
        p.on_copy_sel()  # menu chuột phải/copy không được crash
        result["started"] = True
        root.after(500, step2)

    def step2():
        assert srv.stop() == "stopped", "stop failed"
        assert not srv.is_running(), "vẫn chạy sau stop"
        root.after(500, step3)

    def step3():
        # Hồi quy: Stop KHÔNG được giết server lạ cùng port khác DATA
        # (tình huống panel AppImage giết nhầm server chính của máy).
        fenv = dict(os.environ)
        fenv.pop("LAN_SSH_DATA", None)
        fenv["DATABASE_URL"] = f"sqlite:///{DATA}-foreign.db"
        py, _src = find_server_python()
        fp = subprocess.Popen(
            [py, "-m", "uvicorn", "backend.app.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=APP_ROOT, env=fenv,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(40):
                if health_ok(port):
                    break
                time.sleep(0.5)
            assert health_ok(port), "foreign server không lên"
            assert fp.pid in srv.foreign_pids(), "phải nhận diện được server lạ"
            r = srv.stop()
            assert r == "foreign-running", f"phải từ chối, got {r}"
            assert health_ok(port), "server lạ PHẢI còn sống sau Stop"
            assert _alive(fp.pid), "tiến trình lạ PHẢI còn sống"
        finally:
            fp.terminate()
            try:
                fp.wait(timeout=5)
            except subprocess.TimeoutExpired:
                fp.kill()
        for f in (f"{DATA}-foreign.db",):
            try:
                os.remove(f)
            except OSError:
                pass
        print("SELFTEST-PASS")
        root.destroy()

    root.after(500, step1)
    root.mainloop()
    return 0 if result.get("started") else 1


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Panel điều khiển LAN SSH Manager")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return run_selftest(a.port)
    import tkinter as tk
    root = tk.Tk()
    Panel(root, ServerProc(port=a.port))
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
