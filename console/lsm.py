#!/usr/bin/env python3
"""lsm — Console client cho LAN SSH Manager.

Chạy được trên mọi máy chỉ có python3 (stdlib only, không cần pip/venv),
hợp với máy headless / không có trình duyệt.

Cài đặt (từ máy đã clone repo):
    bash scripts/install-console.sh
    # hoặc thủ công: cp console/lsm.py ~/.local/bin/lsm && chmod +x ~/.local/bin/lsm

Dùng nhanh:
    lsm login --url http://192.168.1.10:8000 -u admin
    lsm status
    lsm ls
    lsm info 1
    lsm exec 1 "uptime"
    lsm batch -i 1,2 "uptime"
    lsm terminal 1        # nhảy vào SSH bằng lệnh ssh của hệ thống
    lsm console ls          # cổng console vật lý (máy chưa có OS)
    lsm console attach 1    # mở console tương tác để cài OS (thoát: Ctrl+])
    lsm menu              # menu tương tác (số 1..n), hợp máy console thuần

Mọi lệnh đều có --url/--token/--json. Env: LSM_URL, LSM_TOKEN, LSM_USER, LSM_PASS.
"""
import argparse
import getpass
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

APP = "lan-ssh-manager"
CFG_DIR = os.path.join(os.path.expanduser("~"), ".config", APP)
CFG_FILE = os.path.join(CFG_DIR, "config.json")
VERSION = "1.1.0"


class ApiError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


# ---------- config ----------

def load_cfg():
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cfg(d):
    os.makedirs(CFG_DIR, exist_ok=True)
    tmp = CFG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CFG_FILE)


def resolve_url(args):
    return (args.url or os.environ.get("LSM_URL")
            or load_cfg().get("url") or "http://127.0.0.1:8000").rstrip("/")


def resolve_token(args):
    return (args.token or os.environ.get("LSM_TOKEN")
            or load_cfg().get("token") or "")


# ---------- http ----------

def api(method, base, path, token="", body=None, query=None):
    url = base + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8") or "{}")
            msg = payload.get("message") or payload.get("detail") or f"HTTP {e.code}"
        except (ValueError, TypeError):
            msg = f"HTTP {e.code}"
        raise ApiError(msg, e.code)
    except urllib.error.URLError as e:
        raise ApiError(f"Không kết nối được server ({e.reason}). "
                       f"Kiểm tra --url và mạng LAN.")


def unwrap(resp):
    """Backend trả {success, data, message}."""
    if isinstance(resp, dict) and "success" in resp:
        if not resp.get("success"):
            raise ApiError(resp.get("message") or "Thất bại")
        if resp.get("message"):
            print(resp["message"])
        return resp.get("data")
    return resp


def need_login(args):
    tok = resolve_token(args)
    if not tok:
        raise ApiError("Chưa đăng nhập. Chạy: lsm login --url http://<IP>:8000 -u admin")
    return tok


# ---------- output ----------

def out(data, as_json):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data
    return data


def table(rows, headers):
    if not rows:
        print("(trống)")
        return
    widths = [len(h) for h in headers]
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(str(c)))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*[str(c) for c in r]))


# ---------- commands ----------

def cmd_login(args):
    url = resolve_url(args)
    user = args.user or os.environ.get("LSM_USER") or input("Tên đăng nhập: ").strip()
    pw = args.password or os.environ.get("LSM_PASS") or getpass.getpass("Mật khẩu: ")
    data = unwrap(api("POST", url, "/api/auth/login",
                      body={"username": user, "password": pw}))
    cfg = load_cfg()
    cfg.update({"url": url, "token": data["token"], "username": data.get("username", user)})
    save_cfg(cfg)
    print(f"Đăng nhập thành công ({cfg['username']}) — server {url}")


def cmd_logout(args):
    url, tok = resolve_url(args), resolve_token(args)
    if tok:
        try:
            unwrap(api("POST", url, "/api/auth/logout", token=tok))
        except ApiError as e:
            print(f"(server: {e})")
    cfg = load_cfg()
    cfg.pop("token", None)
    save_cfg(cfg)
    print("Đã đăng xuất (xóa token local).")


