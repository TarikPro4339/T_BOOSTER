# -*- coding: utf-8 -*-
"""T-BOOSTER yeni özellikler (v1.0.0 Beta) — Yapımcı: TarikPro43391

Bu modül arayüzden bağımsızdır (yalnızca standart kütüphane). Beş özellik:
  1) Geçici dosya temizleyici
  2) DNS & ağ hızlandırıcı (DNS önbelleği temizleme + DNS gecikme testi)
  3) Sistem sağlık puanı
  4) Büyük dosya bulucu (yalnızca okuma / listeleme)
  5) Arka plan uygulama avcısı (RAM'i en çok kullanan işlemler)
"""
from __future__ import annotations

import csv
import heapq
import io
import os
import random
import re
import shutil
import socket
import struct
import subprocess
import time
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
