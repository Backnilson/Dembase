@echo off
title DemBase - Flet Web
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ========================================================
echo   Iniciando DemBase via Navegador Web
echo ========================================================
echo.
echo No navegador do celular (Chrome/Edge/Firefox), acesse o IP local:
echo http://192.168.15.96:8550
echo.
flet run --web --host 0.0.0.0 --port 8550 main.py
pause
