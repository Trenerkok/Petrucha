from __future__ import annotations
import logging
# FIX: Correct import
from system_io import SystemIO 

LOGGER = logging.getLogger(__name__)

class CommandExecutor:
    def __init__(self, speak, legacy_execute) -> None:
        self._speak = speak
        self._legacy_execute = legacy_execute
        self.sys_ctrl = SystemIO()

    def execute(self, command: dict) -> bool:
        if not isinstance(command, dict): return False
        intent = command.get("intent")
        params = command.get("params", {})
        
        LOGGER.info(f"Executing: {intent}")

        if intent == "DEFENSE_CAPABILITIES":
            text = (
                "Я — Петруча, інтелектуальний голосовий асистент. "
                "Я вмію керувати комп'ютером, запускати програми, шукати інформацію в інтернеті, "
                "керувати IoT пристроями та аналізувати зображення з екрану."
            )
            self._speak(text)
            return True

        if intent == "DEFENSE_ARCHITECTURE":
            text = (
                "Моя архітектура складається з модулів розпізнавання мови, "
                "обробки природної мови на базі LLM, "
                "системи виконання команд та нейронного синтезу мови."
            )
            self._speak(text)
            return True

        if intent == "OPEN_ENTRY": 
            self._speak(self.sys_ctrl.open_entry(params.get("entry_id")))
            return True
        
        if intent == "CLOSE_APP":
            self._speak(self.sys_ctrl.close_app(params.get("app_name")))
            return True

        if intent == "RUN_WORKSPACE":
            self._speak(self.sys_ctrl.run_workspace(params.get("workspace_id")))
            return True

        if intent == "IOT_ACTION":
            self._speak(self.sys_ctrl.run_iot_action(params.get("device_id"), params.get("action_name"), params.get("value")))
            return True

        if intent == "WINDOW_MANAGEMENT":
            self._speak(self.sys_ctrl.window_action(params.get("action")))
            return True
            
        if intent == "SYSTEM_STATS":
            self._speak(self.sys_ctrl.get_system_stats())
            return True

        if intent == "VISION_QUERY":
             # Vision is handled in assistant_core, executor just returns true to prevent double speak
             return True

        if intent == "START_NOTES_SESSION":
             self._speak("Починаю запис нотаток.")
             return True

        if intent == "STOP_NOTES_SESSION":
             self._speak("Запис завершено.")
             return True

        if intent == "ANALYZE_NOTES":
             # Handled in core logic
             return True
             
        return False