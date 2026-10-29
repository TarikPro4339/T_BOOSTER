# -*- coding: utf-8 -*-
"""T-BOOSTER Araç Kutusu özellikleri (v1.0.8) — Yapımcı: TarikPro43391

Bu modül arayüzden bağımsızdır (yalnızca standart kütüphane). İçerdikleri:
  - Geçici dosya temizleyici, sistem sağlık puanı
  - DNS testi, internet hız testi
  - Büyük dosya bulucu, yinelenen dosya bulucu (ikisi de yalnızca listeler)
  - Arka plan uygulama avcısı, açık ağ bağlantıları (netstat)
  - Kayıtlı Wi-Fi şifreleri, geri yükleme noktası, güç planları, pil raporu
  - Dosya karma (hash) hesaplayıcı, sistem dosyası denetleyici (SFC),
    hosts dosyası denetimi

Not: Başlangıç uygulamalarını açıp kapatmak için ayrı bir modül yazılmadı —
T-Booster'da bu iş zaten tb_suite.py (v50tools) içindeki, Başlangıç klasörünü
de kapsayan ve güvenli yedekleme yapan asistan tarafından yapılıyor; Araç
Kutusu'ndaki "6 • Başlangıç Uygulamaları" kartı o asistanı açar.
"""
from __future__ import annotations

import csv
import hashlib
import heapq
import io
import ipaddress
import os
import random
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def fmt_size(num_bytes: float) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ---------------------------------------------------------------------------
# 1) Geçici dosya temizleyici
# ---------------------------------------------------------------------------
_SAFE_DIR_NAMES = {"temp", "tmp", "crashdumps", "reportqueue"}


def temp_targets() -> list[dict]:
    env = os.environ
    local = env.get("LOCALAPPDATA", "")
    windir = env.get("WINDIR", env.get("SystemRoot", r"C:\Windows"))
    program_data = env.get("PROGRAMDATA", r"C:\ProgramData")
    user_temp = env.get("TEMP") or env.get("TMP") or ""
    targets = [
        {"key": "user_temp", "label": "Kullanıcı geçici dosyaları", "paths": [user_temp] if user_temp else [],
         "note": "Uygulamaların bıraktığı %TEMP% dosyaları"},
        {"key": "win_temp", "label": "Windows geçici dosyaları", "paths": [str(Path(windir) / "Temp")],
         "note": "C:\\Windows\\Temp"},
        {"key": "crash", "label": "Çökme dökümleri", "paths": [str(Path(local) / "CrashDumps")] if local else [],
         "note": "Eski uygulama çökme kayıtları"},
        {"key": "wer", "label": "Windows hata raporları", "paths": [
            str(Path(program_data) / "Microsoft" / "Windows" / "WER" / "ReportQueue"),
            str(Path(local) / "Microsoft" / "Windows" / "WER" / "ReportQueue") if local else "",
        ], "note": "Gönderilmeyi bekleyen hata raporları"},
    ]
    for target in targets:
        target["paths"] = [p for p in target["paths"] if p]
    return targets


def _is_reparse(entry_or_path) -> bool:
    try:
        if hasattr(entry_or_path, "is_symlink"):
            if entry_or_path.is_symlink():
                return True
            if getattr(entry_or_path, "is_junction", None) and entry_or_path.is_junction():
                return True
            attrs = getattr(entry_or_path.stat(follow_symlinks=False), "st_file_attributes", 0)
        else:
            if os.path.islink(entry_or_path):
                return True
            attrs = getattr(os.lstat(entry_or_path), "st_file_attributes", 0)
        return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except OSError:
        return True


def _assert_safe_dir(path: str | Path) -> Path:
    p = Path(path)
    if p.name.lower() not in _SAFE_DIR_NAMES:
        raise ValueError(f"Güvenli olmayan temizlik klasörü reddedildi: {p}")
    if len(p.parts) < 3 and os.name == "nt":
        raise ValueError(f"Kök klasör reddedildi: {p}")
    return p


def scan_paths(paths: list[str], min_age_days: float = 0.0) -> tuple[int, int]:
    """Toplam bayt ve dosya sayısı. Hiçbir şey silmez."""
    cutoff = time.time() - min_age_days * 86400
    total = count = 0
    for raw in paths:
        try:
            root = _assert_safe_dir(raw)
        except ValueError:
            continue
        if not root.is_dir():
            continue
        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            dirs[:] = [d for d in dirs if not _is_reparse(os.path.join(current, d))]
            for name in files:
                full = os.path.join(current, name)
                try:
                    st = os.lstat(full)
                    if min_age_days and st.st_mtime > cutoff:
                        continue
                    total += st.st_size
                    count += 1
                except OSError:
                    continue
    return total, count


def clean_paths(paths: list[str], min_age_days: float = 1.0) -> dict:
    """Klasör içindeki eski dosyaları siler; kullanımdaki dosyaları atlar."""
    cutoff = time.time() - min_age_days * 86400
    freed = deleted = skipped = 0
    for raw in paths:
        try:
            root = _assert_safe_dir(raw)
        except ValueError:
            continue
        if not root.is_dir():
            continue
        for current, dirs, files in os.walk(root, topdown=False, followlinks=False):
            for name in files:
                full = os.path.join(current, name)
                try:
                    st = os.lstat(full)
                    if st.st_mtime > cutoff:
                        skipped += 1
                        continue
                    os.chmod(full, 0o666)
                    os.remove(full)
                    freed += st.st_size
                    deleted += 1
                except OSError:
                    skipped += 1
            for name in dirs:
                full = os.path.join(current, name)
                if _is_reparse(full):
                    continue
                try:
                    os.rmdir(full)  # yalnızca boşsa silinir
                except OSError:
                    pass
    return {"freed": freed, "deleted": deleted, "skipped": skipped}


