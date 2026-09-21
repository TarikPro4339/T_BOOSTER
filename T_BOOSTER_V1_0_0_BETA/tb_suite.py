# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import threading
import urllib.parse
from pathlib import Path

try:
    import winreg  # type: ignore
except Exception:  # pragma: no cover - Windows only
    winreg = None

PROGRAM_DATA = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
STATE_DIR = PROGRAM_DATA / "TBooster" / "V50"
BENCHMARK_DIR = STATE_DIR / "Benchmark"
BENCHMARK_STATE_FILE = STATE_DIR / "benchmark_state.json"
STARTUP_BACKUP_FILE = STATE_DIR / "startup_backup.json"
STARTUP_DISABLED_DIR = STATE_DIR / "StartupDisabled"
REMOVED_APPS_LOG_FILE = PROGRAM_DATA / "TBooster" / "Yedek" / "removed_microsoft_apps.json"
PRESENTMON_RELEASES_URL = "https://github.com/GameTechDev/PresentMon/releases"

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_PRESENTMON_LOCK = threading.Lock()
_ACTIVE_PRESENTMON: subprocess.Popen | None = None


def _run(args: list[str], timeout: int = 60, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(x) for x in args],
        capture_output=True,
        text=True,
        errors="ignore",
        timeout=timeout,
        check=False,
        cwd=cwd,
        creationflags=_CREATE_NO_WINDOW,
    )


def _powershell(script: str, timeout: int = 90) -> subprocess.CompletedProcess:
    return _run(
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


# ---------------------------------------------------------------------------
# PresentMon benchmark
# ---------------------------------------------------------------------------

def find_presentmon(app_dir: str | Path, selected: str = "") -> Path | None:
    candidates: list[Path] = []
    if selected:
        candidates.append(Path(selected))
    app = Path(app_dir)
    candidates.extend(
        [
            app / "PresentMon.exe",
            app / "PresentMon64.exe",
            app / "tools" / "PresentMon.exe",
            STATE_DIR / "PresentMon" / "PresentMon.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Intel" / "PresentMon" / "PresentMon.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Intel" / "PresentMon" / "PresentMon.Console.exe",
        ]
    )
    found = shutil.which("PresentMon.exe") or shutil.which("PresentMon64.exe")
    if found:
        candidates.insert(0, Path(found))
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.suffix.lower() == ".exe":
                return candidate.resolve()
        except Exception:
            continue
    return None


def process_is_running(process_name: str) -> bool:
    if os.name != "nt":
        return False
    safe = process_name.replace("'", "''")
    result = _powershell(
        f"$p=Get-Process -Name '{Path(safe).stem}' -ErrorAction SilentlyContinue; if($p){{exit 0}}else{{exit 3}}",
        timeout=12,
    )
    return result.returncode == 0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percentile / 100.0)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return ordered[low]
    fraction = rank - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def parse_presentmon_csv(csv_path: str | Path) -> dict:
    path = Path(csv_path)
    if not path.is_file():
        raise RuntimeError("PresentMon CSV çıktısı bulunamadı.")

    frame_times: list[float] = []
    application = ""
    time_column = ""
    candidates = (
        "MsBetweenPresents",
        "MsBetweenDisplayChange",
        "DisplayedTime",
        "MsBetweenAppStart",
    )
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        time_column = next((item for item in candidates if item in headers), "")
        if not time_column:
            raise RuntimeError(
                "PresentMon CSV içinde desteklenen frametime sütunu bulunamadı. "
                "V2 metrikli güncel PresentMon sürümünü kullan."
            )
        for row in reader:
            if not application:
                application = str(row.get("Application") or "")
            raw = str(row.get(time_column) or "").strip()
            if not raw or raw.upper() in {"NA", "N/A", "NAN"}:
                continue
            try:
                value = float(raw.replace(",", "."))
            except ValueError:
                continue
            if 0.05 <= value <= 1000.0:
                frame_times.append(value)

    if len(frame_times) < 30:
        raise RuntimeError(
            f"Yeterli kare ölçülemedi ({len(frame_times)}). Oyun çalışırken aynı sahnede tekrar dene."
        )

    mean_ms = statistics.fmean(frame_times)
    median_ms = statistics.median(frame_times)
    p95_ms = _percentile(frame_times, 95.0)
    p99_ms = _percentile(frame_times, 99.0)
    p999_ms = _percentile(frame_times, 99.9)
    avg_fps = 1000.0 / mean_ms if mean_ms > 0 else 0.0
    low_1 = 1000.0 / p99_ms if p99_ms > 0 else 0.0
    low_01 = 1000.0 / p999_ms if p999_ms > 0 else 0.0
    threshold = max(50.0, median_ms * 2.5)
    stutters = sum(1 for value in frame_times if value >= threshold)

    return {
        "application": application or path.stem,
        "csv": str(path),
        "time_column": time_column,
        "frames": len(frame_times),
        "duration_s": sum(frame_times) / 1000.0,
        "average_fps": avg_fps,
        "one_percent_low": low_1,
        "point_one_percent_low": low_01,
        "average_frametime_ms": mean_ms,
        "median_frametime_ms": median_ms,
        "p95_frametime_ms": p95_ms,
        "p99_frametime_ms": p99_ms,
        "stutter_count": stutters,
        "stutter_threshold_ms": threshold,
        "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
    }