def cmd_status(args):
    url, tok = resolve_url(args), need_login(args)
    d = out(unwrap(api("GET", url, "/api/dashboard", token=tok)), args.json)
    if args.json:
        return
    print(f"Máy: {d['total']}  |  Trực tuyến: {d['online']}  |  "
          f"Ngoại tuyến: {d['offline']}  |  Tắt/không rõ: {d.get('disabled', 0)}")
    table([[m["id"], m["name"], m.get("hostname", ""),
            "TẮT" if not m.get("enabled") else m.get("status", "?")]
           for m in d.get("machines", [])],
          ["ID", "Tên", "IP/host", "Trạng thái"])


def cmd_ls(args):
    url, tok = resolve_url(args), need_login(args)
    ms = out(unwrap(api("GET", url, "/api/machines", token=tok)), args.json)
    if args.json:
        return
    table([[m["id"], m["name"], m["hostname"], m.get("port", 22),
            m.get("username", ""), m.get("auth_type", ""),
            "bật" if m.get("enabled") else "tắt"]
           for m in ms],
          ["ID", "Tên", "IP/host", "Port", "SSH user", "Auth", "Bật"])


def cmd_show(args):
    url, tok = resolve_url(args), need_login(args)
    m = out(unwrap(api("GET", url, f"/api/machines/{args.id}", token=tok)), args.json)
    if args.json:
        return
    for k in ("id", "name", "hostname", "port", "username", "auth_type",
              "group_id", "description", "enabled", "last_seen", "has_credential"):
        print(f"{k:15} {m.get(k)}")


def _prompt_machine(cur=None):
    cur = cur or {}
    def ask(key, label, default="", secret=False):
        d = str(cur.get(key, default) or default)
        hint = f" [{d}]" if d and not secret else ""
        v = (getpass.getpass(f"{label}{hint}: ") if secret
             else input(f"{label}{hint}: ").strip())
        return v if v else d
    name = ask("name", "Tên máy")
    host = ask("hostname", "IP/hostname")
    port = ask("port", "Port SSH", "22")
    user = ask("username", "SSH user")
    auth = ask("auth_type", "Auth (password/key)", "password")
    cred = ask("credential", "Mật khẩu hoặc nội dung private key (trống=giữ cũ)", "", True)
    desc = ask("description", "Mô tả", "")
    return {"name": name, "hostname": host, "port": int(port or 22),
            "username": user, "auth_type": auth, "credential": cred,
            "description": desc, "enabled": True}


def cmd_add(args):
    url, tok = resolve_url(args), need_login(args)
    if args.name and args.host and args.ssh_user:
        body = {"name": args.name, "hostname": args.host, "port": args.port,
                "username": args.ssh_user, "auth_type": args.auth,
                "credential": args.cred or "", "description": args.desc or "",
                "enabled": True}
    else:
        body = _prompt_machine()
    m = unwrap(api("POST", url, "/api/machines", token=tok, body=body))
    print(f"Đã thêm máy #{m['id']} ({m['name']}). Gợi ý: lsm test {m['id']}")


def cmd_del(args):
    url, tok = resolve_url(args), need_login(args)
    if not args.yes and input(f"Xóa máy #{args.id}? (y/N): ").strip().lower() != "y":
        print("Đã hủy.")
        return
    unwrap(api("DELETE", url, f"/api/machines/{args.id}", token=tok))
    print("Đã xóa.")


def cmd_test(args):
    url, tok = resolve_url(args), need_login(args)
    try:
        d = unwrap(api("POST", url, f"/api/machines/{args.id}/test", token=tok))
        print("OK:", (d or {}).get("message", "SSH thành công"))
    except ApiError as e:
        print(f"THẤT BẠI (HTTP {e.code}): {e}")
        sys.exit(1)


def cmd_info(args):
    url, tok = resolve_url(args), need_login(args)
    d = out(unwrap(api("GET", url, f"/api/machines/{args.id}/system", token=tok)), args.json)
    if args.json:
        return
    if isinstance(d, dict):
        for k, v in d.items():
            print(f"{k:15} {v if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False)}")
    else:
        print(d)


def cmd_exec(args):
    url, tok = resolve_url(args), need_login(args)
    command = args.command or " ".join(args.rest or [])
    if not command:
        command = input("Lệnh cần chạy: ").strip()
    if not command:
        raise ApiError("Chưa nhập lệnh.")
    r = out(unwrap(api("POST", url, f"/api/machines/{args.id}/command",
                       token=tok, body={"command": command, "timeout": args.timeout})),
            args.json)
    if args.json:
        return
    print(f"exit={r.get('exit_code')}")
    if r.get("stdout"):
        print(r["stdout"], end="" if r["stdout"].endswith("\n") else "\n")
    if r.get("stderr"):
        print(f"[stderr]\n{r['stderr']}", file=sys.stderr)


