@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Собираю уроки для сайта.
py -3 -m lumen.export_pack
if errorlevel 1 (
  echo  Сборка не удалась.
  pause
  exit /b 1
)
echo.
echo  Готово. Загрузи СОДЕРЖИМОЕ папки web в корень сайта.
echo  Адрес должен открываться по HTTPS, не во вложенной папке.
echo  Папку data, базу и сертификаты загружать не нужно.
echo.
pause