def _load_json(path: Path, default):
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def benchmark_state() -> dict:
    data = _load_json(BENCHMARK_STATE_FILE, {})
    return data if isinstance(data, dict) else {}


def save_benchmark_result(mode: str, result: dict) -> None:
    data = benchmark_state()
    data[mode] = result
    _save_json(BENCHMARK_STATE_FILE, data)


def stop_presentmon_capture() -> None:
    global _ACTIVE_PRESENTMON
    with _PRESENTMON_LOCK:
        proc = _ACTIVE_PRESENTMON
        _ACTIVE_PRESENTMON = None
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def capture_presentmon(
    presentmon_exe: str,
    process_name: str,
    duration_seconds: int,
    mode: str,
    callback,
    delay_seconds: int = 5,
) -> dict:
    global _ACTIVE_PRESENTMON
    exe = Path(presentmon_exe)
    if not exe.is_file():
        raise RuntimeError("PresentMon.exe bulunamadı. Önce resmî PresentMon dosyasını seç.")
    process_name = Path(process_name).name
    duration = max(10, min(int(duration_seconds), 180))
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output = BENCHMARK_DIR / f"{mode}_{Path(process_name).stem}_{stamp}.csv"

    callback(
        f"PresentMon {mode} testi: {delay_seconds} saniye içinde oyuna dön; "
        f"ölçüm {duration} saniye sürecek."
    )
    args = [
        str(exe),
        "--process_name",
        process_name,
        "--output_file",
        str(output),
        "--delay",
        str(delay_seconds),
        "--timed",
        str(duration),
        "--terminate_after_timed",
        "--stop_existing_session",
        "--exclude_dropped",
        "--v2_metrics",
        "--no_console_stats",
    ]
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="ignore",
        creationflags=_CREATE_NO_WINDOW,
    )
    with _PRESENTMON_LOCK:
        _ACTIVE_PRESENTMON = proc
    try:
        stdout, stderr = proc.communicate(timeout=duration + delay_seconds + 45)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise RuntimeError("PresentMon testi zaman aşımına uğradı.")
    finally:
        with _PRESENTMON_LOCK:
            if _ACTIVE_PRESENTMON is proc:
                _ACTIVE_PRESENTMON = None

    if proc.returncode not in (0, None) and not output.is_file():
        detail = (stderr or stdout or "Bilinmeyen PresentMon hatası").strip()
        raise RuntimeError("PresentMon testi tamamlanamadı: " + detail[-700:])

    if not output.is_file():
        # Some PresentMon builds append a suffix even with output_file.
        matches = sorted(
            BENCHMARK_DIR.glob(f"{mode}_{Path(process_name).stem}_{stamp}*.csv"),
            key=lambda item: item.stat().st_mtime_ns,
            reverse=True,
        )
        if matches:
            output = matches[0]
    result = parse_presentmon_csv(output)
    result.update({"mode": mode, "duration_requested_s": duration, "process_name": process_name})
    save_benchmark_result(mode, result)
    callback(
        f"{mode.title()} FPS testi tamamlandı: ortalama {result['average_fps']:.1f} FPS, "
        f"1% Low {result['one_percent_low']:.1f}."
    )
    return result


