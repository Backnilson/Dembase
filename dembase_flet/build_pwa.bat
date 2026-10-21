@echo off
title DemBase - Build PWA (Flet 1.0.1)
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ========================================================
echo   Compilando DemBase Finanças PWA para Produção Web
echo ========================================================
echo.
python "%~dp0build_pwa.py"
echo.
pause
