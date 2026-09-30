# -*- coding: utf-8 -*-
"""
T-BOOSTER - Türkçe doğrulamalı Windows FPS düzenleyici
Yalnızca Windows 10/11 içindir. Harici Python paketi gerektirmez.
"""

from __future__ import annotations

import base64
import ctypes
import datetime as dt
import hashlib
import json
import locale
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import winreg


APP_NAME = "T-BOOSTER CORE"
VERSION = "1.0.0"
AUTHOR = "TarikPro43391"
PLAN_GUID = "ef940bf1-f471-4b72-a09c-d7e87f1c4210"
ESKI_PLANLAR = (
    "ef96db51-caa8-4bc8-b8eb-f5ec48aa3210",  # Python v3
    "ef920ef0-1f7b-4db2-a724-e3f0d3f48210",  # BAT v2
    "efd9c6e8-5a42-4f91-a15e-6bb7b3f14e10",  # BAT v1
)

PROGRAM_DATA = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
DATA_DIR = PROGRAM_DATA / "TBooster"
BACKUP_DIR = DATA_DIR / "Yedek"
BACKUP_FILE = BACKUP_DIR / "tb_yedek.json"
POWER_BACKUP = BACKUP_DIR / "ilk_guc_plani.pow"
LOG_FILE = DATA_DIR / "T_Booster.log"

def _writable_output_directory() -> Path:
    """Windows'un gerçek Masaüstü yolunu bulur; yoksa güvenli bir yazılabilir klasöre düşer."""
    candidates: list[Path] = []

    # Windows Known Folder API: OneDrive veya yerelleştirilmiş Masaüstü yollarını da çözer.
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        result = ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buffer)
        if result == 0 and buffer.value:
            candidates.append(Path(buffer.value))
    except Exception:
        pass

    for env_name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        base = os.environ.get(env_name)
        if base:
            candidates.extend((Path(base) / "Desktop", Path(base) / "Masaüstü"))

    user_profile = Path(os.environ.get("USERPROFILE") or Path.home())
    candidates.extend((
        user_profile / "Desktop",
        user_profile / "Masaüstü",
        Path.home() / "Desktop",
        Path.home() / "Masaüstü",
        Path.home() / "Documents",
        Path.home() / "Belgeler",
        DATA_DIR / "Raporlar",
    ))

    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate).casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".tb_yazma_testi.tmp"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue

    fallback = DATA_DIR / "Raporlar"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DESKTOP = _writable_output_directory()
REPORT_FILE = DESKTOP / "T_Booster_Raporu.txt"

APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
LOGO_FILE = APP_DIR / "TB_logo.png"

ENCODING = locale.getpreferredencoding(False) or "utf-8"

ROOTS = {
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
}

REG_DWORD = winreg.REG_DWORD
REG_SZ = winreg.REG_SZ

