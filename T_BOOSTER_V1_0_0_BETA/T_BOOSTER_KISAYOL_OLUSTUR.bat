@echo off
setlocal
chcp 65001 >nul
set "APP=%~dp0T_BOOSTER_BASLAT.bat"
set "ICO=%~dp0TB.ico"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\T-BOOSTER.lnk'); $s.TargetPath=$env:APP; $s.WorkingDirectory=(Split-Path $env:APP); $s.IconLocation=($env:ICO+',0'); $s.WindowStyle=7; $s.Description='T-BOOSTER v1.0.0 (Beta)'; $s.Save()"
if errorlevel 1 (
    echo Kisayol olusturulamadi.
) else (
    echo Masaustune T-BOOSTER kisayolu olusturuldu.
)
pause
