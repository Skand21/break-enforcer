import ctypes
import ctypes.wintypes
import threading

# Константы Win32
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_F4 = 0x73
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_DELETE = 0x2E

LLKHF_ALTDOWN = 0x20

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Тип callback для хука
HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_long,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.wintypes.ULONG)),
    ]


class KeyboardBlocker:
    """Блокирует системные комбинации клавиш (Alt+Tab, Win, и т.д.) через WH_KEYBOARD_LL."""

    def __init__(self):
        self.enabled = threading.Event()
        self._hook = None
        self._thread = None
        self._thread_id = None
        # Храним ссылку на callback чтобы GC не собрал
        self._callback = HOOKPROC(self._hook_proc)

    def _hook_proc(self, nCode, wParam, lParam):
        """Low-level keyboard hook callback."""
        if nCode >= 0 and self.enabled.is_set():
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            flags = kb.flags
            alt_down = bool(flags & LLKHF_ALTDOWN)

            # Получаем состояние Ctrl и Shift
            ctrl_down = (user32.GetAsyncKeyState(0x11) & 0x8000) != 0
            shift_down = (user32.GetAsyncKeyState(0x10) & 0x8000) != 0

            should_block = False

            # Alt+Tab
            if alt_down and vk == VK_TAB:
                should_block = True
            # Alt+F4
            elif alt_down and vk == VK_F4:
                should_block = True
            # Alt+Escape
            elif alt_down and vk == VK_ESCAPE:
                should_block = True
            # Win key
            elif vk in (VK_LWIN, VK_RWIN):
                should_block = True
            # Ctrl+Escape (Start menu)
            elif ctrl_down and vk == VK_ESCAPE:
                should_block = True
            # Ctrl+Shift+Escape (Task Manager)
            elif ctrl_down and shift_down and vk == VK_ESCAPE:
                should_block = True

            if should_block:
                return 1  # Блокируем клавишу

        return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

    def _run_hook(self):
        """Запускает хук в отдельном потоке с message pump."""
        self._thread_id = kernel32.GetCurrentThreadId()

        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._callback,
            kernel32.GetModuleHandleW(None),
            0,
        )

        if not self._hook:
            return

        # Message pump — необходим для работы хука
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Снимаем хук при выходе из цикла
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None

    def start(self):
        """Запустить поток хука."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_hook, daemon=True)
        self._thread.start()

    def enable(self):
        """Включить блокировку клавиш."""
        self.enabled.set()

    def disable(self):
        """Выключить блокировку клавиш."""
        self.enabled.clear()

    def stop(self):
        """Остановить поток хука."""
        self.disable()
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
