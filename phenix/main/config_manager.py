import json
import os
import logging

LOGGER = logging.getLogger(__name__)

CONFIG_FILE = "petro_config.json"

class ConfigManager:
    """
    Singleton class to manage configuration loading and saving.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.load()
        return cls._instance

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                LOGGER.error(f"Failed to load config: {e}")
                self.data = {}
        else:
            self.data = {}
        
        # --- Defaults ---
        defaults = {
            "stt_backend": "vosk",
            "llm_backend_default": "local",
            "tts_engine": "gtts",
            "muted": False,
            "gemini_model": "gemini-1.5-flash",
            "apps": [],       # Now "entries" (apps, files, folders, sites)
            "workspaces": [],
            "iot_devices": [] # New IoT config
        }

        for key, val in defaults.items():
            if key not in self.data:
                self.data[key] = val

        # --- Migration: Ensure 'apps' has correct structure ---
        if not isinstance(self.data["apps"], list):
            self.data["apps"] = []

        # --- Migration: Ensure 'iot_devices' exists ---
        if "iot_devices" not in self.data:
            self.data["iot_devices"] = []

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    # --- Entries (Apps/Files/Sites) Management ---
    def get_entries(self):
        return self.data.get("apps", [])

    def get_entry_by_id(self, entry_id):
        for entry in self.data.get("apps", []):
            if entry.get("id") == entry_id:
                return entry
        return None

    def update_entries(self, entries_list):
        self.data["apps"] = entries_list
        self.save()

    # --- Workspace Management ---
    def get_workspaces(self):
        return self.data.get("workspaces", [])

    def get_workspace_by_id(self, ws_id):
        for ws in self.data.get("workspaces", []):
            if ws.get("id") == ws_id:
                return ws
        return None

    def update_workspaces(self, ws_list):
        self.data["workspaces"] = ws_list
        self.save()

    # --- IoT Management ---
    def get_iot_devices(self):
        return self.data.get("iot_devices", [])

    def get_iot_device_by_id(self, dev_id):
        for dev in self.data.get("iot_devices", []):
            if dev.get("id") == dev_id:
                return dev
        return None

    def update_iot_devices(self, dev_list):
        self.data["iot_devices"] = dev_list
        self.save()

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            LOGGER.error(f"Failed to save config: {e}")