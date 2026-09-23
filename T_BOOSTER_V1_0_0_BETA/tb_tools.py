# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from xml.sax.saxutils import escape

PROGRAM_DATA = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
STATE_DIR = PROGRAM_DATA / "TBooster" / "Yedek"
NETWORK_BACKUP_FILE = STATE_DIR / "ethernet_low_latency_backup.json"
GAME_PROFILE_STATE_FILE = STATE_DIR / "nvidia_game_profiles.json"
REMOVED_APPS_LOG_FILE = STATE_DIR / "removed_microsoft_apps.json"
TB_PLAN_GUID = "ef940bf1-f471-4b72-a09c-d7e87f1c4210"


MICROSOFT_REMOVABLE_APPS = (
    ("Clipchamp", ("Clipchamp.Clipchamp",)),
    ("Cortana", ("Microsoft.549981C3F5F10",)),
    ("Microsoft Copilot", ("Microsoft.Copilot",)),
    ("Microsoft Haberler", ("Microsoft.BingNews",)),
    ("Microsoft Hava Durumu", ("Microsoft.BingWeather",)),
    ("Yardım Al", ("Microsoft.GetHelp",)),
    ("İpuçları / Başlangıç", ("Microsoft.Getstarted",)),
    ("3D Görüntüleyici", ("Microsoft.Microsoft3DViewer",)),
    ("Microsoft 365 / Office Hub", ("Microsoft.MicrosoftOfficeHub",)),
    ("Microsoft Solitaire Collection", ("Microsoft.MicrosoftSolitaireCollection",)),
    ("Karma Gerçeklik Portalı", ("Microsoft.MixedReality.Portal",)),
    ("Paint 3D", ("Microsoft.MSPaint",)),
    ("Microsoft Kişiler", ("Microsoft.People",)),
    ("Skype", ("Microsoft.SkypeApp",)),
    ("Microsoft To Do", ("Microsoft.Todos",)),
    ("Alarmlar ve Saat", ("Microsoft.WindowsAlarms",)),
    ("Windows Kamera", ("Microsoft.WindowsCamera",)),
    ("Geri Bildirim Merkezi", ("Microsoft.WindowsFeedbackHub",)),
    ("Windows Haritalar", ("Microsoft.WindowsMaps",)),
    ("Ses Kaydedici", ("Microsoft.WindowsSoundRecorder",)),
    ("Eski Posta ve Takvim", ("microsoft.windowscommunicationsapps",)),
    ("Yeni Outlook", ("Microsoft.OutlookForWindows",)),
    ("Telefon Bağlantısı", ("Microsoft.YourPhone",)),
    ("Groove Müzik / Media Player paketi", ("Microsoft.ZuneMusic",)),
    ("Filmler ve TV", ("Microsoft.ZuneVideo",)),
    ("Xbox Uygulaması", ("Microsoft.XboxApp",)),
    ("Xbox Game Bar", ("Microsoft.XboxGamingOverlay",)),
    ("Xbox Oyun Kaplaması", ("Microsoft.XboxGameOverlay",)),
    ("Xbox TCUI", ("Microsoft.Xbox.TCUI",)),
    ("Xbox Kimlik Sağlayıcısı", ("Microsoft.XboxIdentityProvider",)),
    ("Xbox Konuşma Kaplaması", ("Microsoft.XboxSpeechToTextOverlay",)),
    ("Microsoft Teams", ("MicrosoftTeams", "MSTeams")),
    ("Microsoft Whiteboard", ("Microsoft.Whiteboard",)),
    ("Hızlı Yardım", ("MicrosoftCorporationII.QuickAssist",)),
    ("Dev Home", ("Microsoft.Windows.DevHome",)),
)

PROTECTED_MICROSOFT_APP_PACKAGES = {
    "Microsoft.WindowsStore",
    "Microsoft.StorePurchaseApp",
    "Microsoft.SecHealthUI",
    "Microsoft.Windows.SecHealthUI",
    "Microsoft.DesktopAppInstaller",
    "Microsoft.WindowsTerminal",
    "Microsoft.WindowsNotepad",
    "Microsoft.Paint",
    "Microsoft.Windows.Photos",
}