def cmd_batch(args):
    url, tok = resolve_url(args), need_login(args)
    ids = [int(x) for x in args.ids.replace(" ", "").split(",") if x]
    command = args.command or " ".join(args.rest or [])
    if not ids:
        raise ApiError("Chưa chọn máy (--ids 1,2,3).")
    if not command:
        command = input("Lệnh chạy hàng loạt: ").strip()
    d = out(unwrap(api("POST", url, "/api/commands/batch", token=tok,
                       body={"machine_ids": ids, "command": command,
                             "timeout": args.timeout})), args.json)
    if args.json:
        return
    s = d.get("summary", {})
    print(f"Kết quả: {s.get('ok', '?')}/{s.get('total', '?')} OK")
    for r in d.get("results", []):
        mark = "OK " if r.get("success") else "LỖI"
        first = (r.get("stdout") or r.get("error") or "").strip().split("\n")[0][:100]
        print(f"  [{mark}] #{r.get('machine_id')} {r.get('machine_name', '')}: {first}")


def cmd_svc(args):
    url, tok = resolve_url(args), need_login(args)
    if args.action == "ls":
        d = unwrap(api("GET", url, f"/api/machines/{args.id}/services", token=tok))
        print(d.get("running", d))
        return
    if args.action in ("stop", "restart") and not args.yes:
        if input(f"{args.action} service '{args.name}' trên máy #{args.id}? (y/N): "
                 ).strip().lower() != "y":
            print("Đã hủy.")
            return
    r = unwrap(api("POST", url, f"/api/machines/{args.id}/services/{args.name}/{args.action}",
                   token=tok))
    print(r.get("stdout", r))


def cmd_logs(args):
    url, tok = resolve_url(args), need_login(args)
    d = out(unwrap(api("POST", url, f"/api/machines/{args.id}/logs", token=tok,
                       body={"service": args.service or "", "lines": args.lines})),
            args.json)
    if not args.json:
        print(d.get("output", d))


def cmd_files(args):
    url, tok = resolve_url(args), need_login(args)
    d = out(unwrap(api("GET", url, f"/api/machines/{args.id}/files", token=tok,
                       query={"path": args.path})), args.json)
    if args.json:
        return
    print(f"Thư mục: {d.get('path')}")
    table([[e.get("name", ""), "d" if e.get("is_dir") else "f",
            e.get("size", ""), e.get("mtime", "") or ""]
           for e in d.get("entries", [])],
          ["Tên", "Loại", "Size", "Sửa lúc"])


def cmd_users(args):
    url, tok = resolve_url(args), need_login(args)
    us = out(unwrap(api("GET", url, f"/api/machines/{args.id}/users", token=tok)), args.json)
    if args.json:
        return
    table([[u.get("name", ""), u.get("uid", ""), u.get("status", ""),
            u.get("shell", "")] for u in us],
          ["User", "UID", "Trạng thái", "Shell"])


def cmd_audit(args):
    url, tok = resolve_url(args), need_login(args)
    rows = out(unwrap(api("GET", url, "/api/audit", token=tok,
                          query={"limit": args.limit})), args.json)
    if args.json:
        return
    table([[r.get("id", ""), (r.get("created_at", "") or "")[:19].replace("T", " "),
            r.get("action", ""), f"m{r.get('machine_id')}" if r.get("machine_id") else "-",
            (r.get("status", "") or "")[:20]] for r in rows],
          ["ID", "Lúc", "Hành động", "Máy", "KQ"])


def cmd_groups(args):
    url, tok = resolve_url(args), need_login(args)
    gs = out(unwrap(api("GET", url, "/api/groups", token=tok)), args.json)
    if args.json:
        return
    table([[g.get("id", ""), g.get("name", ""), g.get("description", "")] for g in gs],
          ["ID", "Tên", "Mô tả"])


def cmd_terminal(args):
    """Nhảy SSH trực tiếp bằng client ssh của hệ thống (đúng chất console)."""
    url, tok = resolve_url(args), need_login(args)
    m = unwrap(api("GET", url, f"/api/machines/{args.id}", token=tok))
    target = f"{m['username']}@{m['hostname']}"
    cmd = ["ssh", "-p", str(m.get("port", 22)), target]
    print(f"Đang mở SSH: {' '.join(cmd)}  (Ctrl+D hoặc 'exit' để thoát)")
    os.execvp("ssh", cmd)