# Kimliği, kök, yol, değer adı, tür, yeni değer
REGISTRY_EDITS = [
    ("game_mode_allow", "HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", REG_DWORD, 1),
    ("game_mode_enabled", "HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", REG_DWORD, 1),
    ("dvr_enabled", "HKCU", r"System\GameConfigStore", "GameDVR_Enabled", REG_DWORD, 0),
    ("dvr_capture", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", REG_DWORD, 0),
    ("dvr_history", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "HistoricalCaptureEnabled", REG_DWORD, 0),
    ("dvr_audio", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AudioCaptureEnabled", REG_DWORD, 0),
    ("dvr_policy", "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", REG_DWORD, 0),

    ("hags", "HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", REG_DWORD, 2),
    ("power_throttle", "HKLM", r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", REG_DWORD, 1),
    ("foreground_priority", "HKLM", r"SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", REG_DWORD, 0x26),

    ("mmcss_gpu", "HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "GPU Priority", REG_DWORD, 8),
    ("mmcss_priority", "HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Priority", REG_DWORD, 6),
    ("mmcss_sched", "HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Scheduling Category", REG_SZ, "High"),
    ("mmcss_sfio", "HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "SFIO Priority", REG_SZ, "High"),
    ("system_responsiveness", "HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "SystemResponsiveness", REG_DWORD, 10),
    ("network_throttle", "HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "NetworkThrottlingIndex", REG_DWORD, 0xFFFFFFFF),

    # Masaüstü oyun sistemi için güvenli bellek/kapanış varsayılanları.
    ("large_system_cache_desktop", "HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "LargeSystemCache", REG_DWORD, 0),
    ("clear_pagefile_shutdown_off", "HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "ClearPageFileAtShutdown", REG_DWORD, 0),

    ("transparency", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", REG_DWORD, 0),
    ("visual_preset", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", REG_DWORD, 3),
    ("min_animate", "HKCU", r"Control Panel\Desktop\WindowMetrics", "MinAnimate", REG_SZ, "0"),
    ("taskbar_anim", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarAnimations", REG_DWORD, 0),
    ("list_alpha", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ListviewAlphaSelect", REG_DWORD, 0),
    ("list_shadow", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ListviewShadow", REG_DWORD, 0),
    ("preview_desktop", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "DisablePreviewDesktop", REG_DWORD, 1),
    ("aero_peek", "HKCU", r"Software\Microsoft\Windows\DWM", "EnableAeroPeek", REG_DWORD, 0),
    ("drag_full", "HKCU", r"Control Panel\Desktop", "DragFullWindows", REG_SZ, "1"),
    ("font_smoothing", "HKCU", r"Control Panel\Desktop", "FontSmoothing", REG_SZ, "2"),
    ("font_smoothing_type", "HKCU", r"Control Panel\Desktop", "FontSmoothingType", REG_DWORD, 2),
    ("thumbnail_icons", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "IconsOnly", REG_DWORD, 0),
    ("taskbar_thumbnail_cache", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "AlwaysHibernateThumbnails", REG_DWORD, 0),
    ("menu_delay", "HKCU", r"Control Panel\Desktop", "MenuShowDelay", REG_SZ, "0"),
    ("startup_delay", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize", "StartupDelayInMSec", REG_DWORD, 0),
    ("sync_ads", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowSyncProviderNotifications", REG_DWORD, 0),

    # Güvenli gizlilik / Explorer geçmişi ayarları. FPS kazancı iddia edilmez.
    ("recent_docs_history", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoRecentDocsHistory", REG_DWORD, 1),
    ("recent_docs_clear", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "ClearRecentDocsOnExit", REG_DWORD, 1),
    ("recent_docs_track", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Start_TrackDocs", REG_DWORD, 0),
    ("taskbar_widgets", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarDa", REG_DWORD, 0),
    ("taskbar_chat", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarMn", REG_DWORD, 0),
    ("taskbar_taskview", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowTaskViewButton", REG_DWORD, 0),
    ("taskbar_copilot", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowCopilotButton", REG_DWORD, 0),
    ("taskbar_search", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "SearchboxTaskbarMode", REG_DWORD, 1),
    ("taskbar_feeds", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Feeds", "ShellFeedsTaskbarViewMode", REG_DWORD, 2),
    ("taskbar_recommendations", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Start_IrisRecommendations", REG_DWORD, 0),
    ("activity_history_publish", "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "PublishUserActivities", REG_DWORD, 0),
    ("activity_history_upload", "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "UploadUserActivities", REG_DWORD, 0),
    ("consumer_features", "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\CloudContent", "DisableWindowsConsumerFeatures", REG_DWORD, 1),
    ("telemetry", "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", REG_DWORD, 0),
    ("location_tracking", "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors", "DisableLocation", REG_DWORD, 1),
    ("background_apps", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", "GlobalUserDisabled", REG_DWORD, 1),
    ("file_explorer_launch_to", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "LaunchTo", REG_DWORD, 1),
    ("file_explorer_show_frequent", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer", "ShowFrequent", REG_DWORD, 0),
    ("file_explorer_show_recent", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer", "ShowRecent", REG_DWORD, 0),
    ("search_box_suggestions", "HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", REG_DWORD, 1),
    ("storage_sense", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy", "01", REG_DWORD, 0),
    ("feedback_period", "HKCU", r"Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod", REG_DWORD, 0),
    ("input_personalization_text", "HKCU", r"Software\Microsoft\InputPersonalization", "RestrictImplicitTextCollection", REG_DWORD, 1),
    ("input_personalization_ink", "HKCU", r"Software\Microsoft\InputPersonalization", "RestrictImplicitInkCollection", REG_DWORD, 1),

    ("mouse_speed", "HKCU", r"Control Panel\Mouse", "MouseSpeed", REG_SZ, "0"),
    ("mouse_t1", "HKCU", r"Control Panel\Mouse", "MouseThreshold1", REG_SZ, "0"),
    ("mouse_t2", "HKCU", r"Control Panel\Mouse", "MouseThreshold2", REG_SZ, "0"),

    ("delivery_mode", "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode", REG_DWORD, 0),

    ("content_allowed", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "ContentDeliveryAllowed", REG_DWORD, 0),
    ("oem_apps", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "OemPreInstalledAppsEnabled", REG_DWORD, 0),
    ("pre_apps", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "PreInstalledAppsEnabled", REG_DWORD, 0),
    ("silent_apps", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SilentInstalledAppsEnabled", REG_DWORD, 0),
    ("soft_landing", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SoftLandingEnabled", REG_DWORD, 0),
    ("system_suggestions", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SystemPaneSuggestionsEnabled", REG_DWORD, 0),
    ("sub_338388", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338388Enabled", REG_DWORD, 0),
    ("sub_338389", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338389Enabled", REG_DWORD, 0),
    ("sub_353694", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-353694Enabled", REG_DWORD, 0),
]

BCD_NAMES = (
    "useplatformclock",
    "useplatformtick",
    "disabledynamictick",
    "tscsyncpolicy",
)

BACKGROUND_PROCESSES = (
    "Widgets.exe",
    "WidgetService.exe",
    "OneDrive.exe",
    "ms-teams.exe",
    "PhoneExperienceHost.exe",
    "YourPhone.exe",
    "GameBar.exe",
    "XboxPcApp.exe",
)

XBOX_SERVICES = (
    "XblAuthManager",
    "XblGameSave",
    "XboxNetApiSvc",
    "XboxGipSvc",
    "GamingServices",
    "GamingServicesNet",
)

XBOX_PACKAGES = (
    "Microsoft.GamingApp",
    "Microsoft.XboxApp",
    "Microsoft.Xbox.TCUI",
    "Microsoft.XboxGameOverlay",
    "Microsoft.XboxGamingOverlay",
    "Microsoft.XboxIdentityProvider",
    "Microsoft.XboxSpeechToTextOverlay",
)


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def log_line(text: str) -> None:
    ensure_directories()
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {text}\n")


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate() -> None:
    if getattr(sys, "frozen", False):
        executable = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        executable = sys.executable
        params = subprocess.list2cmdline(
            [str(Path(__file__).resolve()), *sys.argv[1:]]
        )

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        params,
        str(APP_DIR),
        1,
    )
    if result <= 32:
        raise RuntimeError(
            f"Yönetici izni alınamadı. Windows hata kodu: {result}"
        )
    raise SystemExit(0)


def run_command(
    args: list[str],
    *,
    check: bool = False,
    timeout: int = 90,
) -> subprocess.CompletedProcess[str]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding=ENCODING,
        errors="replace",
        timeout=timeout,
        creationflags=creationflags,
        check=False,
    )
    joined = subprocess.list2cmdline(args)
    log_line(f"KOMUT: {joined} | KOD: {result.returncode}")
    if result.stdout.strip():
        log_line(f"STDOUT: {result.stdout.strip()}")
    if result.stderr.strip():
        log_line(f"STDERR: {result.stderr.strip()}")
    if check and result.returncode != 0:
        raise RuntimeError(f"Komut başarısız: {joined}\n{result.stderr.strip()}")
    return result


def powershell(script: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=timeout,
    )


def encode_registry_value(value):
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii")}
    if isinstance(value, tuple):
        return list(value)
    return value


def decode_registry_value(value):
    if isinstance(value, dict) and value.get("encoding") == "base64":
        return base64.b64decode(value["data"])
    return value


class BackupStore:
    def __init__(self) -> None:
        ensure_directories()
        self.data: dict = {
            "version": VERSION,
            "created": dt.datetime.now().isoformat(),
            "registry": {},
            "bcd": {},
            "original_power_guid": None,
            "hardware": {},
        }
        if BACKUP_FILE.exists():
            try:
                self.data = json.loads(BACKUP_FILE.read_text(encoding="utf-8"))
            except Exception:
                log_line("Mevcut yedek okunamadı; yeni yedek oluşturulacak.")

    @property
    def exists(self) -> bool:
        return BACKUP_FILE.exists() and bool(self.data.get("registry") or self.data.get("original_power_guid"))

    def save(self) -> None:
        temp_file = BACKUP_FILE.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(BACKUP_FILE)

    def backup_registry(self, item_id: str, root_name: str, path: str, name: str) -> None:
        if item_id in self.data.setdefault("registry", {}):
            return

        record = {
            "root": root_name,
            "path": path,
            "name": name,
            "exists": False,
            "type": None,
            "value": None,
        }
        try:
            with winreg.OpenKey(ROOTS[root_name], path, 0, winreg.KEY_READ) as key:
                value, value_type = winreg.QueryValueEx(key, name)
            record.update(
                exists=True,
                type=value_type,
                value=encode_registry_value(value),
            )
        except FileNotFoundError:
            pass
        except OSError:
            pass

        self.data["registry"][item_id] = record
        self.save()

    def restore_registry(self, callback) -> None:
        registry_data = self.data.get("registry", {})
        items = list(registry_data.items())
        items.reverse()

        for item_id, record in items:
            root = ROOTS[record["root"]]
            path = record["path"]
            name = record["name"]
            callback(f"Registry geri yükleniyor: {name}")
            try:
                if record.get("exists"):
                    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.SetValueEx(
                            key,
                            name,
                            0,
                            int(record["type"]),
                            decode_registry_value(record.get("value")),
                        )
                else:
                    try:
                        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as key:
                            winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
            except Exception as exc:
                log_line(f"Registry geri yükleme uyarısı ({item_id}): {exc}")


def write_registry(
    backup: BackupStore,
    item_id: str,
    root_name: str,
    path: str,
    name: str,
    value_type: int,
    value,
) -> None:
    backup.backup_registry(item_id, root_name, path, name)
    with winreg.CreateKeyEx(ROOTS[root_name], path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, value_type, value)


def get_active_power_guid() -> str:
    result = run_command(["powercfg.exe", "/getactivescheme"], check=True)
    match = re.search(r"[0-9A-Fa-f-]{36}", result.stdout)
    if not match:
        raise RuntimeError("Etkin güç planı GUID değeri okunamadı.")
    return match.group(0)


def power_plan_exists(guid: str) -> bool:
    result = run_command(["powercfg.exe", "/list"])
    return guid.lower() in result.stdout.lower()


def backup_power_plan(backup: BackupStore) -> None:
    if backup.data.get("original_power_guid"):
        return
    guid = get_active_power_guid()
    backup.data["original_power_guid"] = guid
    backup.save()
    run_command(["powercfg.exe", "/export", str(POWER_BACKUP), guid])


def set_power_value(subgroup: str, setting: str, value: int) -> None:
    ok = False
    for mode in ("/setacvalueindex", "/setdcvalueindex"):
        result = run_command(
            [
                "powercfg.exe",
                mode,
                PLAN_GUID,
                subgroup,
                setting,
                str(value),
            ]
        )
        if result.returncode == 0:
            ok = True
    if not ok:
        log_line(f"Desteklenmeyen güç ayarı atlandı: {setting}")


def apply_power_plan(backup: BackupStore, callback) -> None:
    callback("T-Booster maksimum performans güç planı hazırlanıyor...")
    backup_power_plan(backup)
    base_guid = backup.data["original_power_guid"]

    if not power_plan_exists(PLAN_GUID):
        run_command(
            ["powercfg.exe", "/duplicatescheme", base_guid, PLAN_GUID],
            check=True,
        )

    run_command(
        [
            "powercfg.exe",
            "/changename",
            PLAN_GUID,
            "T-BOOSTER - MAKSIMUM FPS",
            "Agresif AC oyun performansi profili",
        ]
    )

    sub_cpu = "54533251-82be-4824-96c1-47b60b740d00"
    settings = [
        # İşlemci minimum, maksimum, aktif soğutma
        (sub_cpu, "893dee8e-2bef-41e0-89c6-b55d0929964c", 100),
        (sub_cpu, "bc5038f7-23e0-4960-96da-33abaf5935ec", 100),
        (sub_cpu, "94d3a615-a899-4ac5-ae2b-e4d8f634367f", 1),
        # EPP 0, agresif boost
        (sub_cpu, "36687f9e-e3a5-4dbf-b1dc-15eb381c6863", 0),
        (sub_cpu, "be337238-0d82-4146-a960-4f3749d470c7", 2),
        # Çekirdek park etmeme
        (sub_cpu, "0cc5b647-c1df-4637-891a-dec35c318583", 100),
        (sub_cpu, "ea062031-0e34-4ff1-9b6d-eb1059334028", 100),
        # PCIe ASPM
        ("501a4d13-42af-4429-9fd1-a8218c268e20", "ee12f906-d277-404b-b6da-e5fa1a576df5", 0),
        # USB selective suspend
        ("2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", 0),
        # Disk idle
        ("0012ee47-9041-4b5d-9b77-535fba8b1442", "6738e2c4-e8a5-4a42-b16a-e040e769756e", 0),
        # Kablosuz adaptör maksimum performans
        ("19cbb8fa-5279-450e-9fac-8a3d5fedd0c1", "12bbebe6-58d6-4636-95bb-3217ef867c1a", 0),
    ]

    for subgroup, setting, value in settings:
        set_power_value(subgroup, setting, value)

    run_command(["powercfg.exe", "/setactive", PLAN_GUID], check=True)

    # Önceki T-Booster sürümlerinden kalan etkin olmayan planları temizle.
    for old_guid in ESKI_PLANLAR:
        if old_guid.lower() == base_guid.lower():
            continue
        if power_plan_exists(old_guid):
            run_command(["powercfg.exe", "/delete", old_guid])


def backup_bcd(backup: BackupStore) -> None:
    if backup.data.get("bcd"):
        return

    result = run_command(["bcdedit.exe", "/enum", "{current}"])
    text = result.stdout
    values = {}
    for name in BCD_NAMES:
        match = re.search(
            rf"(?im)^\s*{re.escape(name)}\s+(\S+)",
            text,
        )
        values[name] = match.group(1) if match else None
    backup.data["bcd"] = values
    backup.save()


def remove_forced_timer_overrides(backup: BackupStore, callback) -> None:
    callback("HPET ve zorlanmış Windows zamanlayıcıları varsayılana alınıyor...")
    backup_bcd(backup)
    for name in BCD_NAMES:
        run_command(["bcdedit.exe", "/deletevalue", "{current}", name])


def restore_bcd(backup: BackupStore, callback) -> None:
    callback("HPET ve BCD zamanlayıcı ayarları geri yükleniyor...")
    for name, original in backup.data.get("bcd", {}).items():
        run_command(["bcdedit.exe", "/deletevalue", "{current}", name])
        if original:
            run_command(["bcdedit.exe", "/set", "{current}", name, str(original)])


def get_video_controllers() -> list[dict]:
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,PNPDeviceID | ConvertTo-Json -Compress"
    )
    result = powershell(script)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data]
    return data if isinstance(data, list) else []


def enable_supported_gpu_msi(backup: BackupStore, callback) -> int:
    callback("Desteklenen ekran kartlarında MSI Mode denetleniyor...")
    count = 0
    for gpu in get_video_controllers():
        pnp_id = gpu.get("PNPDeviceID")
        if not pnp_id:
            continue
        reg_path = (
            rf"SYSTEM\CurrentControlSet\Enum\{pnp_id}"
            r"\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties"
        )
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ) as key:
                _, existing_type = winreg.QueryValueEx(key, "MSISupported")
        except (FileNotFoundError, OSError):
            # Sürücü destek anahtarını oluşturmamışsa zorla üretme.
            continue

        item_id = "gpu_msi_" + hashlib.sha256(reg_path.encode("utf-8")).hexdigest()[:16]
        backup.backup_registry(item_id, "HKLM", reg_path, "MSISupported")
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                reg_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(key, "MSISupported", 0, REG_DWORD, 1)
            count += 1
        except OSError as exc:
            log_line(f"MSI Mode uygulanamadı ({gpu.get('Name')}): {exc}")

    return count


# ---------------------------------------------------------------------------
# Görsel efekt profili
# Yalnızca üç özellik açık kalır:
# - Ekran yazı tipi kenarlarını düzelt
# - Simgeler yerine küçük resimler göster
# - Sürüklerken pencere içeriğini göster
# ---------------------------------------------------------------------------

SPIF_UPDATEINIFILE = 0x0001
SPIF_SENDCHANGE = 0x0002
SPI_FLAGS = SPIF_UPDATEINIFILE | SPIF_SENDCHANGE

SPI_GETDRAGFULLWINDOWS = 0x0026
SPI_SETDRAGFULLWINDOWS = 0x0025
SPI_GETANIMATION = 0x0048
SPI_SETANIMATION = 0x0049
SPI_GETFONTSMOOTHING = 0x004A
SPI_SETFONTSMOOTHING = 0x004B

SPI_GETCOMBOBOXANIMATION = 0x1004
SPI_SETCOMBOBOXANIMATION = 0x1005
SPI_GETLISTBOXSMOOTHSCROLLING = 0x1006
SPI_SETLISTBOXSMOOTHSCROLLING = 0x1007
SPI_GETGRADIENTCAPTIONS = 0x1008
SPI_SETGRADIENTCAPTIONS = 0x1009
SPI_GETHOTTRACKING = 0x100E
SPI_SETHOTTRACKING = 0x100F
SPI_GETMENUANIMATION = 0x1002
SPI_SETMENUANIMATION = 0x1003
SPI_GETMENUFADE = 0x1012
SPI_SETMENUFADE = 0x1013
SPI_GETSELECTIONFADE = 0x1014
SPI_SETSELECTIONFADE = 0x1015
SPI_GETTOOLTIPANIMATION = 0x1016
SPI_SETTOOLTIPANIMATION = 0x1017
SPI_GETTOOLTIPFADE = 0x1018
SPI_SETTOOLTIPFADE = 0x1019
SPI_GETCURSORSHADOW = 0x101A
SPI_SETCURSORSHADOW = 0x101B
SPI_GETDROPSHADOW = 0x1024
SPI_SETDROPSHADOW = 0x1025
SPI_GETUIEFFECTS = 0x103E
SPI_SETUIEFFECTS = 0x103F
SPI_GETCLIENTAREAANIMATION = 0x1042
SPI_SETCLIENTAREAANIMATION = 0x1043


class ANIMATIONINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("iMinAnimate", ctypes.c_int),
    ]


def _spi_get_bool(action: int):
    value = ctypes.c_int()
    ok = ctypes.windll.user32.SystemParametersInfoW(
        action,
        0,
        ctypes.byref(value),
        0,
    )
    if not ok:
        return None
    return bool(value.value)


def _spi_set_bool_pointer(action: int, enabled: bool) -> bool:
    value = ctypes.c_int(1 if enabled else 0)
    return bool(
        ctypes.windll.user32.SystemParametersInfoW(
            action,
            0,
            ctypes.byref(value),
            SPI_FLAGS,
        )
    )


def _spi_set_bool_ui(action: int, enabled: bool) -> bool:
    return bool(
        ctypes.windll.user32.SystemParametersInfoW(
            action,
            1 if enabled else 0,
            None,
            SPI_FLAGS,
        )
    )


def _spi_get_animation():
    info = ANIMATIONINFO(
        ctypes.sizeof(ANIMATIONINFO),
        0,
    )
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETANIMATION,
        ctypes.sizeof(ANIMATIONINFO),
        ctypes.byref(info),
        0,
    )
    if not ok:
        return None
    return bool(info.iMinAnimate)


def _spi_set_animation(enabled: bool) -> bool:
    info = ANIMATIONINFO(
        ctypes.sizeof(ANIMATIONINFO),
        1 if enabled else 0,
    )
    return bool(
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETANIMATION,
            ctypes.sizeof(ANIMATIONINFO),
            ctypes.byref(info),
            SPI_FLAGS,
        )
    )


VISUAL_SPI_ITEMS = {
    "ui_effects": (SPI_GETUIEFFECTS, SPI_SETUIEFFECTS, "pointer"),
    "client_area_animation": (
        SPI_GETCLIENTAREAANIMATION,
        SPI_SETCLIENTAREAANIMATION,
        "pointer",
    ),
    "combo_animation": (
        SPI_GETCOMBOBOXANIMATION,
        SPI_SETCOMBOBOXANIMATION,
        "pointer",
    ),
    "listbox_smooth_scroll": (
        SPI_GETLISTBOXSMOOTHSCROLLING,
        SPI_SETLISTBOXSMOOTHSCROLLING,
        "pointer",
    ),
    "gradient_captions": (
        SPI_GETGRADIENTCAPTIONS,
        SPI_SETGRADIENTCAPTIONS,
        "pointer",
    ),
    "hot_tracking": (
        SPI_GETHOTTRACKING,
        SPI_SETHOTTRACKING,
        "pointer",
    ),
    "menu_animation": (
        SPI_GETMENUANIMATION,
        SPI_SETMENUANIMATION,
        "pointer",
    ),
    "menu_fade": (
        SPI_GETMENUFADE,
        SPI_SETMENUFADE,
        "pointer",
    ),
    "selection_fade": (
        SPI_GETSELECTIONFADE,
        SPI_SETSELECTIONFADE,
        "pointer",
    ),
    "tooltip_animation": (
        SPI_GETTOOLTIPANIMATION,
        SPI_SETTOOLTIPANIMATION,
        "pointer",
    ),
    "tooltip_fade": (
        SPI_GETTOOLTIPFADE,
        SPI_SETTOOLTIPFADE,
        "pointer",
    ),
    "cursor_shadow": (
        SPI_GETCURSORSHADOW,
        SPI_SETCURSORSHADOW,
        "pointer",
    ),
    "drop_shadow": (
        SPI_GETDROPSHADOW,
        SPI_SETDROPSHADOW,
        "pointer",
    ),
    "drag_full_windows": (
        SPI_GETDRAGFULLWINDOWS,
        SPI_SETDRAGFULLWINDOWS,
        "ui",
    ),
    "font_smoothing": (
        SPI_GETFONTSMOOTHING,
        SPI_SETFONTSMOOTHING,
        "ui",
    ),
}


def backup_visual_effects(backup: BackupStore) -> None:
    if backup.data.get("visual_spi"):
        return

    values = {
        "animation": _spi_get_animation(),
    }
    for item_id, (get_action, _set_action, _mode) in VISUAL_SPI_ITEMS.items():
        values[item_id] = _spi_get_bool(get_action)

    backup.data["visual_spi"] = values
    backup.save()


def apply_visual_effect_profile(backup: BackupStore, callback) -> None:
    callback(
        "Görsel efektler ayarlanıyor: yalnızca yazı yumuşatma, "
        "küçük resimler ve pencere içeriği açık kalacak..."
    )
    backup_visual_effects(backup)

    # Genel animasyonları ve geçiş efektlerini kapat.
    # Masaüstü duvar kağıdını etkileyebilen genel UI efekt anahtarına dokunma.
    # Animasyonlar aşağıda tek tek kapatılır.
    _spi_set_animation(False)

    disable_actions = (
        SPI_SETCLIENTAREAANIMATION,
        SPI_SETCOMBOBOXANIMATION,
        SPI_SETLISTBOXSMOOTHSCROLLING,
        SPI_SETGRADIENTCAPTIONS,
        SPI_SETHOTTRACKING,
        SPI_SETMENUANIMATION,
        SPI_SETMENUFADE,
        SPI_SETSELECTIONFADE,
        SPI_SETTOOLTIPANIMATION,
        SPI_SETTOOLTIPFADE,
        SPI_SETCURSORSHADOW,
        SPI_SETDROPSHADOW,
    )
    for action in disable_actions:
        _spi_set_bool_pointer(action, False)

    # Kullanıcının istediği üç özellik.
    _spi_set_bool_ui(SPI_SETFONTSMOOTHING, True)
    _spi_set_bool_ui(SPI_SETDRAGFULLWINDOWS, True)

    run_command(
        ["rundll32.exe", "user32.dll,UpdatePerUserSystemParameters"],
        timeout=30,
    )


def restore_visual_effects(backup: BackupStore, callback) -> None:
    values = backup.data.get("visual_spi") or {}
    if not values:
        return

    callback("İlk görsel efekt tercihleri geri yükleniyor...")

    animation = values.get("animation")
    if animation is not None:
        _spi_set_animation(bool(animation))

    for item_id, (_get_action, set_action, mode) in VISUAL_SPI_ITEMS.items():
        value = values.get(item_id)
        if value is None:
            continue
        if mode == "ui":
            _spi_set_bool_ui(set_action, bool(value))
        else:
            _spi_set_bool_pointer(set_action, bool(value))

    run_command(
        ["rundll32.exe", "user32.dll,UpdatePerUserSystemParameters"],
        timeout=30,
    )


def apply_registry_edits(backup: BackupStore, callback) -> None:
    total = len(REGISTRY_EDITS)
    for index, edit in enumerate(REGISTRY_EDITS, start=1):
        item_id, root, path, name, value_type, value = edit
        callback(f"Windows ayarları düzenleniyor ({index}/{total}): {name}")
        try:
            write_registry(backup, item_id, root, path, name, value_type, value)
        except Exception as exc:
            log_line(f"Registry ayarı atlandı ({item_id}): {exc}")


def close_background_apps(callback) -> int:
    callback("Gereksiz kullanıcı uygulamaları kapatılıyor...")
    closed = 0
    for process in BACKGROUND_PROCESSES:
        result = run_command(["taskkill.exe", "/F", "/IM", process])
        if result.returncode == 0:
            closed += 1
    return closed


def cleanup_old_temp(callback) -> int:
    """Güvenlik gereği devre dışıdır. T-BOOSTER hiçbir dosya silmez."""
    callback("Dosya temizleme devre dışı — hiçbir dosya silinmedi.")
    return 0

def _disabled_cleanup_old_temp_legacy(callback) -> int:
    callback("Eski geçici dosya temizleme kodu kullanılmıyor...")
    cutoff = time.time() - (7 * 24 * 60 * 60)
    roots = [
        Path(os.environ.get("TEMP", "")),
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Temp",
    ]
    removed = 0

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            entries = list(root.iterdir())
        except OSError:
            continue

        for entry in entries:
            try:
                if entry.stat().st_mtime >= cutoff:
                    continue
                if entry.is_file() or entry.is_symlink():
                    entry.unlink(missing_ok=True)
                    removed += 1
                elif entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                    if not entry.exists():
                        removed += 1
            except OSError:
                pass
    return removed


def create_restore_point() -> None:
    script = (
        "try { "
        "Enable-ComputerRestore -Drive $env:SystemDrive -ErrorAction SilentlyContinue; "
        "Checkpoint-Computer -Description 'T_Booster_Oncesi' "
        "-RestorePointType MODIFY_SETTINGS -ErrorAction SilentlyContinue "
        "} catch {}"
    )
    powershell(script, timeout=120)


def hardware_info() -> dict:
    script = r"""
$cpu=(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name).Trim()
$gpu=((Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ' / ').Trim()
$ram=Get-CimInstance Win32_PhysicalMemory
$total=[math]::Round((($ram | Measure-Object Capacity -Sum).Sum/1GB),1)
$modules=@($ram).Count
$build=(Get-CimInstance Win32_OperatingSystem).BuildNumber
$laptop=[bool](Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue)
[pscustomobject]@{CPU=$cpu;GPU=$gpu;RAM=$total;Modules=$modules;Build=$build;Laptop=$laptop} | ConvertTo-Json -Compress
"""
    result = powershell(script)
    try:
        return json.loads(result.stdout)
    except Exception:
        return {
            "CPU": "Bilinmiyor",
            "GPU": "Bilinmiyor",
            "RAM": "?",
            "Modules": "?",
            "Build": "?",
            "Laptop": False,
        }



def read_registry_value(root_name: str, path: str, name: str):
    try:
        with winreg.OpenKey(ROOTS[root_name], path, 0, winreg.KEY_READ) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def verify_applied_settings() -> dict:
    """Uygulama sonrası kritik ayarları yeniden okuyup doğrular."""
    checks: list[tuple[str, bool]] = []

    critical = [
        ("Oyun Modu", "HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1),
        ("Game DVR", "HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 0),
        ("HAGS", "HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2),
        ("Power Throttling", "HKLM", r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", 1),
        ("Fare ivmesi", "HKCU", r"Control Panel\Mouse", "MouseSpeed", "0"),
        ("Menü gecikmesi", "HKCU", r"Control Panel\Desktop", "MenuShowDelay", "0"),
        ("Belge geçmişi", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoRecentDocsHistory", 1),
        ("Widgets kapalı", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarDa", 0),
        ("Arama simgesi", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "SearchboxTaskbarMode", 1),
        ("Görev görünümü gizli", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowTaskViewButton", 0),
        ("Görsel efekt profili özel", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 3),
        ("Yazı tipi yumuşatma", "HKCU", r"Control Panel\Desktop", "FontSmoothing", "2"),
        ("Pencere içeriği sürükleme", "HKCU", r"Control Panel\Desktop", "DragFullWindows", "1"),
        ("Küçük resimler", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "IconsOnly", 0),
        ("Arama önerileri kapalı", "HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", 1),
        ("Storage Sense kapalı", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy", "01", 0),
    ]
    for label, root, path, name, expected in critical:
        checks.append((label, read_registry_value(root, path, name) == expected))

    try:
        checks.append(("T-Booster güç planı", get_active_power_guid().lower() == PLAN_GUID.lower()))
    except Exception:
        checks.append(("T-Booster güç planı", False))

    bcd = run_command(["bcdedit.exe", "/enum", "{current}"])
    bcd_text = bcd.stdout.lower()
    timers_clean = not any(name.lower() in bcd_text for name in BCD_NAMES)
    checks.append(("Zorlanmış timer ayarları", timers_clean))

    passed = sum(1 for _, ok in checks if ok)
    failed = [label for label, ok in checks if not ok]
    return {
        "passed": passed,
        "total": len(checks),
        "failed": failed,
        "items": checks,
    }


def append_verification_to_report(verification: dict) -> None:
    lines = [
        "",
        "OTOMATİK DOĞRULAMA",
        f"- Başarılı: {verification['passed']} / {verification['total']}",
    ]
    for label, ok in verification["items"]:
        lines.append(f"- {'TAMAM' if ok else 'KONTROL GEREKİYOR'}: {label}")
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_FILE.open("a", encoding="utf-8") as handle:
        handle.write("\n" + "\n".join(lines) + "\n")



def disable_xbox_services(callback) -> int:
    callback("Xbox hizmetleri durduruluyor ve devre dışı bırakılıyor...")
    changed = 0
    for service_name in XBOX_SERVICES:
        run_command(["sc.exe", "stop", service_name])
        result = run_command(["sc.exe", "config", service_name, "start=", "disabled"])
        if result.returncode == 0:
            changed += 1
    return changed


def remove_xbox_apps(callback) -> int:
    callback("Xbox uygulamaları kaldırılıyor...")
    script = r"""
$pkgs=@(
'Microsoft.GamingApp',
'Microsoft.XboxApp',
'Microsoft.Xbox.TCUI',
'Microsoft.XboxGameOverlay',
'Microsoft.XboxGamingOverlay',
'Microsoft.XboxIdentityProvider',
'Microsoft.XboxSpeechToTextOverlay'
)
$removed=0
foreach($name in $pkgs){
    Get-AppxPackage -AllUsers -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
        try { Remove-AppxPackage -Package $_.PackageFullName -AllUsers -ErrorAction SilentlyContinue; $removed++ } catch {}
    }
    Get-AppxPackage -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
        try { Remove-AppxPackage -Package $_.PackageFullName -ErrorAction SilentlyContinue; $removed++ } catch {}
    }
    Get-AppxProvisionedPackage -Online | Where-Object { $_.DisplayName -eq $name } | ForEach-Object {
        try { Remove-AppxProvisionedPackage -Online -PackageName $_.PackageName -ErrorAction SilentlyContinue | Out-Null; $removed++ } catch {}
    }
}
Write-Output $removed
"""
    result = powershell(script, timeout=240)
    try:
        return int((result.stdout or "0").strip().splitlines()[-1])
    except Exception:
        return 0


def create_report(
    info: dict,
    msi_count: int,
    closed_count: int,
    cleaned_count: int,
) -> None:
    lines = [
        f"T-BOOSTER v{VERSION} - TÜRKÇE RAPOR",
        f"Yapımcı: {AUTHOR}",
        f"Tarih: {dt.datetime.now():%d.%m.%Y %H:%M:%S}",
        "=" * 82,
        f"Windows Build: {info.get('Build')}",
        f"Windows Build: {info.get('Build')}",
        f"İşlemci: {info.get('CPU')}",
        f"Ekran Kartı: {info.get('GPU')}",
        f"RAM: {info.get('RAM')} GB | Modül: {info.get('Modules')}",
        "",
        "UYGULANANLAR",
        "- T-BOOSTER özel güç planı oluşturuldu.",
        "-  minimum ve maksimum işlemci durumu %100.",
        "- EPP 0, agresif boost ve çekirdek park etmeme hedefleri.",
        "- PCIe, USB, disk ve Wi-Fi güç tasarrufları  kapatıldı.",
        "- Game Mode ve HAGS açıldı.",
        "- Game DVR, arka plan görüntü ve ses kaydı kapatıldı.",
        "- Windows Power Throttling kapatıldı.",
        "- Foreground ve MMCSS Games görev öncelikleri düzenlendi.",
        "- Seçili Windows animasyonları, şeffaflık, Peek ve başlangıç gecikmesi kapatıldı.",
        "- Fare ivmesi kapatıldı.",
        "- Windows önerileri ve sessiz uygulama kurulumları kapatıldı.",
        "- Görsel efektlerde yalnızca yazı tipi yumuşatma, küçük resimler ve pencere içeriğini sürüklerken gösterme açık bırakıldı.",
        "- Son kullanılan belgeler geçmişi kapatıldı ve çıkışta temizlenecek.",
        "- Görev çubuğu arama, widget, sohbet, görev görünümü ve Copilot düğmeleri kapatıldı.",
        "- Başlat önerileri ve haber/feed bileşenleri gizlendi.",
        "- Delivery Optimization eşler arası indirme kapatıldı.",
        "- SystemResponsiveness 10 ve NetworkThrottlingIndex FFFFFFFF uygulandı.",
        "- Zorlanmış HPET/platform clock ve BCD timer ayarları kaldırıldı.",
        f"- MSI Mode uygulanan uyumlu GPU girdisi: {msi_count}",
        f"- Kapatılan arka plan uygulaması: {closed_count}",
        "- Dosya temizleme: DEVRE DIŞI — hiçbir dosya silinmedi.",
        f"- Toplam uygulanan tweak/adım: {len(REGISTRY_EDITS) + 8}",
        "",
        "BİLEREK DOKUNULMAYANLAR",
        "- Defender, Güvenlik Duvarı ve Windows Update hizmetleri.",
        "- VBS, Bellek Bütünlüğü, Secure Boot ve TPM.",
        "- Sanal bellek, memory compression ve ağ yığını.",
        "- Fiziksel HPET aygıtı; yalnızca zorlanmış debug ayarları kaldırıldı.",
        "- Sürücünün destek anahtarı bulunmayan cihazlarda MSI Mode.",
        "- ProcessIdleTasks: FPS artırmaz, bekleyen bakım görevlerini çalıştırır.",
        "- WaitToKillServiceTimeout=200: veri kaybı / servis kapanma riski nedeniyle uygulanmadı.",
        "- DisablePagingExecutive, LargeSystemCache, IOPageLockLimit: eski XP bellek tweakleri uygulanmadı.",
        "- QoS yüzde 20 efsanesi: internet hızını yüzde 20 artırmadığı için uygulanmadı.",
        "",
        "SON KONTROLLER",
        "- Windows Gelişmiş Ekran bölümünden monitörün en yüksek Hz değerini seç.",
        "- Güncel chipset ve ekran kartı sürücülerini üreticinin resmî sitesinden kur.",
        "- Agresif güç profili sıcaklık ve fan sesini artırabilir.",
        "- Değişikliklerin tamamlanması için bilgisayarı yeniden başlat.",
        "- T-BOOSTER hiçbir kullanıcı veya sistem dosyasını silmez.",
    ]
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def apply_boost(callback, progress) -> dict:
    ensure_directories()
    backup = BackupStore()
    info = hardware_info()
    backup.data["hardware"] = info
    backup.save()

    steps = 9

    progress(1, steps)
    callback("İlk ayarlar yedekleniyor ve geri yükleme noktası deneniyor...")
    for edit in REGISTRY_EDITS:
        item_id, root, path, name, *_ = edit
        backup.backup_registry(item_id, root, path, name)
    backup_power_plan(backup)
    backup_bcd(backup)
    backup_visual_effects(backup)
    create_restore_point()

    progress(2, steps)
    apply_power_plan(backup, callback)

    progress(3, steps)
    apply_registry_edits(backup, callback)
    apply_visual_effect_profile(backup, callback)

    progress(4, steps)
    remove_forced_timer_overrides(backup, callback)

    progress(5, steps)
    msi_count = enable_supported_gpu_msi(backup, callback)

    progress(6, steps)
    closed_count = close_background_apps(callback)

    progress(7, steps)
    xbox_service_count = disable_xbox_services(callback)
    xbox_app_count = remove_xbox_apps(callback)
    callback("Dosya silme adımı atlandı — T-BOOSTER hiçbir dosyayı silmez.")
    cleaned_count = 0

    progress(8, steps)
    callback("T-Booster güç planı etkinleştiriliyor ve rapor hazırlanıyor...")
    run_command(["powercfg.exe", "/setactive", PLAN_GUID])
    verification = verify_applied_settings()
    report_error = ""
    try:
        create_report(info, msi_count, closed_count, cleaned_count)
        append_verification_to_report(verification)
    except Exception as exc:
        report_error = str(exc)
        log_line(f"Rapor oluşturma hatası: {exc}")
        callback("Ayarlar başarıyla uygulandı; rapor dosyası oluşturulamadı. İşlem devam ediyor...")

    progress(9, steps)
    callback(
        f"T-BOOST tamamlandı — doğrulama {verification['passed']}/{verification['total']}."
    )
    log_line(
        f"BOOST tamamlandı. Doğrulama: {verification['passed']}/{verification['total']}"
    )
    return {
        "msi": msi_count,
        "closed": closed_count,
        "cleaned": cleaned_count,
        "xbox_services": xbox_service_count,
        "xbox_apps": xbox_app_count,
        "report": str(REPORT_FILE) if REPORT_FILE.exists() else "",
        "report_error": report_error,
        "verification": verification,
    }


def restore_power_plan(backup: BackupStore, callback) -> None:
    callback("İlk güç planı geri yükleniyor...")
    original_guid = backup.data.get("original_power_guid")
    if original_guid:
        if not power_plan_exists(original_guid) and POWER_BACKUP.exists():
            run_command(
                ["powercfg.exe", "/import", str(POWER_BACKUP), original_guid]
            )
        run_command(["powercfg.exe", "/setactive", original_guid])
    else:
        run_command(["powercfg.exe", "/setactive", "SCHEME_BALANCED"])

    for tb_guid in (PLAN_GUID, *ESKI_PLANLAR):
        if original_guid and tb_guid.lower() == original_guid.lower():
            continue
        if power_plan_exists(tb_guid):
            run_command(["powercfg.exe", "/delete", tb_guid])


def restore_all(callback, progress) -> None:
    backup = BackupStore()
    if not backup.exists:
        raise RuntimeError("Geri alınacak T-BOOSTER yedeği bulunamadı.")

    progress(1, 5)
    callback("Tüm Registry değerleri ilk hâline döndürülüyor...")
    backup.restore_registry(callback)

    progress(2, 5)
    restore_visual_effects(backup, callback)

    progress(3, 5)
    restore_bcd(backup, callback)

    progress(4, 5)
    restore_power_plan(backup, callback)

    progress(5, 5)
    callback("Tüm T-BOOSTER ayarları geri alındı.")
    log_line("Tüm ayarlar geri alındı.")




try:
    import psutil  # type: ignore
except Exception:
    psutil = None

CUSTOM_OPTION_GROUPS = {
    "oyun": {
        "game_mode": [
            ("opt_game_mode_allow", "HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", REG_DWORD, 1),
            ("opt_game_mode_enabled", "HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", REG_DWORD, 1),
        ],
        "hags": [
            ("opt_hags", "HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", REG_DWORD, 2),
        ],
        "mouse_accel_off": [
            ("opt_mouse_speed", "HKCU", r"Control Panel\Mouse", "MouseSpeed", REG_SZ, "0"),
            ("opt_mouse_t1", "HKCU", r"Control Panel\Mouse", "MouseThreshold1", REG_SZ, "0"),
            ("opt_mouse_t2", "HKCU", r"Control Panel\Mouse", "MouseThreshold2", REG_SZ, "0"),
        ],
        "focus_assist_off": [
            ("opt_quiet_hours_active", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\QuietHours", "QuietHoursActive", REG_DWORD, 0),
            ("opt_toasts_enabled", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings", "NOC_GLOBAL_SETTING_TOASTS_ENABLED", REG_DWORD, 1),
        ],
        "power_throttle_off": [
            ("opt_power_throttle", "HKLM", r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", REG_DWORD, 1),
        ],
        "mpo_off": [
            ("opt_mpo", "HKLM", r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", REG_DWORD, 5),
        ],
    },
    "windows": {
        "dark_theme": [
            ("opt_theme_apps", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", REG_DWORD, 0),
            ("opt_theme_system", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "SystemUsesLightTheme", REG_DWORD, 0),
        ],
        "long_paths": [
            ("opt_long_paths", "HKLM", r"SYSTEM\CurrentControlSet\Control\FileSystem", "LongPathsEnabled", REG_DWORD, 1),
        ],
        "file_extensions": [
            ("opt_extensions", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "HideFileExt", REG_DWORD, 0),
        ],
        "hidden_files": [
            ("opt_hidden_files", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Hidden", REG_DWORD, 1),
            ("opt_super_hidden", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowSuperHidden", REG_DWORD, 1),
        ],
        "lock_screen_off": [
            ("opt_lock_screen", "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Personalization", "NoLockScreen", REG_DWORD, 1),
        ],
        "bing_search_off": [
            ("opt_bing_search", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", REG_DWORD, 0),
            ("opt_search_suggestions", "HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", REG_DWORD, 1),
        ],
        "recommendations_off": [
            ("opt_recommendations", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Start_IrisRecommendations", REG_DWORD, 0),
        ],
        "taskbar_search_icon": [
            ("opt_search_icon", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "SearchboxTaskbarMode", REG_DWORD, 1),
        ],
        "taskview_off": [
            ("opt_taskview", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowTaskViewButton", REG_DWORD, 0),
        ],
        "taskbar_left": [
            ("opt_taskbar_left", "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarAl", REG_DWORD, 0),
        ],
    },
}


def _run_text_command(cmd):
    try:
        result = run_command(cmd, timeout=8)
        return result.stdout.strip()
    except Exception:
        return ""


def _cpu_usage_percent():
    if psutil:
        try:
            return float(psutil.cpu_percent(interval=None))
        except Exception:
            pass
    out = _run_text_command(["wmic", "cpu", "get", "loadpercentage", "/value"])
    m = re.search(r"LoadPercentage=(\d+)", out, re.I)
    return float(m.group(1)) if m else 0.0


def _ram_usage_percent():
    if psutil:
        try:
            return float(psutil.virtual_memory().percent)
        except Exception:
            pass
    return 0.0


def _disk_usage_info(path="C:\\"):
    try:
        total, used, free = shutil.disk_usage(path)
        return {
            "total_gb": total / (1024 ** 3),
            "used_gb": used / (1024 ** 3),
            "free_gb": free / (1024 ** 3),
            "percent": (used / total * 100) if total else 0.0,
        }
    except Exception:
        return {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "percent": 0.0}


def _cpu_temp_c():
    if psutil:
        try:
            temps = psutil.sensors_temperatures()
            for entries in temps.values():
                if entries:
                    current = getattr(entries[0], 'current', None)
                    if current:
                        return float(current)
        except Exception:
            pass
    out = _run_text_command(["wmic", "/namespace:\\\\root\\wmi", "PATH", "MSAcpi_ThermalZoneTemperature", "get", "CurrentTemperature", "/value"])
    vals = [int(v) for v in re.findall(r"CurrentTemperature=(\d+)", out)]
    for val in vals:
        c = (val / 10.0) - 273.15
        if -10 < c < 150:
            return c
    return None


def _gpu_live_info():
    out = _run_text_command([
        "nvidia-smi",
        "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total,name",
        "--format=csv,noheader,nounits",
    ])
    if out:
        parts = [p.strip() for p in out.split(',')]
        if len(parts) >= 5:
            try:
                return {
                    "usage": float(parts[0]),
                    "temp": float(parts[1]),
                    "mem_used": float(parts[2]),
                    "mem_total": float(parts[3]),
                    "name": parts[4],
                }
            except Exception:
                pass
    return {"usage": None, "temp": None, "mem_used": None, "mem_total": None, "name": None}


def get_live_metrics():
    cpu = _cpu_usage_percent()
    ram = _ram_usage_percent()
    disk = _disk_usage_info()
    cpu_temp = _cpu_temp_c()
    gpu = _gpu_live_info()
    return {
        "cpu_usage": cpu,
        "cpu_temp": cpu_temp,
        "ram_usage": ram,
        "disk": disk,
        "gpu": gpu,
    }


def apply_selected_options(option_ids, callback):
    ensure_directories()
    backup = BackupStore()
    applied = 0
    special = {"hpet": 0, "msi": 0, "xbox": 0}
    callback("Seçili panel ayarları uygulanıyor...")
    for option_id in option_ids:
        if option_id == "hpet_cleanup":
            remove_forced_timer_overrides(backup, callback)
            special["hpet"] += 1
            applied += 1
            continue
        if option_id == "msi_mode":
            special["msi"] += enable_supported_gpu_msi(backup, callback)
            applied += 1
            continue
        if option_id == "xbox_cleanup":
            special["xbox"] += disable_xbox_services(callback)
            special["xbox"] += remove_xbox_apps(callback)
            applied += 1
            continue
        for group in CUSTOM_OPTION_GROUPS.values():
            edits = group.get(option_id)
            if edits:
                for item_id, root, path, name, vtype, value in edits:
                    try:
                        write_registry(backup, item_id, root, path, name, vtype, value)
                    except Exception as exc:
                        log_line(f"Panel seçeneği atlandı ({option_id}/{name}): {exc}")
                applied += 1
                break

    run_command(["rundll32.exe", "user32.dll,UpdatePerUserSystemParameters"], timeout=10)
    callback(f"Seçili panel ayarları tamamlandı: {applied} seçenek uygulandı.")
    return {"applied": applied, **special}


class TBoosterApp:
    DARK = {
        "BG": "#0a0d14",
        "PANEL": "#121826",
        "PANEL_2": "#171f31",
        "GLASS": "#1a2337",
        "BORDER": "#2d3958",
        "TEXT": "#f4f7ff",
        "MUTED": "#aab4cb",
        "ACCENT": "#78e3ff",
        "ACCENT_2": "#9f88ff",
        "GREEN": "#66e1b3",
        "RED": "#ff869f",
        "GOLD": "#ffd98b",
        "SURFACE": "#0d111b",
    }
    LIGHT = {
        "BG": "#eef2f8",
        "PANEL": "#f8fbff",
        "PANEL_2": "#edf3fb",
        "GLASS": "#ffffff",
        "BORDER": "#c9d7ea",
        "TEXT": "#131a26",
        "MUTED": "#5d6b83",
        "ACCENT": "#2bb8ff",
        "ACCENT_2": "#7f6fff",
        "GREEN": "#21b778",
        "RED": "#e05f7b",
        "GOLD": "#d9a936",
        "SURFACE": "#dde6f3",
    }

    def __init__(self) -> None:
        self.theme_name = "dark"
        self.palette = dict(self.DARK)
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{VERSION}")
        self.root.geometry("1220x820")
        self.root.minsize(1100, 760)
        self.root.configure(bg=self.palette["BG"])
        self.root.protocol("WM_DELETE_WINDOW", self.animate_close)

        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.info = hardware_info()
        self.status_var = tk.StringVar(value="Hazır — sistem analiz edildi.")
        self.verify_var = tk.StringVar(value="Doğrulama henüz çalıştırılmadı")
        self.page_title_var = tk.StringVar(value="Kontrol Merkezi")
        self.logo_img = None
        self.metric_vars = {
            "cpu": tk.StringVar(value="CPU: --"),
            "gpu": tk.StringVar(value="GPU: --"),
            "ram": tk.StringVar(value="RAM: --"),
            "disk": tk.StringVar(value="Disk: --"),
        }
        self.metric_progress = {}
        self.progress_value = 0
        self.current_page = "dashboard"

        self.option_vars = {}
        self._create_option_vars()
        self._build_styles()
        self._apply_native_window_effects()
        self._build_ui()
        self.root.after(30, self.animate_open)
        self.root.after(100, self._poll_events)
        self.root.after(300, self._update_metrics)

    def _create_option_vars(self):
        defaults = {
            "game_mode": True,
            "hags": True,
            "mouse_accel_off": True,
            "focus_assist_off": True,
            "power_throttle_off": True,
            "hpet_cleanup": True,
            "msi_mode": True,
            "xbox_cleanup": True,
            "mpo_off": False,
            "dark_theme": False,
            "long_paths": True,
            "file_extensions": True,
            "hidden_files": True,
            "lock_screen_off": False,
            "bing_search_off": True,
            "recommendations_off": True,
            "taskbar_search_icon": True,
            "taskview_off": True,
            "taskbar_left": True,
        }
        for key, value in defaults.items():
            self.option_vars[key] = tk.BooleanVar(value=value)

    @staticmethod
    def _mix(c1: str, c2: str, amount: float) -> str:
        a = tuple(int(c1[i:i+2], 16) for i in (1, 3, 5))
        b = tuple(int(c2[i:i+2], 16) for i in (1, 3, 5))
        rgb = tuple(round(a[i] + (b[i] - a[i]) * amount) for i in range(3))
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    def _apply_native_window_effects(self):
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            dwmapi = ctypes.windll.dwmapi
            def set_attr(attr, value):
                c_val = ctypes.c_int(value)
                dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(c_val), ctypes.sizeof(c_val))
            set_attr(20, 1)
            set_attr(33, 2)
            try:
                set_attr(38, 2)
            except Exception:
                pass
        except Exception as exc:
            log_line(f"Cam efekti uygulanamadı: {exc}")

    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TB.Horizontal.TProgressbar",
            troughcolor=self.palette["PANEL_2"],
            background=self.palette["ACCENT"],
            lightcolor=self.palette["ACCENT"],
            darkcolor=self.palette["ACCENT_2"],
            bordercolor=self.palette["PANEL_2"],
            thickness=12,
        )

    def _load_logo(self):
        if LOGO_FILE.exists():
            try:
                img = tk.PhotoImage(file=str(LOGO_FILE))
                self.logo_img = img.subsample(4,4)
                return self.logo_img
            except Exception as exc:
                log_line(f"Logo yüklenemedi: {exc}")
        return None

    def _rebuild_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self._build_styles()
        self.root.configure(bg=self.palette["BG"])
        self._build_ui()
        self.show_page(self.current_page)

    def switch_theme(self, theme_name: str):
        self.theme_name = theme_name
        self.palette = dict(self.DARK if theme_name == "dark" else self.LIGHT)
        self._rebuild_ui()

    def animate_open(self):
        target_w, target_h = 1220, 820
        start_w, start_h = 980, 640
        x = max((self.root.winfo_screenwidth() - target_w)//2, 20)
        y = max((self.root.winfo_screenheight() - target_h)//2, 20)
        steps = 12
        for step in range(1, steps+1):
            w = int(start_w + (target_w - start_w) * (step/steps))
            h = int(start_h + (target_h - start_h) * (step/steps))
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.root.update_idletasks()
            time.sleep(0.01)

    def animate_close(self):
        try:
            self.root.update_idletasks()
            geo = self.root.geometry().split('+')[0]
            w, h = [int(v) for v in geo.split('x')]
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            steps = 10
            for step in range(steps, 0, -1):
                nw = max(700, int(w * step/steps))
                nh = max(420, int(h * step/steps))
                self.root.geometry(f"{nw}x{nh}+{x}+{y}")
                self.root.update_idletasks()
                time.sleep(0.01)
        except Exception:
            pass
        self.root.destroy()

    def _build_ui(self):
        header = tk.Canvas(self.root, height=130, bg=self.palette["BG"], highlightthickness=0, bd=0)
        header.pack(fill="x")
        self._draw_header(header)

        main = tk.Frame(self.root, bg=self.palette["BG"])
        main.pack(fill="both", expand=True, padx=18, pady=(10, 16))
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(main, bg=self.palette["PANEL"], highlightbackground=self.palette["BORDER"], highlightthickness=1, width=240)
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(0,12))
        self.sidebar.grid_propagate(False)

        self.content = tk.Frame(main, bg=self.palette["BG"])
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(1, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()

    def _draw_header(self, canvas):
        width = 1400
        height = 130
        for y in range(height):
            canvas.create_line(0, y, width, y, fill=self._mix(self.palette["BG"], self.palette["PANEL"], y/height))
        for x, y, r, color in [
            (70, 26, 90, self.palette["ACCENT"]),
            (260, 16, 72, self.palette["ACCENT_2"]),
            (1060, 26, 110, self.palette["ACCENT"]),
            (1180, 50, 85, self.palette["ACCENT_2"]),
        ]:
            for i in range(3):
                rr = r + i*14
                fill = self._mix(color, self.palette["BG"], 0.55 + i*0.1)
                canvas.create_oval(x-rr, y-rr, x+rr, y+rr, fill=fill, outline="")
        logo = self._load_logo()
        if logo is not None:
            canvas.create_image(78, 65, image=logo)
        else:
            canvas.create_oval(24, 20, 132, 110, fill=self.palette["ACCENT_2"], outline="")
            canvas.create_text(78, 65, text="T", fill="white", font=("Times New Roman", 28, "bold italic"))
        canvas.create_text(150, 38, anchor="w", text="T-BOOSTER", fill=self.palette["TEXT"], font=("Times New Roman", 30, "bold italic"))
        canvas.create_text(152, 72, anchor="w", text="LIQUID GLASS X • OYUN MODU / ULTRA MOD • TÜRKÇE PANEL", fill=self.palette["ACCENT"], font=("Segoe UI Semibold", 11, "bold"))
        canvas.create_text(152, 96, anchor="w", text="Animasyonlu açılış • Sol menü • Canlı CPU/GPU/Disk takibi • Dosya silmez", fill=self.palette["MUTED"], font=("Segoe UI", 9))
        canvas.create_text(1180, 40, anchor="e", text=f"v{VERSION}", fill=self.palette["MUTED"], font=("Segoe UI", 11, "bold"))

    def _sidebar_btn(self, parent, icon, text, page):
        bg = self.palette["PANEL"]
        frame = tk.Frame(parent, bg=bg, cursor="hand2")
        frame.pack(fill="x", padx=12, pady=4)
        inner = tk.Frame(frame, bg=bg, highlightthickness=1, highlightbackground=self.palette["BORDER"])
        inner.pack(fill="x")
        tk.Label(inner, text=icon, bg=bg, fg=self.palette["ACCENT"], font=("Segoe UI Emoji", 14)).pack(side="left", padx=(12,8), pady=10)
        tk.Label(inner, text=text, bg=bg, fg=self.palette["TEXT"], font=("Segoe UI Semibold", 10)).pack(side="left", pady=10)
        def click(_e=None):
            self.show_page(page)
        for w in (frame, inner):
            w.bind("<Button-1>", click)
            w.bind("<Enter>", lambda _e, c=inner: c.configure(highlightbackground=self.palette["ACCENT"]))
            w.bind("<Leave>", lambda _e, c=inner: c.configure(highlightbackground=self.palette["BORDER"]))
        return frame

    def _build_sidebar(self):
        top = tk.Frame(self.sidebar, bg=self.palette["PANEL"])
        top.pack(fill="x", pady=(16,10))
        tk.Label(top, text="SOL MENÜ", bg=self.palette["PANEL"], fg=self.palette["MUTED"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16)
        tk.Label(top, textvariable=self.page_title_var, bg=self.palette["PANEL"], fg=self.palette["TEXT"], font=("Segoe UI Black", 16, "bold")).pack(anchor="w", padx=16, pady=(4,0))
        self._sidebar_btn(self.sidebar, "🏠", "Kontrol Merkezi", "dashboard")
        self._sidebar_btn(self.sidebar, "🎮", "Oyun Modu", "gaming")
        self._sidebar_btn(self.sidebar, "🪟", "Windows Ayarları", "windows")
        self._sidebar_btn(self.sidebar, "📜", "İşlem Günlüğü", "logs")

        spacer = tk.Frame(self.sidebar, bg=self.palette["PANEL"])
        spacer.pack(fill="both", expand=True)

        bottom = tk.Frame(self.sidebar, bg=self.palette["PANEL"])
        bottom.pack(fill="x", padx=12, pady=12)
        self._theme_switch(bottom)
        self._mini_action(bottom, "↶ Geri Al", self.start_restore, self.palette["ACCENT"])
        self._mini_action(bottom, "✕ Çıkış", self.animate_close, self.palette["RED"])

    def _mini_action(self, parent, text, command, color):
        btn = tk.Label(parent, text=text, bg=self.palette["PANEL_2"], fg=color, cursor="hand2", font=("Segoe UI Semibold", 10), pady=8)
        btn.pack(fill="x", pady=5)
        btn.bind("<Button-1>", lambda _e: command())
        return btn

    def _theme_switch(self, parent):
        box = tk.Frame(parent, bg=self.palette["PANEL_2"], highlightbackground=self.palette["BORDER"], highlightthickness=1)
        box.pack(fill="x", pady=(0,8))
        tk.Label(box, text="TEMA", bg=self.palette["PANEL_2"], fg=self.palette["MUTED"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8,2))
        row = tk.Frame(box, bg=self.palette["PANEL_2"])
        row.pack(fill="x", padx=8, pady=(0,8))
        for key, label in (("dark", "Liquid Black"), ("light", "Liquid White")):
            active = (self.theme_name == key)
            bg = self.palette["ACCENT"] if active else self.palette["PANEL"]
            fg = "#0b0d14" if active and self.theme_name == "light" else (self.palette["TEXT"] if not active else "#091019")
            chip = tk.Label(row, text=label, bg=bg, fg=fg, cursor="hand2", font=("Segoe UI Semibold", 9), padx=10, pady=6)
            chip.pack(side="left", padx=4, fill="x", expand=True)
            chip.bind("<Button-1>", lambda _e, k=key: self.switch_theme(k))

    def _build_content(self):
        head = tk.Frame(self.content, bg=self.palette["BG"])
        head.grid(row=0, column=0, sticky="ew", pady=(0,10))
        tk.Label(head, textvariable=self.status_var, bg=self.palette["BG"], fg=self.palette["TEXT"], font=("Segoe UI Semibold", 11, "bold")).pack(anchor="w")
        tk.Label(head, textvariable=self.verify_var, bg=self.palette["BG"], fg=self.palette["MUTED"], font=("Segoe UI", 9)).pack(anchor="w", pady=(3,0))
        self.pages_holder = tk.Frame(self.content, bg=self.palette["BG"])
        self.pages_holder.grid(row=1, column=0, sticky="nsew")
        self.pages_holder.grid_rowconfigure(0, weight=1)
        self.pages_holder.grid_columnconfigure(0, weight=1)
        self.pages = {}
        self.pages["dashboard"] = self._build_dashboard_page()
        self.pages["gaming"] = self._build_gaming_page()
        self.pages["windows"] = self._build_windows_page()
        self.pages["logs"] = self._build_logs_page()
        self.show_page("dashboard")

    def show_page(self, page_name):
        self.current_page = page_name
        titles = {
            "dashboard": "Kontrol Merkezi",
            "gaming": "Oyun Modu",
            "windows": "Windows Ayarları",
            "logs": "İşlem Günlüğü",
        }
        self.page_title_var.set(titles.get(page_name, "T-Booster"))
        for name, frame in self.pages.items():
            if name == page_name:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

    def _page(self):
        frame = tk.Frame(self.pages_holder, bg=self.palette["BG"])
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _glass_card(self, parent, title, subtitle=""):
        outer = tk.Frame(parent, bg=self.palette["SURFACE"])
        frame = tk.Frame(outer, bg=self.palette["PANEL"], highlightbackground=self.palette["BORDER"], highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=(0,1), pady=(0,1))
        top = tk.Frame(frame, bg=self.palette["PANEL"])
        top.pack(fill="x", padx=14, pady=(12,6))
        tk.Label(top, text=title, bg=self.palette["PANEL"], fg=self.palette["TEXT"], font=("Segoe UI Semibold", 11, "bold")).pack(side="left")
        if subtitle:
            tk.Label(top, text=subtitle, bg=self.palette["PANEL"], fg=self.palette["MUTED"], font=("Segoe UI", 8)).pack(side="right")
        body = tk.Frame(frame, bg=self.palette["PANEL"])
        body.pack(fill="both", expand=True, padx=14, pady=(0,12))
        return outer, body

    def _metric_card(self, parent, title, var_key, accent):
        outer, body = self._glass_card(parent, title, "CANLI")
        tk.Label(body, textvariable=self.metric_vars[var_key], bg=self.palette["PANEL"], fg=self.palette["TEXT"], font=("Segoe UI Black", 14)).pack(anchor="w", pady=(4,10))
        pb = ttk.Progressbar(body, style="TB.Horizontal.TProgressbar", mode="determinate", maximum=100)
        pb.pack(fill="x")
        self.metric_progress[var_key] = pb
        chip = tk.Frame(body, bg=self.palette["GLASS"], highlightbackground=self.palette["BORDER"], highlightthickness=1)
        chip.pack(fill="x", pady=(10,0))
        tk.Label(chip, text="ANLIK İZLEME", bg=self.palette["GLASS"], fg=accent, font=("Segoe UI Semibold", 8, "bold")).pack(anchor="w", padx=10, pady=(8,1))
        tk.Label(chip, text="Kullanım ve sıcaklık verileri otomatik yenilenir.", bg=self.palette["GLASS"], fg=self.palette["MUTED"], font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=(0,8))
        return outer

    def _build_dashboard_page(self):
        page = self._page()
        top = tk.Frame(page, bg=self.palette["BG"])
        top.grid(row=0, column=0, sticky="ew")
        for i in range(4):
            top.grid_columnconfigure(i, weight=1)
        cards = [
            ("CPU", "cpu", self.palette["ACCENT"]),
            ("GPU", "gpu", self.palette["ACCENT_2"]),
            ("RAM", "ram", self.palette["GREEN"]),
            ("DİSK C", "disk", self.palette["GOLD"]),
        ]
        for idx, (title, key, accent) in enumerate(cards):
            self._metric_card(top, title, key, accent).grid(row=0, column=idx, sticky="nsew", padx=(0 if idx==0 else 8, 0))

        bottom = tk.Frame(page, bg=self.palette["BG"])
        bottom.grid(row=1, column=0, sticky="nsew", pady=(12,0))
        bottom.grid_columnconfigure(0, weight=3)
        bottom.grid_columnconfigure(1, weight=2)
        bottom.grid_rowconfigure(0, weight=1)

        left_outer, left = self._glass_card(bottom, "BOOST MODLARI", "AKILLI / ULTRA")
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(0,8))
        self._hero_action(left, "⚡ AKILLI BOOST", "Dengeli ama güçlü: temel FPS, stabilite ve güvenli ayarlar.", self.palette["GREEN"], lambda: self.start_boost("smart"))
        self._hero_action(left, "🚀 ULTRA BOOST", "Daha agresif: Oyun + Windows panel seçeneklerini de uygula.", self.palette["ACCENT"], lambda: self.start_boost("ultra"))
        self._hero_action(left, "🛠 SEÇİLİ AYARLARI UYGULA", "Sol menüdeki Oyun Modu ve Windows Ayarları seçimlerini uygular.", self.palette["ACCENT_2"], self.start_apply_selected)

        right_outer, right = self._glass_card(bottom, "SİSTEM ÖZETİ", "DONANIM")
        right_outer.grid(row=0, column=1, sticky="nsew", padx=(8,0))
        info_rows = [
            ("Windows", f"Build {self.info.get('Build')}", "🪟"),
            ("İşlemci", str(self.info.get('CPU')), "🧠"),
            ("Ekran Kartı", str(self.info.get('GPU')), "🎮"),
            ("Bellek", f"{self.info.get('RAM')} GB • {self.info.get('Modules')} modül", "💾"),
        ]
        for label, value, icon in info_rows:
            row = tk.Frame(right, bg=self.palette["PANEL_2"], highlightbackground=self.palette["BORDER"], highlightthickness=1)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=icon, bg=self.palette["PANEL_2"], fg=self.palette["ACCENT"], font=("Segoe UI Emoji", 12)).pack(side="left", padx=(10,8), pady=8)
            txt = tk.Frame(row, bg=self.palette["PANEL_2"])
            txt.pack(side="left", fill="x", expand=True, pady=8)
            tk.Label(txt, text=label, bg=self.palette["PANEL_2"], fg=self.palette["MUTED"], font=("Segoe UI", 8)).pack(anchor="w")
            tk.Label(txt, text=value, bg=self.palette["PANEL_2"], fg=self.palette["TEXT"], font=("Segoe UI Semibold", 9), wraplength=320, justify="left").pack(anchor="w")
        return page

    def _hero_action(self, parent, title, subtitle, accent, command):
        card = tk.Frame(parent, bg=self.palette["GLASS"], highlightbackground=accent, highlightthickness=1, cursor="hand2")
        card.pack(fill="x", pady=6)
        row = tk.Frame(card, bg=self.palette["GLASS"])
        row.pack(fill="both", expand=True, padx=16, pady=14)
        icon = tk.Canvas(row, width=58, height=58, bg=self.palette["GLASS"], highlightthickness=0, bd=0)
        icon.pack(side="left", padx=(0,14))
        icon.create_oval(3,3,55,55, fill=accent, outline="")
        icon.create_text(29,29, text=title.split()[0], fill="white", font=("Segoe UI Emoji", 18))
        texts = tk.Frame(row, bg=self.palette["GLASS"])
        texts.pack(side="left", fill="x", expand=True)
        tk.Label(texts, text=title, bg=self.palette["GLASS"], fg=self.palette["TEXT"], font=("Segoe UI Black", 15)).pack(anchor="w")
        tk.Label(texts, text=subtitle, bg=self.palette["GLASS"], fg=self.palette["MUTED"], font=("Segoe UI", 9), wraplength=520, justify="left").pack(anchor="w", pady=(3,0))
        tk.Label(row, text="›", bg=self.palette["GLASS"], fg=accent, font=("Segoe UI", 26, "bold")).pack(side="right")
        for w in (card, row, icon, texts):
            w.bind("<Button-1>", lambda _e, cmd=command: cmd())
        return card

    def _toggle_row(self, parent, title, desc, var, accent):
        row = tk.Frame(parent, bg=self.palette["PANEL_2"], highlightbackground=self.palette["BORDER"], highlightthickness=1)
        row.pack(fill="x", pady=4)
        meta = tk.Frame(row, bg=self.palette["PANEL_2"])
        meta.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        tk.Label(meta, text=title, bg=self.palette["PANEL_2"], fg=self.palette["TEXT"], font=("Segoe UI Semibold", 10)).pack(anchor="w")
        tk.Label(meta, text=desc, bg=self.palette["PANEL_2"], fg=self.palette["MUTED"], font=("Segoe UI", 8), wraplength=500, justify="left").pack(anchor="w")
        canvas = tk.Canvas(row, width=58, height=30, bg=self.palette["PANEL_2"], highlightthickness=0, bd=0, cursor="hand2")
        canvas.pack(side="right", padx=12)
        def redraw(*_a):
            canvas.delete("all")
            on = var.get()
            track = accent if on else self.palette["SURFACE"]
            knob_x = 42 if on else 16
            canvas.create_oval(3,4,55,26, outline=self.palette["BORDER"], width=1, fill=track)
            canvas.create_oval(knob_x-10, 5, knob_x+10, 25, outline="", fill="white")
        def toggle(_e=None):
            var.set(not var.get())
            redraw()
        canvas.bind("<Button-1>", toggle)
        row.bind("<Button-1>", toggle)
        var.trace_add("write", lambda *_a: redraw())
        redraw()
        return row

    def _build_gaming_page(self):
        page = self._page()
        outer, body = self._glass_card(page, "OYUN MODU PANELİ", "FPS ODAKLI")
        outer.grid(row=0, column=0, sticky="nsew")
        items = [
            ("Game Mode", "Windows oyun odak ayarı açık kalır.", "game_mode", self.palette["ACCENT"]),
            ("HAGS", "Donanım hızlandırmalı GPU zamanlaması.", "hags", self.palette["ACCENT_2"]),
            ("Fare İvmesi Kapalı", "Daha tutarlı nişan ve masaüstü hareketi.", "mouse_accel_off", self.palette["GREEN"]),
            ("Odak Asistanı Kapalı", "Bildirim / focus assist baskılamasını kapatır.", "focus_assist_off", self.palette["GOLD"]),
            ("Power Throttling Kapalı", "Arka planda güç kısıtını azaltır.", "power_throttle_off", self.palette["ACCENT"]),
            ("HPET Zorlamasını Temizle", "Zorlanmış timer override değerlerini kaldırır.", "hpet_cleanup", self.palette["RED"]),
            ("MSI Mode", "Desteklenen GPU kayıtlarında MSI Mode dener.", "msi_mode", self.palette["ACCENT_2"]),
            ("Xbox Temizliği", "Xbox hizmetlerini kapatır ve paketleri kaldırmayı dener.", "xbox_cleanup", self.palette["RED"]),
            ("MPO Kapat", "Sorun çıkaran çok düzlemli kaplamayı devre dışı bırakır.", "mpo_off", self.palette["GREEN"]),
        ]
        for title, desc, key, accent in items:
            self._toggle_row(body, title, desc, self.option_vars[key], accent)
        self._mini_action(body, "Seçili Oyun Ayarlarını Uygula", self.start_apply_selected, self.palette["ACCENT"])
        return page

    def _build_windows_page(self):
        page = self._page()
        outer, body = self._glass_card(page, "WINDOWS AYARLARI PANELİ", "TÜRKÇE")
        outer.grid(row=0, column=0, sticky="nsew")
        items = [
            ("Karanlık Tema", "Windows için koyu modu etkinleştirir.", "dark_theme", self.palette["ACCENT"]),
            ("Uzun Dosya Yolları", "260 karakter sınırını kaldırmayı dener.", "long_paths", self.palette["GREEN"]),
            ("Dosya Uzantıları", "Dosya uzantılarını görünür yapar.", "file_extensions", self.palette["ACCENT_2"]),
            ("Gizli Dosyalar", "Gizli öğeleri gösterir.", "hidden_files", self.palette["GOLD"]),
            ("Kilit Ekranı Kapat", "Mümkün olan sürümlerde lock screen kapatılır.", "lock_screen_off", self.palette["RED"]),
            ("Başlat Bing Arama Kapalı", "Başlat / arama web önerilerini azaltır.", "bing_search_off", self.palette["ACCENT"]),
            ("Başlat Önerileri Kapalı", "Tavsiye edilen öğeleri gizler.", "recommendations_off", self.palette["GREEN"]),
            ("Görev Çubuğu Arama Simgesi", "Aramayı kutu yerine simge yapar.", "taskbar_search_icon", self.palette["ACCENT_2"]),
            ("Görev Görünümü Kapat", "Task View düğmesini gizler.", "taskview_off", self.palette["GOLD"]),
            ("Görev Çubuğu Sol Hizala", "Simgeleri sola alır.", "taskbar_left", self.palette["RED"]),
        ]
        for title, desc, key, accent in items:
            self._toggle_row(body, title, desc, self.option_vars[key], accent)
        self._mini_action(body, "Seçili Windows Ayarlarını Uygula", self.start_apply_selected, self.palette["ACCENT"])
        return page

    def _build_logs_page(self):
        page = self._page()
        outer, body = self._glass_card(page, "İŞLEM GÜNLÜĞÜ", "CANLI")
        outer.grid(row=0, column=0, sticky="nsew")
        self.log_box = tk.Text(body, bg=self.palette["SURFACE"], fg=self.palette["TEXT"], insertbackground=self.palette["TEXT"], relief="flat", font=("Consolas", 9), padx=12, pady=10, state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True)
        self._append_log("T-BOOSTER hazır.")
        self._append_log("Bu sürüm dosya silmez. Canlı panel ve sol menü etkindir.")
        return page

    def _append_log(self, text):
        if not hasattr(self, 'log_box'):
            return
        self.log_box.configure(state='normal')
        stamp = dt.datetime.now().strftime('%H:%M:%S')
        self.log_box.insert('end', f'[{stamp}] {text}\n')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def _set_busy(self, busy):
        self.busy = busy
        self.root.configure(cursor='watch' if busy else '')

    def _callback(self, text):
        self.events.put(("log", text))

    def _progress_callback(self, current, total):
        value = int(current / max(total, 1) * 100)
        self.events.put(("progress", value))

    def _update_metrics(self):
        try:
            metrics = get_live_metrics()
            cpu_temp = metrics['cpu_temp']
            cpu_text = f"{metrics['cpu_usage']:.0f}%"
            if cpu_temp is not None:
                cpu_text += f" • {cpu_temp:.0f}°C"
            self.metric_vars['cpu'].set(cpu_text)
            self.metric_progress['cpu']['value'] = max(0, min(100, metrics['cpu_usage']))

            gpu = metrics['gpu']
            if gpu.get('usage') is None:
                self.metric_vars['gpu'].set('Destek yok / ölçülemiyor')
                self.metric_progress['gpu']['value'] = 0
            else:
                gpu_text = f"{gpu['usage']:.0f}%"
                if gpu.get('temp') is not None:
                    gpu_text += f" • {gpu['temp']:.0f}°C"
                self.metric_vars['gpu'].set(gpu_text)
                self.metric_progress['gpu']['value'] = max(0, min(100, gpu['usage']))

            self.metric_vars['ram'].set(f"{metrics['ram_usage']:.0f}% kullanım")
            self.metric_progress['ram']['value'] = max(0, min(100, metrics['ram_usage']))

            disk = metrics['disk']
            self.metric_vars['disk'].set(f"{disk['free_gb']:.0f} GB boş / {disk['total_gb']:.0f} GB")
            self.metric_progress['disk']['value'] = max(0, min(100, disk['percent']))
        except Exception as exc:
            log_line(f"Canlı metrik hatası: {exc}")
        self.root.after(1200, self._update_metrics)

    def _selected_option_ids(self):
        return [k for k, v in self.option_vars.items() if v.get()]

    def apply_ultra_preset(self):
        ultra = [
            'game_mode','hags','mouse_accel_off','focus_assist_off','power_throttle_off','hpet_cleanup','msi_mode','xbox_cleanup','mpo_off',
            'long_paths','file_extensions','hidden_files','bing_search_off','recommendations_off','taskbar_search_icon','taskview_off','taskbar_left'
        ]
        for key in self.option_vars:
            self.option_vars[key].set(key in ultra)

    def start_boost(self, mode='smart'):
        if self.busy:
            return
        if mode == 'ultra':
            self.apply_ultra_preset()
        warning = (
            "T-BOOST çalışacak.\n\n"
            f"Mod: {'ULTRA' if mode=='ultra' else 'AKILLI'}\n"
            "• FPS odaklı ana sistem tweakleri\n"
            "• Seçili panel ayarları\n"
            "• Görsel efektlerde sadece 3 seçenek açık\n"
            "• Dosya silme yok\n\n"
            "Devam edilsin mi?"
        )
        if not messagebox.askyesno(APP_NAME, warning):
            return
        self._set_busy(True)
        self.verify_var.set('Uygulama sonrası otomatik kontrol yapılacak')
        threading.Thread(target=self._boost_worker, args=(mode,), daemon=True).start()

    def _boost_worker(self, mode):
        try:
            result = apply_boost(self._callback, self._progress_callback)
            extras = apply_selected_options(self._selected_option_ids(), self._callback)
            result['extras'] = extras
            self.events.put(("done_boost", result))
        except Exception as exc:
            log_line(traceback.format_exc())
            self.events.put(("error", f"BOOST tamamlanamadı:\n{exc}"))

    def start_apply_selected(self):
        if self.busy:
            return
        if not messagebox.askyesno(APP_NAME, "Seçili panel ayarları uygulansın mı?"):
            return
        self._set_busy(True)
        threading.Thread(target=self._apply_selected_worker, daemon=True).start()

    def _apply_selected_worker(self):
        try:
            result = apply_selected_options(self._selected_option_ids(), self._callback)
            self.events.put(("done_custom", result))
        except Exception as exc:
            log_line(traceback.format_exc())
            self.events.put(("error", f"Panel ayarları uygulanamadı:\n{exc}"))

    def start_restore(self):
        if self.busy:
            return
        if not BACKUP_FILE.exists():
            messagebox.showinfo(APP_NAME, 'Geri alınacak yedek bulunamadı.')
            return
        if not messagebox.askyesno(APP_NAME, 'Tüm T-Booster ayarları geri alınsın mı?'):
            return
        self._set_busy(True)
        threading.Thread(target=self._restore_worker, daemon=True).start()

    def _restore_worker(self):
        try:
            restore_all(self._callback, self._progress_callback)
            self.events.put(("done_restore", None))
        except Exception as exc:
            log_line(traceback.format_exc())
            self.events.put(("error", f"Geri alma tamamlanamadı:\n{exc}"))

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == 'log':
                    msg = event[1]
                    self.status_var.set(msg)
                    self._append_log(msg)
                elif kind == 'progress':
                    self.progress_value = event[1]
                elif kind == 'done_custom':
                    self._set_busy(False)
                    res = event[1]
                    self.verify_var.set(f"Seçili ayarlar uygulandı • {res['applied']} seçenek")
                    messagebox.showinfo(APP_NAME, f"Seçili panel ayarları tamamlandı.\n\nUygulanan seçenek: {res['applied']}")
                elif kind == 'done_boost':
                    self._set_busy(False)
                    result = event[1]
                    verification = result['verification']
                    extras = result.get('extras', {})
                    if verification['failed']:
                        verify_text = f"{verification['passed']}/{verification['total']} kontrol başarılı • kontrol edilmeli: " + ", ".join(verification['failed'])
                    else:
                        verify_text = f"{verification['passed']}/{verification['total']} kritik kontrol başarılı"
                    self.verify_var.set(verify_text)
                    message = (
                        "T-BOOST tamamlandı.\n\n"
                        f"Doğrulama: {verification['passed']}/{verification['total']}\n"
                        f"Ek panel seçeneği: {extras.get('applied', 0)}\n"
                        f"MSI Mode sayısı: {result.get('msi',0)} + {extras.get('msi',0)}\n"
                        f"Xbox işlemleri: {result.get('xbox_services',0)} + {result.get('xbox_apps',0)}\n"
                        "Değişikliklerin tamamlanması için yeniden başlatma önerilir."
                    )
                    if messagebox.askyesno(APP_NAME, message + "\n\nŞimdi yeniden başlatılsın mı?"):
                        run_command(["shutdown.exe", "/r", "/t", "5", "/c", "T-BOOSTER tamamlandı."])
                        self.animate_close()
                elif kind == 'done_restore':
                    self._set_busy(False)
                    self.verify_var.set('İlk ayarlar geri yüklendi')
                    if messagebox.askyesno(APP_NAME, 'Tüm ayarlar geri alındı.\n\nŞimdi yeniden başlatılsın mı?'):
                        run_command(["shutdown.exe", "/r", "/t", "5", "/c", "T-BOOSTER ayarları geri alındı."])
                        self.animate_close()
                elif kind == 'error':
                    self._set_busy(False)
                    self.status_var.set('Bir hata oluştu — günlük dosyasına bak.')
                    self._append_log('HATA: ' + event[1])
                    messagebox.showerror(APP_NAME, event[1])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def run(self):
        self.root.mainloop()

def show_startup_error(exc: BaseException) -> None:
    details = traceback.format_exc()
    try:
        ensure_directories()
        crash_file = DESKTOP / "T_BOOSTER_CRASH_LOG.txt"
        crash_file.write_text(details, encoding="utf-8")
    except Exception:
        crash_file = Path("T_BOOSTER_CRASH_LOG.txt")

    try:
        ctypes.windll.user32.MessageBoxW(
            None,
            f"T-BOOSTER açılırken hata oluştu.\n\n{exc}\n\n"
            f"Günlük: {crash_file}",
            "T-BOOSTER",
            0x10,
        )
    except Exception:
        pass


def main() -> None:
    if not is_windows():
        raise SystemExit("T-BOOSTER yalnızca Windows 10/11 üzerinde çalışır.")
    ensure_directories()
    if not is_admin():
        elevate()
    log_line(f"{APP_NAME} v{VERSION} başlatıldı.")
    app = TBoosterApp()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        show_startup_error(exc)
        raise
