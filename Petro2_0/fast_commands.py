import re
from typing import Optional, Dict
from config import Config

class FastCommandMatcher:
    def __init__(self):
        self.cfg = Config()

    def match(self, text: str) -> Optional[Dict]:
        text = text.lower().strip()

        # --- COURSEWORK DEFENSE ---
        if "що ти вмієш" in text or "твої можливості" in text:
            return {"intent": "DEFENSE_CAPABILITIES", "params": {}}
        
        if "як ти працюєш" in text or "твоя архітектура" in text or "принцип роботи" in text:
             return {"intent": "DEFENSE_ARCHITECTURE", "params": {}}

        # --- 1. Entries ---
        entries = self.cfg.get_entries()
        if text.startswith("відкрий") or text.startswith("запусти"):
            target = text.replace("відкрий", "").replace("запусти", "").strip()
            for entry in entries:
                for vname in entry.get("voice_phrases", []):
                    if vname in target:
                        return {"intent": "OPEN_ENTRY", "params": {"entry_id": entry["id"]}}
        
        if text.startswith("закрий") or text.startswith("вимкни"):
            target = text.replace("закрий", "").replace("вимкни", "").strip()
            for entry in entries:
                if entry.get("type") == "app":
                    for vname in entry.get("voice_phrases", []):
                        if vname in target:
                            return {"intent": "CLOSE_APP", "params": {"app_name": entry["id"]}}

        # --- 2. Protocols (Workspaces) ---
        workspaces = self.cfg.get_workspaces()
        for ws in workspaces:
            for vname in ws.get("voice_phrases", []):
                if vname in text:
                    return {"intent": "RUN_WORKSPACE", "params": {"workspace_id": ws["id"]}}

        # --- 3. IoT ---
        for dev in self.cfg.get_iot_devices():
            for action in dev.get("actions", []):
                for phrase in action.get("voice_phrases", []):
                    if phrase in text:
                        import re
                        num_match = re.search(r'\d+', text)
                        val = int(num_match.group()) if num_match else None
                        return {
                            "intent": "IOT_ACTION", 
                            "params": {"device_id": dev["id"], "action_name": action["name"], "value": val}
                        }

        # --- 4. Timer ---
        if "таймер" in text or "засічи" in text:
            m = re.search(r'(\d+)\s*(хв|мін)', text)
            if m: return {"intent": "START_TIMER", "params": {"minutes": int(m.group(1))}}
        if "стоп" in text and "таймер" in text:
             return {"intent": "STOP_TIMER", "params": {}}

        # --- 5. System ---
        if "згорни" in text and "вікна" in text:
            return {"intent": "WINDOW_MANAGEMENT", "params": {"action": "minimize_all"}}
        if "покажи робочий стіл" in text:
            return {"intent": "WINDOW_MANAGEMENT", "params": {"action": "minimize_all"}}
        
        # --- 6. Notes/Memory ---
        if "запам'ятай" in text: return {"intent": "REMEMBER_FACT", "params": {"text": text}}
        if "очисти" in text and "пам'ят" in text: return {"intent": "CLEAR_MEMORY", "params": {}}
        
        if "що" in text and "екрані" in text: return {"intent": "VISION_QUERY", "params": {}}
        if "статистик" in text: return {"intent": "SYSTEM_STATS", "params": {}}

        return None