import os
import sys
import platform
import subprocess
import webbrowser
import logging
import datetime
import glob
import shutil
import time
import requests
from config_manager import ConfigManager

# Try importing automation libraries
try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import serial
except ImportError:
    serial = None

try:
    import paho.mqtt.publish as publish
except ImportError:
    publish = None

LOGGER = logging.getLogger(__name__)

class SystemController:
    """
    Handles OS-level interactions, IoT control, and workspace execution.
    """

    def __init__(self):
        self.cfg = ConfigManager()
        self.system = platform.system().lower()
        self.home_dir = os.path.expanduser("~")
        
        # Notes directory setup
        self.notes_dir = os.path.join(self.home_dir, "Documents", "Petrucha_Notes")
        if not os.path.exists(self.notes_dir):
            os.makedirs(self.notes_dir, exist_ok=True)

    # --- Generic Entry Control (Apps, Files, Folders, Sites) ---
    def open_entry(self, entry_id: str) -> str:
        """Opens a configured entry (app, file, folder, website)."""
        entry = self.cfg.get_entry_by_id(entry_id)
        if not entry:
            return f"Запис '{entry_id}' не знайдено в налаштуваннях."

        etype = entry.get("type", "app")
        path = entry.get("path_or_url", "")
        name = entry.get("display_name", entry_id)

        LOGGER.info(f"Opening entry: {name} ({etype}) -> {path}")

        try:
            if etype == "website":
                if not path.startswith("http"): path = "https://" + path
                webbrowser.open(path)
                return f"Відкриваю сайт: {name}"
            
            elif etype == "folder":
                if os.path.exists(path):
                    if "win" in self.system: os.startfile(path)
                    elif "darwin" in self.system: subprocess.Popen(["open", path])
                    else: subprocess.Popen(["xdg-open", path])
                    return f"Відкриваю папку: {name}"
                else:
                    return f"Папку не знайдено: {path}"

            elif etype == "file":
                if os.path.exists(path):
                    if "win" in self.system: os.startfile(path)
                    elif "darwin" in self.system: subprocess.Popen(["open", path])
                    else: subprocess.Popen(["xdg-open", path])
                    return f"Відкриваю файл: {name}"
                else:
                    return f"Файл не знайдено: {path}"

            elif etype == "app":
                # Use existing robust app opening logic if it's an exe
                if path and os.path.exists(path):
                    if "win" in self.system: subprocess.Popen(path)
                    elif "darwin" in self.system: subprocess.Popen(["open", path])
                    else: subprocess.Popen([path], shell=True)
                    return f"Запускаю програму: {name}"
                else:
                    # Try to resolve if path is empty or invalid
                    resolved = self._resolve_app_path(entry_id) # Fallback to auto-discovery
                    if resolved:
                        if "win" in self.system: subprocess.Popen(resolved)
                        else: subprocess.Popen([resolved], shell=True)
                        return f"Запускаю програму: {name}"
                    return f"Не можу знайти програму: {name}"
            
            return f"Невідомий тип запису: {etype}"

        except Exception as e:
            LOGGER.error(f"Error opening entry {name}: {e}")
            return f"Помилка при відкритті: {name}"

    def _resolve_app_path(self, app_id: str) -> str:
        # Simplified auto-discovery for common apps
        common_paths = [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            os.path.join(os.environ.get("AppData", ""), "Programs"),
            os.path.join(os.environ.get("LocalAppData", ""), "Programs")
        ]
        exe_map = {
            "steam": ["Steam\\Steam.exe"],
            "discord": ["Discord\\Update.exe", "Discord\\app-*\\Discord.exe"],
            "telegram": ["Telegram Desktop\\Telegram.exe"],
            "spotify": ["Spotify\\Spotify.exe"],
            "vscode": ["Microsoft VS Code\\Code.exe"],
            "browser": ["Google\\Chrome\\Application\\chrome.exe"],
        }
        candidates = exe_map.get(app_id, [f"{app_id}.exe"])
        if shutil.which(candidates[0]): return candidates[0]
        for base in common_paths:
            for sub in candidates:
                full = os.path.join(base, sub)
                if os.path.exists(full): return full
        return None

    def close_app(self, entry_id: str) -> str:
        """Closes an application by ID."""
        entry = self.cfg.get_entry_by_id(entry_id)
        name = entry.get("display_name", entry_id) if entry else entry_id
        
        # Determine process name
        proc_name = f"{entry_id}.exe"
        if entry and entry.get("type") == "app" and entry.get("path_or_url"):
            proc_name = os.path.basename(entry["path_or_url"])
        
        # Fallback map
        if not entry:
            proc_map = {"steam": "steam.exe", "discord": "discord.exe", "telegram": "telegram.exe", "browser": "chrome.exe"}
            proc_name = proc_map.get(entry_id, f"{entry_id}.exe")

        LOGGER.info(f"Closing app: {name} (proc: {proc_name})")
        
        closed = False
        if psutil:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() == proc_name.lower():
                        proc.terminate()
                        closed = True
                except: pass
        
        if not closed:
            try:
                cmd = f"taskkill /f /im {proc_name}" if "win" in self.system else f"pkill -f {proc_name}"
                subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                closed = True # Assume success if no error thrown, hard to verify without psutil
            except: pass

        return f"Закриваю {name}." if closed else f"Не знайшов запущений {name}."

    # --- IoT Control ---
    def run_iot_action(self, device_id: str, action_name: str) -> str:
        device = self.cfg.get_iot_device_by_id(device_id)
        if not device: return f"Пристрій '{device_id}' не знайдено."

        action = next((a for a in device.get("actions", []) if a["name"] == action_name), None)
        if not action: return f"Дія '{action_name}' не знайдена для {device['display_name']}."

        conn_type = device.get("connection_type")
        params = device.get("connection_params", {})
        payload_template = action.get("payload", "")

        LOGGER.info(f"IoT Action: {device['display_name']} -> {action['display_name']} ({conn_type})")

        try:
            if conn_type == "HTTP":
                url = params.get("url", "")
                method = params.get("method", "GET")
                # Simple template substitution if needed
                if payload_template:
                    # If payload is JSON-like, send as json, else params?
                    # For simplicity, assume GET params or POST body
                    pass 
                
                if method == "GET":
                    # Append payload to URL if it looks like query params
                    if "?" not in url and payload_template: url += f"?{payload_template}"
                    elif payload_template: url += f"&{payload_template}"
                    requests.get(url, timeout=5)
                elif method == "POST":
                    requests.post(url, data=payload_template, timeout=5)
                
                return f"Виконано: {device['display_name']} - {action['display_name']}"

            elif conn_type == "MQTT":
                if not publish: return "Бібліотека MQTT не встановлена."
                broker = params.get("broker", "localhost")
                topic = params.get("topic", "home/test")
                publish.single(topic, payload_template, hostname=broker)
                return f"MQTT: {device['display_name']} -> {action['display_name']}"

            elif conn_type == "Serial":
                if not serial: return "Бібліотека Serial не встановлена."
                port = params.get("port", "COM3")
                baud = int(params.get("baudrate", 9600))
                with serial.Serial(port, baud, timeout=1) as ser:
                    ser.write(payload_template.encode('utf-8'))
                return f"Serial: {device['display_name']} -> {action['display_name']}"

        except Exception as e:
            LOGGER.error(f"IoT Error: {e}")
            return f"Помилка IoT: {e}"

        return "Невідомий тип підключення."

    # --- Workspaces ---
    def run_workspace(self, workspace_id: str) -> str:
        ws = self.cfg.get_workspace_by_id(workspace_id)
        if not ws: return "Режим не знайдено."

        steps = ws.get("steps", [])
        display_name = ws.get("display_name", workspace_id)
        
        LOGGER.info(f"Running workspace: {display_name}")
        results = []
        
        for step in steps:
            action = step.get("action")
            try:
                if action == "OPEN_ENTRY":
                    eid = step.get("entry_id")
                    if eid: results.append(self.open_entry(eid))
                
                elif action == "CLOSE_APP":
                    eid = step.get("app_id")
                    if eid: results.append(self.close_app(eid))
                
                elif action == "OPEN_WEBSITE":
                    url = step.get("url")
                    if url: 
                        self.open_website(url)
                        results.append("Сайт відкрито")
                
                elif action == "WINDOW":
                    sub = step.get("subaction")
                    if sub == "minimize_all":
                        self.window_management("minimize_all")
                        results.append("Робочий стіл")
                
                elif action == "WAIT":
                    sec = int(step.get("seconds", 1))
                    time.sleep(sec)
                
                time.sleep(0.5)
            except Exception as e:
                LOGGER.error(f"Workspace step error: {e}")

        return f"Режим '{display_name}' виконано."

    # --- Legacy Helpers ---
    def open_website(self, url: str):
        if not url.startswith("http"): url = "https://" + url
        webbrowser.open(url)

    def window_management(self, action: str):
        if pyautogui and action == "minimize_all":
            if "win" in self.system: pyautogui.hotkey("win", "d")
            else: pyautogui.hotkey("super", "d")

    # --- Notes ---
    def create_note_file(self) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"Note_{timestamp}.md"
        path = os.path.join(self.notes_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Нотатки від {timestamp}\n\n")
        return path

    def append_to_note(self, path: str, text: str):
        if path and os.path.exists(path):
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"- {text}\n")

    def read_note(self, path: str) -> str:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: return f.read()
        return ""

    def get_latest_note(self) -> str:
        files = glob.glob(os.path.join(self.notes_dir, "*.md"))
        if not files: return ""
        return max(files, key=os.path.getctime)