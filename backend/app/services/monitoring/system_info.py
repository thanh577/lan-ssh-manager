"""SystemInfoService: predefined commands only. Frontend never sends raw shell here."""
from ..ssh.manager import run_command

COMMANDS = {
    "os": "cat /etc/os-release 2>/dev/null || uname -a",
    "kernel": "uname -r",
    "hostname": "hostname",
    "uptime": "uptime -p 2>/dev/null || uptime",
    "load": "cat /proc/loadavg",
    "memory": "free -m",
    "disk": "df -h / /home 2>/dev/null || df -h",
    "cpu": "nproc; echo ---; cat /proc/loadavg",
    "network": "ip -brief address 2>/dev/null || ifconfig 2>/dev/null || ss -tlnp 2>/dev/null",
}


async def collect(machine, timeout: int = 20) -> dict:
    info: dict = {}
    for key, cmd in COMMANDS.items():
        try:
            r = await run_command(machine, cmd, timeout=timeout)
            info[key] = (r.get("stdout") or "").strip()[:4000]
        except Exception as e:
            info[key] = f"ERROR: {e}"
    # light parse for dashboard
    info["summary"] = _summarize(info)
    return info


def _summarize(info: dict) -> dict:
    s: dict = {}
    try:
        # memory: parse free -m line "Mem: total used free ..."
        for line in info.get("memory", "").splitlines():
            if line.startswith("Mem:"):
                p = line.split()
                total, used = float(p[1]), float(p[2])
                s["mem_pct"] = round(used / total * 100, 1) if total else 0
                s["mem"] = line.strip()
                break
    except Exception:
        pass
    try:
        # disk: first / line
        for line in info.get("disk", "").splitlines():
            if line.endswith(" /") or " / " in line or line.split()[-1] == "/":
                p = line.split()
                s["disk"] = line.strip()
                # Use% column usually idx 4
                for tok in p:
                    if tok.endswith("%"):
                        s["disk_pct"] = float(tok.replace("%", ""))
                        break
                break
    except Exception:
        pass
    try:
        s["load"] = info.get("load", "").split()[0:3]
    except Exception:
        pass
    s["uptime"] = info.get("uptime", "")[:200]
    return s
