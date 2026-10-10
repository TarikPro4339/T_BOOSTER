@echo off
setlocal
chcp 65001 >nul
title T-Booster
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0T_BOOSTER_V1_0_2.py"
    if errorlevel 1 (
        echo.
        echo T-Booster kapanirken bir sorunla karsilasti. Yukaridaki mesaji inceleyebilir veya
        echo bu pencereyi kapatip tekrar deneyebilirsiniz.
        pause
    )
    exit /b
)

where python >nul 2>&1
if not errorlevel 1 (
    python "%~dp0T_BOOSTER_V1_0_2.py"
    if errorlevel 1 (
        echo.
        echo T-Booster kapanirken bir sorunla karsilasti. Yukaridaki mesaji inceleyebilir veya
        echo bu pencereyi kapatip tekrar deneyebilirsiniz.
        pause
    )
    exit /b
)

echo Bilgisayarinizda Python 3 bulunamadi.
echo T-Booster'i calistirabilmek icin lutfen once python.org adresinden Python 3'u kurun,
echo ardindan bu dosyayi tekrar calistirin. Yardimci olabilecegimiz baska bir sey olursa
echo buradayiz.
echo.
pause
