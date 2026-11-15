@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Lumen запускается.
echo  Это окно должно оставаться открытым, пока вы занимаетесь.
echo  Сайт: http://127.0.0.1:8765/
echo.
py -3 -m lumen.server
echo.
echo  Сервер остановился. Если сайт не открылся, запустите этот файл ещё раз.
pause
