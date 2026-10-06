@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 (
  echo.
  echo Build failed. See the message above.
  pause
  exit /b 1
)
echo.
echo Build complete.
pause