def _change(before: float, after: float, higher_is_better: bool = True) -> float:
    if before == 0:
        return 0.0
    delta = (after - before) / before * 100.0
    return delta if higher_is_better else -delta


def create_benchmark_report() -> dict:
    state = benchmark_state()
    before = state.get("before")
    after = state.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise RuntimeError("Önce ve Sonra testlerinin ikisi de tamamlanmadı.")

    comparison = {
        "average_fps_pct": _change(float(before["average_fps"]), float(after["average_fps"])),
        "one_percent_low_pct": _change(float(before["one_percent_low"]), float(after["one_percent_low"])),
        "point_one_percent_low_pct": _change(float(before["point_one_percent_low"]), float(after["point_one_percent_low"])),
        "frametime_pct": _change(float(before["average_frametime_ms"]), float(after["average_frametime_ms"]), False),
        "stutter_delta": int(after["stutter_count"]) - int(before["stutter_count"]),
    }
    report = {"before": before, "after": after, "comparison": comparison}
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    json_path = BENCHMARK_DIR / "TB_Benchmark_Comparison.json"
    html_path = BENCHMARK_DIR / "TB_Benchmark_Raporu.html"
    _save_json(json_path, report)

    def metric(title: str, key: str, suffix: str = "", decimals: int = 1) -> str:
        b = float(before[key])
        a = float(after[key])
        return (
            f"<div class='metric'><div class='name'>{html.escape(title)}</div>"
            f"<div class='values'><span class='before'>{b:.{decimals}f}{suffix}</span>"
            f"<span class='arrow'>→</span><span class='after'>{a:.{decimals}f}{suffix}</span></div></div>"
        )

    css = """
    body{font-family:Segoe UI,Arial;background:#070a12;color:#f8fbff;margin:0;padding:32px}
    .wrap{max-width:920px;margin:auto}.hero{padding:28px;border:1px solid #674cff;border-radius:22px;background:linear-gradient(135deg,#11182b,#1a1230)}
    h1{margin:0;color:#b994ff}.sub{color:#a9b9d6;margin-top:8px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:20px}
    .metric{background:#121a2a;border:1px solid #2f4265;border-radius:16px;padding:16px}.name{color:#a9b9d6;font-size:14px}.values{font-size:24px;font-weight:800;margin-top:8px}
    .before{color:#ff7394}.after{color:#58e5ad}.arrow{margin:0 12px;color:#ffd26d}.gain{margin-top:18px;font-size:30px;font-weight:900;color:#58e5ad}
    .note{margin-top:18px;color:#a9b9d6;font-size:13px}.footer{margin-top:24px;color:#b994ff;font-weight:700}
    """
    gain = comparison["average_fps_pct"]
    body = f"""<!doctype html><html><head><meta charset='utf-8'><title>T-Booster Benchmark Raporu</title><style>{css}</style></head>
    <body><div class='wrap'><div class='hero'><h1>T-BOOSTER — ÖNCE / SONRA TESTİ</h1><div class='sub'>🔰 T-BOOSTER RAPORU</div>
    <div class='sub'>{html.escape(str(after.get('application') or before.get('application') or 'Oyun'))}</div>
    <div class='gain'>Ortalama FPS farkı: {gain:+.1f}%</div></div>
    <div class='grid'>
    {metric('Ortalama FPS','average_fps')}
    {metric('1% Low','one_percent_low')}
    {metric('0.1% Low','point_one_percent_low')}
    {metric('Ortalama Frametime','average_frametime_ms',' ms',2)}
    {metric('Takılma Sayısı','stutter_count','',0)}
    {metric('Kare Sayısı','frames','',0)}
    </div><div class='note'>Sonuçların güvenilir olması için iki testte aynı oyun, çözünürlük, grafik ayarı ve sahne kullanılmalıdır.</div>
    <div class='footer'>🔰 T-BOOSTER v1.0.0 (Beta) • Yapımcı: TarikPro43391</div></div></body></html>"""
    html_path.write_text(body, encoding="utf-8")
    return {"report": report, "html": str(html_path), "json": str(json_path)}


