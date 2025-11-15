import os
import sys
import json
import queue
import platform
import subprocess
import glob
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
from thefuzz import fuzz, process  # для safety-layer команд

# ---------------------- Завантаження конфігурації ----------------------

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
COMMANDS = CONFIG["commands"]

LLM_BASE_URL = CONFIG.get("llm_base_url", "http://127.0.0.1:1234")
LLM_MODEL = CONFIG.get("llm_model", "phi-3.5-mini-instruct")
GEMINI_MODEL = CONFIG.get("gemini_model", "gemini-2.5-flash")
LLM_BACKEND = CONFIG.get("llm_backend_default", "local").lower()

# небезпечні команди – ТІЛЬКИ точний збіг, без fuzz
DANGEROUS_COMMANDS = {"power_off", "sleep", "server"}

# ---------------------- ASR / Vosk ----------------------

model_path = "uk_v3/model"
samplerate = 16000
model = vosk.Model(model_path)
rec = vosk.KaldiRecognizer(model, samplerate)
q = queue.Queue()

# ---------------------- Аудіо / TTS ----------------------

mixer.init()
keyboard = Controller()
voice = ""  # остання фраза

# новий глобальний прапор
MUTED = False  # якщо True – Петруча не говорить вголос

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def speak(text: str):
    global MUTED

    # завжди лог у консоль
    print(f"[TTS] {text}")

    # якщо тихий режим – не відтворюємо звук
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
        print(f"[Помилка TTS] {e}")


# ---------------------- LLM backend-и ----------------------

def ask_llm_local(question: str) -> str:
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
        print(f"[LLM/local] Помилка запиту: {e}")
        return ""


def ask_gemini(question: str) -> str:
    if not GEMINI_API_KEY:
        print("[Gemini] GEMINI_API_KEY не заданий")
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
        print(f"[Gemini] Помилка запиту: {e}")
        return ""


def ask_smart(question: str) -> str:
    backend = LLM_BACKEND
    print(f"[LLM] Режим: {backend}, питання: {question!r}")

    if backend == "off":
        return ""

    if backend == "gemini":
        ans = ask_gemini(question)
        if ans:
            return ans
        ans = ask_llm_local(question)
        return ans

    # default local
    ans = ask_llm_local(question)
    return ans


# ---------------------- Мануал ----------------------

def print_manual():
    print("======================================")
    print("  Голосовий асистент Петруча")
    print(" by Бартаков Максим і Самуць Назар")
    print("======================================")
    print("Базові можливості:")
    print("  - Годинник:        «петро котра година», «петруча поточний час»")
    print("  - Погода:         «петро яка погода», «погода»")
    print("  - Монетка:        «петро підкинь монетку»")
    print("  - Пошук в Google: «петро загугли ...»")
    print("  - Пошук в YouTube:«петро увімкни відео ...»")
    print("  - Гучність:       «петро збільшити гучність на 20» тощо")
    print("  - Вимкнення/сон:  «петро вимкни комп'ютер», «петро сон»")
    print("")
    print("Керування ПК:")
    print("  - Телеграм:       «петро відкрий телеграм», «петро запусти телеграм»")
    print("  - Браузер:        «петро відкрий браузер», «петро відкрий хром»")
    print("  - Скріншот:       «петро зроби скріншот», «петро зроби скрін»")
    print("  - Папки:          «петро відкрий завантаження», «відкрий документи», «відкрий робочий стіл»")
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


# ---------------------- Safety-layer: нормалізація ASR ----------------------

ARTIFACT_MAP = {
    # варіанти Gemini
    "геміні": "джеміні",
    "геміни": "джеміні",
    "гіміні": "джеміні",
    "хіміні": "джеміні",
    "жміні": "джеміні",
    "жміні": "джеміні",
    "жиміні": "джеміні",
    "заміні": "джеміні",
    "заміни": "джеміні",
    "замина": "джеміні",
    "заміна": "джеміні",
    "замени": "джеміні",
    "замінаи": "джеміні",
    "gmini": "gemini",
    "zamini": "gemini",

    # варіанти імені асистента (якщо треба)
    "петруха": "петруча",
    "пітруча": "петруча",
}


def normalize_asr_text(text: str) -> str:
    t = text.lower().strip()
    # нормалізація пробілів
    t = " ".join(t.split())
    # словникові заміни по словам
    words = t.split(" ")
    norm_words = []
    for w in words:
        norm_words.append(ARTIFACT_MAP.get(w, w))
    return " ".join(norm_words)


# ---------------------- Парсер команд з fuzz ----------------------