def empty_recycle_bin() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)
        return result in (0, -2147418113)  # S_OK / zaten boş
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 2) DNS & ağ
# ---------------------------------------------------------------------------
DNS_SERVERS = [
    ("Cloudflare", "1.1.1.1"),
    ("Google", "8.8.8.8"),
    ("Quad9", "9.9.9.9"),
    ("OpenDNS", "208.67.222.222"),
    ("AdGuard", "94.140.14.14"),
]
DNS_TEST_DOMAINS = ["www.google.com", "www.cloudflare.com", "www.microsoft.com", "www.youtube.com"]


def build_dns_query(domain: str, query_id: int | None = None) -> tuple[int, bytes]:
    qid = random.randint(0, 0xFFFF) if query_id is None else query_id
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)  # RD=1, 1 soru
    labels = b"".join(bytes([len(p)]) + p.encode("ascii") for p in domain.strip(".").split("."))
    question = labels + b"\x00" + struct.pack(">HH", 1, 1)  # A / IN
    return qid, header + question


def dns_response_matches(data: bytes, qid: int) -> bool:
    if len(data) < 12:
        return False
    rid, flags = struct.unpack(">HH", data[:4])
    return rid == qid and bool(flags & 0x8000)  # QR=1


def dns_query_time(server: str, domain: str, timeout: float = 1.5, port: int = 53) -> float | None:
    qid, packet = build_dns_query(domain)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        start = time.perf_counter()
        sock.sendto(packet, (server, port))
        data, _addr = sock.recvfrom(2048)
        elapsed = (time.perf_counter() - start) * 1000.0
        return elapsed if dns_response_matches(data, qid) else None
    except (OSError, socket.timeout):
        return None
    finally:
        sock.close()


def dns_benchmark(servers=None, domains=None, rounds: int = 2, timeout: float = 1.5, progress=None, port: int = 53) -> list[dict]:
    servers = servers or DNS_SERVERS
    domains = domains or DNS_TEST_DOMAINS
    results = []
    for index, (name, ip) in enumerate(servers):
        times: list[float] = []
        total = 0
        for _ in range(rounds):
            for domain in domains:
                total += 1
                value = dns_query_time(ip, domain, timeout, port)
                if value is not None:
                    times.append(value)
        results.append({
            "name": name, "ip": ip, "ok": len(times), "total": total,
            "avg_ms": (sum(times) / len(times)) if times else None,
            "min_ms": min(times) if times else None,
        })
        if progress:
            progress(index + 1, len(servers), name)
    results.sort(key=lambda r: (r["avg_ms"] is None, r["avg_ms"] if r["avg_ms"] is not None else 0))
    return results


def flush_dns() -> tuple[bool, str]:
    if os.name != "nt":
        return False, "DNS önbelleği yalnızca Windows'ta temizlenir."
    try:
        proc = subprocess.run(["ipconfig.exe", "/flushdns"], capture_output=True, text=True, timeout=15,
                              errors="ignore", creationflags=_CREATE_NO_WINDOW)
        return proc.returncode == 0, (proc.stdout or proc.stderr or "").strip()
    except Exception as exc:
        return False, str(exc)


def tcp_latency(host: str = "1.1.1.1", port: int = 443, count: int = 4, timeout: float = 2.0) -> list[float]:
    values = []
    for _ in range(count):
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                values.append((time.perf_counter() - start) * 1000.0)
        except OSError:
            pass
    return values


# ---------------------------------------------------------------------------
# 3) Sistem sağlık puanı
# ---------------------------------------------------------------------------
def memory_used_percent() -> float | None:
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return float(stat.dwMemoryLoad)
        info = {}
        with open("/proc/meminfo", encoding="ascii") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0])
        return 100.0 * (1 - info["MemAvailable"] / info["MemTotal"])
    except Exception:
        return None


def uptime_hours() -> float | None:
    try:
        if os.name == "nt":
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.GetTickCount64.restype = ctypes.c_ulonglong
            return kernel.GetTickCount64() / 3_600_000.0
        with open("/proc/uptime", encoding="ascii") as handle:
            return float(handle.read().split()[0]) / 3600.0
    except Exception:
        return None