# ---------- serial console (máy chưa có OS) ----------

def _console_list(url, tok):
    return unwrap(api("GET", url, "/api/consoles", token=tok))


def cmd_console_ls(args):
    url, tok = resolve_url(args), need_login(args)
    d = out(_console_list(url, tok), args.json)
    if args.json:
        return
    print("Cổng serial thấy trên máy chủ:",
          ", ".join(p["device"] for p in d.get("system_ports", [])) or "(không thấy)")
    table([[c["id"], c["name"], c["device"], c.get("baudrate", ""),
            c.get("machine_name", "") or "",
            "ĐANG DÙNG" if c.get("in_use") else ("rảnh" if c.get("enabled") else "tắt")]
           for c in d.get("consoles", [])],
          ["ID", "Tên", "Cổng", "Baud", "Máy", "Trạng thái"])


def cmd_console_add(args):
    url, tok = resolve_url(args), need_login(args)
    name = args.cname or input("Tên (vd Máy 04 - console): ").strip()
    device = args.device or input("Thiết bị trên máy chủ app (vd /dev/ttyUSB0): ").strip()
    if not name or not device:
        raise ApiError("Cần nhập tên và thiết bị.")
    body = {"name": name, "device": device, "baudrate": args.baud,
            "description": args.desc or ""}
    c = unwrap(api("POST", url, "/api/consoles", token=tok, body=body))
    print(f"Đã thêm console #{c['id']} ({c['device']} @ {c['baudrate']}).")


def cmd_console_del(args):
    url, tok = resolve_url(args), need_login(args)
    if not args.yes and input(f"Xóa console #{args.id}? (y/N): ").strip().lower() != "y":
        print("Đã hủy.")
        return
    unwrap(api("DELETE", url, f"/api/consoles/{args.id}", token=tok))
    print("Đã xóa.")


def cmd_console_release(args):
    url, tok = resolve_url(args), need_login(args)
    unwrap(api("POST", url, f"/api/consoles/{args.id}/release", token=tok))
    print("Đã giải phóng.")


def cmd_console_break(args):
    url, tok = resolve_url(args), need_login(args)
    unwrap(api("POST", url, f"/api/consoles/{args.id}/break", token=tok))
    print("Đã gửi BREAK.")


def cmd_console_attach(args):
    """Mở console tương tác qua polling REST (gõ từng phím như ngồi trực tiếp)."""
    url, tok = resolve_url(args), need_login(args)
    cid = args.id
    stop = threading.Event()
    state = {"seq": 0}

    def poller():
        while not stop.is_set():
            try:
                d = unwrap(api("GET", url, f"/api/consoles/{cid}/read", token=tok,
                               query={"since": state["seq"]}))
                state["seq"] = d.get("next", state["seq"])
                for e in d.get("entries", []):
                    sys.stdout.write(e.get("data", ""))
                sys.stdout.flush()
            except ApiError as e:
                print(f"\n[Lỗi đọc console: {e}]", file=sys.stderr)
                stop.set()
            except Exception:
                pass
            stop.wait(0.4)

    print(f"Đã nối console #{cid} (gõ trực tiếp, thoát: Ctrl+])...")
    t = threading.Thread(target=poller, daemon=True)
    t.start()
    try:
        if sys.stdin.isatty():
            import tty
            import termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                while not stop.is_set():
                    ch = os.read(fd, 1)
                    if not ch:
                        break
                    if ch == b"\x1d":  # Ctrl+]
                        break
                    try:
                        unwrap(api("POST", url, f"/api/consoles/{cid}/write",
                                   token=tok, body={"data": ch.decode("utf-8", "replace")}))
                    except ApiError as e:
                        print(f"\n[Lỗi gửi phím: {e}]", file=sys.stderr)
                        break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
                print()
        else:
            for line in sys.stdin:
                if stop.is_set():
                    break
                unwrap(api("POST", url, f"/api/consoles/{cid}/write",
                           token=tok, body={"data": line}))
    except ApiError as e:
        print(f"Lỗi: {e}", file=sys.stderr)
    finally:
        stop.set()
        t.join(timeout=2)
        print("Đã ngắt console.")


# ---------- menu tương tác ----------

