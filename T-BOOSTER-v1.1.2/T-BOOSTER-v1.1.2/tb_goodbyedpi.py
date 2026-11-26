"""Run the bundled Turkey DNS profile for the lifetime of a Windows job."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import tkinter as tk


class _BasicJobLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedJobLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicJobLimits),
        ("IoInfo", ctypes.c_ulonglong * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _SessionJob:
    def __init__(self):
        api = self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        api.CreateJobObjectW.restype = wintypes.HANDLE
        api.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        api.SetInformationJobObject.restype = wintypes.BOOL
        api.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        api.OpenProcess.restype = wintypes.HANDLE
        api.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        api.AssignProcessToJobObject.restype = wintypes.BOOL
        api.CloseHandle.argtypes = (wintypes.HANDLE,)
        api.CloseHandle.restype = wintypes.BOOL
        self.handle = api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        settings = _ExtendedJobLimits()
        settings.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not api.SetInformationJobObject(self.handle, 9, ctypes.byref(settings), ctypes.sizeof(settings)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def add(self, pid):
        process = self.api.OpenProcess(0x0101, False, pid)  # PROCESS_SET_QUOTA | PROCESS_TERMINATE
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(process)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class TemporaryGoodbyeDpi:
    START_TEXT = "Erişim Engeli Açma"
    STOP_TEXT = "Erişim Engeli Açma · Durdur"

    def __init__(self, root, status, directory):
        self.root = root
        self.status = status
        self.directory = directory
        self.label = tk.StringVar(master=root, value=self.START_TEXT)
        self.process = None
        self.job = None

    def toggle(self):
        if self.process is not None:
            self.stop()
            return

        script = self.directory / "turkey_dnsredir.cmd"
        if not script.is_file():
            self.status.set("GoodbyeDPI başlatılamadı. turkey_dnsredir.cmd bulunamadı.")
            return

        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        command = system_root / "System32" / "cmd.exe"
        job = None
        process = None
        try:
            job = _SessionJob()
            # Let CMD read a start signal only after it belongs to the session job.
            process = subprocess.Popen(
                [str(command), "/d", "/q", "/c", "set /p tb_dpi_gate= && turkey_dnsredir.cmd"],
                cwd=self.directory, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            job.add(process.pid)
            process.stdin.write(b"run\r\n")
            process.stdin.close()
        except OSError as error:
            if job is not None:
                job.close()
            if process is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
                if process.poll() is None:
                    process.kill()
            self.status.set(f"GoodbyeDPI başlatılamadı. {error}")
            return

        self.job = job
        self.process = process
        self.label.set(self.STOP_TEXT)
        self.status.set("GoodbyeDPI geçici oturumu başlatılıyor…")
        self.root.after(400, self._poll, process, True)

    def _poll(self, process, first=False):
        if self.process is not process:
            return
        code = process.poll()
        if code is None:
            if first:
                self.status.set("GoodbyeDPI geçici oturumu çalışıyor.")
            self.root.after(400, self._poll, process)
            return
        self._close_job()
        if code:
            self.status.set(f"GoodbyeDPI kapandı (çıkış kodu {code}).")
        else:
            self.status.set("GoodbyeDPI geçici oturumu sona erdi.")

    def _close_job(self):
        self.job.close()
        self.job = None
        self.process = None
        self.label.set(self.START_TEXT)

    def stop(self):
        if self.process is not None:
            self._close_job()
            self.status.set("GoodbyeDPI geçici oturumu durduruldu.")
