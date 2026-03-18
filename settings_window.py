import tkinter as tk
from tkinter import scrolledtext
from settings import get_settings, _valid_time


DAY_MAP = {"Пн": 0, "Вт": 1, "Ср": 2, "Чт": 3, "Пт": 4, "Сб": 5, "Вс": 6}
DAY_REVERSE = {v: k for k, v in DAY_MAP.items()}


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
        self.window.resizable(False, True)
        self.window.attributes("-topmost", True)

        style = {"bg": "#2b2b2b", "fg": "#ffffff", "font": ("Segoe UI", 12)}
        entry_style = {"bg": "#3c3c3c", "fg": "#ffffff", "font": ("Segoe UI", 12),
                        "insertbackground": "#ffffff", "relief": "flat", "width": 8}
        time_entry_style = {"bg": "#3c3c3c", "fg": "#ffffff", "font": ("Segoe UI", 12),
                            "insertbackground": "#ffffff", "relief": "flat", "width": 6}
        section_style = {"bg": "#2b2b2b", "fg": "#aaaaaa", "font": ("Segoe UI", 12, "bold")}
        cb_style = {"bg": "#2b2b2b", "fg": "#ffffff", "selectcolor": "#3c3c3c",
                    "activebackground": "#2b2b2b", "activeforeground": "#ffffff",
                    "font": ("Segoe UI", 12)}

        # Скроллируемая область
        canvas = tk.Canvas(self.window, bg="#2b2b2b", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        main_frame = tk.Frame(canvas, bg="#2b2b2b", padx=20, pady=15)
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        main_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Прокрутка колёсиком мыши
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.window.protocol("WM_DELETE_WINDOW", lambda: self._close(canvas))

        row = 0

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
        for label_text, key in fields:
            tk.Label(main_frame, text=label_text, anchor="w", **style).grid(
                row=row, column=0, sticky="w", pady=4)
            entry = tk.Entry(main_frame, **entry_style)
            entry.insert(0, str(getattr(self.settings, key)))
            entry.grid(row=row, column=1, sticky="e", pady=4, padx=(10, 0))
            self._entries[key] = entry
            row += 1

        # --- Предупреждение ---
        tk.Label(main_frame, text="Предупреждение до перерыва (сек):",
                 anchor="w", **style).grid(row=row, column=0, sticky="w", pady=4)
        self._warning_dur_entry = tk.Entry(main_frame, **entry_style)
        self._warning_dur_entry.insert(0, str(self.settings.warning_duration_sec))
        self._warning_dur_entry.grid(row=row, column=1, sticky="e", pady=4, padx=(10, 0))
        row += 1

        # --- Обеденный перерыв ---
        tk.Label(main_frame, text="Обеденный перерыв:",
                 anchor="w", **section_style).grid(row=row, column=0, columnspan=2,
                                                   sticky="w", pady=(15, 5))
        row += 1

        self._lunch_enabled_var = tk.BooleanVar(value=self.settings.lunch_enabled)
        tk.Checkbutton(
            main_frame, text="Включить обеденный перерыв",
            variable=self._lunch_enabled_var,
            command=self._toggle_lunch_fields, **cb_style,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        tk.Label(main_frame, text="Начало (ЧЧ:ММ):", anchor="w", **style).grid(
            row=row, column=0, sticky="w", pady=4)
        self._lunch_start_entry = tk.Entry(main_frame, **time_entry_style)
        self._lunch_start_entry.insert(0, self.settings.lunch_start)
        self._lunch_start_entry.grid(row=row, column=1, sticky="e", pady=4, padx=(10, 0))
        row += 1

        tk.Label(main_frame, text="Конец (ЧЧ:ММ):", anchor="w", **style).grid(
            row=row, column=0, sticky="w", pady=4)
        self._lunch_end_entry = tk.Entry(main_frame, **time_entry_style)
        self._lunch_end_entry.insert(0, self.settings.lunch_end)
        self._lunch_end_entry.grid(row=row, column=1, sticky="e", pady=4, padx=(10, 0))
        row += 1

        self._toggle_lunch_fields()

        # --- Режим сна ---
        tk.Label(main_frame, text="Режим сна:",
                 anchor="w", **section_style).grid(row=row, column=0, columnspan=2,
                                                   sticky="w", pady=(15, 5))
        row += 1

        self._sleep_enabled_var = tk.BooleanVar(value=self.settings.sleep_enabled)
        tk.Checkbutton(
            main_frame, text="Включить режим сна",
            variable=self._sleep_enabled_var,
            command=self._toggle_sleep_fields, **cb_style,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        tk.Label(main_frame, text="Начало (ЧЧ:ММ):", anchor="w", **style).grid(
            row=row, column=0, sticky="w", pady=4)
        self._sleep_start_entry = tk.Entry(main_frame, **time_entry_style)
        self._sleep_start_entry.insert(0, self.settings.sleep_start)
        self._sleep_start_entry.grid(row=row, column=1, sticky="e", pady=4, padx=(10, 0))
        row += 1

        tk.Label(main_frame, text="Конец (ЧЧ:ММ):", anchor="w", **style).grid(
            row=row, column=0, sticky="w", pady=4)
        self._sleep_end_entry = tk.Entry(main_frame, **time_entry_style)
        self._sleep_end_entry.insert(0, self.settings.sleep_end)
        self._sleep_end_entry.grid(row=row, column=1, sticky="e", pady=4, padx=(10, 0))
        row += 1

        self._toggle_sleep_fields()

        # --- Расписание занятий ---
        tk.Label(main_frame, text="Расписание занятий:",
                 anchor="w", **section_style).grid(row=row, column=0, columnspan=2,
                                                   sticky="w", pady=(15, 5))
        row += 1

        self._class_enabled_var = tk.BooleanVar(value=self.settings.class_schedule_enabled)
        tk.Checkbutton(
            main_frame, text="Включить расписание занятий",
            variable=self._class_enabled_var,
            command=self._toggle_class_fields, **cb_style,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        tk.Label(main_frame, text="Формат: Пн,Ср,Пт 10:00-11:30",
                 anchor="w", bg="#2b2b2b", fg="#888888",
                 font=("Segoe UI", 10)).grid(row=row, column=0, columnspan=2,
                                              sticky="w", pady=(0, 4))
        row += 1

        self._class_schedule_text = scrolledtext.ScrolledText(
            main_frame, width=40, height=4,
            bg="#3c3c3c", fg="#ffffff", font=("Segoe UI", 11),
            insertbackground="#ffffff", relief="flat", wrap="word",
        )
        self._class_schedule_text.grid(row=row, column=0, columnspan=2, sticky="we")
        self._class_schedule_text.insert("1.0", self._schedule_to_text(self.settings.class_schedule))
        row += 1

        self._toggle_class_fields()

        # --- Автовыключение ---
        tk.Label(main_frame, text="Автовыключение:",
                 anchor="w", **section_style).grid(row=row, column=0, columnspan=2,
                                                   sticky="w", pady=(15, 5))
        row += 1

        self._shutdown_enabled_var = tk.BooleanVar(value=self.settings.auto_shutdown_enabled)
        tk.Checkbutton(
            main_frame, text="Выключать ПК в 01:00",
            variable=self._shutdown_enabled_var, **cb_style,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        # --- Упражнения ---
        tk.Label(main_frame, text="Упражнения (одно на строку):",
                 anchor="w", **section_style).grid(row=row, column=0, columnspan=2,
                                                   sticky="w", pady=(15, 5))
        row += 1

        self._exercises_text = scrolledtext.ScrolledText(
            main_frame, width=50, height=10,
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
                  command=lambda: self._close(canvas), **btn_style).pack(side="left", padx=5)

        # Размер и позиция окна
        self.window.update_idletasks()
        w = max(main_frame.winfo_reqwidth() + 40, 500)
        h = min(main_frame.winfo_reqheight() + 30, 700)
        x = (self.window.winfo_screenwidth() - w) // 2
        y = (self.window.winfo_screenheight() - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

    def _close(self, canvas):
        """Закрыть окно и отвязать события."""
        canvas.unbind_all("<MouseWheel>")
        self.window.destroy()

    def _toggle_lunch_fields(self):
        state = "normal" if self._lunch_enabled_var.get() else "disabled"
        self._lunch_start_entry.config(state=state)
        self._lunch_end_entry.config(state=state)

    def _toggle_sleep_fields(self):
        state = "normal" if self._sleep_enabled_var.get() else "disabled"
        self._sleep_start_entry.config(state=state)
        self._sleep_end_entry.config(state=state)

    def _toggle_class_fields(self):
        state = "normal" if self._class_enabled_var.get() else "disabled"
        self._class_schedule_text.config(state=state)

    def _schedule_to_text(self, schedule):
        """Конвертировать список слотов в текст."""
        lines = []
        for slot in schedule:
            days_str = ",".join(DAY_REVERSE.get(d, "?") for d in sorted(slot.get("days", [])))
            lines.append(f"{days_str} {slot.get('start', '')}-{slot.get('end', '')}")
        return "\n".join(lines)

    def _text_to_schedule(self, text):
        """Распарсить текст в список слотов расписания."""
        schedule = []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                continue
            days_part, time_part = parts
            days = []
            for d in days_part.split(","):
                d = d.strip()
                if d in DAY_MAP:
                    days.append(DAY_MAP[d])
            if not days or "-" not in time_part:
                continue
            start, end = time_part.split("-", 1)
            if _valid_time(start) and _valid_time(end):
                schedule.append({"days": days, "start": start, "end": end})
        return schedule

    def _save(self):
        for key, entry in self._entries.items():
            try:
                value = int(entry.get())
                setattr(self.settings, key, value)
            except ValueError:
                pass

        # Предупреждение
        try:
            self.settings.warning_duration_sec = int(self._warning_dur_entry.get())
        except ValueError:
            pass

        # Обеденный перерыв
        self.settings.lunch_enabled = self._lunch_enabled_var.get()
        self.settings.lunch_start = self._lunch_start_entry.get().strip()
        self.settings.lunch_end = self._lunch_end_entry.get().strip()

        # Режим сна
        self.settings.sleep_enabled = self._sleep_enabled_var.get()
        self.settings.sleep_start = self._sleep_start_entry.get().strip()
        self.settings.sleep_end = self._sleep_end_entry.get().strip()

        # Расписание занятий
        self.settings.class_schedule_enabled = self._class_enabled_var.get()
        schedule_text = self._class_schedule_text.get("1.0", "end-1c")
        self.settings.class_schedule = self._text_to_schedule(schedule_text)

        # Автовыключение
        self.settings.auto_shutdown_enabled = self._shutdown_enabled_var.get()

        # Упражнения
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