def cmd_menu(args):
    url = resolve_url(args)
    try:
        tok = need_login(args)
    except ApiError as e:
        print(e)
        print("--- Đăng nhập ---")
        cmd_login(args)
        url = resolve_url(args)
        tok = need_login(args)
    while True:
        print("\n=== LAN SSH Manager (console) ===")
        print(" 1. Trạng thái tổng quan      2. Danh sách máy")
        print(" 3. Xem thông tin máy         4. Chạy lệnh 1 máy")
        print(" 5. Chạy lệnh hàng loạt       6. Dịch vụ")
        print(" 7. Nhật ký hệ thống          8. Duyệt tệp")
        print(" 9. Kiểm tra SSH              0. Thoát")
        c = input("Chọn [0-9]: ").strip()
        try:
            if c == "0" or c.lower() in ("q", "quit", "exit"):
                break
            elif c == "1":
                cmd_status(args)
            elif c == "2":
                cmd_ls(args)
            elif c == "3":
                args.id = int(input("ID máy: "))
                cmd_info(args)
            elif c == "4":
                args.id = int(input("ID máy: "))
                args.command, args.rest = "", None
                cmd_exec(args)
            elif c == "5":
                args.ids = input("IDs (vd 1,2,3): ")
                args.command, args.rest = "", None
                cmd_batch(args)
            elif c == "6":
                args.id = int(input("ID máy: "))
                sub = input("ls | status <tên> | restart <tên>: ").split()
                if not sub or sub[0] == "ls":
                    args.action, args.name = "ls", ""
                else:
                    args.action = sub[0]
                    args.name = sub[1] if len(sub) > 1 else input("Tên service: ")
                cmd_svc(args)
            elif c == "7":
                args.id = int(input("ID máy: "))
                args.service = input("Service (trống=log hệ thống): ").strip()
                cmd_logs(args)
            elif c == "8":
                args.id = int(input("ID máy: "))
                args.path = input("Đường dẫn [/]: ").strip() or "/"
                cmd_files(args)
            elif c == "9":
                args.id = int(input("ID máy: "))
                cmd_test(args)
            else:
                print("Lựa chọn không hợp lệ.")
        except ApiError as e:
            print(f"Lỗi: {e}")
        except (ValueError, KeyboardInterrupt):
            print()
            continue


# ---------- cli ----------

def add_common(p):
    p.add_argument("--url", default="", help="VD http://192.168.1.10:8000 (hoặc env LSM_URL)")
    p.add_argument("--token", default="", help="Token (hoặc env LSM_TOKEN)")
    p.add_argument("--json", action="store_true", help="In JSON thô cho script")