def microsoft_removable_app_labels() -> list[str]:
    return [label for label, _packages in MICROSOFT_REMOVABLE_APPS]


def remove_microsoft_consumer_apps(callback) -> dict:
    # Current-user Appx packages only. Provisioned packages are untouched.
    targets = []
    label_map = {}
    for label, package_names in MICROSOFT_REMOVABLE_APPS:
        for package_name in package_names:
            if package_name in PROTECTED_MICROSOFT_APP_PACKAGES:
                continue
            targets.append(package_name)
            label_map[package_name] = label

    target_json = json.dumps(targets, ensure_ascii=False)
    label_json = json.dumps(label_map, ensure_ascii=False)

    script = rf"""
$ErrorActionPreference = 'Continue'
$targets = ConvertFrom-Json @'
{target_json}
'@
$labels = ConvertFrom-Json @'
{label_json}
'@
$protected = @(
    'Microsoft.WindowsStore',
    'Microsoft.StorePurchaseApp',
    'Microsoft.SecHealthUI',
    'Microsoft.Windows.SecHealthUI',
    'Microsoft.DesktopAppInstaller',
    'Microsoft.WindowsTerminal',
    'Microsoft.WindowsNotepad',
    'Microsoft.Paint',
    'Microsoft.Windows.Photos'
)
$results = @()
foreach ($target in $targets) {{
    if ($protected -contains [string]$target) {{ continue }}
    $packages = @(Get-AppxPackage -Name ([string]$target) -ErrorAction SilentlyContinue)
    if ($packages.Count -eq 0) {{
        $results += [pscustomobject]@{{
            Name = [string]$target
            Label = [string]$labels.PSObject.Properties[[string]$target].Value
            Status = 'NotInstalled'
            Error = ''
        }}
        continue
    }}
    foreach ($package in $packages) {{
        try {{
            Remove-AppxPackage -Package $package.PackageFullName -ErrorAction Stop
            $results += [pscustomobject]@{{
                Name = [string]$package.Name
                Label = [string]$labels.PSObject.Properties[[string]$target].Value
                Status = 'Removed'
                Error = ''
            }}
        }}
        catch {{
            $results += [pscustomobject]@{{
                Name = [string]$package.Name
                Label = [string]$labels.PSObject.Properties[[string]$target].Value
                Status = 'Failed'
                Error = [string]$_.Exception.Message
            }}
        }}
    }}
}}
$results | ConvertTo-Json -Depth 5 -Compress
"""
    callback(
        "Microsoft Store, Defender ve temel Windows bileşenleri korunarak "
        "seçilmiş tüketici uygulamaları kaldırılıyor…"
    )
    result = _powershell(script, timeout=300)
    if result.returncode != 0 and not (result.stdout or "").strip():
        raise RuntimeError(
            (result.stderr or "Remove-AppxPackage çalıştırılamadı.").strip()
        )

    raw = (result.stdout or "").strip()
    if not raw:
        rows = []
    else:
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Microsoft uygulama kaldırma sonucu okunamadı: " + str(exc)
            ) from exc

    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        rows = []

    removed = []
    failed = []
    not_installed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = {
            "name": str(row.get("Name") or ""),
            "label": str(row.get("Label") or row.get("Name") or ""),
            "error": str(row.get("Error") or ""),
        }
        status = str(row.get("Status") or "")
        if status == "Removed":
            removed.append(item)
            callback("Kaldırıldı: " + item["label"])
        elif status == "Failed":
            failed.append(item)
            callback(
                "Kaldırılamadı: "
                + item["label"]
                + (" — " + item["error"] if item["error"] else "")
            )
        else:
            not_installed.append(item)

    callback(
        "Microsoft uygulama temizliği tamamlandı: "
        f"{len(removed)} kaldırıldı, {len(failed)} başarısız."
    )
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    previous = {}
    try:
        if REMOVED_APPS_LOG_FILE.exists():
            previous = json.loads(REMOVED_APPS_LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        previous = {}
    merged = {}
    for item in (previous.get("removed", []) if isinstance(previous, dict) else []):
        if isinstance(item, dict) and item.get("name"):
            merged[str(item["name"])] = dict(item)
    stamp = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    for item in removed:
        saved = dict(item)
        saved["removed_at"] = stamp
        merged[str(saved.get("name"))] = saved
    REMOVED_APPS_LOG_FILE.write_text(
        json.dumps({"updated_at": stamp, "removed": list(merged.values())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "removed": removed,
        "failed": failed,
        "not_installed": not_installed,
        "scope": "current_user",
        "store_protected": True,
        "defender_protected": True,
        "log_file": str(REMOVED_APPS_LOG_FILE),
    }

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_ACTIVE_SESSION_LOCK = threading.Lock()
_ACTIVE_SESSION = {
    "process": None,
    "previous_plan": None,
    "timer_mode": None,
    "timer_request": 5000,
    "stop_requested": False,
}


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(x) for x in args],
        capture_output=True,
        text=True,
        errors="ignore",
        timeout=timeout,
        check=False,
        creationflags=_CREATE_NO_WINDOW,
    )


def _powershell(script: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return _run([
        "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
        "-Command", script,
    ], timeout=timeout)


def active_power_plan_guid() -> str | None:
    result = _run(["powercfg.exe", "/getactivescheme"], timeout=12)
    match = re.search(r"([0-9a-fA-F-]{36})", result.stdout or "")
    return match.group(1).lower() if match else None


def set_power_plan(guid: str | None) -> bool:
    if not guid:
        return False
    return _run(["powercfg.exe", "/setactive", guid], timeout=15).returncode == 0


class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [
        ("Version", ctypes.c_uint32),
        ("ControlMask", ctypes.c_uint32),
        ("StateMask", ctypes.c_uint32),
    ]


def _set_process_performance(process: subprocess.Popen, priority: str) -> dict:
    if os.name != "nt":
        return {"priority": False, "power_throttling": False}

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
    priority_flag = 0x00000080 if priority == "high" else 0x00008000
    priority_ok = bool(kernel32.SetPriorityClass(handle, priority_flag))

    # ProcessPowerThrottling = 4. ExecutionSpeed bit = 0x1.
    state = PROCESS_POWER_THROTTLING_STATE(1, 0x1, 0x0)
    set_info = kernel32.SetProcessInformation
    set_info.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    set_info.restype = ctypes.c_bool
    throttling_ok = bool(
        set_info(handle, 4, ctypes.byref(state), ctypes.sizeof(state))
    )
    return {"priority": priority_ok, "power_throttling": throttling_ok}


def request_timer_05() -> dict:
    if os.name != "nt":
        return {"ok": False, "error": "Yalnızca Windows"}
    with _ACTIVE_SESSION_LOCK:
        if _ACTIVE_SESSION.get("timer_mode"):
            return {"ok": True, "mode": _ACTIVE_SESSION["timer_mode"], "actual_ms": 0.5}
        try:
            ntdll = ctypes.WinDLL("ntdll")
            func = ntdll.NtSetTimerResolution
            func.argtypes = [ctypes.c_ulong, ctypes.c_ubyte, ctypes.POINTER(ctypes.c_ulong)]
            func.restype = ctypes.c_long
            current = ctypes.c_ulong()
            status = int(func(5000, 1, ctypes.byref(current)))
            if status >= 0:
                _ACTIVE_SESSION["timer_mode"] = "native_05"
                return {"ok": True, "mode": "native_05", "actual_ms": current.value / 10000.0}
        except Exception:
            pass
        try:
            winmm = ctypes.WinDLL("winmm")
            if int(winmm.timeBeginPeriod(1)) == 0:
                _ACTIVE_SESSION["timer_mode"] = "winmm_1ms"
                return {"ok": True, "mode": "winmm_1ms", "actual_ms": 1.0}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": "Timer isteği kabul edilmedi."}


def release_timer() -> None:
    if os.name != "nt":
        return
    with _ACTIVE_SESSION_LOCK:
        mode = _ACTIVE_SESSION.get("timer_mode")
        try:
            if mode == "native_05":
                ntdll = ctypes.WinDLL("ntdll")
                func = ntdll.NtSetTimerResolution
                func.argtypes = [ctypes.c_ulong, ctypes.c_ubyte, ctypes.POINTER(ctypes.c_ulong)]
                func.restype = ctypes.c_long
                current = ctypes.c_ulong()
                func(5000, 0, ctypes.byref(current))
            elif mode == "winmm_1ms":
                ctypes.WinDLL("winmm").timeEndPeriod(1)
        finally:
            _ACTIVE_SESSION["timer_mode"] = None


def run_game_session(
    exe_path: str,
    priority: str,
    callback,
    previous_plan: str | None,
) -> dict:
    path = Path(exe_path)
    if not path.is_file() or path.suffix.lower() != ".exe":
        raise RuntimeError("Geçerli bir oyun EXE dosyası seçilmedi.")

    with _ACTIVE_SESSION_LOCK:
        existing = _ACTIVE_SESSION.get("process")
        if existing is not None and existing.poll() is None:
            raise RuntimeError("Başka bir T-Booster oyun oturumu zaten çalışıyor.")
        _ACTIVE_SESSION["previous_plan"] = previous_plan
        _ACTIVE_SESSION["stop_requested"] = False

    timer = request_timer_05()
    callback(
        f"Oturumluk timer: {timer.get('actual_ms', '—')} ms ({timer.get('mode', 'kapalı')})."
    )
    process = subprocess.Popen([str(path)], cwd=str(path.parent))
    with _ACTIVE_SESSION_LOCK:
        _ACTIVE_SESSION["process"] = process

    process_result = _set_process_performance(process, priority)
    callback(
        "Oyun işlemi başlatıldı; öncelik="
        + ("Yüksek" if priority == "high" else "Normal Üstü")
        + f", güç kısıtlaması kapalı={process_result['power_throttling']}."
    )

    exit_code = process.wait()
    release_timer()
    if previous_plan:
        set_power_plan(previous_plan)
    with _ACTIVE_SESSION_LOCK:
        _ACTIVE_SESSION["process"] = None
        _ACTIVE_SESSION["previous_plan"] = None
    return {
        "exit_code": exit_code,
        "priority": process_result["priority"],
        "power_throttling": process_result["power_throttling"],
        "timer": timer,
        "restored_plan": bool(previous_plan),
    }


def stop_active_session() -> None:
    release_timer()
    with _ACTIVE_SESSION_LOCK:
        previous = _ACTIVE_SESSION.get("previous_plan")
        _ACTIVE_SESSION["stop_requested"] = True
    if previous:
        set_power_plan(str(previous))
    with _ACTIVE_SESSION_LOCK:
        _ACTIVE_SESSION["previous_plan"] = None


def _json_from_ps(script: str, timeout: int = 80):
    result = _powershell(script, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "PowerShell hatası").strip())
    raw = (result.stdout or "").strip()
    if not raw:
        return []
    return json.loads(raw)


def ethernet_backup_exists() -> bool:
    return NETWORK_BACKUP_FILE.exists()


def _network_snapshot() -> list[dict]:
    script = r'''
$ErrorActionPreference = 'Stop'
$items = @()
$adapters = Get-NetAdapter -Physical | Where-Object {
    $_.Status -ne 'Disabled' -and $_.MediaType -eq '802.3'
}
foreach ($a in $adapters) {
    $rss = Get-NetAdapterRss -Name $a.Name -ErrorAction SilentlyContinue
    $pm = Get-NetAdapterPowerManagement -Name $a.Name -ErrorAction SilentlyContinue
    $im = Get-NetAdapterAdvancedProperty -Name $a.Name -RegistryKeyword '*InterruptModeration' -ErrorAction SilentlyContinue | Select-Object -First 1
    $items += [pscustomobject]@{
        Name = $a.Name
        InterfaceDescription = $a.InterfaceDescription
        RssEnabled = if ($null -ne $rss) { [bool]$rss.Enabled } else { $null }
        AllowComputerToTurnOffDevice = if ($null -ne $pm) { [string]$pm.AllowComputerToTurnOffDevice } else { $null }
        WakeOnMagicPacket = if ($null -ne $pm) { [string]$pm.WakeOnMagicPacket } else { $null }
        WakeOnPattern = if ($null -ne $pm) { [string]$pm.WakeOnPattern } else { $null }
        InterruptModerationValue = if ($null -ne $im) { [string]$im.RegistryValue } else { $null }
        InterruptModerationDisplay = if ($null -ne $im) { [string]$im.DisplayValue } else { $null }
    }
}
$items | ConvertTo-Json -Depth 5 -Compress
'''
    data = _json_from_ps(script)
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


def apply_ethernet_low_latency(interrupt_moderation_off: bool, callback) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _network_snapshot()
    if not snapshot:
        raise RuntimeError("Etkin fiziksel Ethernet adaptörü bulunamadı.")
    if not NETWORK_BACKUP_FILE.exists():
        NETWORK_BACKUP_FILE.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    names = [str(item.get("Name", "")) for item in snapshot if item.get("Name")]
    encoded_names = json.dumps(names, ensure_ascii=False)
    im_line = ""
    if interrupt_moderation_off:
        im_line = r'''
    Set-NetAdapterAdvancedProperty -Name $name -RegistryKeyword '*InterruptModeration' -RegistryValue 0 -NoRestart -ErrorAction SilentlyContinue
'''
    script = rf'''
$ErrorActionPreference = 'Continue'
$names = ConvertFrom-Json @'
{encoded_names}
'@
foreach ($name in $names) {{
    Enable-NetAdapterRss -Name $name -NoRestart -ErrorAction SilentlyContinue
    Disable-NetAdapterPowerManagement -Name $name -NoRestart -ErrorAction SilentlyContinue
{im_line}
}}
foreach ($name in $names) {{
    Restart-NetAdapter -Name $name -Confirm:$false -ErrorAction SilentlyContinue
}}
'''
    result = _powershell(script, timeout=120)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Ağ ayarı uygulanamadı").strip())
    callback("Ethernet: RSS açık ve adaptör güç tasarrufu kapalı olarak uygulandı.")
    if interrupt_moderation_off:
        callback("Ethernet: Interrupt Moderation deneysel olarak kapatılmaya çalışıldı.")
    return {"adapters": names, "interrupt_moderation_off": interrupt_moderation_off}


def restore_ethernet(callback) -> dict:
    if not NETWORK_BACKUP_FILE.exists():
        return {"restored": False, "reason": "yedek_yok"}
    items = json.loads(NETWORK_BACKUP_FILE.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise RuntimeError("Ethernet yedeği geçersiz.")

    payload = json.dumps(items, ensure_ascii=False)
    script = rf'''
$ErrorActionPreference = 'Continue'
$items = ConvertFrom-Json @'
{payload}
'@
foreach ($item in $items) {{
    $name = [string]$item.Name
    if ($item.RssEnabled -eq $true) {{ Enable-NetAdapterRss -Name $name -NoRestart -ErrorAction SilentlyContinue }}
    elseif ($item.RssEnabled -eq $false) {{ Disable-NetAdapterRss -Name $name -NoRestart -ErrorAction SilentlyContinue }}

    $params = @{{ Name = $name; NoRestart = $true; ErrorAction = 'SilentlyContinue' }}
    if ($null -ne $item.AllowComputerToTurnOffDevice) {{ $params.AllowComputerToTurnOffDevice = [string]$item.AllowComputerToTurnOffDevice }}
    if ($null -ne $item.WakeOnMagicPacket) {{ $params.WakeOnMagicPacket = [string]$item.WakeOnMagicPacket }}
    if ($null -ne $item.WakeOnPattern) {{ $params.WakeOnPattern = [string]$item.WakeOnPattern }}
    Set-NetAdapterPowerManagement @params

    if ($null -ne $item.InterruptModerationValue -and [string]$item.InterruptModerationValue -ne '') {{
        Set-NetAdapterAdvancedProperty -Name $name -RegistryKeyword '*InterruptModeration' -RegistryValue ([string]$item.InterruptModerationValue) -NoRestart -ErrorAction SilentlyContinue
    }}
}}
foreach ($item in $items) {{ Restart-NetAdapter -Name ([string]$item.Name) -Confirm:$false -ErrorAction SilentlyContinue }}
'''
    result = _powershell(script, timeout=120)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Ethernet geri alınamadı").strip())
    NETWORK_BACKUP_FILE.unlink(missing_ok=True)
    callback("Ethernet adaptörü yedeklenen ayarlarına döndürüldü.")
    return {"restored": True, "adapters": [i.get("Name") for i in items]}


def build_nvidia_game_profile_xml(exe_path: str) -> str:
    path = Path(exe_path)
    profile_name = escape("T-BOOSTER GAME - " + path.stem[:70])
    exe_name = escape(path.name)
    settings = [
        ("Preferred refresh rate", 6600001, 1),
        ("Vertical Sync", 11041231, 138504007),
        ("Texture filtering - Quality", 13510289, 20),
        ("Shader Cache Size", 11306135, 10240),
        ("Virtual Reality pre-rendered frames", 269553971, 0),
        ("Power management mode", 274197361, 1),
        ("Triple buffering", 553505273, 0),
    ]
    blocks = []
    for name, setting_id, value in settings:
        blocks.append(f'''      <ProfileSetting>\n        <SettingNameInfo>{escape(name)}</SettingNameInfo>\n        <SettingID>{setting_id}</SettingID>\n        <SettingValue>{value}</SettingValue>\n        <ValueType>Dword</ValueType>\n      </ProfileSetting>''')
    return (
        '<?xml version="1.0" encoding="utf-16"?>\n'
        '<ArrayOfProfile>\n  <Profile>\n'
        f'    <ProfileName>{profile_name}</ProfileName>\n'
        f'    <Executeables><string>{exe_name}</string></Executeables>\n'
        '    <Settings>\n' + "\n".join(blocks) + '\n    </Settings>\n'
        '  </Profile>\n</ArrayOfProfile>\n'
    )


def import_nvidia_game_profile(inspector_exe: str, exe_path: str, callback) -> dict:
    path = Path(exe_path)
    if not path.is_file() or path.suffix.lower() != ".exe":
        raise RuntimeError("Geçerli oyun EXE dosyası seçilmedi.")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    nip = STATE_DIR / ("TB_GAME_" + re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem) + ".nip")
    nip.write_text(build_nvidia_game_profile_xml(str(path)), encoding="utf-16")
    result = _run([inspector_exe, "-silentImport", str(nip)], timeout=120)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "NVIDIA profil hatası").strip())
    state = {"exe": str(path), "nip": str(nip), "profile": "T-BOOSTER GAME - " + path.stem}
    GAME_PROFILE_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    callback("NVIDIA oyun bazlı performans profili uygulandı: " + path.name)
    return state


