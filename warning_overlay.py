import ctypes
import tkinter as tk
from overlay import get_virtual_screen_geometry
from config import WARNING_ALPHA, FONT_WARNING, FONT_MESSAGE, TEXT_COLOR, OVERLAY_BG, MSG_WARNING

user32 = ctypes.windll.user32

# Windows API constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


class WarningOverlay:
    """Полупрозрачный click-through оверлей с обратным отсчётом."""

    def __init__(self, root: tk.Tk, duration_sec: int = 30, on_complete=None):
        self.root = root
        self.remaining = duration_sec
        self.on_complete = on_complete
        self.window = None
        self._timer_label = None

    def show(self):
        """Показать предупреждение."""
        vx, vy, vw, vh = get_virtual_screen_geometry()

        self.window = tk.Toplevel(self.root)
        self.window.title("")
        self.window.configure(bg=OVERLAY_BG)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", WARNING_ALPHA)
        self.window.geometry(f"{vw}x{vh}+{vx}+{vy}")

        # Не блокируем закрытие — но и не закрываем по крестику
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)

        # Центрируем контент на основном мониторе
        primary_w = user32.GetSystemMetrics(0)
        primary_h = user32.GetSystemMetrics(1)
        cx = -vx + primary_w // 2
        cy = -vy + primary_h // 2

        frame = tk.Frame(self.window, bg=OVERLAY_BG)
        frame.place(x=cx, y=cy, anchor="center")

        tk.Label(
            frame, text=MSG_WARNING,
            font=FONT_MESSAGE, fg=TEXT_COLOR, bg=OVERLAY_BG,
        ).pack(pady=(0, 10))

        self._timer_label = tk.Label(
            frame, text=str(self.remaining),
            font=FONT_WARNING, fg=TEXT_COLOR, bg=OVERLAY_BG,
        )
        self._timer_label.pack()

        # Делаем окно click-through через Windows API
        self.window.update_idletasks()
        self._apply_clickthrough()

        self.window.after(1000, self._tick)

    def _apply_clickthrough(self):
        """Применить WS_EX_TRANSPARENT чтобы клики проходили сквозь окно."""
        try:
            hwnd = int(self.window.frame(), 16)
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            )
        except Exception:
            pass

    def _tick(self):
        if self.window is None:
            return
        self.remaining -= 1
        if self.remaining <= 0:
            self.destroy()
            if self.on_complete:
                self.on_complete()
            return
        self._timer_label.config(text=str(self.remaining))
        self.window.after(1000, self._tick)

    def destroy(self):
        """Уничтожить оверлей."""
        if self.window:
            self.window.destroy()
            self.window = None
