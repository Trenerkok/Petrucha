import re
from typing import Optional, Dict
from config_manager import ConfigManager

class FastCommandMatcher:
    """
    Matches user text against regex patterns and dynamic config names.
    """
    
    def __init__(self):
        self.cfg = ConfigManager()

    def match(self, text: str) -> Optional[Dict]:
        text = text.lower().strip()

        # --- 1. Entries (Apps/Files/Sites) ---
        entries = self.cfg.get_entries()
        
        # Open
        if text.startswith("відкрий") or text.startswith("запусти"):
            target = text.replace("відкрий", "").replace("запусти", "").strip()
            if target:
                for entry in entries:
                    for vname in entry.get("voice_names", []):
                        if vname in target:
                            return {"intent": "OPEN_ENTRY", "params": {"entry_id": entry["id"]}}
        
        # Close
        if text.startswith("zakryi") or text.startswith("закрий") or text.startswith("вимкни"):
            target = text.replace("закрий", "").replace("вимкни", "").strip()
            if target:
                for entry in entries:
                    if entry.get("type") == "app":
                        for vname in entry.get("voice_names", []):
                            if vname in target:
                                return {"intent": "CLOSE_APP", "params": {"app_name": entry["id"]}}

        # --- 2. Workspaces ---
        workspaces = self.cfg.get_workspaces()
        for ws in workspaces:
            for vname in ws.get("voice_names", []):
                if vname in text:
                    return {"intent": "RUN_WORKSPACE", "params": {"workspace_id": ws["id"]}}

        # --- 3. IoT Devices ---
        devices = self.cfg.get_iot_devices()
        for dev in devices:
            for action in dev.get("actions", []):
                for phrase in action.get("voice_phrases", []):
                    if phrase in text:
                        return {
                            "intent": "IOT_ACTION", 
                            "params": {"device_id": dev["id"], "action_name": action["name"]}
                        }

        # --- 4. Window Management ---
        if "згорни" in text and ("все" in text or "всі" in text or "вікна" in text):
            return {"intent": "WINDOW_MANAGEMENT", "params": {"action": "minimize_all"}}
        if "покажи робочий стіл" in text:
            return {"intent": "WINDOW_MANAGEMENT", "params": {"action": "minimize_all"}}
        
        # --- 5. Notes ---
        if ("створи" in text or "почни" in text) and ("нотатк" in text or "запис" in text):
            return {"intent": "START_NOTES_SESSION", "params": {}}
        if ("зупини" in text or "заверши" in text) and ("нотатк" in text or "запис" in text):
            return {"intent": "STOP_NOTES_SESSION", "params": {}}
        if ("проаналізуй" in text) and ("нотатк" in text):
            return {"intent": "ANALYZE_NOTES", "params": {}}

        return None