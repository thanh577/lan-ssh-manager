# sshman.ps1 — menu điều khiển LAN SSH Manager trên Windows.
#
#   Chạy menu:   powershell -ExecutionPolicy Bypass -File scripts\sshman.ps1
#   Hoặc:        scripts\sshman.bat            (double-click cũng được)
#   Lệnh nhanh:  scripts\sshman.bat start | stop | restart | status | logs
#
# Đổi port:  $env:PORT = 9000; scripts\sshman.bat start
#
# Tương đương scripts/sshman.sh bản Linux (menu 1.Start 2.Stop 3.Restart
# 4.Status 5.Logs). Windows không có systemd nên bỏ nhánh systemctl,
# quản lý tiến trình bằng PID file + sweep process uvicorn sót.

param([string]$Action = "")

$ErrorActionPreference = "Stop"
$Root    = Split-Path $PSScriptRoot -Parent
$Port    = if ($env:PORT) { $env:PORT } else { "8000" }
$PidFile = Join-Path $env:TEMP "sshman-$Port.pid"
$LogFile = Join-Path $Root "logs\sshman-win.log"
$Py      = Join-Path $Root "backend\venv\Scripts\python.exe"

function Get-LanIp {
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.PrefixOrigin -ne "WellKnown" } |
            Select-Object -First 1 -ExpandProperty IPAddress)
        if ($ip) { return $ip }
    } catch {}
    return "localhost"
}

function Get-Url { return "http://$(Get-LanIp):$Port" }

function Test-Running {
    if (-not (Test-Path $PidFile)) { return $false }
    $saved = Get-Content $PidFile -ErrorAction SilentlyContinue
    if (-not $saved) { return $false }
    return (Get-Process -Id $saved -ErrorAction SilentlyContinue) -ne $null
}

function Test-PortOpen {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($r -is [string]) { return $r -match '"status"\s*:\s*"ok"' }
        return ($r.success -eq $true -and $r.data.status -eq "ok") -or ($r.status -eq "ok")
    } catch { return $false }
}

function Open-Web {
    $u = Get-Url
    Write-Host "==> Mở web: $u"
    try { Start-Process $u } catch { Write-Host "(tự mở trình duyệt với địa chỉ trên)" }
}

function Ensure-Env {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "data"), (Join-Path $Root "logs") | Out-Null
    if (-not (Test-Path (Join-Path $Root ".env"))) {
        Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    }
    if (-not (Test-Path $Py)) {
        Write-Host "==> Tạo venv lần đầu..."
        & python -m venv (Join-Path $Root "backend\venv")
    }
    Write-Host "==> Kiểm tra thư viện..."
    & $Py -m pip install -q -r (Join-Path $Root "backend\requirements.txt")
}

function Start-App {
    if ((Test-Running) -or (Test-PortOpen)) {
        Write-Host "==> App đã chạy (port $Port)."
        Open-Web
        return
    }
    Ensure-Env
    Write-Host "==> Khởi động app (log: $LogFile)..."
    "[$(Get-Date -Format s)] starting port $Port" | Out-File $LogFile -Append -Encoding utf8
    $p = Start-Process -FilePath $Py `
        -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "$Port" `
        -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err"
    $p.Id | Out-File $PidFile -Encoding ascii -NoNewline
    $ok = $false
    for ($i = 0; $i -lt 25; $i++) {
        if (Test-PortOpen) { $ok = $true; break }
        Start-Sleep 1
    }
    if ($ok) {
        Write-Host "==> App đã chạy (PID $($p.Id)). Tài khoản mặc định: admin/admin123"
        Open-Web
    } else {
        Write-Host "!! App chưa lên sau 25s — xem log: $LogFile"
    }
}

function Stop-App {
    if (Test-Running) {
        $id = Get-Content $PidFile
        Write-Host "==> Dừng app (PID $id)..."
        Stop-Process -Id $id -ErrorAction SilentlyContinue
        Start-Sleep 2
        if (Get-Process -Id $id -ErrorAction SilentlyContinue) {
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    # Dọn tiến trình sót (start thủ công / crash không xóa pidfile)
    $strays = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*uvicorn*backend.app.main*" -and $_.CommandLine -like "*--port* $Port*" }
    foreach ($s in $strays) {
        Write-Host "==> Dừng tiến trình sót: $($s.ProcessId)"
        Stop-Process -Id $s.ProcessId -ErrorAction SilentlyContinue
    }
    Start-Sleep 1
    if (Test-PortOpen) {
        Write-Host "!! Port $Port vẫn mở — kiểm tra tiến trình khác đang giữ port."
        return
    }
    Write-Host "==> Đã dừng."
}

function Show-Status {
    if ((Test-Running) -or (Test-PortOpen)) { Write-Host "App ĐANG CHẠY — $(Get-Url)" }
    else { Write-Host "App CHƯA chạy. Gõ: sshman (menu)" }
}

function Show-Menu {
    while ($true) {
        Write-Host ""
        Write-Host "=== LAN SSH Manager — $(Get-Url) ==="
        Show-Status
        Write-Host " 1. Start server"
        Write-Host " 2. Stop server"
        Write-Host " 3. Restart server"
        Write-Host " 4. Status"
        Write-Host " 5. Xem logs"
        Write-Host " 0. Thoát"
        $c = Read-Host "Chọn [0-5]"
        switch ($c) {
            "1" { Start-App }
            "2" { Stop-App }
            "3" { Stop-App; Start-App }
            "4" { Show-Status }
            "5" { Get-Content $LogFile -Tail 50 -Wait -ErrorAction SilentlyContinue }
            { $_ -in "0", "q", "quit", "exit" } { break }
            default { Write-Host "Chọn số 0-5." }
        }
    }
}

switch ($Action) {
    ""        { Show-Menu }
    "start"   { Start-App }
    "stop"    { Stop-App }
    "restart" { Stop-App; Start-App }
    "status"  { Show-Status }
    "logs"    { Get-Content $LogFile -Tail 50 -Wait }
    default   { Write-Host "Dùng: sshman.ps1 [start|stop|restart|status|logs] (không tham số = menu)"; exit 1 }
}
