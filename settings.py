import json
import os

# Путь к файлу настроек
_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
SETTINGS_DIR = os.path.join(_APPDATA, "BreakEnforcer")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

# Дефолтные упражнения
DEFAULT_EXERCISES = [
    # Разминка / растяжка
    "Наклоны головы влево-вправо, вперёд-назад",
    "Круговые вращения головой",
    "Вращение плечами вперёд и назад",
    "Поднимите руки вверх и потянитесь к потолку",
    "Замок за спиной — растяжка плеч",
    "Наклоны корпуса в стороны",
    "Скручивания корпуса сидя/стоя",
    "Круговые вращения кистями рук",
    "Растяжка запястий — ладонь к себе/от себя",
    "Махи руками — ножницы перед грудью",
    "Повороты корпуса с разведёнными руками",
    "Наклон вперёд — достать пальцами до пола",
    "Растяжка квадрицепса — согните ногу назад",
    "Вращение тазом по кругу",
    "Растяжка шеи — ухо к плечу с помощью руки",
    "Сведение лопаток — расправьте плечи",
    "Глубокий вдох-выдох с поднятием рук",
    "Растяжка икр — упор в стену, нога назад",
    "Растяжка грудных — руки в дверном проёме",
    "Кошка-корова стоя — прогиб и округление спины",
]

# Дефолтные значения
DEFAULTS = {
    "work_duration_min": 60,
    "break_duration_min": 3,
    "extended_break_min": 5,
    "postpone_min": 10,
    "max_postpones": 2,
    "idle_threshold_min": 5,
    "exercises": DEFAULT_EXERCISES,
    "lunch_enabled": False,
    "lunch_start": "13:00",
    "lunch_end": "14:00",
    "warning_duration_sec": 30,
    "sleep_enabled": False,
    "sleep_start": "23:00",
    "sleep_end": "07:00",
    "class_schedule_enabled": False,
    "class_schedule": [],
    "auto_shutdown_enabled": False,
}


def _valid_time(value: str) -> bool:
    """Проверяет формат HH:MM."""
    try:
        h, m = value.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, AttributeError):
        return False


class Settings:
    """Менеджер настроек. Загружает/сохраняет JSON в %APPDATA%/BreakEnforcer/."""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self._data["exercises"] = list(DEFAULT_EXERCISES)
        self.load()

    def load(self):
        """Загрузить настройки из файла. Если файла нет — используются дефолты."""
        if not os.path.exists(SETTINGS_FILE):
            return
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for key in DEFAULTS:
                if key in saved:
                    self._data[key] = saved[key]
        except Exception:
            pass

    def save(self):
        """Сохранить настройки в файл."""
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def reset_exercises(self):
        """Сбросить упражнения к дефолтным."""
        self._data["exercises"] = list(DEFAULT_EXERCISES)

    # --- Доступ к значениям (минуты) ---

    @property
    def work_duration_min(self) -> int:
        return self._data["work_duration_min"]

    @work_duration_min.setter
    def work_duration_min(self, value: int):
        self._data["work_duration_min"] = max(1, int(value))

    @property
    def break_duration_min(self) -> int:
        return self._data["break_duration_min"]

    @break_duration_min.setter
    def break_duration_min(self, value: int):
        self._data["break_duration_min"] = max(1, int(value))

    @property
    def extended_break_min(self) -> int:
        return self._data["extended_break_min"]

    @extended_break_min.setter
    def extended_break_min(self, value: int):
        self._data["extended_break_min"] = max(1, int(value))

    @property
    def postpone_min(self) -> int:
        return self._data["postpone_min"]

    @postpone_min.setter
    def postpone_min(self, value: int):
        self._data["postpone_min"] = max(1, int(value))

    @property
    def max_postpones(self) -> int:
        return self._data["max_postpones"]

    @max_postpones.setter
    def max_postpones(self, value: int):
        self._data["max_postpones"] = max(0, int(value))

    @property
    def idle_threshold_min(self) -> int:
        return self._data["idle_threshold_min"]

    @idle_threshold_min.setter
    def idle_threshold_min(self, value: int):
        self._data["idle_threshold_min"] = max(1, int(value))

    @property
    def exercises(self) -> list:
        return self._data["exercises"]

    @exercises.setter
    def exercises(self, value: list):
        self._data["exercises"] = list(value)

    @property
    def lunch_enabled(self) -> bool:
        return self._data["lunch_enabled"]

    @lunch_enabled.setter
    def lunch_enabled(self, value: bool):
        self._data["lunch_enabled"] = bool(value)

    @property
    def lunch_start(self) -> str:
        return self._data["lunch_start"]

    @lunch_start.setter
    def lunch_start(self, value: str):
        if _valid_time(value):
            self._data["lunch_start"] = value

    @property
    def lunch_end(self) -> str:
        return self._data["lunch_end"]

    @lunch_end.setter
    def lunch_end(self, value: str):
        if _valid_time(value):
            self._data["lunch_end"] = value

    @property
    def warning_duration_sec(self) -> int:
        return self._data["warning_duration_sec"]

    @warning_duration_sec.setter
    def warning_duration_sec(self, value: int):
        self._data["warning_duration_sec"] = max(5, min(120, int(value)))

    @property
    def sleep_enabled(self) -> bool:
        return self._data["sleep_enabled"]

    @sleep_enabled.setter
    def sleep_enabled(self, value: bool):
        self._data["sleep_enabled"] = bool(value)

    @property
    def sleep_start(self) -> str:
        return self._data["sleep_start"]

    @sleep_start.setter
    def sleep_start(self, value: str):
        if _valid_time(value):
            self._data["sleep_start"] = value

    @property
    def sleep_end(self) -> str:
        return self._data["sleep_end"]

    @sleep_end.setter
    def sleep_end(self, value: str):
        if _valid_time(value):
            self._data["sleep_end"] = value

    @property
    def class_schedule_enabled(self) -> bool:
        return self._data["class_schedule_enabled"]

    @class_schedule_enabled.setter
    def class_schedule_enabled(self, value: bool):
        self._data["class_schedule_enabled"] = bool(value)

    @property
    def class_schedule(self) -> list:
        return self._data["class_schedule"]

    @class_schedule.setter
    def class_schedule(self, value: list):
        validated = []
        for item in value:
            if (isinstance(item, dict)
                    and "days" in item and "start" in item and "end" in item
                    and isinstance(item["days"], list)
                    and all(isinstance(d, int) and 0 <= d <= 6 for d in item["days"])
                    and _valid_time(item["start"]) and _valid_time(item["end"])):
                validated.append(item)
        self._data["class_schedule"] = validated

    @property
    def auto_shutdown_enabled(self) -> bool:
        return self._data["auto_shutdown_enabled"]

    @auto_shutdown_enabled.setter
    def auto_shutdown_enabled(self, value: bool):
        self._data["auto_shutdown_enabled"] = bool(value)

    # --- Конвертеры в секунды (для остального кода) ---

    @property
    def work_duration_sec(self) -> int:
        return self.work_duration_min * 60

    @property
    def break_duration_sec(self) -> int:
        return self.break_duration_min * 60

    @property
    def extended_break_sec(self) -> int:
        return self.extended_break_min * 60

    @property
    def postpone_sec(self) -> int:
        return self.postpone_min * 60

    @property
    def idle_threshold_sec(self) -> int:
        return self.idle_threshold_min * 60


# Синглтон
_instance = None


def get_settings() -> Settings:
    """Получить глобальный экземпляр настроек."""
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance
