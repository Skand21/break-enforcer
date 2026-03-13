import tkinter as tk
from tkinter import scrolledtext
from settings import get_settings


class SettingsWindow:
    """Окно настроек приложения."""

    def __init__(self, root: tk.Tk, on_save=None):
        self.root = root
        self.on_save = on_save
        self.settings = get_settings()
        self.window = None

    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        self.window = tk.Toplevel(self.root)
        self.window.title("Настройки — Break Enforcer")
        self.window.configure(bg="#2b2b2b")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)

        style = {"bg": "#2b2b2b", "fg": "#ffffff", "font": ("Segoe UI", 12)}
        entry_style = {"bg": "#3c3c3c", "fg": "#ffffff", "font": ("Segoe UI", 12),
                        "insertbackground": "#ffffff", "relief": "flat", "width": 8}

        main_frame = tk.Frame(self.window, bg="#2b2b2b", padx=20, pady=15)
        main_frame.pack(fill="both", expand=True)

        # --- Параметры таймеров ---
        fields = [
            ("Время работы (мин):", "work_duration_min"),
            ("Длительность перерыва (мин):", "break_duration_min"),
            ("Перерыв после отложения (мин):", "extended_break_min"),
            ("Время отсрочки (мин):", "postpone_min"),
            ("Макс. отложений:", "max_postpones"),
            ("Порог неактивности (мин):", "idle_threshold_min"),
        ]

        self._entries = {}
        for i, (label_text, key) in enumerate(fields):
            tk.Label(main_frame, text=label_text, anchor="w", **style).grid(
                row=i, column=0, sticky="w", pady=4)
            entry = tk.Entry(main_frame, **entry_style)
            entry.insert(0, str(getattr(self.settings, key)))
            entry.grid(row=i, column=1, sticky="e", pady=4, padx=(10, 0))
            self._entries[key] = entry

        row = len(fields)

        # --- Упражнения ---
        tk.Label(main_frame, text="Упражнения (одно на строку):",
                 anchor="w", **style).grid(row=row, column=0, columnspan=2,
                                           sticky="w", pady=(15, 5))
        row += 1

        self._exercises_text = scrolledtext.ScrolledText(
            main_frame, width=50, height=12,
            bg="#3c3c3c", fg="#ffffff", font=("Segoe UI", 11),
            insertbackground="#ffffff", relief="flat", wrap="word",
        )
        self._exercises_text.grid(row=row, column=0, columnspan=2, sticky="we")
        self._exercises_text.insert("1.0", "\n".join(self.settings.exercises))
        row += 1

        # --- Кнопки ---
        btn_frame = tk.Frame(main_frame, bg="#2b2b2b")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(15, 0))

        btn_style = {"font": ("Segoe UI", 12), "relief": "flat",
                     "padx": 15, "pady": 5, "cursor": "hand2"}

        tk.Button(btn_frame, text="Сохранить", bg="#4CAF50", fg="#ffffff",
                  activebackground="#45a049", activeforeground="#ffffff",
                  command=self._save, **btn_style).pack(side="left", padx=5)

        tk.Button(btn_frame, text="Сбросить упражнения", bg="#FF9800", fg="#ffffff",
                  activebackground="#F57C00", activeforeground="#ffffff",
                  command=self._reset_exercises, **btn_style).pack(side="left", padx=5)

        tk.Button(btn_frame, text="Отмена", bg="#555555", fg="#ffffff",
                  activebackground="#666666", activeforeground="#ffffff",
                  command=self.window.destroy, **btn_style).pack(side="left", padx=5)

        # Центрируем окно
        self.window.update_idletasks()
        w = self.window.winfo_width()
        h = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() - w) // 2
        y = (self.window.winfo_screenheight() - h) // 2
        self.window.geometry(f"+{x}+{y}")

    def _save(self):
        for key, entry in self._entries.items():
            try:
                value = int(entry.get())
                setattr(self.settings, key, value)
            except ValueError:
                pass

        exercises_raw = self._exercises_text.get("1.0", "end-1c")
        exercises = [line.strip() for line in exercises_raw.splitlines() if line.strip()]
        self.settings.exercises = exercises

        self.settings.save()
        if self.on_save:
            self.on_save()
        self.window.destroy()

    def _reset_exercises(self):
        self.settings.reset_exercises()
        self._exercises_text.delete("1.0", "end")
        self._exercises_text.insert("1.0", "\n".join(self.settings.exercises))
