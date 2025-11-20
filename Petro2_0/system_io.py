import os
import platform
import subprocess
import webbrowser
import logging
import shutil
import time
import requests
import glob
import json
import base64
from datetime import datetime
from config import Config
from io import BytesIO

# Optional imports
try: import pyautogui
except ImportError: pyautogui = None
try: import psutil
except ImportError: psutil = None
try: import serial
except ImportError: serial = None
try: import paho.mqtt.publish as publish
except ImportError: publish = None
try: from duckduckgo_search import DDGS
except ImportError: DDGS = None

LOGGER = logging.getLogger(__name__)

class SystemIO:
    """
    Handles OS-level operations: apps, files, media, IoT, System Stats, Web Search, Notes.
    """
    def __init__(self):
        self.cfg = Config()
        self.system = platform.system().lower()
        self.home_dir = os.path.expanduser("~")
        self.notes_dir = os.path.join(self.home_dir, "Documents", "Petrucha_Notes")
        if not os.path.exists(self.notes_dir):
            os.makedirs(self.notes_dir, exist_ok=True)

    # --- System Monitoring ---
    def get_system_stats(self) -> str:
        if not psutil: return "Модуль psutil не встановлено."
        
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        
        report = f"Завантаження процесора: {cpu}%.\n"
        report += f"Використано оперативної пам'яті: {mem.percent}% ({round(mem.used/1024**3, 1)} ГБ).\n"
        
        battery = psutil.sensors_battery()
        if battery:
            plugged = "на зарядці" if battery.power_plugged else "від батареї"
            report += f"Заряд батареї: {battery.percent}% ({plugged})."
            
        return report

    # --- Web Search (Agent) ---
    def web_search(self, query: str) -> str:
        """Returns text results from DuckDuckGo."""
        if not DDGS: return "Модуль пошуку не встановлено."
        
        LOGGER.info(f"Searching web for: {query}")
        try:
            # Try-catch block specifically for DDGS connectivity issues
            results = DDGS().text(query, max_results=3)
            if not results: return "Нічого не знайшов."
            
            summary = ""
            for r in results:
                summary += f"- {r['title']}: {r['body']}\n"
            return summary
        except Exception as e:
            LOGGER.error(f"Search error: {e}")
            return "Не вдалося виконати пошук (помилка з'єднання)."

    # --- Vision Helpers ---
    def get_screenshot_base64(self) -> str:
        """Returns optimized screen image as base64 string for Gemini."""
        if not pyautogui: return None
        try:
            img = pyautogui.screenshot()
            
            # OPTIMIZATION: Resize if image is huge to prevent API 503 errors
            # Max dimension 1024px is usually enough for LLM to read text
            img.thumbnail((1024, 1024))
            
            # Convert to RGB (JPEG doesn't support Alpha channel)
            img = img.convert("RGB")
            
            buffered = BytesIO()
            # Save as JPEG with compression
            img.save(buffered, format="JPEG", quality=80)
            
            return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            LOGGER.error(f"Screenshot error: {e}")
            return None

    # --- Entries (Apps, Files, Folders, Sites) ---
    def open_entry(self, entry_id: str) -> str:
        entries = self.cfg.get_entries()
        entry = next((e for e in entries if e["id"] == entry_id), None)
        
        if not entry: 
            return self._open_raw_app(entry_id)

        etype = entry.get("type", "app")
        path = entry.get("path", "")
        name = entry.get("name", entry_id)

        LOGGER.info(f"Opening {name} ({etype}) -> {path}")

        try:
            if etype == "website":
                if not path.startswith("http"): path = "https://" + path
                webbrowser.open(path)
                return f"Відкриваю сайт: {name}"
            
            elif etype in ["folder", "file"]:
                if os.path.exists(path):
                    if "win" in self.system: os.startfile(path)
                    elif "darwin" in self.system: subprocess.Popen(["open", path])
                    else: subprocess.Popen(["xdg-open", path])
                    return f"Відкриваю: {name}"
                return f"Шлях не знайдено: {path}"

            elif etype == "app":
                if path and os.path.exists(path):
                    if "win" in self.system: subprocess.Popen(path)
                    else: subprocess.Popen([path], shell=True)
                    return f"Запускаю: {name}"
                else:
                    return self._open_raw_app(entry_id, display_name=name)

        except Exception as e:
            LOGGER.error(f"Open error: {e}")
            return f"Помилка: {e}"
        
        return "Невідомий тип."

    def _open_raw_app(self, app_name, display_name=None):
        name = display_name or app_name
        search_paths = [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            os.path.join(os.environ.get("AppData", ""), "Programs"),
            os.path.join(os.environ.get("LocalAppData", ""), "Programs")
        ]
        exe_map = {
            "steam": "Steam\\Steam.exe",
            "discord": "Discord\\Update.exe",
            "telegram": "Telegram Desktop\\Telegram.exe",
            "spotify": "Spotify\\Spotify.exe",
            "chrome": "Google\\Chrome\\Application\\chrome.exe",
            "browser": "Google\\Chrome\\Application\\chrome.exe",
            "notepad": "notepad.exe",
            "calc": "calc.exe"
        }
        
        target_exe = exe_map.get(app_name.lower(), f"{app_name}.exe")
        
        if shutil.which(target_exe):
            subprocess.Popen(target_exe, shell=True)
            return f"Запускаю {name}."

        for base in search_paths:
            full = os.path.join(base, target_exe)
            if os.path.exists(full):
                subprocess.Popen(full)
                return f"Запускаю {name}."
        
        return f"Не можу знайти програму '{name}'."

    def close_app(self, entry_id: str) -> str:
        entries = self.cfg.get_entries()
        entry = next((e for e in entries if e["id"] == entry_id), None)
        
        proc_name = f"{entry_id}.exe"
        display_name = entry["name"] if entry else entry_id
        
        if entry and entry.get("path") and entry.get("type") == "app":
            proc_name = os.path.basename(entry["path"])
        
        if not entry:
            proc_name = {
                "steam": "steam.exe", "discord": "Discord.exe", 
                "telegram": "Telegram.exe", "chrome": "chrome.exe", "browser": "chrome.exe"
            }.get(entry_id.lower(), f"{entry_id}.exe")

        closed = False
        if psutil:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    if p.info['name'].lower() == proc_name.lower():
                        p.terminate()
                        closed = True
                except: pass
        
        if not closed:
            try:
                cmd = f"taskkill /f /im {proc_name}" if "win" in self.system else f"pkill -f {proc_name}"
                subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Taskkill success is hard to detect without checking error code, usually assume success if run
                closed = True
            except: pass
            
        return f"Закриваю {display_name}." if closed else f"Не знайшов процес {display_name}."

    # --- Media & Window ---
    def media_action(self, action: str) -> str:
        if not pyautogui: return "Помилка: бібліотека керування не встановлена."
        try:
            if action == "play_pause": pyautogui.press("playpause")
            elif action == "next": pyautogui.press("nexttrack")
            elif action == "prev": pyautogui.press("prevtrack")
            elif action == "vol_up": pyautogui.press("volumeup")
            elif action == "vol_down": pyautogui.press("volumedown")
            elif action == "mute": pyautogui.press("volumemute")
            return "Виконую медіа-дію."
        except: return "Не вдалося виконати."

    def window_action(self, action: str) -> str:
        if not pyautogui: return "Помилка: бібліотека керування не встановлена."
        try:
            if action == "minimize_all":
                if "win" in self.system: pyautogui.hotkey("win", "d")
                else: pyautogui.hotkey("super", "d")
                return "Робочий стіл."
        except: pass
        return "Помилка вікон."

    def take_screenshot(self) -> str:
        if not pyautogui: return "Помилка: бібліотека не встановлена."
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.home_dir, "Pictures", f"screen_{ts}.png")
        try:
            pyautogui.screenshot().save(path)
            return f"Скріншот збережено."
        except: return "Помилка скріншоту."

    # --- Workspaces ---
    def run_workspace(self, ws_id: str) -> str:
        workspaces = self.cfg.get_workspaces()
        ws = next((w for w in workspaces if w["id"] == ws_id), None)
        if not ws: return "Режим не знайдено."
        
        LOGGER.info(f"Running workspace: {ws['name']}")
        
        for step in ws.get("steps", []):
            act = step.get("action")
            try:
                if act == "OPEN_ENTRY": 
                    if step.get("target_id"): self.open_entry(step["target_id"])
                elif act == "CLOSE_APP":
                    if step.get("target_id"): self.close_app(step["target_id"])
                elif act == "OPEN_WEBSITE":
                    if step.get("url"): webbrowser.open(step["url"])
                elif act == "MEDIA":
                    if step.get("subaction"): self.media_action(step["subaction"])
                elif act == "WINDOW":
                    if step.get("subaction"): self.window_action(step["subaction"])
                elif act == "WAIT":
                    time.sleep(int(step.get("value", 1)))
                elif act == "IOT":
                    self.run_iot_action(step.get("device_id"), step.get("action_name"), step.get("value"))
                
                time.sleep(0.5)
            except Exception as e:
                LOGGER.error(f"Step error: {e}")

        return f"Режим '{ws['name']}' виконано."

    # --- IoT ---
    def run_iot_action(self, dev_id: str, act_name: str, value=None) -> str:
        devs = self.cfg.get_iot_devices()
        dev = next((d for d in devs if d["id"] == dev_id), None)
        if not dev: return f"Пристрій {dev_id} не знайдено."
        
        action = next((a for a in dev.get("actions", []) if a["name"] == act_name), None)
        if not action: return f"Дія {act_name} не знайдена."

        ctype = dev.get("connection_type")
        params = dev.get("connection_params", {})
        template = action.get("payload", "")
        
        payload = template
        if value is not None and "{value}" in template:
            payload = template.replace("{value}", str(value))

        try:
            if ctype == "HTTP":
                url = params.get("url", "")
                if params.get("method", "GET") == "GET":
                    sep = "&" if "?" in url else "?"
                    if payload: url += f"{sep}{payload}"
                    requests.get(url, timeout=5)
                else:
                    requests.post(url, data=payload, timeout=5)
                return f"IoT: {dev['display_name']} -> {action['name']}"

            elif ctype == "MQTT" and publish:
                broker = params.get("broker", "localhost")
                topic = params.get("topic", "test")
                publish.single(topic, payload, hostname=broker)
                return f"IoT MQTT: {dev['display_name']}"

            elif ctype == "Serial" and serial:
                port = params.get("port", "COM3")
                baud = int(params.get("baudrate", 9600))
                with serial.Serial(port, baud, timeout=1) as ser:
                    ser.write(payload.encode('utf-8'))
                return f"IoT Serial: {dev['display_name']}"

        except Exception as e:
            return f"IoT Помилка: {e}"
        return "IoT не налаштовано."

    # --- Notes ---
    def create_note_file(self) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"Note_{timestamp}.md"
        path = os.path.join(self.notes_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Нотатки від {timestamp}\n\n")
        return path

    def append_to_note(self, path: str, text: str):
        if path and os.path.exists(path):
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"- {text}\n")

    def get_notes_list(self):
        files = glob.glob(os.path.join(self.notes_dir, "*.md"))
        files.sort(key=os.path.getctime, reverse=True)
        return [os.path.basename(f) for f in files]

    def read_note(self, filename):
        path = os.path.join(self.notes_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: return f.read()
        return ""

    def get_latest_note(self) -> str:
        files = glob.glob(os.path.join(self.notes_dir, "*.md"))
        if not files: return ""
        return max(files, key=os.path.getctime)