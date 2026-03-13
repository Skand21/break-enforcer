import ctypes
import random
import tkinter as tk
from config import (
    OVERLAY_BG, OVERLAY_ALPHA, TEXT_COLOR,
    BUTTON_BG, BUTTON_FG, BUTTON_ACTIVE_BG,
    FONT_TIMER, FONT_MESSAGE, FONT_SUB, FONT_BUTTON,
    MSG_BREAK, MSG_DONE,
)

user32 = ctypes.windll.user32


def get_virtual_screen_geometry():
    """Возвращает (x, y, width, height) виртуального экрана (все мониторы)."""
    x = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    y = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
    w = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
    h = user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
    return x, y, w, h


class BreakOverlay:
    """Полноэкранный тёмный оверлей с обратным отсчётом."""

    def __init__(self, root: tk.Tk, duration_sec: int, on_dismiss, exercises=None,
                 message=None, show_exercises=True):
        """
        root: главное окно tkinter
        duration_sec: длительность перерыва в секундах
        on_dismiss: callback при нажатии кнопки "Я размялся!"
        exercises: список упражнений (если None — не показываем)
        message: текст заголовка (по умолчанию MSG_BREAK)
        show_exercises: показывать ли упражнения
        """
        self.root = root
        self.duration = duration_sec
        self.remaining = duration_sec
        self.on_dismiss = on_dismiss
        self._exercises_list = exercises or []
        self._message = message or MSG_BREAK
        self._show_exercises = show_exercises
        self.window = None
        self._button = None
        self._timer_label = None
        self._msg_label = None
        self._sub_label = None

    def show(self):
        """Показать оверлей."""
        vx, vy, vw, vh = get_virtual_screen_geometry()

        self.window = tk.Toplevel(self.root)
        self.window.title("")
        self.window.configure(bg=OVERLAY_BG)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", OVERLAY_ALPHA)
        self.window.geometry(f"{vw}x{vh}+{vx}+{vy}")

        # Блокируем закрытие
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)
        self.window.bind("<Key>", lambda e: "break")
        self.window.bind("<Button-1>", lambda e: "break")

        # Центрируем контент на основном мониторе (0,0)
        primary_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        primary_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        # Смещение основного монитора относительно виртуального экрана
        cx = -vx + primary_w // 2
        cy = -vy + primary_h // 2

        # Рамка для контента
        frame = tk.Frame(self.window, bg=OVERLAY_BG)
        frame.place(x=cx, y=cy, anchor="center")

        self._msg_label = tk.Label(
            frame, text=self._message,
            font=FONT_MESSAGE, fg=TEXT_COLOR, bg=OVERLAY_BG,
        )
        self._msg_label.pack(pady=(0, 10))

        self._timer_label = tk.Label(
            frame, text=self._format_time(self.remaining),
            font=FONT_TIMER, fg=TEXT_COLOR, bg=OVERLAY_BG,
        )
        self._timer_label.pack(pady=(0, 10))

        # Случайные упражнения (3-4 штуки)
        if self._show_exercises and self._exercises_list:
            selected = random.sample(
                self._exercises_list, min(4, len(self._exercises_list))
            )
            exercises_text = "\n".join(
                f"  {i+1}. {ex}" for i, ex in enumerate(selected)
            )
        else:
            exercises_text = ""

        self._sub_label = tk.Label(
            frame, text=exercises_text,
            font=FONT_SUB, fg="#aaaaaa", bg=OVERLAY_BG,
            justify="left",
        )
        self._sub_label.pack(pady=(0, 30))

        # Кнопка — скрыта до окончания таймера
        self._button = tk.Button(
            frame, text=MSG_DONE,
            font=FONT_BUTTON,
            fg=BUTTON_FG, bg=BUTTON_BG,
            activebackground=BUTTON_ACTIVE_BG,
            activeforeground=BUTTON_FG,
            relief="flat", padx=30, pady=10,
            command=self._dismiss,
        )
        # Пока не показываем кнопку

        # Принудительный фокус
        self.window.focus_force()
        self.window.lift()
        self._force_foreground()

        # Запускаем тик через 1 секунду (чтобы не съедать первую секунду)
        self.window.after(1000, self._tick)
        # Периодически возвращаем фокус
        self._enforce_focus()

    def _format_time(self, seconds: int) -> str:
        m, s = divmod(max(0, seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _tick(self):
        if self.window is None:
            return
        self.remaining -= 1
        if self.remaining <= 0:
            self._timer_label.config(text="00:00")
            self._sub_label.config(text="Нажмите кнопку чтобы продолжить работу")
            self._button.pack(pady=(20, 0))
            # Разрешаем клик по кнопке
            self.window.unbind("<Button-1>")
            return
        self._timer_label.config(text=self._format_time(self.remaining))
        self.window.after(1000, self._tick)

    def _enforce_focus(self):
        """Периодически возвращает фокус на оверлей."""
        if self.window is None:
            return
        try:
            self.window.lift()
            self.window.focus_force()
            self._force_foreground()
        except tk.TclError:
            return
        self.window.after(500, self._enforce_focus)

    def _force_foreground(self):
        try:
            hwnd = int(self.window.frame(), 16)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _dismiss(self):
        """Закрыть оверлей."""
        if self.window:
            self.window.destroy()
            self.window = None
        if self.on_dismiss:
            self.on_dismiss()

    def destroy(self):
        """Принудительно уничтожить оверлей."""
        if self.window:
            self.window.destroy()
            self.window = None