def bios_rebar_probe() -> dict:
    script = r'''
$ErrorActionPreference = 'SilentlyContinue'
$fw = 'Bilinmiyor'
try {
    $v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control').PEFirmwareType
    if ($v -eq 2) { $fw = 'UEFI' } elseif ($v -eq 1) { $fw = 'Legacy BIOS' }
} catch {}
$secure = 'Desteklenmiyor/Bilinmiyor'
try { $secure = if (Confirm-SecureBootUEFI) { 'Açık' } else { 'Kapalı' } } catch {}
$diskStyle = 'Bilinmiyor'
try {
    $sys = Get-CimInstance Win32_OperatingSystem
    $drive = $sys.SystemDrive.TrimEnd(':')
    $part = Get-Partition -DriveLetter $drive -ErrorAction Stop
    $diskStyle = (Get-Disk -Number $part.DiskNumber).PartitionStyle.ToString()
} catch {}
$bios = Get-CimInstance Win32_BIOS | Select-Object -First 1
$board = Get-CimInstance Win32_BaseBoard | Select-Object -First 1
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })
[pscustomobject]@{
    Firmware = $fw
    SecureBoot = $secure
    PartitionStyle = $diskStyle
    BiosVendor = [string]$bios.Manufacturer
    BiosVersion = [string]$bios.SMBIOSBIOSVersion
    BiosDate = if ($bios.ReleaseDate) { $bios.ReleaseDate.ToString('yyyy-MM-dd') } else { '' }
    BoardManufacturer = [string]$board.Manufacturer
    BoardProduct = [string]$board.Product
    GPUs = $gpus
} | ConvertTo-Json -Depth 5 -Compress
'''
    data = _json_from_ps(script)
    if not isinstance(data, dict):
        raise RuntimeError("BIOS bilgileri okunamadı.")

    gpu_names = [str(x) for x in (data.get("GPUs") or []) if str(x).strip()]

    def _gpu_support_hint(names):
        combined = " | ".join(names).upper()
        if "NVIDIA" in combined or "GEFORCE" in combined or "RTX" in combined or "GTX" in combined:
            if re.search(r"RTX\s*(30|40|50)", combined):
                return "Desteklenebilir (NVIDIA nesli uygun)"
            if re.search(r"RTX\s*20", combined) or re.search(r"GTX\s*1[0-9]{3}", combined):
                return "Muhtemelen desteklenmiyor / sınırlı"
            return "NVIDIA GPU bulundu — sürücüden doğrulama gerekiyor"
        if "AMD" in combined or "RADEON" in combined or "RX " in combined:
            if re.search(r"RX\s*(6|7)\d{3}", combined):
                return "Desteklenebilir (AMD SAM / Re-Size BAR)"
            return "AMD GPU bulundu — BIOS ve sürücüden doğrulama gerekiyor"
        return "GPU modeli üzerinden net doğrulanamadı"

    rebar = None
    possible_smi = [
        "nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        r"C:\Windows\System32\nvidia-smi.exe",
    ]
    for smi in possible_smi:
        result = _run([smi, "-q"], timeout=25)
        if result.returncode == 0 and (result.stdout or "").strip():
            match = re.search(r"Resizable BAR\s*:\s*([^\r\n]+)", result.stdout or "", re.I)
            if match:
                rebar = match.group(1).strip()
                break

    if not rebar:
        rebar = _gpu_support_hint(gpu_names)

    data["ResizableBAR"] = rebar

    recommendations = []
    if data.get("Firmware") != "UEFI":
        recommendations.append("Re-Size BAR için tam UEFI ve genellikle CSM kapalı olmalı.")
    if str(data.get("PartitionStyle", "")).upper() != "GPT":
        recommendations.append("Sistem diski GPT değil; CSM kapatmadan önce dönüşüm/uyumluluk kontrolü gerekir.")
    if any(k in str(rebar).lower() for k in ["disabled", "no", "off", "kapalı"]):
        recommendations.append("BIOS'ta Above 4G Decoding ve Re-Size BAR/SAM desteğini kontrol et.")
    if "desteklenebilir" in str(rebar).lower() or "doğrulama gerekiyor" in str(rebar).lower():
        recommendations.append("Anakart BIOS'unda Above 4G Decoding + Re-Size BAR/SAM seçeneklerini etkinleştirip en güncel GPU sürücüsünü kullan.")
    if "muhtemelen desteklenmiyor" in str(rebar).lower():
        recommendations.append("Bu GPU neslinde resmi Re-Size BAR desteği sınırlı olabilir; yanlış 'bilinmiyor' yerine destek durumu gösterildi.")
    if not recommendations:
        recommendations.append("UEFI/GPT tarafı uygun görünüyor; Re-Size BAR durumu sürücü tarafından doğrulandıysa ayar genel olarak hazır.")
    recommendations.append("XMP/D.O.C.P./EXPO yalnızca uzun stabilite testi sonrası kullanılmalı.")
    data["Recommendations"] = recommendations
    return data

