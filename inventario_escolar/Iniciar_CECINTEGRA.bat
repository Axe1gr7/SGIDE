@echo off
title Servidor CECINTEGRA - Iniciando sistema...
color 0A

:: 1) Se ubica automaticamente en la carpeta del script
cd /d "%~dp0"

echo ==================================================
echo | Iniciando contenedores de Docker (servidor)... |
echo ==================================================
echo.

:: 2) Asegura que los contenedores esten corriendo en segundo plano
docker-compose up -d

:: 3) Obtiene la IP local de la computadora para informacion en pantalla
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set "MY_IP=%%a"
)
set "MY_IP=%MY_IP: =%"

echo.
echo ===================================================
echo   ¡Sistema iniciado correctamente! 
echo   IP local del servidor: %MY_IP%   
echo   Nombre de red: %COMPUTERNAME%    
echo ===================================================
echo.

:: 4) Espera 3 segundos y abre la app en la PC Anfitriona
timeout /t 3 /nobreak > nul
start http://localhost

exit