# ---------------------------------------------------------------------------
# Startup assistant
# ---------------------------------------------------------------------------

REGISTRY_STARTUP_LOCATIONS = (
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "Kullanıcı"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run", "Tüm kullanıcılar"),
    ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Tüm kullanıcılar (32-bit)"),
)

PROTECTED_TOKENS = (
    "securityhealth", "windows defender", "defender", "antivirus", "antimalware",
    "realtek", "audio", "nahimic", "synaptics", "touchpad", "keyboard", "mouse",
    "nvidia", "amd", "intel graphics", "radeon", "bluetooth", "wlan", "wireless",
    "t-booster", "tbooster",
)


def _startup_backup_data() -> dict:
    data = _load_json(STARTUP_BACKUP_FILE, {"entries": {}})
    if not isinstance(data, dict):
        data = {"entries": {}}
    if not isinstance(data.get("entries"), dict):
        data["entries"] = {}
    return data


def _startup_id(kind: str, scope: str, location: str, name: str) -> str:
    return "|".join((kind, scope, location, name)).lower()


def _publisher_guess(name: str, command: str) -> str:
    text = f"{name} {command}".lower()
    mapping = (
        ("microsoft", "Microsoft"), ("onedrive", "Microsoft"), ("teams", "Microsoft"),
        ("nvidia", "NVIDIA"), ("amd", "AMD"), ("radeon", "AMD"),
        ("intel", "Intel"), ("realtek", "Realtek"), ("discord", "Discord"),
        ("steam", "Valve"), ("epic", "Epic Games"), ("adobe", "Adobe"),
        ("logitech", "Logitech"), ("razer", "Razer"), ("corsair", "Corsair"),
    )
    for token, publisher in mapping:
        if token in text:
            return publisher
    return "Bilinmiyor"


def _startup_advice(name: str, command: str) -> tuple[str, str, bool]:
    text = f"{name} {command}".lower()
    protected = any(token in text for token in PROTECTED_TOKENS)
    if protected:
        return "Sistem / sürücü — dokunma", "Sistem", True
    if any(token in text for token in ("updater", "update", "launcher", "adobe", "teams", "discord", "spotify", "skype")):
        return "Kullanmıyorsan kapatılabilir", "Orta", False
    if any(token in text for token in ("onedrive", "dropbox", "google drive", "steam", "epic")):
        return "Kullanımına göre karar ver", "Orta", False
    return "Kontrol ederek kapat", "Bilinmiyor", False


def _root_from_name(name: str):
    if winreg is None:
        raise RuntimeError("Başlangıç yönetimi yalnızca Windows'ta kullanılabilir.")
    return winreg.HKEY_CURRENT_USER if name == "HKCU" else winreg.HKEY_LOCAL_MACHINE


