import ctypes
import ctypes.wintypes
import time

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("dwTime", ctypes.wintypes.DWORD),
    ]


def get_idle_seconds():
    """Возвращает количество секунд с момента последнего ввода (мышь/клавиатура)."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        tick_count = ctypes.windll.kernel32.GetTickCount64()
        elapsed_ms = tick_count - lii.dwTime
        return elapsed_ms / 1000.0
    return 0.0


class ActivityMonitor:
    """Отслеживает активность пользователя за ПК.

    Таймер работы идёт только когда пользователь активен.
    Если нет активности > idle_threshold — считаем что пользователь ушёл.
    """

    def __init__(self, idle_threshold_sec: int = 300):
        self.idle_threshold = idle_threshold_sec
        self._accumulated_work_sec = 0.0
        self._last_check_time = time.monotonic()
        self._was_active = True

    def reset(self):
        """Сбросить накопленное рабочее время."""
        self._accumulated_work_sec = 0.0
        self._last_check_time = time.monotonic()
        self._was_active = True

    def tick(self) -> float:
        """Обновить состояние и вернуть накопленное рабочее время в секундах.

        Вызывать периодически (раз в секунду).
        Рабочее время увеличивается только если пользователь активен.
        """
        now = time.monotonic()
        delta = now - self._last_check_time
        self._last_check_time = now

        idle = get_idle_seconds()
        is_active = idle < self.idle_threshold

        if is_active:
            if self._was_active:
                # Был активен и остаётся — добавляем всё время
                self._accumulated_work_sec += delta
            else:
                # Вернулся из неактивности — не добавляем время простоя
                pass
        # Если не активен — время не добавляем

        self._was_active = is_active
        return self._accumulated_work_sec

    def subtract_time(self, seconds: float):
        """Уменьшить накопленное рабочее время (для отсрочки)."""
        self._accumulated_work_sec = max(0, self._accumulated_work_sec - seconds)

    @property
    def work_seconds(self) -> float:
        return self._accumulated_work_sec

    @property
    def is_user_active(self) -> bool:
        return get_idle_seconds() < self.idle_threshold
