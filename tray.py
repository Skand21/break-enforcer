import threading
from PIL import Image, ImageDraw, ImageFont
import pystray
from config import MSG_TRAY_TITLE


def create_icon_image(color="#4CAF50", text="B"):
    """Генерирует иконку 64x64 с текстом (время или буква)."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill=color, outline="#ffffff", width=2)

    # Размер шрифта зависит от длины текста
    if len(text) <= 2:
        font_size = 30
    elif len(text) <= 3:
        font_size = 24
    else:
        font_size = 18

    try:
        font = ImageFont.truetype("segoeui.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    draw.text((32, 32), text, fill="#ffffff", font=font, anchor="mm")
    return img


class TrayIcon:
    """Иконка в системном трее с меню управления."""

    def __init__(self, get_status_text, on_postpone, on_break_now, on_settings):
        """
        get_status_text: callable -> str, возвращает "До перерыва: XX:XX"
        on_postpone: callable, вызывается при отложении
        on_break_now: callable, вызывается для немедленного перерыва
        on_settings: callable, вызывается для открытия настроек
        """
        self._get_status = get_status_text
        self._on_postpone = on_postpone
        self._on_break_now = on_break_now
        self._on_settings = on_settings
        self._icon = None
        self._thread = None
        self.can_postpone = True
        self.is_break_active = False
        self.is_lunch_active = False
        self.is_sleep_active = False
        self.is_class_paused = False
        self._lunch_info = ""
        self._sleep_info = ""
        self._class_info = ""

    def _create_menu(self):
        items = [
            pystray.MenuItem(
                lambda item: self._get_status(),
                lambda icon, item: None,
                enabled=False,
            ),
        ]

        # Информация об обеде
        if self._lunch_info:
            items.append(pystray.MenuItem(
                lambda item: f"Обед: {self._lunch_info}",
                lambda icon, item: None,
                enabled=False,
            ))

        # Информация о сне
        if self._sleep_info:
            items.append(pystray.MenuItem(
                lambda item: f"Сон: {self._sleep_info}",
                lambda icon, item: None,
                enabled=False,
            ))

        # Информация о занятии
        if self._class_info:
            items.append(pystray.MenuItem(
                lambda item: self._class_info,
                lambda icon, item: None,
                enabled=False,
            ))

        is_scheduled = self.is_lunch_active or self.is_sleep_active

        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Отложить на 10 мин",
                lambda icon, item: self._on_postpone(),
                enabled=lambda item: (self.can_postpone
                                      and not self.is_break_active
                                      and not is_scheduled),
            ),
            pystray.MenuItem(
                "Перерыв сейчас",
                lambda icon, item: self._on_break_now(),
                enabled=lambda item: (not self.is_break_active
                                      and not is_scheduled),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Настройки",
                lambda icon, item: self._on_settings(),
                enabled=lambda item: (not self.is_break_active
                                      and not is_scheduled),
            ),
        ]
        return pystray.Menu(*items)

    def start(self, remaining_sec=None):
        """Запустить иконку в отдельном потоке."""
        if remaining_sec is not None:
            minutes = int(remaining_sec) // 60
            text = f"{minutes}m" if minutes > 0 else "<1"
        else:
            text = "60m"
        self._icon = pystray.Icon(
            MSG_TRAY_TITLE,
            create_icon_image(text=text),
            MSG_TRAY_TITLE,
            menu=self._create_menu(),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def update(self, remaining_sec=None):
        """Обновить меню, tooltip и иконку с временем."""
        if not self._icon or (self._thread and not self._thread.is_alive()):
            self._restart(remaining_sec)
            return
        try:
            status = self._get_status()
            self._icon.title = status
            self._icon.update_menu()

            # Рисуем время на иконке
            if self.is_sleep_active:
                self._icon.icon = create_icon_image("#9C27B0", "Z")
            elif self.is_lunch_active:
                self._icon.icon = create_icon_image("#2196F3", "L")
            elif self.is_break_active:
                self._icon.icon = create_icon_image("#FF5722", "!")
            elif self.is_class_paused:
                self._icon.icon = create_icon_image("#FF9800", "C")
            elif remaining_sec is not None:
                minutes = int(remaining_sec) // 60
                text = f"{minutes}m" if minutes > 0 else "<1"
                self._icon.icon = create_icon_image("#4CAF50", text)
        except Exception:
            # Иконка могла быть уничтожена — пересоздаём
            self._restart(remaining_sec)

    def _restart(self, remaining_sec=None):
        """Пересоздать иконку если она пропала."""
        try:
            if self._icon:
                self._icon.stop()
        except Exception:
            pass
        self._icon = None
        self.start(remaining_sec)

    def update_icon_color(self, color):
        """Сменить цвет иконки."""
        if self._icon:
            self._icon.icon = create_icon_image(color)

    def stop(self):
        """Остановить иконку."""
        if self._icon:
            self._icon.stop()
