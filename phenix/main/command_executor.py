from __future__ import annotations
import logging
import random
from typing import Callable, Optional
from system_controller import SystemController

LOGGER = logging.getLogger(__name__)

VoiceCallback = Callable[[str], None]
LegacyExecutor = Callable[[str, Optional[str]], None]

class CommandExecutor:
    """
    Routes structured commands (intents) to the appropriate controller.
    """

    def __init__(self, speak: VoiceCallback, legacy_execute: LegacyExecutor) -> None:
        self._speak = speak
        self._legacy_execute = legacy_execute
        self.sys_ctrl = SystemController()

    def execute(self, command: dict) -> bool:
        if not isinstance(command, dict): return False

        intent = command.get("intent")
        params = command.get("params", {})
        answer_uk = command.get("answer_uk")

        if not intent: return False

        LOGGER.info(f"Executing Intent: {intent} | Params: {params}")

        if answer_uk and intent not in ["OPEN_ENTRY", "CLOSE_APP", "RUN_WORKSPACE", "IOT_ACTION"]:
            self._speak(answer_uk)

        # --- Handlers ---

        if intent == "OPEN_ENTRY" or intent == "OPEN_APP":
            # Unified handler
            eid = params.get("entry_id") or params.get("app_name")
            res = self.sys_ctrl.open_entry(eid)
            self._speak(res)
            return True

        elif intent == "CLOSE_APP":
            app_name = params.get("app_name", "")
            res = self.sys_ctrl.close_app(app_name)
            self._speak(res)
            return True

        elif intent == "RUN_WORKSPACE":
            ws_id = params.get("workspace_id", "")
            res = self.sys_ctrl.run_workspace(ws_id)
            self._speak(res)
            return True

        elif intent == "IOT_ACTION":
            dev_id = params.get("device_id")
            act_name = params.get("action_name")
            res = self.sys_ctrl.run_iot_action(dev_id, act_name)
            self._speak(res)
            return True

        elif intent == "WINDOW_MANAGEMENT":
            action = params.get("action", "")
            self.sys_ctrl.window_management(action)
            self._speak("Виконую.")
            return True

        elif intent == "START_NOTES_SESSION":
            self._speak("Починаю запис нотаток.")
            return True

        elif intent == "STOP_NOTES_SESSION":
            self._speak("Запис нотаток завершено.")
            return True

        elif intent == "ANALYZE_NOTES":
            self._speak("Аналізую нотатки...")
            return True

        elif intent == "SMALLTALK":
            return True

        elif intent == "UNKNOWN":
            return False

        return False