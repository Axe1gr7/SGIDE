@echo off
setlocal EnableDelayedExpansion

echo ==================================================================
echo               CECINTEGRA - Acceso directo al sistema              
echo ==================================================================
echo.

set "SERVER_IP=192.168.100.100"

echo Sistema disponible para la red: http://!SERVER_IP!
echo.
echo ==================================================================
echo  Comparte la URL con los usuarios de la misma red                 
echo  Asegurate de permitir el puerto TCP 80 en el Firewall de Windows 
echo ==================================================================
echo.
start http://!SERVER_IP!
pause
endlocal