def startup_entry_count() -> int | None:
    if os.name != "nt":
        return None
    try:
        import winreg
        total = 0
        for hive, path in ((winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                           (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run")):
            try:
                with winreg.OpenKey(hive, path) as key:
                    total += winreg.QueryInfoKey(key)[1]
            except OSError:
                continue
        return total
    except Exception:
        return None


def system_drive_free() -> tuple[float, float] | None:
    try:
        root = (os.environ.get("SystemDrive", "C:") + "\\") if os.name == "nt" else "/"
        usage = shutil.disk_usage(root)
        return 100.0 * usage.free / usage.total, usage.free / (1024 ** 3)
    except Exception:
        return None


def collect_health_inputs(temp_bytes: int | None = None) -> dict:
    disk = system_drive_free()
    return {
        "ram_used_pct": memory_used_percent(),
        "disk_free_pct": disk[0] if disk else None,
        "disk_free_gb": disk[1] if disk else None,
        "uptime_h": uptime_hours(),
        "startup_count": startup_entry_count(),
        "temp_mb": (temp_bytes / (1024 * 1024)) if temp_bytes is not None else None,
    }


def _curve(value: float, points: list[tuple[float, float]]) -> float:
    """(x, 0..1) noktaları arasında doğrusal geçiş."""
    if value <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / max(1e-9, x1 - x0)
    return points[-1][1]


def compute_health(inputs: dict) -> dict:
    items = []

    def add(key, title, weight, ratio, detail, tip):
        level = "ok" if ratio >= 0.75 else ("warning" if ratio >= 0.4 else "bad")
        items.append({"key": key, "title": title, "weight": weight, "ratio": ratio, "level": level,
                      "detail": detail, "tip": tip if level != "ok" else ""})

    ram = inputs.get("ram_used_pct")
    if ram is not None:
        add("ram", "RAM kullanımı", 25, _curve(ram, [(60, 1.0), (80, 0.6), (92, 0.2), (100, 0.0)]),
            f"%{ram:.0f} dolu", "Arka plan uygulamalarını kapat (Uygulama Avcısı'nı kullan).")
    disk = inputs.get("disk_free_pct")
    if disk is not None:
        gb = inputs.get("disk_free_gb")
        extra = f" ({gb:.0f} GB)" if gb is not None else ""
        add("disk", "Sistem diski boş alanı", 25, _curve(disk, [(3, 0.05), (8, 0.35), (15, 0.7), (25, 1.0)]),
            f"%{disk:.0f} boş{extra}", "Geçici dosyaları temizle, Büyük Dosya Bulucu ile yer aç.")
    uptime = inputs.get("uptime_h")
    if uptime is not None:
        add("uptime", "Yeniden başlatma", 15, _curve(uptime, [(48, 1.0), (168, 0.6), (336, 0.25), (720, 0.0)]),
            f"{uptime / 24:.1f} gündür açık", "Bilgisayarı yeniden başlat; bellek sızıntıları temizlenir.")
    startup = inputs.get("startup_count")
    if startup is not None:
        add("startup", "Başlangıç uygulamaları", 20, _curve(startup, [(8, 1.0), (15, 0.6), (25, 0.25), (40, 0.0)]),
            f"{startup} kayıt", "Gereksiz başlangıç uygulamalarını kapat.")
    temp_mb = inputs.get("temp_mb")
    if temp_mb is not None:
        add("temp", "Geçici dosyalar", 15, _curve(temp_mb, [(500, 1.0), (2000, 0.6), (5000, 0.25), (10000, 0.0)]),
            fmt_size(temp_mb * 1024 * 1024), "Geçici Dosya Temizleyici'yi çalıştır.")

    total_weight = sum(i["weight"] for i in items)
    score = round(100 * sum(i["weight"] * i["ratio"] for i in items) / total_weight) if total_weight else 0
    grade = "Mükemmel" if score >= 90 else "İyi" if score >= 75 else "Orta" if score >= 55 else "Zayıf"
    return {"score": int(score), "grade": grade, "items": items}


# ---------------------------------------------------------------------------
# 4) Büyük dosya bulucu (yalnızca okuma)
# ---------------------------------------------------------------------------
_SKIP_DIRS = {"$recycle.bin", "system volume information", "windows", "$windows.~bt", "$windows.~ws"}


def find_large_files(root: str, top_n: int = 25, min_bytes: int = 50 * 1024 * 1024, cancel=None,
                     progress=None, max_seconds: float = 240.0) -> dict:
    heap: list[tuple[int, str]] = []
    scanned = 0
    started = time.time()
    timed_out = False
    stack = [str(root)]
    while stack:
        if cancel and cancel():
            break
        if time.time() - started > max_seconds:
            timed_out = True
            break
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink() or (getattr(entry, "is_junction", None) and entry.is_junction()):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.lower() not in _SKIP_DIRS:
                                stack.append(entry.path)
                            continue
                        if entry.is_file(follow_symlinks=False):
                            scanned += 1
                            size = entry.stat(follow_symlinks=False).st_size
                            if size >= min_bytes:
                                if len(heap) < top_n:
                                    heapq.heappush(heap, (size, entry.path))
                                elif size > heap[0][0]:
                                    heapq.heapreplace(heap, (size, entry.path))
                    except OSError:
                        continue
        except OSError:
            continue
        if progress and scanned and scanned % 3000 < 50:
            progress(scanned, current)
    files = sorted(heap, reverse=True)
    return {"files": [{"size": s, "path": p} for s, p in files], "scanned": scanned, "timed_out": timed_out}


# ---------------------------------------------------------------------------
# 5) Arka plan uygulama avcısı
# ---------------------------------------------------------------------------
PROTECTED_PROCESSES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "winlogon.exe", "svchost.exe", "dwm.exe", "explorer.exe", "fontdrvhost.exe", "audiodg.exe",
    "memory compression", "memcompression", "secure system", "ctfmon.exe", "sihost.exe", "taskhostw.exe",
    "runtimebroker.exe", "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "textinputhost.exe", "conhost.exe", "wudfhost.exe", "spoolsv.exe", "msmpeng.exe", "securityhealthservice.exe",
    "securityhealthsystray.exe", "lsaiso.exe", "dllhost.exe", "wmiprvse.exe", "tasklist.exe", "taskmgr.exe",
}

KNOWN_BACKGROUND_APPS = {
    "chrome.exe": "Tarayıcı — oyundan önce kapat",
    "msedge.exe": "Tarayıcı — oyundan önce kapat",
    "firefox.exe": "Tarayıcı — oyundan önce kapat",
    "opera.exe": "Tarayıcı — oyundan önce kapat",
    "discord.exe": "Sohbet uygulaması — RAM kullanır",
    "spotify.exe": "Müzik — arka planda çalışır",
    "onedrive.exe": "Bulut eşitleme",
    "teams.exe": "Toplantı uygulaması",
    "ms-teams.exe": "Toplantı uygulaması",
    "steamwebhelper.exe": "Steam arayüzü",
    "epicgameslauncher.exe": "Oyun başlatıcı",
    "battle.net.exe": "Oyun başlatıcı",
    "skype.exe": "Görüşme uygulaması",
    "whatsapp.exe": "Mesajlaşma",
    "telegram.exe": "Mesajlaşma",
    "adobeupdateservice.exe": "Güncelleme servisi",
    "googledrivefs.exe": "Bulut eşitleme",
    "dropbox.exe": "Bulut eşitleme",
}


def parse_tasklist_csv(text: str) -> list[dict]:
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 5:
            continue
        name, pid_text, mem_text = row[0], row[1], row[-1]
        digits = re.sub(r"\D", "", mem_text)
        if not pid_text.strip().isdigit() or not digits:
            continue
        rows.append({"name": name, "pid": int(pid_text), "mem_mb": int(digits) / 1024.0})
    return rows


def is_protected_process(name: str, pid: int) -> bool:
    lowered = name.strip().lower()
    return lowered in PROTECTED_PROCESSES or pid in (0, 4, os.getpid()) or "t-booster" in lowered


def list_processes(limit: int = 40) -> list[dict]:
    if os.name != "nt":
        return []
    proc = subprocess.run(["tasklist.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=20,
                          errors="ignore", creationflags=_CREATE_NO_WINDOW)
    rows = parse_tasklist_csv(proc.stdout or "")
    for row in rows:
        row["protected"] = is_protected_process(row["name"], row["pid"])
        row["hint"] = KNOWN_BACKGROUND_APPS.get(row["name"].lower(), "")
    rows.sort(key=lambda r: r["mem_mb"], reverse=True)
    return rows[:limit]


def list_wifi_profiles() -> list[str]:
    if os.name != "nt":
        return []
    proc = subprocess.run(["netsh.exe", "wlan", "show", "profiles"], capture_output=True, text=True,
                          timeout=15, errors="ignore", creationflags=_CREATE_NO_WINDOW)
    names = []
    for line in (proc.stdout or "").splitlines():
        match = re.search(r":\s*(.+?)\s*$", line) if "All User Profile" in line else None
        if match:
            names.append(match.group(1))
    return names


def get_wifi_password(profile: str) -> dict:
    if os.name != "nt":
        return {"ssid": profile, "password": None, "note": "Yalnızca Windows'ta okunabilir."}
    proc = subprocess.run(
        ["netsh.exe", "wlan", "show", "profile", f"name={profile}", "key=clear"],
        capture_output=True, text=True, timeout=15, errors="ignore", creationflags=_CREATE_NO_WINDOW,
    )
    text = proc.stdout or ""
    if not text.strip():
        return {"ssid": profile, "password": None, "note": "Okunamadı (yönetici izni gerekebilir)."}
    key_match = re.search(r"Key Content\s*:\s*(.+)", text)
    if key_match:
        return {"ssid": profile, "password": key_match.group(1).strip(), "note": ""}
    if re.search(r"Security key\s*:\s*Absent", text, re.IGNORECASE):
        return {"ssid": profile, "password": None, "note": "Şifresiz / açık ağ."}
    return {"ssid": profile, "password": None, "note": "Şifre bulunamadı."}


def list_wifi_with_passwords(progress=None) -> list[dict]:
    profiles = list_wifi_profiles()
    results = []
    for index, name in enumerate(profiles):
        results.append(get_wifi_password(name))
        if progress:
            progress(index + 1, len(profiles), name)
    return results


# ---------------------------------------------------------------------------
# 8) Sistem geri yükleme noktası
# ---------------------------------------------------------------------------
def create_restore_point(description: str = "T-Booster Yedek Noktası") -> tuple[bool, str]:
    """Checkpoint-Computer ile Windows Sistem Geri Yükleme noktası oluşturur.
    Windows varsayılan olarak günde yalnızca bir nokta oluşturulmasına izin
    verir; bu durumda da bir hata değil, anlaşılır bir mesaj döner."""
    if os.name != "nt":
        return False, "Geri yükleme noktası yalnızca Windows'ta oluşturulabilir."
    safe_desc = description.replace('"', "'").strip() or "T-Booster Yedek Noktası"
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f'Checkpoint-Computer -Description "{safe_desc}" -RestorePointType "MODIFY_SETTINGS"\n'
        "'OK'"
    )
    try:
        flags = _CREATE_NO_WINDOW
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=90, creationflags=flags, errors="ignore",
        )
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        if "OK" in output.splitlines()[-1:] or "OK" in output:
            return True, f'"{safe_desc}" geri yükleme noktası oluşturuldu.'
        if "frequency" in error.lower() or "sıklık" in error.lower():
            return False, "Windows son 24 saatte zaten bir geri yükleme noktası oluşturdu; tekrar denemek için biraz bekle."
        if "system restore" in error.lower() and "disab" in error.lower():
            return False, "Sistem Geri Yükleme bu sürücüde kapalı görünüyor; önce Windows ayarlarından açman gerekir."
        return False, error[:220] if error else "Geri yükleme noktası oluşturulamadı (bilinmeyen sebep)."
    except subprocess.TimeoutExpired:
        return False, "İşlem zaman aşımına uğradı; Windows geri yükleme servisi meşgul olabilir."
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# 9) Güç planı yöneticisi
# ---------------------------------------------------------------------------
_GUID_RE = re.compile(r"Power Scheme GUID:\s*([0-9a-fA-F-]{36})\s*\(([^)]*)\)\s*(\*)?")


def list_power_plans() -> list[dict]:
    if os.name != "nt":
        return []
    try:
        flags = _CREATE_NO_WINDOW
        result = subprocess.run(["powercfg.exe", "/list"], capture_output=True, text=True,
                                timeout=8, creationflags=flags, errors="ignore")
        text = (result.stdout or "").strip()
    except Exception:
        text = ""
    plans = []
    for match in _GUID_RE.finditer(text):
        guid, name, star = match.groups()
        plans.append({"guid": guid, "name": name.strip(), "active": bool(star)})
    return plans


def set_active_power_plan(guid: str) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Güç planları yalnızca Windows'ta değiştirilebilir."
    try:
        flags = _CREATE_NO_WINDOW
        result = subprocess.run(["powercfg.exe", "/setactive", guid], capture_output=True, text=True,
                                timeout=10, creationflags=flags, errors="ignore")
        if result.returncode == 0:
            return True, "Güç planı değiştirildi."
        return False, (result.stderr or result.stdout or "Güç planı değiştirilemedi.").strip()
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# 10) İnternet hız testi (indirme / yükleme / gecikme)
# ---------------------------------------------------------------------------
_SPEEDTEST_DOWNLOAD_URL = "https://speed.cloudflare.com/__down?bytes={size}"
_SPEEDTEST_UPLOAD_URL = "https://speed.cloudflare.com/__up"


def _mbps(num_bytes: int, seconds: float) -> float:
    if seconds <= 0:
        return 0.0
    return round((num_bytes * 8) / seconds / 1_000_000, 1)


def measure_download_speed(duration: float = 6.0, chunk_size: int = 262_144) -> float | None:
    url = _SPEEDTEST_DOWNLOAD_URL.format(size=50_000_000)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "T-Booster/1.0"})
        start = time.perf_counter()
        total = 0
        with urllib.request.urlopen(request, timeout=10) as response:
            while True:
                if time.perf_counter() - start > duration:
                    break
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
        elapsed = time.perf_counter() - start
        return _mbps(total, elapsed) if total else None
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def measure_upload_speed(duration: float = 5.0, chunk_size: int = 262_144) -> float | None:
    payload_chunk = os.urandom(chunk_size)

    def body():
        start = time.perf_counter()
        sent = 0
        while time.perf_counter() - start < duration:
            sent += len(payload_chunk)
            yield payload_chunk
        body.sent = sent

    try:
        start = time.perf_counter()
        request = urllib.request.Request(
            _SPEEDTEST_UPLOAD_URL, data=(payload_chunk * 20), method="POST",
            headers={"User-Agent": "T-Booster/1.0", "Content-Type": "application/octet-stream"},
        )
        with urllib.request.urlopen(request, timeout=10):
            pass
        elapsed = time.perf_counter() - start
        return _mbps(len(payload_chunk) * 20, elapsed)
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def run_speed_test(progress=None) -> dict:
    if progress:
        progress("ping")
    pings = tcp_latency("1.1.1.1", 443, 4, 2.0)
    ping_ms = round(sum(pings) / len(pings), 0) if pings else None

    if progress:
        progress("download")
    download = measure_download_speed()

    if progress:
        progress("upload")
    upload = measure_upload_speed()

    return {"ping_ms": ping_ms, "download_mbps": download, "upload_mbps": upload}


