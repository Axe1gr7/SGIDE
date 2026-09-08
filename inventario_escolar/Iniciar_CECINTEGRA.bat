@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ==================================================================
echo                CECINTEGRA - Servidor para red local               
echo ==================================================================
echo.

docker compose up -d --build
if errorlevel 1 (
    echo No fue posible iniciar Docker Compose
    pause
    exit /b 1
)

set "SERVER_IP="
for /f "tokens=*" %%A in ('powershell -NoProfile -Command "(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -notmatch 'Docker|Virtual|Hyper-V|WSL' } | Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254*' -and $_.IPAddress -notlike '127*' } | Select-Object -First 1).IPAddress"') do set "SERVER_IP=%%A"

if not defined SERVER_IP set "SERVER_IP=IP_DEL_SERVIDOR"

echo.
echo Sistema disponible en este servidor: http://localhost
echo Sistema disponible para la red:      http://!SERVER_IP!
echo.
echo ==================================================================
echo  Comparte la segunda URL con los usuarios de la misma red         
echo  Asegurate de permitir el puerto TCP 80 en el Firewall de Windows 
echo ==================================================================
echo.
start http://localhost
pause
endlocal