def list_startup_entries() -> list[dict]:
    if os.name != "nt" or winreg is None:
        return []
    entries: list[dict] = []
    backup = _startup_backup_data().get("entries", {})

    for root_name, key_path, scope in REGISTRY_STARTUP_LOCATIONS:
        try:
            with winreg.OpenKey(_root_from_name(root_name), key_path, 0, winreg.KEY_READ) as key:
                index = 0
                while True:
                    try:
                        name, value, value_type = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    index += 1
                    command = str(value)
                    advice, impact, protected = _startup_advice(name, command)
                    entry_id = _startup_id("registry", root_name, key_path, name)
                    entries.append({
                        "id": entry_id, "name": name, "command": command, "scope": scope,
                        "kind": "Registry", "enabled": True, "publisher": _publisher_guess(name, command),
                        "impact": impact, "recommendation": advice, "protected": protected,
                        "root": root_name, "path": key_path, "value_type": int(value_type),
                    })
        except OSError:
            pass

    startup_folders = (
        (Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup", "Kullanıcı"),
        (Path(os.environ.get("PROGRAMDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\StartUp", "Tüm kullanıcılar"),
    )
    for folder, scope in startup_folders:
        if not folder.is_dir():
            continue
        for item in sorted(folder.iterdir()):
            if not item.is_file():
                continue
            command = str(item)
            advice, impact, protected = _startup_advice(item.stem, command)
            entry_id = _startup_id("file", scope, str(folder), item.name)
            entries.append({
                "id": entry_id, "name": item.stem, "command": command, "scope": scope,
                "kind": "Başlangıç klasörü", "enabled": True,
                "publisher": _publisher_guess(item.stem, command), "impact": impact,
                "recommendation": advice, "protected": protected, "file": str(item),
            })

    current_ids = {item["id"] for item in entries}
    for entry_id, item in backup.items():
        if not isinstance(item, dict) or item.get("restored") or entry_id in current_ids:
            continue
        restored_item = dict(item)
        restored_item.update({"id": entry_id, "enabled": False})
        entries.append(restored_item)

    entries.sort(key=lambda item: (not bool(item.get("enabled")), str(item.get("name", "")).lower()))
    return entries


def disable_startup_entries(entry_ids: list[str]) -> dict:
    all_entries = {item["id"]: item for item in list_startup_entries()}
    backup = _startup_backup_data()
    changed = []
    skipped = []
    for entry_id in entry_ids:
        item = all_entries.get(entry_id)
        if not item or not item.get("enabled"):
            skipped.append(entry_id)
            continue
        if item.get("protected"):
            skipped.append(item.get("name", entry_id))
            continue
        if item.get("kind") == "Registry":
            root_name = str(item["root"])
            key_path = str(item["path"])
            name = str(item["name"])
            with winreg.OpenKey(_root_from_name(root_name), key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
                value, value_type = winreg.QueryValueEx(key, name)
                winreg.DeleteValue(key, name)
            saved = dict(item)
            saved.update({"value": value, "value_type": int(value_type), "restored": False, "disabled_at": dt.datetime.now().isoformat(timespec="seconds")})
        else:
            source = Path(str(item["file"]))
            target_dir = STARTUP_DISABLED_DIR / re.sub(r"[^A-Za-z0-9_.-]+", "_", str(item["scope"]))
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source.name
            if target.exists():
                target = target_dir / f"{source.stem}_{int(dt.datetime.now().timestamp())}{source.suffix}"
            shutil.move(str(source), str(target))
            saved = dict(item)
            saved.update({"backup_file": str(target), "restored": False, "disabled_at": dt.datetime.now().isoformat(timespec="seconds")})
        backup["entries"][entry_id] = saved
        changed.append(item.get("name", entry_id))
    _save_json(STARTUP_BACKUP_FILE, backup)
    return {"changed": changed, "skipped": skipped}


def restore_startup_entries(entry_ids: list[str]) -> dict:
    backup = _startup_backup_data()
    changed = []
    failed = []
    for entry_id in entry_ids:
        item = backup.get("entries", {}).get(entry_id)
        if not isinstance(item, dict) or item.get("restored"):
            continue
        try:
            if item.get("kind") == "Registry":
                root_name = str(item["root"])
                key_path = str(item["path"])
                with winreg.CreateKeyEx(_root_from_name(root_name), key_path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, str(item["name"]), 0, int(item["value_type"]), item.get("value"))
            else:
                target = Path(str(item["file"]))
                source = Path(str(item["backup_file"]))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
            item["restored"] = True
            item["restored_at"] = dt.datetime.now().isoformat(timespec="seconds")
            changed.append(item.get("name", entry_id))
        except Exception as exc:
            failed.append({"name": item.get("name", entry_id), "error": str(exc)})
    _save_json(STARTUP_BACKUP_FILE, backup)
    return {"changed": changed, "failed": failed}


# ---------------------------------------------------------------------------
# Backup center / restore point
# ---------------------------------------------------------------------------

def create_restore_point(description: str = "T-Booster Öncesi") -> dict:
    safe = re.sub(r"[^A-Za-z0-9ÇĞİÖŞÜçğıöşü ._-]+", "", description)[:80]
    script = (
        "$ErrorActionPreference='Stop'; "
        f"Checkpoint-Computer -Description '{safe.replace("'", "''")}' -RestorePointType 'MODIFY_SETTINGS'; "
        "Write-Output 'OK'"
    )
    result = _powershell(script, timeout=240)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Geri yükleme noktası oluşturulamadı.").strip()
        raise RuntimeError(detail)
    return {"created": True, "description": safe, "output": (result.stdout or "").strip()}


def backup_status(paths: dict[str, str]) -> list[dict]:
    rows = []
    for label, raw in paths.items():
        path = Path(raw)
        exists = path.exists()
        modified = "—"
        size = 0
        if exists:
            try:
                stat = path.stat()
                modified = dt.datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M")
                size = stat.st_size
            except Exception:
                pass
        rows.append({"label": label, "path": str(path), "exists": exists, "modified": modified, "size": size})
    return rows


def export_backup_report(paths: dict[str, str]) -> str:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "backups": backup_status(paths),
        "startup_entries": list_startup_entries(),
        "benchmark": benchmark_state(),
        "removed_apps": _load_json(REMOVED_APPS_LOG_FILE, {}),
    }
    output = STATE_DIR / "TB_Yedek_Raporu.json"
    _save_json(output, data)
    return str(output)


# ---------------------------------------------------------------------------
# Removed Microsoft apps recovery
# ---------------------------------------------------------------------------

def load_removed_apps() -> list[dict]:
    data = _load_json(REMOVED_APPS_LOG_FILE, {})
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("removed", []) or data.get("history", [])
    else:
        rows = []
    result = []
    seen = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("Name") or "")
        label = str(item.get("label") or item.get("Label") or name)
        if not name or name in seen:
            continue
        seen.add(name)
        fallback_date = data.get("updated_at", "") if isinstance(data, dict) else ""
        result.append({
            "name": name,
            "label": label,
            "removed_at": str(
                item.get("removed_at")
                or item.get("RemovedAt")
                or fallback_date
            ),
        })
    return result


def _save_removed_apps(items: list[dict]) -> None:
    _save_json(
        REMOVED_APPS_LOG_FILE,
        {"updated_at": dt.datetime.now().isoformat(timespec="seconds"), "removed": items},
    )


def store_search_url(label: str) -> str:
    return "ms-windows-store://search/?query=" + urllib.parse.quote(label)


def reinstall_removed_app(package_name: str, label: str, callback) -> dict:
    safe_name = package_name.replace("'", "''")
    callback("Yeniden kayıt deneniyor: " + label)
    script = rf'''
$ErrorActionPreference = 'Stop'
$pkg = Get-AppxPackage -AllUsers -Name '{safe_name}' |
    Sort-Object Version -Descending |
    Select-Object -First 1
if ($null -eq $pkg) {{ exit 3 }}
$manifest = Join-Path $pkg.InstallLocation 'AppxManifest.xml'
if (-not (Test-Path $manifest)) {{ exit 4 }}
Add-AppxPackage -DisableDevelopmentMode -Register $manifest -ErrorAction Stop
Write-Output 'RESTORED'
'''
    result = _powershell(script, timeout=180)
    restored = result.returncode == 0 and "RESTORED" in (result.stdout or "")
    if restored:
        items = [item for item in load_removed_apps() if item.get("name") != package_name]
        _save_removed_apps(items)
        callback("Yeniden kuruldu/kaydedildi: " + label)
        return {"restored": True, "name": package_name, "label": label}
    callback("Yerel paket bulunamadı; Microsoft Store sayfası gerekli: " + label)
    return {
        "restored": False,
        "needs_store": True,
        "name": package_name,
        "label": label,
        "store_url": store_search_url(label),
        "error": (result.stderr or result.stdout or "Yerel Appx paketi bulunamadı.").strip(),
    }
