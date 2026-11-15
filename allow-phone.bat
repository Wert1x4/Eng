@echo off
chcp 65001 >nul
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
netsh advfirewall firewall add rule name="Lumen 8765" dir=in action=allow protocol=TCP localport=8765 profile=any
echo.
echo  Телефон в той же сети Wi-Fi может открыть Lumen.
echo  Адрес и код — на странице http://127.0.0.1:8765/
echo.
pause
