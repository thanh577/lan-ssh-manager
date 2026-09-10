@echo off
REM Build LAN SSH Manager -> 1 file exe doc lap (chay tren may Windows).
REM Yeu cau: Python 3.10+ (tick "Add to PATH" khi cai), co mang lan dau.
REM Cach dung: double-click file nay (hoac: scripts\build_exe.bat)
REM Ket qua: ssh_manager\LAN-SSH-Manager-win64-<VER>.exe
setlocal
cd /d "%~dp0.."

set VER=1.2.4
set NAME=LAN-SSH-Manager-win64-%VER%

if not exist backend\venv\Scripts\python.exe (
  echo ==^> Tao venv lan dau...
  python -m venv backend\venv
)
echo ==^> Cai thu vien + PyInstaller...
backend\venv\Scripts\python -m pip install -q -r backend\requirements.txt pyinstaller
if errorlevel 1 goto :err

echo ==^> Build exe (vai phut)...
backend\venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed ^
  --name "%NAME%" ^
  --add-data "frontend;frontend" ^
  --add-data ".env.example;." ^
  --collect-all uvicorn ^
  --collect-all asyncssh ^
  gui\app_win.py
if errorlevel 1 goto :err

if not exist ssh_manager mkdir ssh_manager
copy /Y "dist\%NAME%.exe" "ssh_manager\%NAME%.exe"
echo ==^> XONG: ssh_manager\%NAME%.exe
echo     Copy file exe sang may Windows bat ky, double-click la chay.
pause
exit /b 0

:err
echo !! Build that bai — xem loi ben tren.
pause
exit /b 1