# ---------------------------------------------------------------------------
# 11) Pil sağlığı raporu
# ---------------------------------------------------------------------------
def _parse_mwh(text: str) -> int | None:
    match = re.search(r"([\d.,]+)\s*mWh", text)
    if not match:
        return None
    try:
        return int(float(match.group(1).replace(",", "")))
    except ValueError:
        return None


def battery_health_report() -> dict:
    if os.name != "nt":
        return {"has_battery": False, "error": "Pil raporu yalnızca Windows'ta oluşturulabilir."}
    try:
        with tempfile.TemporaryDirectory(prefix="tbooster_batt_") as tmp:
            out_path = os.path.join(tmp, "battery-report.html")
            flags = _CREATE_NO_WINDOW
            result = subprocess.run(
                ["powercfg.exe", "/batteryreport", "/output", out_path],
                capture_output=True, text=True, timeout=20, creationflags=flags, errors="ignore",
            )
            combined = f"{result.stdout or ''} {result.stderr or ''}"
            if not os.path.exists(out_path):
                if "no battery" in combined.lower() or "pil" in combined.lower() and "yok" in combined.lower():
                    return {"has_battery": False, "error": "Bu cihazda pil bulunamadı."}
                return {"has_battery": False, "error": combined.strip() or "Pil raporu oluşturulamadı."}
            with open(out_path, encoding="utf-8", errors="ignore") as handle:
                html = handle.read()
    except Exception as exc:
        return {"has_battery": False, "error": str(exc)}

    if "DESIGN CAPACITY" not in html.upper():
        return {"has_battery": False, "error": "Bu cihazda pil bulunamadı."}

    design_capacity = full_charge = cycle_count = None
    for label, block in re.findall(r'<span class="label">([^<]+)</span>\s*</td>\s*<td[^>]*>(.*?)</td>', html, re.S | re.I):
        clean_label = label.strip().upper()
        clean_value = re.sub("<[^<]+?>", "", block).strip()
        if clean_label == "DESIGN CAPACITY":
            design_capacity = _parse_mwh(clean_value)
        elif clean_label == "FULL CHARGE CAPACITY":
            full_charge = _parse_mwh(clean_value)
        elif clean_label == "CYCLE COUNT":
            digits = re.sub(r"\D", "", clean_value)
            cycle_count = int(digits) if digits else None

    health_pct = None
    if design_capacity and full_charge and design_capacity > 0:
        health_pct = round(100 * full_charge / design_capacity, 1)

    return {
        "has_battery": True,
        "design_capacity_mwh": design_capacity,
        "full_charge_mwh": full_charge,
        "cycle_count": cycle_count,
        "health_pct": health_pct,
        "error": None,
    }