def match_command(text: str):
    """
    Повертає (cmd, cleaned_text, has_alias):
    - cmd: код команди або None
    - cleaned_text: текст без alias і службових слів
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
            # Прибираємо службові слова після alias
            for tbr in TBR:
                tbr_l = tbr.lower()
                if cleaned.startswith(tbr_l):
                    cleaned = cleaned[len(tbr_l):].strip()
            break

    # 2. Спершу пробуємо точний пошук
    for cmd, phrases in COMMANDS.items():
        for phrase in phrases:
            phrase_l = phrase.lower()
            if phrase_l and phrase_l in cleaned:
                return cmd, cleaned, has_alias

    # 3. Fuzzy-пошук (safety-layer), крім небезпечних команд
    variants = []
    mapping = {}
    for cmd, phrases in COMMANDS.items():
        if cmd in DANGEROUS_COMMANDS:
            continue  # тільки точні збіги
        for phrase in phrases:
            phrase_l = phrase.lower()
            if phrase_l:
                variants.append(phrase_l)
                mapping[phrase_l] = cmd

    if variants:
        best_phrase, score = process.extractOne(
            cleaned,
            variants,
            scorer=fuzz.token_set_ratio
        )
        if score >= 80:  # поріг схожості
            cmd = mapping.get(best_phrase)
            if cmd:
                print(f"[FUZZ] best='{best_phrase}', score={score}, cmd='{cmd}'")
                return cmd, cleaned, has_alias

    return None, cleaned, has_alias


# ---------------------- Виконання команд ----------------------

def execute_cmd(cmd: str):
    global voice, LLM_BACKEND

    # --- базові команди ---
    if cmd == "ctime":
        now = datetime.now().strftime("%H:%M:%S")
        speak(f"Поточний час {now}")

    elif cmd == "mute_on":
        global MUTED
        MUTED = True
        try:
            if mixer.music.get_busy():
                mixer.music.stop()
                mixer.music.unload()
        except Exception:
            pass
        print("[MUTE] Тихий режим увімкнено.")
        # speak("Добре, буду мовчати.")  # якщо хочеш без голосу – закоментуй

    elif cmd == "mute_off":
        MUTED = False
        print("[MUTE] Тихий режим вимкнено.")
        speak("Повернув голос, знову можу говорити.")


    elif cmd == "pogoda":
        speak("Перевіряю погоду...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://meteofor.com.ua/weather-volodymyr-4927/now/")
        html = driver.page_source

        speak(f"станом на {datetime.now().strftime('%H:%M')}")

        soup = BeautifulSoup(html, "html.parser")
        divs = soup.find_all("div", class_="now-desc")
        titles = soup.find_all("div", class_="now-feel")
        temp = soup.find_all("div", class_="now-weather")

        if divs:
            speak("зараз у місті Володимир")
            speak(divs[0].get_text())
        if temp:
            speak("температура")
            speak(temp[0].get_text())
        if titles:
            speak(titles[0].get_text())
        driver.quit()

    elif cmd == "server":
        HOST = "192.168.1.104"
        PORT = 22
        USERNAME = "madarog"
        PASSWORD = "pt123pt321"
        SU_PASSWORD = "123456"

        def ssh_interactive_su_command(cmd_line: str):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(HOST, port=PORT, username=USERNAME, password=PASSWORD, timeout=10)
            except Exception as e:
                print("Connect failed:", e)
                return

            channel = client.invoke_shell()
            time.sleep(1)
            while channel.recv_ready():
                print(channel.recv(1024).decode(errors="ignore"), end="")

            channel.send("su\n")
            time.sleep(1)

            if channel.recv_ready():
                output = channel.recv(1024).decode(errors="ignore")
                print(output, end="")
                if "Password:" in output or "password:" in output:
                    channel.send(SU_PASSWORD + "\n")

            time.sleep(1)
            while channel.recv_ready():
                print(channel.recv(1024).decode(errors="ignore"), end="")

            print(f"Executing as su: {cmd_line}")
            channel.send(cmd_line + "\n")

            time.sleep(2)
            while channel.recv_ready():
                output = channel.recv(1024).decode(errors="ignore")
                print(output, end="")

            channel.close()
            client.close()

        ssh_interactive_su_command("systemctl reboot -i")

    elif cmd == "Hello":
        speak("Привіт, я уважно тебе слухаю")

    elif cmd == "youtube":
        new_voice = voice.lower()
        try:
            for _ in range(2):
                new_voice = new_voice[: new_voice.index(" ")] + new_voice[new_voice.index(" ") + 1 :]
            new_voice = new_voice[new_voice.index(" ") :]
            plus_voice = new_voice.replace(" ", "+")[1:]
            url = "https://www.youtube.com/results?search_query=" + plus_voice
            webbrowser.open(url)
            speak("Ось відео, які вдалось знайти по даному запиту в ютуб")
        except ValueError:
            speak("Не можу розібрати запит для ютуба.")

    elif cmd == "google":
        new_voice = voice.lower()
        try:
            for _ in range(2):
                new_voice = new_voice[: new_voice.index(" ")] + new_voice[new_voice.index(" ") + 1 :]
            new_voice = new_voice[new_voice.index(" ") :]
            plus_voice = new_voice.replace(" ", "+")[1:]
            url = "https://www.google.com/search?q=" + plus_voice
            webbrowser.open(url)
            speak("Ось дані, які вдалось знайти по даному запиту у гугл")
        except ValueError:
            speak("Не можу розібрати запит для гугл.")

    elif cmd == "power_off":
        speak("вимикаю комп'ютер")
        os.system("shutdown now -h")

    elif cmd == "sleep":
        speak("ввожу комп'ютер у сон")
        os.system("systemctl suspend")

    elif cmd == "volume_up":
        random_voice = voice.lower()
        try:
            x_volumeup = int(random_voice[random_voice.index("на") + 3 :])
            for _ in range(round(x_volumeup / 2)):
                keyboard.press(Key.media_volume_up)
                keyboard.release(Key.media_volume_up)
        except (ValueError, IndexError):
            speak("Не можу знайти число для збільшення гучності.")

    elif cmd == "volume_down":
        random_voice = voice.lower()
        try:
            x_volumedown = int(random_voice[random_voice.index("на") + 3 :])
            for _ in range(round(x_volumedown / 2)):
                keyboard.press(Key.media_volume_down)
                keyboard.release(Key.media_volume_down)
        except (ValueError, IndexError):
            speak("Не можу знайти число для зменшення гучності.")

    elif cmd == "set_volume":
        random_voice = voice.lower()
        try:
            x_volumeset = int(random_voice[random_voice.index("на") + 3 :])
            for _ in range(100):
                keyboard.press(Key.media_volume_down)
                keyboard.release(Key.media_volume_down)
            for _ in range(round(x_volumeset / 2)):
                keyboard.press(Key.media_volume_up)
                keyboard.release(Key.media_volume_up)
        except (ValueError, IndexError):
            speak("Не можу знайти рівень гучності.")

    elif cmd == "close_petro":
        speak("до нових зустрічей")
        os._exit(0)

    elif cmd == "random":
        random_voice = voice.lower()
        try:
            int1_part = random_voice[: random_voice.index(" до ")]
            for _ in range(3):
                int1_part = int1_part[: int1_part.index(" ")] + int1_part[int1_part.index(" ") + 1 :]
            int1 = int(int1_part[int1_part.index(" ") + 1 :])

            int2 = int(random_voice[random_voice.index("до") + 3 :])

            random_integer = random.randint(int1, int2)
            speak(f"випадкове число від {int1} до {int2}: {random_integer}")
        except (ValueError, IndexError):
            speak("Не можу розібрати числа для випадкового діапазону.")

    elif cmd == "coin":
        if random.randint(1, 2) == 1:
            speak("Випав герб")
        else:
            speak("Випала Копійка")

    elif cmd == "stop_petro":
        speak("Перехожу в режим очікування")
        pyautogui.hotkey("ctrl", "alt", "del")
        speak("Вихід з режиму очікування")

    # --- режими LLM ---
    elif cmd == "llm_local":
        LLM_BACKEND = "local"
        speak("Перейшов у режим локальної моделі.")

    elif cmd == "llm_gemini":
        if not GEMINI_API_KEY:
            speak("Ключ Gemini не налаштований, не можу підключитися до Джеміні.")
        else:
            LLM_BACKEND = "gemini"
            speak("Перейшов у режим Джеміні. Потрібен стабільний інтернет.")

    elif cmd == "llm_off":
        LLM_BACKEND = "off"
        speak("Вимикаю мовні моделі. Працюю в офлайн-режимі, тільки базові команди.")

    # --- help ---
    elif cmd == "help":
        speak(
            "Я вмію показувати час, погоду, підкидати монетку, шукати в гуглі та ютубі, "
            "керувати гучністю, вимикати комп'ютер, керувати деякими програмами, "
            "робити скріншоти та шукати файли. Також можу відповідати на питання "
            "через локальну модель або Джеміні."
        )
        print_manual()

    # --- нові команди керування ПК ---

    elif cmd == "open_telegram":
        speak("Відкриваю телеграм.")
        try:
            if platform.system().lower().startswith("win"):
                # варіанти шляхів, можна дописати свої
                possible_paths = [
                    os.path.join(os.getenv("LOCALAPPDATA", ""), "Telegram Desktop", "Telegram.exe"),
                    os.path.join(os.getenv("PROGRAMFILES", ""), "Telegram Desktop", "Telegram.exe"),
                    os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Telegram Desktop", "Telegram.exe"),
                ]
                started = False
                for p in possible_paths:
                    if p and os.path.exists(p):
                        os.startfile(p)
                        started = True
                        break
                if not started:
                    # fallback
                    subprocess.Popen(["start", "telegram"], shell=True)
            else:
                # Linux/macOS
                try:
                    subprocess.Popen(["telegram-desktop"])
                except FileNotFoundError:
                    subprocess.Popen(["telegram"])
        except Exception as e:
            print(f"[open_telegram] помилка: {e}")
            speak("Не вдалося відкрити телеграм.")

    elif cmd == "open_browser":
        speak("Відкриваю браузер.")
        try:
            webbrowser.open("https://www.google.com")
        except Exception as e:
            print(f"[open_browser] помилка: {e}")
            speak("Не вдалося відкрити браузер.")

    elif cmd == "screenshot":
        speak("Роблю скріншот.")
        try:
            img = pyautogui.screenshot()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            home = os.path.expanduser("~")
            pictures = os.path.join(home, "Pictures")
            if not os.path.isdir(pictures):
                save_dir = os.getcwd()
            else:
                save_dir = pictures
            filename = os.path.join(save_dir, f"screenshot_{timestamp}.png")
            img.save(filename)
            speak("Скріншот збережено.")
            print(f"[screenshot] saved to {filename}")
        except Exception as e:
            print(f"[screenshot] помилка: {e}")
            speak("Не вдалося зробити скріншот.")

    elif cmd == "open_folder":
        # дивимося, про яку папку йдеться за ключовими словами
        t = voice.lower()
        home = os.path.expanduser("~")
        path = None

        if "завантаження" in t or "загрузки" in t or "завантажень" in t:
            # Downloads / Завантаження
            for name in ["Downloads", "Завантаження"]:
                p = os.path.join(home, name)
                if os.path.isdir(p):
                    path = p
                    break
        elif "документи" in t or "documents" in t:
            for name in ["Documents", "Документи"]:
                p = os.path.join(home, name)
                if os.path.isdir(p):
                    path = p
                    break
        elif "робочий стіл" in t or "робочому столі" in t or "desktop" in t:
            for name in ["Desktop", "Робочий стіл"]:
                p = os.path.join(home, name)
                if os.path.isdir(p):
                    path = p
                    break

        if not path:
            speak("Я не зрозумів, яку папку потрібно відкрити.")
            return

        speak("Відкриваю папку.")
        try:
            system = platform.system().lower()
            if system.startswith("win"):
                os.startfile(path)
            elif system == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"[open_folder] помилка: {e}")
            speak("Не вдалося відкрити папку.")

    elif cmd == "search_file":
        # намагаємось витягнути назву файлу/документа із voice
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
            print(f"[search_file] помилка при пошуку: {e}")

        if not found_path:
            speak("Я не знайшов такий файл.")
            return

        speak("Знайшов файл, відкриваю.")
        try:
            system = platform.system().lower()
            if system.startswith("win"):
                os.startfile(found_path)
            elif system == "darwin":
                subprocess.Popen(["open", found_path])
            else:
                subprocess.Popen(["xdg-open", found_path])
        except Exception as e:
            print(f"[search_file] помилка при відкритті: {e}")
            speak("Не вдалося відкрити файл.")


# ---------------------- Аудіо callback ----------------------

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    q.put(bytes(indata))


# ---------------------- Основний цикл розпізнавання ----------------------

def recognition_loop():
    global voice
    print("Система очікує команд...")

    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if not text:
                continue

            print(f"Розпізнано: {text}")
            voice = text

            cmd, cleaned_text, has_alias = match_command(text)

            if cmd:
                execute_cmd(cmd)
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


def main():
    print_manual()
    threading = __import__("threading")
    threading.Thread(target=recognition_loop, daemon=True).start()
    with sd.RawInputStream(
        samplerate=samplerate,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while True:
            sd.sleep(1000)


if __name__ == "__main__":
    try:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except Exception:
        pass

    main()
