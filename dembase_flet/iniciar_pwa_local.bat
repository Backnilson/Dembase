@echo off
title DemBase Finanças - Servidor Local PWA (Flet 1.0.1)
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ========================================================
echo   DemBase Finanças — Servidor Local de Testes PWA
echo ========================================================
echo.
echo Se ainda não compilou o PWA, execute primeiro: build_pwa.bat
echo.
echo Para testar no celular conectado no mesmo Wi-Fi, acesse:
echo http://192.168.15.96:8000
echo.
echo Para testar no computador:
echo http://localhost:8000
echo ========================================================
echo.
cd /d "%~dp0.."
flet serve dist --port 8000
pause
