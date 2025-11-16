import os
import sys
import json
import queue
import platform
import subprocess
import glob
import logging
import threading
import urllib.parse
from datetime import datetime
import random
import time
import webbrowser
import sounddevice as sd
import vosk
from pygame import mixer
import asyncio
from pynput.keyboard import Key, Controller
import pyautogui
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from gtts import gTTS
import paramiko
from thefuzz import fuzz, process  # для fuzzy-команд

from ui import start_ui, ui_add_message, ui_set_status

# ===================== ЛОГИ =====================

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_path = os.path.join(LOG_DIR, "petro.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
LOGGER = logging.getLogger("petro")

# ===================== КОНФІГ =====================

CONFIG_PATH = "petro_config.json"


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise RuntimeError(f"Не знайдено файл конфігурації: {path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    for key in ["alias", "tbr", "commands"]:
        if key not in cfg:
            raise RuntimeError(f"В конфігу немає обов'язкового ключа: {key}")

    return cfg


CONFIG = load_config(CONFIG_PATH)

ALIASES = CONFIG["alias"]
TBR = CONFIG["tbr"]
COMMANDS = CONFIG["commands"]          # словник {cmd_code: [frazy...]}

APPS_MAP = CONFIG.get("apps", {})      # {"steam": "C:/...", "telegram": "C:/..."}
LLM_BASE_URL = CONFIG.get("llm_base_url", "http://127.0.0.1:1234")
LLM_MODEL = CONFIG.get("llm_model", "phi-3.5-mini-instruct")
GEMINI_MODEL = CONFIG.get("gemini_model", "gemini-2.5-flash")
LLM_BACKEND = CONFIG.get("llm_backend_default", "local").lower()

# небезпечні команди (тільки точний матч + підтвердження)
DANGEROUS_COMMANDS = {"power_off", "sleep", "server"}

# ===================== ASR / Vosk =====================

model_path = "uk_v3/model"
samplerate = 16000
model = vosk.Model(model_path)
rec = vosk.KaldiRecognizer(model, samplerate)
q = queue.Queue()

# ===================== АУДІО / СТАН =====================

mixer.init()
keyboard = Controller()
voice = ""  # остання фраза

# глобальні прапори
MUTED = False   # якщо True – Петруча не говорить вголос
MIC_ON = True   # якщо False – ігноруємо мікрофон

# Додаємо підтримку ключа з config:
GEMINI_API_KEY = CONFIG.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")

# стан підтвердження небезпечних дій
PENDING_CONFIRM = None
# формат: {"type": "power_off"|"sleep"|..., "data": {...}}


# ===================== TTS =====================

def speak(text: str, to_ui: bool = True) -> None:
    """Озвучити текст (або тільки залогувати, якщо MUTED)."""
    global MUTED

    msg = f"Петруча: {text}"
    LOGGER.info(msg)
    print(f"[TTS] {text}")
    if to_ui:
        ui_add_message("assistant", text)

    if MUTED:
        return

    try:
        filename = "text.mp3"
        tts = gTTS(text=text, lang="uk")
        tts.save(filename)

        mixer.music.load(filename)
        mixer.music.play()

        while mixer.music.get_busy():
            time.sleep(0.1)

        mixer.music.unload()
        os.remove(filename)
    except Exception as e:
        LOGGER.error("Помилка TTS: %s", e)


# ===================== LLM backend-и =====================

def ask_llm_local(question: str) -> str:
    """Запит до локальної LLM (LM Studio, сумісний з OpenAI API)."""
    try:
        url = f"{LLM_BASE_URL.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ти україномовний асистент. "
                        "Відповідай коротко, 1–3 речення, без форматування."
                    ),
                },
                {"role": "user", "content": question},
            ],
            "temperature": 0.2,
        }
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        LOGGER.error("[LLM/local] Помилка запиту: %s", e)
        return ""


def ask_gemini(question: str) -> str:
    """Звичайна відповідь від Gemini у форматі тексту."""
    if not GEMINI_API_KEY:
        LOGGER.warning("GEMINI_API_KEY не заданий")
        return ""

    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        }
        body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Ти україномовний голосовий асистент Петруча. "
                            "Відповідай коротко, 1–3 речення, без форматування."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": question}],
                }
            ],
        }
        resp = requests.post(url, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        LOGGER.error("[Gemini] Помилка запиту: %s", e)
        return ""


def ask_gemini_url(query: str) -> str | None:
    """
    Спеціальний запит до Gemini: повернути тільки URL сайту,
    який найкраще відповідає запиту користувача.
    """
    if not GEMINI_API_KEY:
        return None

    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        }
        body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Ти помічник, який повертає лише один URL сайту. "
                            "Користувач дає опис або назву сервісу. "
                            "Поверни ТІЛЬКИ одну коректну https-URL-адресу, "
                            "без пояснень, тексту чи форматування."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": query}],
                }
            ],
        }
        resp = requests.post(url, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        for token in text.split():
            if token.startswith("http://") or token.startswith("https://"):
                return token
        return None
    except Exception as e:
        LOGGER.error("[Gemini URL] Помилка запиту: %s", e)
        return None


def ask_smart(question: str) -> str:
    """
    Високоуровневий вибір backend'а:
    - off   → нічого не робимо;
    - gemini→ Gemini з fallback на локальну;
    - local → тільки локальна.
    """
    backend = LLM_BACKEND
    LOGGER.info("[LLM] Режим: %s, питання: %r", backend, question)

    if backend == "off":
        return ""

    if backend == "gemini":
        ans = ask_gemini(question)
        if ans:
            return ans
        return ask_llm_local(question)

    # default local
    return ask_llm_local(question)


# ===================== МАНУАЛ =====================

def print_manual():
    print("======================================")
    print("  Голосовий асистент Петруча")
    print("  by Бартаков Максим і Самуць Назар")
    print("======================================")
    print("Базові можливості:")
    print("  - Годинник:        «петро котра година», «петруча поточний час»")
    print("  - Погода:         «петро яка погода», «погода»")
    print("  - Монетка:        «петро підкинь монетку»")
    print("  - Пошук в Google: «петро загугли що таке дуб»")
    print("  - Пошук в YouTube:«петро відкрий відео про котів на ютубі»")
    print("  - LLM-відповіді:  «петро розкажи що таке дуб» (через LLM)")
    print("  - Гучність:       «петро збільшити гучність на 20» тощо")
    print("  - Вимкнення/сон:  «петро вимкни комп'ютер», «петро сон»")
    print("")
    print("Керування ПК:")
    print("  - Телеграм:       «петро відкрий телеграм»")
    print("  - Браузер:        «петро відкрий браузер»")
    print("  - Стім:           «петро відкрий стім»")
    print("  - Скріншот:       «петро зроби скріншот»")
    print("  - Папки:          «петро відкрий завантаження / документи / робочий стіл»")
    print("  - Файли:          «петро знайди файл звіт», «знайди документ договор»")
    print("")
    print("Режими LLM:")
    print("  - Локальна модель: «петро режим локальної моделі»")
    print("  - Gemini онлайн:   «петро режим джеміні / геміні / gmini / zamini ...»")
    print("  - Офлайн режим:    «петро офлайн режим»")
    print("")
    print("Голосова довідка:")
    print("  - «петро що ти вмієш», «петро довідка», «петро help»")
    print("======================================")


# ===================== SAFETY NORMALIZATION =====================

ARTIFACT_MAP = {
    # варіанти Gemini
    "геміні": "джеміні",
    "геміни": "джеміні",
    "гіміні": "джеміні",
    "хіміні": "джеміні",
    "жміні": "джеміні",
    "жиміні": "джеміні",
    "заміні": "джеміні",
    "заміни": "джеміні",
    "заміна": "джеміні",
    "zamini": "gemini",
    "gmini": "gemini",

    # варіанти імені асистента
    "петруха": "петруча",
    "пітруча": "петруча",
}


def normalize_asr_text(text: str) -> str:
    t = text.lower().strip()
    t = " ".join(t.split())
    words = t.split(" ")
    norm_words = [ARTIFACT_MAP.get(w, w) for w in words]
    return " ".join(norm_words)


# ===================== ПАРСЕР КОМАНД =====================

def match_command(text: str):
    """
    Повертає (cmd, cleaned_text, has_alias):
    - cmd: код команди або None
    - cleaned_text: текст без alias і службових слів (для LLM / Google / YouTube)
    - has_alias: чи починалося висловлювання з імені асистента
    """
    original = normalize_asr_text(text)
    cleaned = original
    has_alias = False

    # 1. Прибираємо alias на початку
    for alias in ALIASES:
        alias_l = alias.lower()
        if cleaned.startswith(alias_l):
            has_alias = True
            cleaned = cleaned[len(alias_l):].strip()
            break

    cmd_search_text = cleaned

    # 2. Прибираємо службові слова тільки з cleaned_text (НЕ з cmd_search_text)
    for tbr in TBR:
        tbr_l = tbr.lower()
        if cleaned.startswith(tbr_l):
            cleaned = cleaned[len(tbr_l):].strip()
            break

    # --------- 3. Точний пошук фраз команд ---------
    for cmd, phrases in COMMANDS.items():
        for phrase in phrases:
            phrase_l = phrase.lower()
            if phrase_l and phrase_l in cmd_search_text:
                return cmd, cleaned, has_alias

    # --------- 4. Fuzzy-пошук (крім небезпечних команд) ---------
    variants = []
    mapping = {}
    for cmd, phrases in COMMANDS.items():
        if cmd in DANGEROUS_COMMANDS:
            continue
        for phrase in phrases:
            phrase_l = phrase.lower()
            if phrase_l:
                variants.append(phrase_l)
                mapping[phrase_l] = cmd

    if variants:
        best_phrase, score = process.extractOne(
            cmd_search_text,
            variants,
            scorer=fuzz.token_set_ratio,
        )
        if score >= 80:
            cmd = mapping.get(best_phrase)
            if cmd:
                LOGGER.info("[FUZZ] best='%s', score=%d, cmd='%s'", best_phrase, score, cmd)
                return cmd, cleaned, has_alias

    return None, cleaned, has_alias


# ===================== ДОПОМОЖНІ Ф-Ї =====================

def extract_int_after_word(text: str, marker: str) -> int | None:
    try:
        idx = text.index(marker) + len(marker)
        part = text[idx:].strip()
        digits = "".join(ch for ch in part if ch.isdigit())
        return int(digits) if digits else None
    except ValueError:
        return None


def confirm_dangerous(action_type: str, description: str, data: dict | None = None):
    """
    Поставити запит на підтвердження небезпечної дії.
    action_type: 'power_off' | 'sleep' | 'server' | ...
    """
    global PENDING_CONFIRM
    PENDING_CONFIRM = {"type": action_type, "data": data or {}}
    speak(description + " Скажи «підтверджую» або «відміна».")


def handle_confirmation(cmd: str):
    """
    Обробка команд підтвердження / відміни для PENDING_CONFIRM.
    cmd: 'confirm' | 'cancel'
    """
    global PENDING_CONFIRM
    if not PENDING_CONFIRM:
        speak("Немає небезпечної дії, яку треба підтвердити.")
        return

    if cmd == "cancel":
        PENDING_CONFIRM = None
        speak("Добре, відміняю дію.")
        return

    if cmd == "confirm":
        action = PENDING_CONFIRM
        PENDING_CONFIRM = None
        t = action["type"]
        data = action.get("data", {})
        system = platform.system().lower()

        if t == "power_off":
            speak("Вимикаю комп'ютер.")
            if system.startswith("win"):
                os.system("shutdown /s /t 0")
            else:
                os.system("systemctl poweroff")

        elif t == "sleep":
            speak("Переводжу комп'ютер у сон.")
            if system.startswith("win"):
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            else:
                os.system("systemctl suspend")

        elif t == "server":
            speak("Запускаю небезпечну команду на сервері.")
            # тут можна викликати ssh-логіку, якщо потрібно
        else:
            speak("Я не знаю, як виконати цю дію після підтвердження.")


# ===================== ВИКОНАННЯ КОМАНД =====================

def execute_cmd(cmd: str, cleaned_text: str | None = None) -> None:
    global voice, LLM_BACKEND, MUTED

    system = platform.system().lower()

    # підтвердження / відміна
    if cmd in {"confirm", "cancel"}:
        handle_confirmation(cmd)
        return

    # --- базові команди ---
    if cmd == "ctime":
        now = datetime.now().strftime("%H:%M:%S")
        speak(f"Поточний час {now}")

    elif cmd == "mute_on":
        MUTED = True
        ui_set_status(muted=True)
        LOGGER.info("[MUTE] Тихий режим увімкнено.")

    elif cmd == "mute_off":
        MUTED = False
        ui_set_status(muted=False)
        speak("Повернув голос, знову можу говорити.")

    elif cmd == "pogoda":
        speak("Перевіряю погоду...")
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            driver = webdriver.Chrome(options=chrome_options)
            driver.get("https://meteofor.com.ua/weather-volodymyr-4927/now/")
            html = driver.page_source

            speak(f"Станом на {datetime.now().strftime('%H:%M')}")

            soup = BeautifulSoup(html, "html.parser")
            desc = soup.find("div", class_="now-desc")
            temp = soup.find("div", class_="now-weather")
            feel = soup.find("div", class_="now-feel")

            speak("Зараз у місті Володимир.")
            if desc:
                speak(desc.get_text())
            if temp:
                speak("Температура " + temp.get_text())
            if feel:
                speak(feel.get_text())
        except Exception as e:
            LOGGER.error("Помилка при отриманні погоди: %s", e)
            speak("Не вдалося отримати погоду.")
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    elif cmd == "server":
        confirm_dangerous("server", "Ти хочеш виконати небезпечну команду на сервері.")

    elif cmd == "Hello":
        speak("Привіт, я уважно тебе слухаю.")

    elif cmd == "youtube":
        query = (cleaned_text or voice).strip()
        if not query:
            speak("Скажи, яке відео тебе цікавить.")
            return
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
        webbrowser.open(url)
        speak("Відкрив результати пошуку на ютубі.")

    elif cmd == "google":
        query = (cleaned_text or voice).strip()
        if not query:
            speak("Сформулюй, будь ласка, що саме загуглити.")
            return
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        webbrowser.open(url)
        speak("Відкрив результати пошуку в гуглі.")

    elif cmd == "power_off":
        confirm_dangerous("power_off", "Ти хочеш вимкнути комп'ютер?")

    elif cmd == "sleep":
        confirm_dangerous("sleep", "Ти хочеш перевести комп'ютер у сон?")

    elif cmd == "volume_up":
        num = extract_int_after_word(voice.lower(), "на")
        if num is None:
            speak("Не можу знайти число для збільшення гучності.")
            return
        for _ in range(round(num / 2)):
            keyboard.press(Key.media_volume_up)
            keyboard.release(Key.media_volume_up)

    elif cmd == "volume_down":
        num = extract_int_after_word(voice.lower(), "на")
        if num is None:
            speak("Не можу знайти число для зменшення гучності.")
            return
        for _ in range(round(num / 2)):
            keyboard.press(Key.media_volume_down)
            keyboard.release(Key.media_volume_down)

    elif cmd == "set_volume":
        num = extract_int_after_word(voice.lower(), "на")
        if num is None:
            speak("Не можу знайти рівень гучності.")
        else:
            for _ in range(100):
                keyboard.press(Key.media_volume_down)
                keyboard.release(Key.media_volume_down)
            for _ in range(round(num / 2)):
                keyboard.press(Key.media_volume_up)
                keyboard.release(Key.media_volume_up)

    elif cmd == "close_petro":
        speak("До нових зустрічей.")
        os._exit(0)

    elif cmd == "random":
        txt = voice.lower()
        try:
            parts = txt.split("від", 1)[1].strip()
            left, right = parts.split("до", 1)
            int1 = int("".join(ch for ch in left if ch.isdigit()))
            int2 = int("".join(ch for ch in right if ch.isdigit()))
            if int1 > int2:
                int1, int2 = int2, int1
            rv = random.randint(int1, int2)
            speak(f"Випадкове число від {int1} до {int2}: {rv}")
        except Exception:
            speak("Не можу розібрати діапазон для випадкового числа.")

    elif cmd == "coin":
        if random.randint(1, 2) == 1:
            speak("Випав герб.")
        else:
            speak("Випала копійка.")

    elif cmd == "stop_petro":
        speak("Переходжу в режим очікування. Просто не говори мені нічого певний час.")

    # --- режими LLM ---
    elif cmd == "llm_local":
        LLM_BACKEND = "local"
        ui_set_status(llm_mode="local")
        speak("Перейшов у режим локальної моделі.")

    elif cmd == "llm_gemini":
        if not GEMINI_API_KEY:
            speak("Ключ Gemini не налаштований, не можу підключитися до Джеміні.")
        else:
            LLM_BACKEND = "gemini"
            ui_set_status(llm_mode="gemini")
            speak("Перейшов у режим Джеміні. Потрібен стабільний інтернет.")

    elif cmd == "llm_off":
        LLM_BACKEND = "off"
        ui_set_status(llm_mode="off")
        speak("Вимикаю мовні моделі. Працюю в офлайн-режимі, тільки базові команди.")

    # --- help ---
    elif cmd == "help":
        speak(
            "Я вмію показувати час, погоду, підкидати монетку, шукати в гуглі та ютубі, "
            "керувати гучністю, відкривати деякі програми, робити скріншоти та шукати файли. "
            "Також можу відповідати на питання через локальну модель або Джеміні."
        )
        print_manual()

    # --- керування ПК ---

    elif cmd == "open_telegram":
        speak("Відкриваю телеграм.")
        try:
            if system.startswith("win"):
                exe = APPS_MAP.get("telegram")
                if exe and os.path.exists(exe):
                    os.startfile(exe)
                else:
                    subprocess.Popen(["start", "telegram"], shell=True)
            else:
                try:
                    subprocess.Popen(["telegram-desktop"])
                except FileNotFoundError:
                    subprocess.Popen(["telegram"])
        except Exception as e:
            LOGGER.error("[open_telegram] помилка: %s", e)
            speak("Не вдалося відкрити телеграм.")

    elif cmd == "open_browser":
        speak("Відкриваю браузер.")
        try:
            url = "https://www.google.com"
            webbrowser.open(url)
        except Exception as e:
            LOGGER.error("[open_browser] помилка: %s", e)
            speak("Не вдалося відкрити браузер.")

    elif cmd == "open_steam":
        speak("Відкриваю Стім.")
        exe = APPS_MAP.get("steam")
        try:
            if system.startswith("win") and exe and os.path.exists(exe):
                os.startfile(exe)
            elif system.startswith("win"):
                subprocess.Popen(["start", "steam"], shell=True)
            else:
                subprocess.Popen(["steam"])
        except Exception as e:
            LOGGER.error("[open_steam] помилка: %s", e)
            speak("Не вдалося відкрити Стім.")

    elif cmd == "screenshot":
        speak("Роблю скріншот.")
        try:
            img = pyautogui.screenshot()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            home = os.path.expanduser("~")
            pictures = os.path.join(home, "Pictures")
            save_dir = pictures if os.path.isdir(pictures) else os.getcwd()
            filename = os.path.join(save_dir, f"screenshot_{timestamp}.png")
            img.save(filename)
            speak("Скріншот збережено.")
            LOGGER.info("[screenshot] saved to %s", filename)
        except Exception as e:
            LOGGER.error("[screenshot] помилка: %s", e)
            speak("Не вдалося зробити скріншот.")

    elif cmd == "open_folder":
        t = voice.lower()
        home = os.path.expanduser("~")
        path = None

        if any(x in t for x in ["завантаження", "завантажень", "загрузки", "загрузок", "download"]):
            for name in ["Downloads", "Завантаження", "Загрузки"]:
                p = os.path.join(home, name)
                if os.path.isdir(p):
                    path = p
                    break
        elif any(x in t for x in ["документи", "документів", "documents"]):
            for name in ["Documents", "Документи"]:
                p = os.path.join(home, name)
                if os.path.isdir(p):
                    path = p
                    break
        elif any(x in t for x in ["робочий стіл", "робочому столі", "desktop"]):
            for name in ["Desktop", "Робочий стіл"]:
                p = os.path.join(home, name)
                if os.path.isdir(p):
                    path = p
                    break

        if not path:
            speak("Я не зрозумів, яку папку потрібно відкрити або вона не знайдена.")
            return

        speak("Відкриваю папку.")
        try:
            if system.startswith("win"):
                os.startfile(path)
            elif system == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            LOGGER.error("[open_folder] помилка: %s", e)
            speak("Не вдалося відкрити папку.")

    elif cmd == "search_file":
        t = voice.lower()
        name_part = ""
        for key in ["файл", "файлик", "документ"]:
            if key in t:
                idx = t.index(key) + len(key)
                name_part = t[idx:].strip()
                break

        if not name_part:
            speak("Скажи, будь ласка, назву файлу або документа.")
            return

        speak("Пробую знайти файл.")
        home = os.path.expanduser("~")
        pattern = f"*{name_part}*"
        found_path = None

        try:
            for root, dirs, files in os.walk(home):
                matches = glob.glob(os.path.join(root, pattern))
                if matches:
                    found_path = matches[0]
                    break
        except Exception as e:
            LOGGER.error("[search_file] помилка при пошуку: %s", e)

        if not found_path:
            speak("Я не знайшов такий файл.")
            return

        speak("Знайшов файл, відкриваю.")
        try:
            if system.startswith("win"):
                os.startfile(found_path)
            elif system == "darwin":
                subprocess.Popen(["open", found_path])
            else:
                subprocess.Popen(["xdg-open", found_path])
        except Exception as e:
            LOGGER.error("[search_file] помилка при відкритті: %s", e)
            speak("Не вдалося відкрити файл.")

    elif cmd == "open_website":
        query = (cleaned_text or voice).strip()
        if not query:
            speak("Скажи, який сайт потрібно відкрити.")
            return

        url = ask_gemini_url(query)
        if not url:
            url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
            speak("Я не зміг визначити конкретний сайт, відкриваю пошук у гуглі.")
        else:
            speak("Відкриваю сайт, який найкраще підходить до опису.")

        try:
            webbrowser.open(url)
        except Exception as e:
            LOGGER.error("[open_website] помилка: %s", e)
            speak("Не вдалося відкрити сайт.")

    else:
        LOGGER.warning("execute_cmd: невідома команда %s", cmd)
        speak("Поки що не вмію виконувати цю команду.")


# ===================== АУДІО CALLBACK =====================

def audio_callback(indata, frames, time_info, status):
    if status:
        LOGGER.warning("Audio status: %s", status)
    if not MIC_ON:
        return
    q.put(bytes(indata))


# ===================== ОСНОВНИЙ ЦИКЛ РОЗПІЗНАВАННЯ =====================

def recognition_loop():
    """
    Основний цикл розпізнавання голосу з Vosk.
    Працює в окремому потоці, читає з черги q,
    враховує прапор MIC_ON (щоб можна було "вимкнути мікрофон").
    """
    global voice, MIC_ON
    print("Система очікує команд...")

    while True:
        data = q.get()

        if not MIC_ON:
            continue

        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if not text:
                continue

            print(f"Розпізнано: {text}")
            voice = text

            cmd, cleaned_text, has_alias = match_command(text)

            if cmd:
                execute_cmd(cmd, cleaned_text)
            else:
                if has_alias and cleaned_text:
                    answer = ask_smart(cleaned_text)
                    if answer:
                        speak(answer)
                    else:
                        print("Команда не розпізнана (LLM нічого не повернула)")
                        speak("Я не зміг отримати відповідь від моделі.")
                else:
                    print("Команда не розпізнана")


# ===================== AIoT ШАБЛОН (НА МАЙБУТНЄ) =====================

"""
# ========== AIoT / SMART HOME ==========
# Цей блок поки що не використовується. Він показує архітектуру
# для підключення лампочок, сервоприводів та сенсорів у майбутньому.

class SmartLampController:
    def __init__(self, port: str):
        # тут можна ініціалізувати serial / mqtt / http-клієнт
        self.port = port

    def turn_on(self, room: str | None = None):
        # надіслати команду "увімкнути лампу" в потрібну кімнату
        pass

    def turn_off(self, room: str | None = None):
        pass

class ServoController:
    def __init__(self, port: str):
        self.port = port

    def set_angle(self, angle: int):
        # від 0 до 180
        pass

class SensorHub:
    def __init__(self, port: str):
        self.port = port

    def read_temperature(self) -> float:
        # прочитати значення з температурного сенсора
        return 0.0

# Приклад використання:
# lamp = SmartLampController("/dev/ttyUSB0")
# servo = ServoController("/dev/ttyUSB1")
# sensors = SensorHub("/dev/ttyUSB2")
#
# І далі в execute_cmd можна буде додати intent'и:
# - "turn_on_lamp"
# - "turn_off_lamp"
# - "set_servo_angle"
# - "get_temperature"
"""

# ===================== MAIN =====================

def main():
    """
    Точка входу:
    - друкує мануал у консоль;
    - запускає потік розпізнавання Vosk;
    - запускає потік мікрофона;
    - стартує графічний UI з текстовим вводом як у чаті.
    """
    print_manual()

    # ----------------- CALLBACK-и ДЛЯ UI -----------------

    def on_ui_send_text(text: str):
        """
        Обробка вводу з текстового поля UI.

        Логіка:
          1) спочатку завжди пробуємо знайти команду;
          2) якщо команда знайдена — виконуємо її (незалежно від alias);
          3) якщо команди немає:
             - якщо LLM вимкнена → просто кажемо, що не розумію;
             - якщо LLM увімкнена → відправляємо питання в LLM.
        """
        global voice
        voice = text.strip()
        if not voice:
            return

        # показуємо текст у чаті як репліку користувача
        ui_add_message("user", voice)

        cmd, cleaned_text, has_alias = match_command(voice)

        # 1) якщо команда знайдена — виконуємо її завжди
        if cmd:
            execute_cmd(cmd, cleaned_text)
            return

        # 2) команди немає, дивимось на LLM
        if LLM_BACKEND == "off":
            msg = "Команда не розпізнана. LLM зараз вимкнена."
            ui_add_message("assistant", msg)
            speak(msg)
            return

        # текст для моделі:
        #   якщо є alias і cleaned_text → беремо cleaned_text (без «петро» і службових слів)
        #   інакше → весь voice
        question = cleaned_text if (has_alias and cleaned_text) else voice

        answer = ask_smart(question)
        if answer:
            ui_add_message("assistant", answer)
            speak(answer)
        else:
            ui_add_message("assistant", "Я не зміг отримати відповідь від моделі.")
            speak("Я не зміг отримати відповідь від моделі.")

    def on_ui_toggle_mute():
        """
        Кнопка Mute в UI — вмикає/вимикає голос (TTS),
        але логіка/LLM/команди при цьому продовжують працювати.
        """
        global MUTED
        MUTED = not MUTED
        ui_set_status(muted=MUTED)
        if MUTED:
            ui_add_message("assistant", "Тихий режим активовано.")
        else:
            ui_add_message("assistant", "Голос увімкнено.")

    def on_ui_toggle_mic():
        """
        Кнопка Mic в UI — просто перестає обробляти аудіо з черги q,
        щоб Петруча «не чув» мікрофон.
        """
        global MIC_ON
        MIC_ON = not MIC_ON
        ui_set_status(mic_on=MIC_ON)
        if MIC_ON:
            ui_add_message("assistant", "Мікрофон увімкнено.")
        else:
            ui_add_message("assistant", "Мікрофон вимкнено.")

    # ----------------- ПОТІК РОЗПІЗНАВАННЯ VOSK -----------------

    threading.Thread(target=recognition_loop, daemon=True).start()

    # ----------------- ПОТІК МІКРОФОНА -----------------

    def mic_loop():
        with sd.RawInputStream(
            samplerate=samplerate,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            while True:
                sd.sleep(1000)

    threading.Thread(target=mic_loop, daemon=True).start()

    # ----------------- Старт UI (ГОЛОВНИЙ ПОТІК) -----------------

    start_ui(on_ui_send_text, on_ui_toggle_mute, on_ui_toggle_mic)


if __name__ == "__main__":
    try:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except Exception:
        pass

    main()
