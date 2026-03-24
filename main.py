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
from config import MSG_LUNCH, MSG_SLEEP, MSG_SHUTDOWN
from notification_overlay import NotificationOverlay

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
        self._lunch_end_time = None

        # Режим сна
        self._is_sleep_break = False
        self._sleep_triggered_date = None
        self._sleep_end_time = None

        # Расписание занятий
        self._is_in_class = False
        self._timer_paused_for_class = False

        # Автовыключение в 01:00
        self._shutdown_warnings_shown = set()  # уже показанные предупреждения (в секундах)
        self._shutdown_triggered = False
        self._shutdown_warning_overlay = None

        # Трей
        self.tray = TrayIcon(
            get_status_text=self._status_text,
            on_postpone=self._on_postpone,
            on_break_now=self._on_break_now,
            on_settings=self._on_settings,
        )
        self._update_tray_lunch_info()
        self._update_tray_sleep_info()

    def _status_text(self) -> str:
        if self._is_sleep_break:
            return "Время спать..."
        if self._is_lunch_break:
            return "Обеденный перерыв..."
        if self.is_break_active:
            return "Перерыв идёт..."
        if self._timer_paused_for_class:
            return "Занятие (таймер на паузе)"
        remaining = max(0, self.settings.work_duration_sec - self.activity.work_seconds)
        m, s = divmod(int(remaining), 60)
        return f"До перерыва: {m:02d}:{s:02d}"

    def _on_postpone(self):
        """Отложить перерыв."""
        if (self.is_break_active
                or self._is_lunch_break
                or self._is_sleep_break
                or self.postpone_count >= self.settings.max_postpones):
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

    def _update_tray_sleep_info(self):
        """Обновить информацию о сне в трее."""
        if self.settings.sleep_enabled:
            self.tray._sleep_info = f"{self.settings.sleep_start} – {self.settings.sleep_end}"
        else:
            self.tray._sleep_info = ""

    def _on_settings_saved(self):
        """Применить новые настройки без перезапуска."""
        self.activity.idle_threshold = self.settings.idle_threshold_sec
        self._update_tray_lunch_info()
        self._update_tray_sleep_info()
        remaining = max(0, self.settings.work_duration_sec - self.activity.work_seconds)
        self.tray.update(remaining_sec=remaining)

    # ===== Обычный перерыв =====

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
        """Перерыв завершён."""
        self.kb_blocker.disable()
        self.is_break_active = False
        self._is_lunch_break = False
        self._is_sleep_break = False
        self.tray.is_break_active = False
        self.tray.is_lunch_active = False
        self.tray.is_sleep_active = False
        self._lunch_end_time = None
        self._sleep_end_time = None

        # Сбрасываем счётчики
        self.postpone_count = 0
        self.tray.can_postpone = True
        self.activity.reset()
        self._warning_played = False

        self.tray.update(remaining_sec=self.settings.work_duration_sec)

    # ===== Обеденный перерыв =====

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
            warning_sec = self.settings.warning_duration_sec
            if remaining_sec <= warning_sec:
                return
            self._lunch_end_time = end
            self._start_lunch_break(remaining_sec)

    def _start_lunch_break(self, duration_sec: int):
        """Запустить обеденный перерыв с предупреждением."""
        self._is_lunch_break = True
        warning_sec = min(self.settings.warning_duration_sec, duration_sec - 10)
        self._warning_overlay = WarningOverlay(
            self.root, duration_sec=warning_sec,
            on_complete=lambda: self._show_lunch_overlay(),
        )
        self._warning_overlay.show()

    def _show_lunch_overlay(self):
        """Показать блокирующий оверлей обеда."""
        if self.is_break_active:
            return

        self._warning_overlay = None
        now = datetime.datetime.now()
        remaining = int((self._lunch_end_time - now).total_seconds())
        if remaining <= 0:
            self._is_lunch_break = False
            return

        self.is_break_active = True
        self.tray.is_break_active = True
        self.tray.is_lunch_active = True

        self.kb_blocker.enable()
        self.tray.update()

        self.overlay = BreakOverlay(
            self.root, remaining, self._on_break_done,
            message=MSG_LUNCH, show_exercises=False, allow_dismiss=False,
        )
        self.overlay.show()
        self._sync_scheduled_timer(self._lunch_end_time)

    # ===== Режим сна =====

    def _check_sleep(self):
        """Проверка режима сна."""
        if not self.settings.sleep_enabled or self.is_break_active:
            return

        today = datetime.date.today()
        if self._sleep_triggered_date == today:
            return

        now = datetime.datetime.now()
        try:
            sh, sm = self.settings.sleep_start.split(":")
            eh, em = self.settings.sleep_end.split(":")
            start = now.replace(hour=int(sh), minute=int(sm), second=0, microsecond=0)
            end_time = now.replace(hour=int(eh), minute=int(em), second=0, microsecond=0)
        except (ValueError, AttributeError):
            return

        # Сон переходит через полночь: 23:00 → 07:00
        if end_time <= start:
            if now >= start:
                # Вечер: после начала сна, конец завтра
                end_time += datetime.timedelta(days=1)
            elif now < end_time:
                # Утро: до конца сна, начало было вчера
                start -= datetime.timedelta(days=1)
            else:
                # Между концом и началом — не время сна
                return

        if start <= now < end_time:
            self._sleep_triggered_date = today
            remaining_sec = int((end_time - now).total_seconds())
            warning_sec = self.settings.warning_duration_sec
            if remaining_sec <= warning_sec:
                return
            self._sleep_end_time = end_time
            self._start_sleep_break(remaining_sec)

    def _start_sleep_break(self, duration_sec: int):
        """Запустить режим сна с предупреждением."""
        self._is_sleep_break = True
        warning_sec = min(self.settings.warning_duration_sec, duration_sec - 10)
        self._warning_overlay = WarningOverlay(
            self.root, duration_sec=warning_sec,
            on_complete=lambda: self._show_sleep_overlay(),
        )
        self._warning_overlay.show()

    def _show_sleep_overlay(self):
        """Показать блокирующий оверлей сна."""
        if self.is_break_active:
            return

        self._warning_overlay = None
        now = datetime.datetime.now()
        remaining = int((self._sleep_end_time - now).total_seconds())
        if remaining <= 0:
            self._is_sleep_break = False
            return

        self.is_break_active = True
        self.tray.is_break_active = True
        self.tray.is_sleep_active = True

        self.kb_blocker.enable()
        self.tray.update()

        self.overlay = BreakOverlay(
            self.root, remaining, self._on_break_done,
            message=MSG_SLEEP, show_exercises=False, allow_dismiss=False,
        )
        self.overlay.show()
        self._sync_scheduled_timer(self._sleep_end_time)

    # ===== Синхронизация таймера с реальным временем =====

    def _sync_scheduled_timer(self, end_time):
        """Периодически синхронизирует таймер оверлея с реальным временем."""
        if not self.overlay or not self.overlay.window:
            return
        now = datetime.datetime.now()
        remaining = int((end_time - now).total_seconds())
        if remaining <= 0:
            self._on_break_done()
            return
        self.overlay.update_remaining(remaining)
        self.root.after(10000, lambda: self._sync_scheduled_timer(end_time))

    # ===== Расписание занятий =====

    def _check_class_schedule(self):
        """Проверяет, идёт ли сейчас занятие. Если да — ставит таймер на паузу."""
        if not self.settings.class_schedule_enabled:
            if self._is_in_class:
                self._is_in_class = False
                self._timer_paused_for_class = False
                self.tray.is_class_paused = False
                self.tray._class_info = ""
            return

        now = datetime.datetime.now()
        weekday = now.weekday()  # Пн=0
        current_time_str = now.strftime("%H:%M")

        in_class = False
        class_end_str = ""

        for slot in self.settings.class_schedule:
            if weekday not in slot.get("days", []):
                continue
            slot_start = slot.get("start", "")
            slot_end = slot.get("end", "")
            if slot_start <= current_time_str < slot_end:
                in_class = True
                class_end_str = slot_end
                break

        if in_class and not self._is_in_class:
            # Вошли в окно занятия
            self._is_in_class = True
            self._timer_paused_for_class = True
            self.tray.is_class_paused = True
            self.tray._class_info = f"Занятие до {class_end_str}"
            # Отменяем предупреждение если оно висит
            if self._warning_overlay:
                self._warning_overlay.destroy()
                self._warning_overlay = None
                self._warning_played = False
        elif not in_class and self._is_in_class:
            # Вышли из окна занятия
            self._is_in_class = False
            self._timer_paused_for_class = False
            self.tray.is_class_paused = False
            self.tray._class_info = ""

    # ===== Автовыключение ПК =====

    def _check_auto_shutdown(self):
        """Проверка автовыключения в 01:00. Предупреждения за 10, 5, 1 мин и 30 сек."""
        if not self.settings.auto_shutdown_enabled or self._shutdown_triggered:
            return

        now = datetime.datetime.now()
        shutdown_time = now.replace(hour=1, minute=0, second=0, microsecond=0)

        # Если уже после 01:00 но до 05:00 — выключение уже должно было быть
        if now >= shutdown_time and now.hour < 5:
            self._shutdown_triggered = True
            self._do_shutdown()
            return

        # Если до полуночи — shutdown_time завтра
        if now.hour >= 5:
            shutdown_time += datetime.timedelta(days=1)

        remaining = int((shutdown_time - now).total_seconds())

        # Предупреждения: 600с (10мин), 300с (5мин), 60с (1мин), 30с
        thresholds = [
            (600, "Компьютер выключится через 10 минут"),
            (300, "Компьютер выключится через 5 минут"),
            (60, "Компьютер выключится через 1 минуту"),
        ]

        for threshold, message in thresholds:
            if (remaining <= threshold
                    and threshold not in self._shutdown_warnings_shown):
                self._shutdown_warnings_shown.add(threshold)
                notif = NotificationOverlay(self.root, text=message, duration_sec=10)
                notif.show()

        # 30 секунд — затемнение экрана
        if remaining <= 30 and 30 not in self._shutdown_warnings_shown:
            self._shutdown_warnings_shown.add(30)
            self._shutdown_warning_overlay = WarningOverlay(
                self.root, duration_sec=remaining,
                on_complete=self._do_shutdown,
            )
            # Меняем текст предупреждения
            self._shutdown_warning_overlay.show()

        if remaining <= 0:
            self._do_shutdown()

    def _do_shutdown(self):
        """Выключить компьютер."""
        self._shutdown_triggered = True
        import subprocess
        subprocess.Popen(["shutdown", "/s", "/t", "30"])

    # ===== Главный таймер =====

    def _check_timer(self):
        """Периодическая проверка — пора ли делать перерыв."""
        self._check_auto_shutdown()

        if not self.is_break_active:
            # Проверяем расписания
            self._check_lunch()
            self._check_sleep()
            self._check_class_schedule()

            if (not self.is_break_active
                    and not self._is_lunch_break
                    and not self._is_sleep_break
                    and not self._timer_paused_for_class):
                work_time = self.activity.tick()
                remaining = self.settings.work_duration_sec - work_time

                warning_sec = self.settings.warning_duration_sec
                if 0 < remaining <= warning_sec and not self._warning_played:
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
