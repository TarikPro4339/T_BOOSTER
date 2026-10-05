@echo off
setlocal
chcp 65001 >nul
set "APP=%~dp0t-booster.bat"
set "ICO=%~dp0TB.ico"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\T-Booster.lnk'); $s.TargetPath=$env:APP; $s.WorkingDirectory=(Split-Path $env:APP); $s.IconLocation=($env:ICO+',0'); $s.WindowStyle=7; $s.Description='T-Booster v1.0.1'; $s.Save()"
if errorlevel 1 (
    echo Kisayol olusturulamadi. Lutfen bu dosyayi tekrar calistirmayi deneyin.
) else (
    echo Masaustunuze T-Booster kisayolu olusturuldu. Artik oradan acabilirsiniz.
)
pause
