@echo off
setlocal
chcp 65001 >nul
title T-BOOSTER v1.0.0 (Beta)
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0T_BOOSTER_V1_0_0_BETA.py"
    if errorlevel 1 pause
    exit /b
)

where python >nul 2>&1
if not errorlevel 1 (
    python "%~dp0T_BOOSTER_V1_0_0_BETA.py"
    if errorlevel 1 pause
    exit /b
)

echo Python 3 bulunamadi.
echo Python 3 kurup tekrar deneyin.
pause
