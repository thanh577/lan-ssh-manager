@echo off
REM Build LAN SSH Manager -> 1 file exe doc lap (chay tren may Windows).
REM Yeu cau: Python 3.10+ (tick "Add to PATH" khi cai), co mang lan dau.
REM Cach dung: double-click file nay (hoac: scripts\build_exe.bat)
REM Ket qua: ssh_manager\LAN-SSH-Manager-win64-<VER>.exe
setlocal
cd /d "%~dp0.."

if "%VER%"=="" set VER=1.2.6
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
  --paths . ^
  --add-data "frontend;frontend" ^
  --add-data ".env.example;." ^
  --hidden-import backend.app.main ^
  --hidden-import backend.app.api.auth ^
  --hidden-import backend.app.api.machines ^
  --hidden-import backend.app.api.groups ^
  --hidden-import backend.app.api.dashboard ^
  --hidden-import backend.app.api.system ^
  --hidden-import backend.app.api.commands ^
  --hidden-import backend.app.api.services_api ^
  --hidden-import backend.app.api.logs ^
  --hidden-import backend.app.api.files ^
  --hidden-import backend.app.api.audit ^
  --hidden-import backend.app.api.terminal ^
  --hidden-import backend.app.api.users_api ^
  --hidden-import backend.app.api.consoles ^
  --hidden-import backend.app.api.youtube ^
  --hidden-import uvicorn.logging ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import uvicorn.protocols.websockets.auto ^
  --hidden-import uvicorn.lifespan.on ^
  --collect-all uvicorn ^
  --collect-all asyncssh ^
  --collect-all sqlalchemy ^
  --collect-all jose ^
  --collect-all passlib ^
  --collect-all bcrypt ^
  --collect-all cryptography ^
  --collect-all multipart ^
  --collect-all websockets ^
  --collect-all serial ^
  --collect-all jinja2 ^
  --collect-all pydantic_settings ^
  --copy-metadata asyncssh ^
  --copy-metadata uvicorn ^
  --copy-metadata sqlalchemy ^
  --copy-metadata cryptography ^
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