def build_parser():
    p = argparse.ArgumentParser(prog="lsm", description="Console client cho LAN SSH Manager")
    p.add_argument("-V", "--version", action="version", version=f"lsm {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("login", help="Đăng nhập và lưu token")
    s.add_argument("--url", default=""); s.add_argument("-u", "--user", default="")
    s.add_argument("-p", "--password", default="")
    s.set_defaults(fn=cmd_login)

    s = sub.add_parser("logout", help="Đăng xuất (xóa token)")
    add_common(s); s.set_defaults(fn=cmd_logout)

    for name, help_, fn in [
        ("status", "Tổng quan online/offline", cmd_status),
        ("ls", "Danh sách máy (alias: machines)", cmd_ls),
        ("machines", "Danh sách máy", cmd_ls),
        ("audit", "Nhật ký thao tác", cmd_audit),
        ("groups", "Danh sách nhóm", cmd_groups),
        ("menu", "Menu tương tác cho máy console", cmd_menu),
    ]:
        s = sub.add_parser(name, help=help_)
        add_common(s)
        if name == "audit":
            s.add_argument("-n", "--limit", type=int, default=50)
        s.set_defaults(fn=fn)

    s = sub.add_parser("show", help="Chi tiết 1 máy")
    add_common(s); s.add_argument("id", type=int); s.set_defaults(fn=cmd_show)

    s = sub.add_parser("add", help="Thêm máy")
    add_common(s)
    s.add_argument("--name", default=""); s.add_argument("--host", default="")
    s.add_argument("--port", type=int, default=22); s.add_argument("--ssh-user", default="")
    s.add_argument("--auth", default="password", choices=["password", "key"])
    s.add_argument("--cred", default=""); s.add_argument("--desc", default="")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("del", help="Xóa máy")
    add_common(s); s.add_argument("id", type=int)
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(fn=cmd_del)

    s = sub.add_parser("test", help="Kiểm tra SSH")
    add_common(s); s.add_argument("id", type=int); s.set_defaults(fn=cmd_test)

    s = sub.add_parser("info", help="Thông tin hệ thống (CPU/RAM/disk/OS)")
    add_common(s); s.add_argument("id", type=int); s.set_defaults(fn=cmd_info)

    s = sub.add_parser("exec", help='Chạy lệnh: lsm exec 1 "uptime"')
    add_common(s); s.add_argument("id", type=int)
    s.add_argument("command", nargs="?", default="")
    s.add_argument("rest", nargs="*", help=argparse.SUPPRESS)
    s.add_argument("-t", "--timeout", type=int, default=30)
    s.set_defaults(fn=cmd_exec)

    s = sub.add_parser("batch", help='Lệnh hàng loạt: lsm batch -i 1,2 "uptime"')
    add_common(s); s.add_argument("-i", "--ids", default="")
    s.add_argument("command", nargs="?", default="")
    s.add_argument("rest", nargs="*", help=argparse.SUPPRESS)
    s.add_argument("-t", "--timeout", type=int, default=30)
    s.set_defaults(fn=cmd_batch)

    s = sub.add_parser("svc", help="Dịch vụ: lsm svc 1 ls | lsm svc 1 restart nginx")
    add_common(s); s.add_argument("id", type=int)
    s.add_argument("action", choices=["ls", "status", "start", "stop", "restart", "enable", "disable"])
    s.add_argument("name", nargs="?", default="")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(fn=cmd_svc)

    s = sub.add_parser("logs", help="Xem log: lsm logs 1 --service nginx")
    add_common(s); s.add_argument("id", type=int)
    s.add_argument("-s", "--service", default=""); s.add_argument("-n", "--lines", type=int, default=100)
    s.set_defaults(fn=cmd_logs)

    s = sub.add_parser("files", help="Duyệt tệp: lsm files 1 /home/tha")
    add_common(s); s.add_argument("id", type=int)
    s.add_argument("path", nargs="?", default="/")
    s.set_defaults(fn=cmd_files)

    s = sub.add_parser("users", help="User Linux trên máy")
    add_common(s); s.add_argument("id", type=int); s.set_defaults(fn=cmd_users)

    s = sub.add_parser("terminal", help="Mở SSH trực tiếp (dùng lệnh ssh hệ thống)")
    add_common(s); s.add_argument("id", type=int); s.set_defaults(fn=cmd_terminal)

    c = sub.add_parser("console", help="Console vật lý cho máy chưa có OS")
    csub = c.add_subparsers(dest="console_cmd", required=True)
    s = csub.add_parser("ls", help="Liệt kê cổng console")
    add_common(s); s.set_defaults(fn=cmd_console_ls)
    s = csub.add_parser("add", help="Khai báo cổng: lsm console add --name ... --device /dev/ttyUSB0")
    add_common(s)
    s.add_argument("--name", dest="cname", default=""); s.add_argument("--device", default="")
    s.add_argument("--baud", type=int, default=115200); s.add_argument("--desc", default="")
    s.set_defaults(fn=cmd_console_add)
    s = csub.add_parser("del", help="Xóa cổng console")
    add_common(s); s.add_argument("id", type=int)
    s.add_argument("-y", "--yes", action="store_true"); s.set_defaults(fn=cmd_console_del)
    s = csub.add_parser("attach", help="Mở console tương tác (thoát: Ctrl+])")
    add_common(s); s.add_argument("id", type=int); s.set_defaults(fn=cmd_console_attach)
    s = csub.add_parser("release", help="Giải phóng session kẹt")
    add_common(s); s.add_argument("id", type=int); s.set_defaults(fn=cmd_console_release)
    s = csub.add_parser("break", help="Gửi tín hiệu BREAK")
    add_common(s); s.add_argument("id", type=int); s.set_defaults(fn=cmd_console_break)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    for attr in ("url", "token", "json", "user", "password", "ids", "command",
                 "rest", "timeout", "action", "name", "yes", "service",
                 "lines", "path", "id", "limit", "cname", "device", "baud",
                 "desc", "console_cmd"):
        if not hasattr(args, attr):
            setattr(args, attr, "" if attr != "timeout" and attr != "lines" and attr != "limit" else 30)
    if not hasattr(args, "json") or args.json is None:
        args.json = False
    try:
        args.fn(args)
    except ApiError as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
