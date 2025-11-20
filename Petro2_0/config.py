import json
import os
import logging

LOGGER = logging.getLogger(__name__)
CONFIG_FILE = "petro_config.json"

class Config:
    """
    Singleton for configuration management.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.load()
        return cls._instance

    def load(self):
        self.data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                LOGGER.error(f"Failed to load config: {e}")

        # Defaults
        defaults = {
            "stt_backend": "vosk",
            "llm_backend": "local",
            "tts_engine": "silero",     # Changed default to silero
            "muted": False,
            "wake_word_enabled": True,
            "gemini_key": "",
            "gemini_model": "gemini-1.5-flash",
            "local_llm_url": "http://127.0.0.1:1234",
            "entries": [],
            "workspaces": [],
            "iot_devices": []
        }

        for key, val in defaults.items():
            if key not in self.data:
                self.data[key] = val

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            LOGGER.error(f"Failed to save config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    # --- Robust List Management ---
    def get_entries(self): 
        return list(self.data.get("entries", []))

    def update_entries(self, new_list):
        self.data["entries"] = new_list
        self.save()

    def get_workspaces(self): 
        return list(self.data.get("workspaces", []))

    def update_workspaces(self, new_list):
        self.data["workspaces"] = new_list
        self.save()

    def get_iot_devices(self): 
        return list(self.data.get("iot_devices", []))

    def update_iot_devices(self, new_list):
        self.data["iot_devices"] = new_list
        self.save()