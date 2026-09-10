@echo off
REM sshman.bat — wrapper để chạy menu từ cmd / double-click.
REM Dùng: sshman.bat [start^|stop^|restart^|status^|logs]  (không tham số = menu)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sshman.ps1" %*
