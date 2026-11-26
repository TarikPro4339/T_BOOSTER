@echo off
setlocal
chcp 65001 >nul
title T-Booster
cd /d "%~dp0"

py -3 -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto launch_py

for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    set "TB_PYTHON=%%P"
    "%%P" -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
    if not errorlevel 1 goto launch_python
)

echo Tkinter destekli Python 3.10 veya daha yeni bir surum bulunamadi.
echo T-Booster'i calistirabilmek icin lutfen once python.org adresinden Python'u kurun,
echo ardindan bu dosyayi tekrar calistirin. Yardimci olabilecegimiz baska bir sey olursa
echo buradayiz.
echo.
pause
exit /b 1

:launch_py
py -3 "%~dp0T_BOOSTER_V1_1_2.py"
goto check_result

:launch_python
"%TB_PYTHON%" "%~dp0T_BOOSTER_V1_1_2.py"

:check_result
set "TB_EXIT_CODE=%errorlevel%"
if not "%TB_EXIT_CODE%"=="0" (
    echo.
    echo T-Booster bir sorunla karsilasti. Ayrintilar icin yukaridaki mesaji inceleyin.
    pause
)
exit /b %TB_EXIT_CODE%
