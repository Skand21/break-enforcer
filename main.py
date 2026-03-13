import datetime
import os
import sys
import tkinter as tk

import ctypes

from settings import get_settings
from activity import ActivityMonitor
from keyboard_hook import KeyboardBlocker
from overlay import BreakOverlay
from warning_overlay import WarningOverlay
from tray import TrayIcon
from settings_window import SettingsWindow
from config import MSG_LUNCH

# DPI awareness для корректного отображения на HiDPI экранах
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _ensure_single_instance():
    """Не даёт запустить второй экземпляр. Возвращает handle мьютекса."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "BreakEnforcer_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(mutex)
        sys.exit(0)
    return mutex


class BreakEnforcer:
    """Главный класс приложения."""

    def __init__(self):
        self._mutex = _ensure_single_instance()

        self.root = tk.Tk()
        self.root.withdraw()  # Скрываем главное окно

        self.settings = get_settings()
        self.activity = ActivityMonitor(self.settings.idle_threshold_sec)
        self.kb_blocker = KeyboardBlocker()
        self.overlay = None
        self._settings_window = None

        self.postpone_count = 0
        self.is_break_active = False
        self._warning_played = False
        self._warning_overlay = None
        self._tray_update_counter = 0

        # Обеденный перерыв
        self._is_lunch_break = False
        self._lunch_triggered_date = None

        # Трей
        self.tray = TrayIcon(
            get_status_text=self._status_text,
            on_postpone=self._on_postpone,
            on_break_now=self._on_break_now,
            on_settings=self._on_settings,
            on_quit=self._on_quit,
        )
        self._update_tray_lunch_info()

    def _status_text(self) -> str:
        if self._is_lunch_break:
            return "Обеденный перерыв..."
        if self.is_break_active:
            return "Перерыв идёт..."
        remaining = max(0, self.settings.work_duration_sec - self.activity.work_seconds)
        m, s = divmod(int(remaining), 60)
        return f"До перерыва: {m:02d}:{s:02d}"

    def _on_postpone(self):
        """Отложить перерыв."""
        if self.is_break_active or self.postpone_count >= self.settings.max_postpones:
            return

        # Убираем предупреждение если оно показано
        if self._warning_overlay:
            self._warning_overlay.destroy()
            self._warning_overlay = None

        self.postpone_count += 1
        self.activity.subtract_time(self.settings.postpone_sec)
        self._warning_played = False

        if self.postpone_count >= self.settings.max_postpones:
            self.tray.can_postpone = False

        remaining = max(0, self.settings.work_duration_sec - self.activity.work_seconds)
        self.tray.update(remaining_sec=remaining)

    def _on_break_now(self):
        """Принудительный перерыв."""
        if not self.is_break_active:
            self.root.after(0, self._start_break)

    def _on_settings(self):
        """Открыть окно настроек."""
        self.root.after(0, self._show_settings)

    def _show_settings(self):
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self.root, on_save=self._on_settings_saved)
        self._settings_window.show()

    def _update_tray_lunch_info(self):
        """Обновить информацию об обеде в трее."""
        if self.settings.lunch_enabled:
            self.tray._lunch_info = f"{self.settings.lunch_start} – {self.settings.lunch_end}"
        else:
            self.tray._lunch_info = ""

    def _on_settings_saved(self):
        """Применить новые настройки без перезапуска."""
        self.activity.idle_threshold = self.settings.idle_threshold_sec
        self._update_tray_lunch_info()
        remaining = max(0, self.settings.work_duration_sec - self.activity.work_seconds)
        self.tray.update(remaining_sec=remaining)

    def _on_quit(self):
        """Выход из приложения."""
        self.kb_blocker.stop()
        self.tray.stop()
        self.root.after(0, self.root.quit)

    def _start_break(self):
        """Показать оверлей перерыва."""
        if self.is_break_active:
            return

        # Убираем предупреждение если ещё висит
        if self._warning_overlay:
            self._warning_overlay.destroy()
            self._warning_overlay = None

        self.is_break_active = True
        self.tray.is_break_active = True

        # Длительность зависит от количества отложений
        duration = (self.settings.extended_break_sec
                    if self.postpone_count > 0
                    else self.settings.break_duration_sec)

        self.kb_blocker.enable()
        self.tray.update()

        self.overlay = BreakOverlay(
            self.root, duration, self._on_break_done,
            exercises=self.settings.exercises,
        )
        self.overlay.show()

    def _on_break_done(self):
        """Перерыв завершён (кнопка нажата)."""
        self.kb_blocker.disable()
        self.is_break_active = False
        self._is_lunch_break = False
        self.tray.is_break_active = False
        self.tray.is_lunch_active = False

        # Сбрасываем счётчики
        self.postpone_count = 0
        self.tray.can_postpone = True
        self.activity.reset()
        self._warning_played = False

        self.tray.update(remaining_sec=self.settings.work_duration_sec)

    def _check_lunch(self):
        """Проверка обеденного перерыва."""
        if not self.settings.lunch_enabled or self.is_break_active:
            return

        today = datetime.date.today()
        if self._lunch_triggered_date == today:
            return

        now = datetime.datetime.now()
        try:
            sh, sm = self.settings.lunch_start.split(":")
            eh, em = self.settings.lunch_end.split(":")
            start = now.replace(hour=int(sh), minute=int(sm), second=0, microsecond=0)
            end = now.replace(hour=int(eh), minute=int(em), second=0, microsecond=0)
        except (ValueError, AttributeError):
            return

        if start <= now < end:
            self._lunch_triggered_date = today
            remaining_sec = int((end - now).total_seconds())
            if remaining_sec <= 30:
                # Слишком мало осталось — не блокируем
                return
            self._start_lunch_break(remaining_sec)

    def _start_lunch_break(self, duration_sec: int):
        """Запустить обеденный перерыв с предупреждением."""
        self._is_lunch_break = True
        self._warning_overlay = WarningOverlay(
            self.root, duration_sec=30,
            on_complete=lambda: self._show_lunch_overlay(duration_sec - 30),
        )
        self._warning_overlay.show()

    def _show_lunch_overlay(self, duration_sec: int):
        """Показать блокирующий оверлей обеда."""
        if self.is_break_active:
            return

        self._warning_overlay = None
        self.is_break_active = True
        self.tray.is_break_active = True
        self.tray.is_lunch_active = True

        self.kb_blocker.enable()
        self.tray.update()

        self.overlay = BreakOverlay(
            self.root, duration_sec, self._on_break_done,
            message=MSG_LUNCH, show_exercises=False,
        )
        self.overlay.show()

    def _check_timer(self):
        """Периодическая проверка — пора ли делать перерыв."""
        if not self.is_break_active:
            # Проверяем обед
            self._check_lunch()

            if not self.is_break_active and not self._is_lunch_break:
                work_time = self.activity.tick()
                remaining = self.settings.work_duration_sec - work_time

                # Визуальное предупреждение за 30 секунд
                if 0 < remaining <= 30 and not self._warning_played:
                    self._warning_played = True
                    self._warning_overlay = WarningOverlay(
                        self.root, duration_sec=int(remaining),
                        on_complete=self._start_break,
                    )
                    self._warning_overlay.show()

                if remaining <= 0 and not self._warning_overlay:
                    self._start_break()

        # Обновляем трей каждые 10 секунд
        self._tray_update_counter += 1
        if self._tray_update_counter >= 10:
            self._tray_update_counter = 0
            remaining = max(0, self.settings.work_duration_sec - self.activity.work_seconds)
            self.tray.update(remaining_sec=remaining)

        self.root.after(1000, self._check_timer)

    def run(self):
        """Запуск приложения."""
        # Запуск компонентов
        self.kb_blocker.start()
        self.tray.start(remaining_sec=self.settings.work_duration_sec)

        # Запуск проверки таймера
        self.root.after(1000, self._check_timer)

        # Автозапуск — добавляем в автозагрузку Windows
        _setup_autostart()

        # Главный цикл tkinter
        self.root.mainloop()


def _setup_autostart():
    """Добавляет приложение в автозагрузку Windows (папка Startup)."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        if getattr(sys, 'frozen', False):
            # PyInstaller .exe
            command = f'"{sys.executable}"'
        else:
            # Обычный Python
            exe_path = sys.executable
            script_path = os.path.abspath(__file__)
            command = f'"{exe_path}" "{script_path}"'

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "BreakEnforcer", 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
    except Exception:
        pass  # Не критично если не удалось


if __name__ == "__main__":
    app = BreakEnforcer()
    app.run()
