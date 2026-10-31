@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto check
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 (
  echo Can cai Python 3.11 tro len tu https://www.python.org/downloads/
  echo Khi cai, chon Python Launcher va Add Python to PATH.
  pause
  exit /b 1
)
py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto failed
:check
.venv\Scripts\python.exe -c "import autoclap, telethon, PySide6" >nul 2>&1
if not errorlevel 1 goto run
.venv\Scripts\python.exe -m ensurepip --upgrade
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto failed
:run
.venv\Scripts\python.exe -m autoclap
if errorlevel 1 goto failed
exit /b 0
:failed
echo Khong khoi dong duoc AutoClap. Xem thong bao loi o tren.
pause
exit /b 1
