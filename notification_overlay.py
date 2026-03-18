import ctypes
import tkinter as tk

user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080


class NotificationOverlay:
    """Небольшое уведомление в правом нижнем углу (click-through, автоскрытие)."""

    def __init__(self, root: tk.Tk, text: str, duration_sec: int = 8):
        self.root = root
        self._text = text
        self._duration = duration_sec
        self.window = None

    def show(self):
        self.window = tk.Toplevel(self.root)
        self.window.title("")
        self.window.configure(bg="#1a1a1a")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.85)
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)

        frame = tk.Frame(self.window, bg="#1a1a1a", padx=20, pady=15)
        frame.pack()

        tk.Label(
            frame, text=self._text,
            font=("Segoe UI", 16), fg="#ffffff", bg="#1a1a1a",
            justify="center",
        ).pack()

        self.window.update_idletasks()
        w = self.window.winfo_width()
        h = self.window.winfo_height()
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        x = screen_w - w - 20
        y = screen_h - h - 60
        self.window.geometry(f"+{x}+{y}")

        # Click-through + не показывать в таскбаре
        self.window.update_idletasks()
        try:
            hwnd = int(self.window.frame(), 16)
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
            )
        except Exception:
            pass

        self.window.after(self._duration * 1000, self.destroy)

    def destroy(self):
        if self.window:
            self.window.destroy()
            self.window = None