# ---------------------------------------------------------------------------
# 12) Yinelenen dosya bulucu (yalnızca listeler, hiçbir şey silmez)
# ---------------------------------------------------------------------------
def _hash_head(path: str, size: int = 65536) -> str | None:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha1(handle.read(size), usedforsecurity=False).hexdigest()
    except OSError:
        return None


def _hash_full(path: str, cancel=None, chunk: int = 1024 * 1024) -> str | None:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while True:
                if cancel and cancel():
                    return None
                data = handle.read(chunk)
                if not data:
                    break
                digest.update(data)
    except OSError:
        return None
    return digest.hexdigest()


def find_duplicate_files(root: str, min_bytes: int = 10 * 1024 * 1024, cancel=None, progress=None,
                         max_seconds: float = 300.0, max_groups: int = 150) -> dict:
    """Aynı içeriğe sahip dosyaları bulur. Önce boyuta, sonra dosya başlığına,
    en son tam karmaya bakar; böylece büyük dosyaların çoğu hiç tam okunmaz."""
    started = time.time()
    by_size: dict[int, list[str]] = {}
    scanned = 0
    timed_out = cancelled = False
    stack = [str(root)]
    while stack:
        if cancel and cancel():
            cancelled = True
            break
        if time.time() - started > max_seconds:
            timed_out = True
            break
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink() or (getattr(entry, "is_junction", None) and entry.is_junction()):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.lower() not in _SKIP_DIRS:
                                stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            scanned += 1
                            size = entry.stat(follow_symlinks=False).st_size
                            if size >= min_bytes:
                                by_size.setdefault(size, []).append(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue
        if progress and scanned and scanned % 2000 < 40:
            progress("scan", scanned)

    groups: list[dict] = []
    candidates = [(size, paths) for size, paths in by_size.items() if len(paths) >= 2]
    for index, (size, paths) in enumerate(candidates):
        if cancelled or (cancel and cancel()):
            cancelled = True
            break
        if time.time() - started > max_seconds:
            timed_out = True
            break
        if progress:
            progress("hash", index + 1, len(candidates))
        by_head: dict[str, list[str]] = {}
        for path in paths:
            head = _hash_head(path)
            if head is not None:
                by_head.setdefault(head, []).append(path)
        for same_head in by_head.values():
            if len(same_head) < 2:
                continue
            by_full: dict[str, list[str]] = {}
            for path in same_head:
                full = _hash_full(path, cancel)
                if full is not None:
                    by_full.setdefault(full, []).append(path)
            for same in by_full.values():
                if len(same) >= 2:
                    groups.append({"size": size, "paths": sorted(same), "wasted": size * (len(same) - 1)})
    groups.sort(key=lambda g: g["wasted"], reverse=True)
    return {
        "groups": groups[:max_groups],
        "group_count": len(groups),
        "wasted_total": sum(g["wasted"] for g in groups),
        "scanned": scanned,
        "timed_out": timed_out,
        "cancelled": cancelled,
    }


# ---------------------------------------------------------------------------
# 13) Açık ağ bağlantıları (netstat) — yalnızca okur
# ---------------------------------------------------------------------------
def _split_endpoint(address: str) -> tuple[str, str]:
    host, _, port = address.rpartition(":")
    return host, port


def parse_netstat(text: str) -> list[dict]:
    """`netstat -ano` çıktısını ayrıştırır. Durum metni dile göre değişebildiği
    için dinleme durumu, uzak adresin 0.0.0.0:0 / [::]:0 olmasından anlaşılır."""
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        proto = parts[0].upper()
        if proto == "TCP" and len(parts) >= 5:
            local, remote, state, pid = parts[1], parts[2], parts[3], parts[4]
        elif proto == "UDP":
            local, remote, state, pid = parts[1], parts[2], "", parts[-1]
        else:
            continue
        if not pid.isdigit():
            continue
        local_host, local_port = _split_endpoint(local)
        remote_host, remote_port = _split_endpoint(remote)
        listening = proto == "TCP" and remote_port == "0" and remote_host in ("0.0.0.0", "[::]", "::")
        exposed = listening and local_host in ("0.0.0.0", "[::]", "::")
        upper = state.upper()
        if listening:
            label = "Dinliyor"
        elif upper == "ESTABLISHED":
            label = "Bağlı"
        elif upper == "TIME_WAIT":
            label = "Bekliyor"
        elif proto == "UDP":
            label = "UDP"
        else:
            label = state or "—"
        rows.append({
            "proto": proto, "local": local, "remote": remote, "state": label,
            "pid": int(pid), "listening": listening, "exposed": exposed,
            "established": upper == "ESTABLISHED",
        })
    return rows


def list_connections() -> list[dict]:
    if os.name != "nt":
        return []
    proc = subprocess.run(["netstat.exe", "-ano"], capture_output=True, text=True, timeout=25,
                          errors="ignore", creationflags=_CREATE_NO_WINDOW)
    rows = parse_netstat(proc.stdout or "")
    names: dict[int, str] = {}
    try:
        tasks = subprocess.run(["tasklist.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=20,
                               errors="ignore", creationflags=_CREATE_NO_WINDOW)
        names = {row["pid"]: row["name"] for row in parse_tasklist_csv(tasks.stdout or "")}
    except Exception:
        pass
    for row in rows:
        row["process"] = names.get(row["pid"], "") or ("Sistem" if row["pid"] in (0, 4) else "?")
    rows.sort(key=lambda r: (not r["exposed"], not r["listening"], r["process"].casefold(), r["local"]))
    return rows


# ---------------------------------------------------------------------------
# 14) Dosya karma (hash) hesaplayıcı / doğrulayıcı
# ---------------------------------------------------------------------------
def hash_file(path: str, cancel=None, progress=None, chunk: int = 1024 * 1024) -> dict | None:
    md5 = hashlib.md5(usedforsecurity=False)
    sha1 = hashlib.sha1(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = os.path.getsize(path)
    done = 0
    with open(path, "rb") as handle:
        while True:
            if cancel and cancel():
                return None
            data = handle.read(chunk)
            if not data:
                break
            md5.update(data)
            sha1.update(data)
            sha256.update(data)
            done += len(data)
            if progress:
                progress(done, size)
    return {"md5": md5.hexdigest(), "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest(), "size": size}


_HASH_LENGTHS = {32: "md5", 40: "sha1", 64: "sha256"}


def compare_hash(expected: str, results: dict) -> tuple[str | None, bool]:
    """Yapıştırılan karmanın türünü uzunluğundan çıkarır ve eşleşmeyi döndürür."""
    cleaned = re.sub(r"[\s:\-]", "", expected or "").lower()
    algo = _HASH_LENGTHS.get(len(cleaned))
    if not algo or not re.fullmatch(r"[0-9a-f]+", cleaned):
        return None, False
    return algo, results.get(algo) == cleaned


# ---------------------------------------------------------------------------
# 15) Sistem dosyası denetleyici (SFC)
# ---------------------------------------------------------------------------
def decode_console_bytes(data: bytes) -> str:
    """sfc.exe çıktısı çoğu Windows'ta UTF-16'dır; boş baytlara bakarak ayırt eder."""
    if not data:
        return ""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff") or data.count(b"\x00") > len(data) // 4:
        trimmed = data[: len(data) - (len(data) % 2)]
        return trimmed.decode("utf-16-le", errors="ignore").lstrip("\ufeff")
    return data.decode("utf-8", errors="ignore")


_SFC_PATTERNS = (
    ("pending", re.compile(r"requires reboot|yeniden\s+ba[sş]lat", re.I)),
    ("unfixable", re.compile(r"unable to fix|d[uü]zeltemedi|onaramad", re.I)),
    ("repaired", re.compile(r"successfully repaired|ba[sş]ar[ıi]yla\s+onard", re.I)),
    ("clean", re.compile(r"did not find any integrity violations|ihlali\s+bulamad", re.I)),
    ("violations", re.compile(r"found integrity violations|ihlalleri\s+buldu", re.I)),
)


def classify_sfc_output(text: str) -> str:
    for name, pattern in _SFC_PATTERNS:
        if pattern.search(text or ""):
            return name
    return "unknown"


def _sfc_clean_text(text: str) -> str:
    lines = [ln.strip() for ln in re.split(r"[\r\n]+", text) if ln.strip() and "%" not in ln]
    return " ".join(lines)[:420]


def run_sfc(mode: str = "verify", progress=None, cancel=None, _command=None) -> dict:
    """mode: "verify" (yalnızca denetler) veya "repair" (denetler ve onarır)."""
    if _command is None:
        if os.name != "nt":
            return {"result": "error", "percent": 0, "text": "SFC yalnızca Windows'ta çalışır.", "returncode": None}
        sfc = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "sfc.exe")
        _command = [sfc, "/verifyonly" if mode == "verify" else "/scannow"]
    try:
        proc = subprocess.Popen(_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=_CREATE_NO_WINDOW)
    except OSError as exc:
        return {"result": "error", "percent": 0, "text": f"SFC başlatılamadı: {exc}", "returncode": None}

    buffer = bytearray()
    lock = threading.Lock()

    def reader():
        try:
            while True:
                chunk = proc.stdout.read1(4096)
                if not chunk:
                    break
                with lock:
                    buffer.extend(chunk)
        except (OSError, ValueError):
            pass

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    last_percent = -1
    while proc.poll() is None:
        if cancel and cancel():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            thread.join(timeout=2)
            return {"result": "cancelled", "percent": max(0, last_percent), "text": "Denetim durduruldu.", "returncode": proc.returncode}
        with lock:
            snapshot = bytes(buffer)
        found = re.findall(r"(\d{1,3})\s*%", decode_console_bytes(snapshot))
        if found:
            percent = min(100, int(found[-1]))
            if percent != last_percent:
                last_percent = percent
                if progress:
                    progress(percent)
        time.sleep(0.2)
    thread.join(timeout=3)
    with lock:
        text = decode_console_bytes(bytes(buffer))
    return {"result": classify_sfc_output(text), "percent": 100, "text": _sfc_clean_text(text), "returncode": proc.returncode}


# ---------------------------------------------------------------------------
# 16) Hosts dosyası denetimi (yalnızca okur)
# ---------------------------------------------------------------------------
_BLOCK_ADDRESSES = {"127.0.0.1", "0.0.0.0", "::1", "::"}
_WATCHED_SITES = (
    "google.", "microsoft.", "windowsupdate.", "live.com", "office.", "github.", "facebook.", "instagram.",
    "paypal.", "apple.", "amazon.", "youtube.", "twitter.", "discord.", "steampowered.", "epicgames.",
    "roblox.", "mozilla.", "avast.", "kaspersky.", "malwarebytes.", "eset.", "bitdefender.",
)


def hosts_path() -> str:
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")


def parse_hosts(text: str) -> list[dict]:
    entries = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            entries.append({"line": number, "ip": parts[0], "host": "", "kind": "Geçersiz", "level": "bad",
                            "note": "Bu satırda alan adı yok."})
            continue
        ip, names = parts[0], parts[1:]
        try:
            ipaddress.ip_address(ip.split("%", 1)[0])
            valid_ip = True
        except ValueError:
            valid_ip = False
        for name in names:
            lowered = name.lower()
            watched = any(site in lowered for site in _WATCHED_SITES)
            if not valid_ip:
                kind, level, note = "Geçersiz", "bad", "IP adresi geçerli değil."
            elif lowered == "localhost" and ip in _BLOCK_ADDRESSES:
                kind, level, note = "Normal", "ok", "Standart yerel ad."
            elif ip in _BLOCK_ADDRESSES:
                if watched:
                    kind, level, note = "Engelleme", "warn", "Önemli bir site engellenmiş."
                else:
                    kind, level, note = "Engelleme", "info", "Yerel adrese yönlendirilip engellenmiş."
            else:
                if watched:
                    kind, level, note = "Yönlendirme", "bad", "Bilinen site başka IP'ye yönlendirilmiş (şüpheli)"
                else:
                    kind, level, note = "Yönlendirme", "warn", "Özel bir IP'ye yönlendiriliyor."
            entries.append({"line": number, "ip": ip, "host": name, "kind": kind, "level": level, "note": note})
    return entries


def read_hosts_file(path: str | None = None, max_entries: int = 2000) -> dict:
    target = path or hosts_path()
    if not os.path.exists(target):
        return {"path": target, "exists": False, "entries": [], "counts": {}, "size": 0, "modified": "", "truncated": False,
                "error": "Hosts dosyası bulunamadı."}
    try:
        with open(target, encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read()
        stat = os.stat(target)
    except OSError as exc:
        return {"path": target, "exists": True, "entries": [], "counts": {}, "size": 0, "modified": "", "truncated": False,
                "error": str(exc)}
    entries = parse_hosts(text)
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["level"]] = counts.get(entry["level"], 0) + 1
    order = {"bad": 0, "warn": 1, "info": 2, "ok": 3}
    entries.sort(key=lambda e: (order.get(e["level"], 9), e["line"]))
    return {
        "path": target, "exists": True, "entries": entries[:max_entries], "counts": counts, "total": len(entries),
        "size": stat.st_size, "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
        "truncated": len(entries) > max_entries, "error": None,
    }


def end_process(pid: int, name: str) -> tuple[bool, str]:
    if is_protected_process(name, pid):
        return False, f"{name} korumalı bir sistem işlemi; kapatılamaz."
    if os.name != "nt":
        return False, "İşlem sonlandırma yalnızca Windows'ta çalışır."
    try:
        proc = subprocess.run(["taskkill.exe", "/PID", str(int(pid)), "/F"], capture_output=True, text=True,
                              timeout=15, errors="ignore", creationflags=_CREATE_NO_WINDOW)
        text = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, text or ("Kapatıldı" if proc.returncode == 0 else "Kapatılamadı")
    except Exception as exc:
        return False, str(exc)
