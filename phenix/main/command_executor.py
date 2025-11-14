from __future__ import annotations
import random
import logging
from typing import Callable, Optional

LOGGER = logging.getLogger(__name__)

VoiceCallback = Callable[[str], None]
LegacyExecutor = Callable[[str, Optional[str]], None]


class CommandExecutor:
    """Handle structured command dictionaries produced by the NLU layer."""

    def __init__(self, speak: VoiceCallback, legacy_execute: LegacyExecutor) -> None:
        self._speak = speak
        self._legacy_execute = legacy_execute

    def execute(self, command: dict) -> bool:
        """Execute a structured command. Returns True if handled."""
        if not isinstance(command, dict):
            return False

        intent = command.get("intent")
        if not intent:
            return False

        LOGGER.info("Structured intent received: %s", intent)
        LOGGER.debug("Full command payload: %s", command)

        if command.get("confirmation_required") and intent not in {"ask_clarification", "smalltalk", "unknown"}:
            message = command.get("notes") or "Потрібно підтвердження. Повторіть, будь ласка."
            self._speak(message)
            return True

        handler = getattr(self, f"_handle_{intent}", None)
        if callable(handler):
            return bool(handler(command))

        LOGGER.warning("No handler for intent '%s'", intent)
        self._speak("Поки що не можу виконати цю дію.")
        return False

    # --- Intent handlers -------------------------------------------------

    def _handle_turn_on(self, command: dict) -> bool:
        device_type = command.get("device_type")
        if device_type in {"lamp", "group"}:
            self._legacy_execute("lamp", "")
            answer = command.get("answer_uk")
            if answer:
                self._speak(answer)
            return True
        if device_type == "system" and command.get("device_name") == "комп'ютер":
            self._speak("Комп'ютер уже увімкнений.")
            return True
        self._speak("Не знаю, як увімкнути цей пристрій.")
        return False

    def _handle_turn_off(self, command: dict) -> bool:
        device_type = command.get("device_type")
        if device_type in {"lamp", "group"}:
            self._legacy_execute("lamp_off", "")
            answer = command.get("answer_uk")
            if answer:
                self._speak(answer)
            return True
        if device_type == "system" and command.get("device_name") == "комп'ютер":
            self._legacy_execute("power_off", "")
            return True
        self._speak("Не знаю, як вимкнути цей пристрій.")
        return False

    def _handle_set_brightness(self, command: dict) -> bool:
        value = self._extract_number(command.get("value"))
        if value is None:
            self._speak("Потрібно сказати рівень яскравості у відсотках.")
            return True
        if not 0 <= value <= 100:
            self._speak("Яскравість має бути від 0 до 100 відсотків.")
            return True
        self._speak("Наразі я не вмію керувати яскравістю, але запам'ятав прохання.")
        return True

    def _handle_set_temperature(self, command: dict) -> bool:
        temperature = self._extract_number(command.get("temperature"))
        if temperature is None:
            self._speak("Скажіть, будь ласка, яку температуру потрібно встановити.")
            return True
        if not 10 <= temperature <= 30:
            self._speak("Температуру можна встановлювати від 10 до 30 градусів.")
            return True
        self._speak("Ще не вмію керувати кондиціонером, але передам побажання.")
        return True

    def _handle_open_curtains(self, command: dict) -> bool:
        self._speak("Поки що штори не підключені до системи.")
        return True

    def _handle_close_curtains(self, command: dict) -> bool:
        self._speak("Поки що штори не підключені до системи.")
        return True

    def _handle_set_mode(self, command: dict) -> bool:
        mode = command.get("mode")
        if not mode:
            self._speak("Який режим потрібно активувати?")
            return True
        self._speak(f"Запам'ятав режим {mode}, але поки не можу його встановити.")
        return True

    def _handle_ask_clarification(self, command: dict) -> bool:
        """Коли моделі бракує одного важливого параметра."""
        message = command.get("notes") or command.get("answer_uk")
        if not message:
            message = "Я не до кінця зрозумів. Спробуй, будь ласка, сказати це інакше або уточнити деталі."
        self._speak(message)
        return True

    def _handle_activate_scene(self, command: dict) -> bool:
        scene = command.get("group_name") or command.get("mode") or command.get("device_name")
        if scene:
            self._speak(f"Сцена {scene} поки що не налаштована.")
        else:
            self._speak("Яка сцена вас цікавить?")
        return True

    def _handle_smalltalk(self, command: dict) -> bool:
        """Невимушена розмова / привітання."""
        answer = command.get("answer_uk")
        if not answer:
            canned = [
                "Все нормально, працюю і слухаю тебе. А як ти?",
                "Потихеньку, головне, що ти мене не вимикаєш.",
                "Нормально, стежу за тим, що ти робиш.",
                "Та живу собі в залізі, все стабільно.",
            ]
            answer = random.choice(canned)
        self._speak(answer)
        return True

    def _handle_unknown(self, command: dict) -> bool:
        """Коли взагалі незрозуміло, що від користувача потрібно."""
        answer = command.get("answer_uk")
        if not answer:
            answer = "Я не зрозумів, що ти маєш на увазі. Можеш переформулювати простішими словами?"
        self._speak(answer)
        return True

    # --- Helpers ---------------------------------------------------------

    @staticmethod
    def _extract_number(value: Optional[object]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            LOGGER.warning("Cannot interpret value '%s' as number", value)
            return None