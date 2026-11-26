"""Startup sequence and the application-level tools for T-BOOSTER."""

import json
import time
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import filedialog, messagebox


class StartupScene:
    WIDTH = 512
    HEIGHT = 312
    BACKGROUND = "#0b1528"

    def __init__(self, root, name, version, author, logo_path, prepare, finish, on_error):
        self.root = root
        self.prepare = prepare
        self.finish = finish
        self.on_error = on_error
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        x = (root.winfo_screenwidth() - self.WIDTH) // 2
        y = (root.winfo_screenheight() - self.HEIGHT) // 2
        self.window.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        canvas = self.canvas = tk.Canvas(self.window, bg=self.BACKGROUND, bd=0, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.create_rectangle(1, 1, self.WIDTH - 2, self.HEIGHT - 2, outline="#294873")
        canvas.create_line(37, 34, 475, 34, fill="#21385b")
        canvas.create_rectangle(37, 33, 111, 35, fill="#589bff", outline="")
        canvas.create_text(475, 52, anchor="e", text=version, fill="#a8caff", font=("Segoe UI Semibold", 10))
        canvas.create_oval(219, 65, 293, 139, outline="#3662a0", width=1)
        self.orbit = canvas.create_arc(219, 65, 293, 139, start=0, extent=75,
                                       style="arc", outline="#74b2ff", width=3)
        try:
            raw_logo = tk.PhotoImage(master=self.window, file=str(logo_path))
            scale = max(1, (max(raw_logo.width(), raw_logo.height()) + 54) // 55)
            self.logo = raw_logo.subsample(scale)
            canvas.create_image(256, 102, image=self.logo)
        except tk.TclError:
            canvas.create_text(256, 102, text="T", fill="#f4f8ff", font=("Segoe UI", 25, "bold"))
        canvas.create_text(256, 168, text=name, fill="#f5f9ff", font=("Segoe UI", 26, "bold"))
        canvas.create_text(256, 201, text=f"Yapımcı  ·  {author}", fill="#a8caff",
                           font=("Segoe UI Semibold", 10))
        self.status = canvas.create_text(37, 250, anchor="w", fill="#c5d8f2", font=("Segoe UI", 10))
        self.percent = canvas.create_text(475, 250, anchor="e", fill="#a8caff", font=("Segoe UI Semibold", 10))
        canvas.create_rectangle(37, 271, 475, 278, fill="#203650", outline="")
        self.bar = canvas.create_rectangle(37, 271, 37, 278, fill="#5a9fff", outline="")

        self.progress = 0.0
        self.started = time.monotonic()
        self._phase("Başlatılıyor…", 22)
        self.window.deiconify()
        self.window.lift()
        self._animate()
        self.window.after(340, self._show_preparation)

    def _phase(self, label, target):
        self.canvas.itemconfigure(self.status, text=label)
        self.target = target

    def _show_preparation(self):
        self._phase("Arayüz hazırlanıyor…", 68)
        self.window.after(330, self._prepare_workspace)

    def _prepare_workspace(self):
        try:
            self.prepare()
        except Exception as error:
            self.on_error(error)
            self.root.destroy()
            return
        self._phase("Kontrol merkezi hazır", 100)
        self.window.after(540, self._reveal)

    def _animate(self):
        elapsed = time.monotonic() - self.started
        self.progress += (self.target - self.progress) * 0.15
        if self.target - self.progress < 0.5:
            self.progress = float(self.target)
        self.canvas.itemconfigure(self.orbit, start=(elapsed * -210) % 360)
        self.canvas.coords(self.bar, 37, 271, 37 + 438 * self.progress / 100, 278)
        self.canvas.itemconfigure(self.percent, text=f"%{round(self.progress)}")
        self.animation_id = self.window.after(16, self._animate)

    def _reveal(self):
        self.window.after_cancel(self.animation_id)
        self.window.destroy()
        self.finish()


class ReleaseUi:
    def __init__(self, app, toggle_class):
        self.app = app
        self.toggle_class = toggle_class
        self.pinned = tk.BooleanVar(master=app.root, value=False)
        self.search_window = None
        self.asya_window = None

    def show_asya_message(self, _event=None):
        if self.asya_window is not None and self.asya_window.winfo_exists():
            self.asya_window.lift()
            return

        app = self.app
        palette = app.palette
        window = self.asya_window = tk.Toplevel(app.root, bg=palette["PANEL"])
        window.withdraw()
        window.title("Asya")
        window.transient(app.root)
        window.resizable(False, False)
        tk.Label(window, text="♥", bg=palette["PANEL"], fg="#df5f8c",
                 font=("Segoe UI Symbol", 32)).pack(pady=(18, 0))
        tk.Label(window, text="Asya seni seviyorum", bg=palette["PANEL"], fg=palette["TEXT"],
                 font=("Segoe UI Semibold", 17)).pack(padx=36, pady=(2, 14))
        close = app.action_button(window, "Kapat", window.destroy)
        close.pack(pady=(0, 18))
        window.bind("<Escape>", lambda _e: window.destroy())
        window.bind("<Return>", lambda _e: window.destroy())
        window.update_idletasks()
        width, height = window.winfo_reqwidth(), window.winfo_reqheight()
        x = app.root.winfo_rootx() + (app.root.winfo_width() - width) // 2
        y = app.root.winfo_rooty() + (app.root.winfo_height() - height) // 2
        window.geometry(f"{x:+d}{y:+d}")
        window.deiconify()
        close.focus_set()

    @staticmethod
    def _search_key(value):
        letters = unicodedata.normalize("NFKD", value.casefold().replace("ı", "i"))
        return "".join(char for char in letters if not unicodedata.combining(char))

    def search(self, _event=None):
        app = self.app
        if self.search_window is not None and self.search_window.winfo_exists():
            self.search_window.lift()
            self.search_window.focus_force()
            return "break"
        palette = app.palette
        window = self.search_window = tk.Toplevel(app.root, bg=palette["PANEL"])
        window.title("Sayfa ara")
        window.transient(app.root)
        window.minsize(360, 310)
        x = app.root.winfo_rootx() + max(0, (app.root.winfo_width() - 440) // 2)
        y = app.root.winfo_rooty() + 95
        window.geometry(f"440x350+{x}+{y}")
        search = tk.StringVar(master=window)
        tk.Label(window, text="Sayfa adı", bg=palette["PANEL"], fg=palette["TEXT"],
                 font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=16, pady=(12, 4))
        entry = tk.Entry(window, textvariable=search, bg=palette["SURFACE"], fg=palette["TEXT"],
                         insertbackground=palette["TEXT"], font=("Segoe UI", 11))
        entry.pack(fill="x", padx=16, ipady=5)
        results = tk.Listbox(window, bg=palette["SURFACE"], fg=palette["TEXT"],
                             selectbackground="#205fc4", selectforeground="white",
                             font=("Segoe UI", 10), activestyle="none", exportselection=False)
        results.pack(fill="both", expand=True, padx=16, pady=8)
        footer = tk.Frame(window, bg=palette["PANEL"])
        footer.pack(fill="x", padx=16, pady=(0, 12))
        matches = []

        def open_selection(_event=None):
            selected = results.curselection()
            if selected:
                page = matches[selected[0]]
                window.destroy()
                app.show_page(page)
            return "break"

        def refresh(*_args):
            query = self._search_key(search.get().strip())
            matches.clear()
            results.delete(0, "end")
            for page, title in app.PAGE_TITLES.items():
                if query in self._search_key(title):
                    matches.append(page)
                    results.insert("end", title)
            if matches:
                results.selection_set(0)
                results.activate(0)
            open_button.configure(state="normal" if matches else "disabled")
            status.configure(text=f"{len(matches)} sayfa" if matches else "Eşleşen sayfa bulunamadı")

        def move_selection(event):
            if matches:
                selected = results.curselection()
                index = selected[0] if selected else 0
                index = max(0, min(len(matches) - 1, index + (1 if event.keysym == "Down" else -1)))
                results.selection_clear(0, "end")
                results.selection_set(index)
                results.activate(index)
                results.see(index)
            return "break"

        status = tk.Label(footer, bg=palette["PANEL"], fg=palette["MUTED"], font=("Segoe UI", 9))
        status.pack(side="left")
        open_button = app.action_button(footer, "Sayfayı aç", open_selection)
        open_button.pack(side="right")
        search.trace_add("write", refresh)
        entry.bind("<Down>", move_selection)
        entry.bind("<Up>", move_selection)
        entry.bind("<Return>", open_selection)
        results.bind("<Return>", open_selection)
        results.bind("<Double-Button-1>", open_selection)
        window.bind("<Escape>", lambda _event: window.destroy())
        window.bind("<Control-k>", lambda _event: "break")
        refresh()
        window.grab_set()
        entry.focus_set()
        return "break"

    def build_about(self, name, version, author):
        app = self.app
        page = app._page()
        credit, content = app._glass_card(page, f"{name} {version}", "KREDİLER")
        credit.pack(fill="x", pady=(0, 10))
        tk.Label(content, text="Yapımcı", bg=app.palette["PANEL"], fg=app.palette["MUTED"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 3))
        tk.Label(content, text=author, bg=app.palette["PANEL"], fg=app.palette["TEXT"],
                 font=("Segoe UI Semibold", 24)).pack(anchor="w", pady=(0, 8))

        profile, actions = app._glass_card(page, "Tweak profilleri", "SEÇİMLER")
        profile.pack(fill="x", pady=(0, 10))
        row = tk.Frame(actions, bg=app.palette["PANEL"])
        row.pack(fill="x", pady=(0, 6))
        app.action_button(row, "Profili kaydet", self.save_profile).pack(side="left", padx=(0, 8))
        app.action_button(row, "Profil yükle", self.load_profile).pack(side="left")
        tk.Label(actions, text="Profil yükleme, uygulamadaki tweak seçimlerini günceller.",
                 bg=app.palette["PANEL"], fg=app.palette["MUTED"], font=("Segoe UI", 9)).pack(anchor="w")

        tools, actions = app._glass_card(page, "Pencere ve sistem", "")
        tools.pack(fill="x")
        pin = tk.Frame(actions, bg=app.palette["PANEL_2"], highlightbackground=app.palette["BORDER"],
                       highlightthickness=1)
        pin.pack(side="left", padx=(0, 10))
        tk.Label(pin, text="En üstte tut", bg=app.palette["PANEL_2"], fg=app.palette["TEXT"],
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(10, 4))
        self.toggle_class(pin, self.pinned, app.palette["SURFACE"], app.palette["BORDER"],
                          command=lambda: app.root.attributes("-topmost", self.pinned.get())).pack(side="left")
        app.action_button(actions, "Sistem özetini kopyala", self.copy_summary).pack(side="left")
        return page

    def _save_text(self, title, filename, extension, description, content):
        app = self.app
        path = filedialog.asksaveasfilename(parent=app.root, title=title, initialfile=filename,
                                            defaultextension=extension, filetypes=[(description, "*" + extension)])
        if not path:
            return
        try:
            Path(path).write_text(content, encoding="utf-8")
        except OSError as error:
            messagebox.showerror(title, str(error), parent=app.root)
            return
        app.status_var.set(f"Kaydedildi · {Path(path).name}")

    def save_profile(self):
        options = {key: variable.get() for key, variable in self.app.option_vars.items()}
        content = json.dumps({"format": "t-booster-tweak-profile", "version": 1, "options": options}, indent=2)
        self._save_text("Tweak profilini kaydet", "t-booster-profil.json", ".json", "Tweak profili", content + "\n")

    def load_profile(self):
        app = self.app
        name = filedialog.askopenfilename(parent=app.root, title="Tweak profili yükle",
                                          filetypes=[("Tweak profili", "*.json")])
        if not name:
            return
        try:
            path = Path(name)
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("Profil dosyası 1 MB sınırını aşıyor.")
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if (not isinstance(data, dict) or data.get("format") != "t-booster-tweak-profile"
                    or type(data.get("version")) is not int or data["version"] != 1):
                raise ValueError("T-Booster profil biçimi tanınmadı.")
            options = data.get("options")
            if not isinstance(options, dict) or any(type(value) is not bool for value in options.values()):
                raise ValueError("Profildeki tweak değerleri geçersiz.")
            recognized = {key: value for key, value in options.items() if key in app.option_vars}
            if not recognized:
                raise ValueError("Profilde bu sürümün tanıdığı bir tweak yok.")
        except (OSError, ValueError, RecursionError) as error:
            messagebox.showerror("Profil yüklenemedi", str(error), parent=app.root)
            return
        for key, value in recognized.items():
            app.option_vars[key].set(value)
        app.status_var.set(f"Profil yüklendi · {len(recognized)} tweak seçimi güncellendi.")

    def copy_summary(self):
        app = self.app
        fields = (("windows", "Windows"), ("cpu", "İşlemci"), ("board", "Anakart"),
                  ("bios", "BIOS"), ("gpu", "Ekran kartı"), ("ram", "Bellek"), ("storage", "Depolama"))
        summary = "\n".join(f"{label}: {app.hardware_vars[key].get()}" for key, label in fields)
        app.root.clipboard_clear()
        app.root.clipboard_append(f"{app.root.title()} · Sistem özeti\n\n{summary}")
        app.status_var.set("Sistem özeti panoya kopyalandı.")

    def export_log(self):
        app = self.app
        entries = app.log_box.get("1.0", "end-1c")
        self._save_text("İşlem günlüğünü dışa aktar", "t-booster-gunluk.txt", ".txt", "Metin dosyası",
                        f"{app.root.title()} · İşlem günlüğü\n\n{entries}")
