@echo off
title DemBase - Flet Android
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ========================================================
echo   Iniciando DemBase para App Flet no Celular (Android)
echo ========================================================
echo.
echo Certifique-se de que o celular esta no mesmo Wi-Fi do PC.
echo Abra o aplicativo Flet no Android e escaneie o QR Code ou digite a URL.
echo.
flet run --android main.py
pause
