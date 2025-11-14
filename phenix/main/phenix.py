import os
import json
import logging  # BEGIN NLU MOD
import sounddevice as sd
import threading
import numpy as np
import whisper
from datetime import datetime
import random
import sys
import time
import webbrowser
import pyautogui
from pygame import mixer
from pynput.keyboard import Key, Controller
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import serial
import re
from gtts import gTTS
from typing import Optional

# BEGIN NLU MOD
from command_executor import CommandExecutor
from llm_client import LLMClient
from nlu_interpreter import NLUInterpreter
# END NLU MOD

# BEGIN VAD MOD
from vad_recorder import VADUtteranceRecorder
# END VAD MOD

# ----------------
# --- Опції ---
opts = {
    "alias":(
        "петруча", "петро", "петр", "петре", "петруче", "пєтька","петька","петросян", "пьотрік",
        "петя пяточкін", "пєтя", "петя", "пєтя пяточкін", "петруша"
    ),
    "tbr":(
        "розкажи","покажи","скільки","скажи", "увімкни програму", "увімкни", "запусти", "запусти програму",
        "ввімкни програму", "увімкни гру", "запусти гру", "ввімкни гру"
    ),
    "cmds":{
        "ctime": (
            "поточний час", "котрий час", "яка година", "котра година", "скільки годин", "поточна година", "час"
        ),
        "youtube": ("увімкни відео", "ввімкни відео", "включи відео", "знайди відео"),
        "pogoda":("погода","гуляти"),
        "google":(
            "загугли", "подивись у гугл", "знайди у гугл", "подивись в google", "знайди в google"
        ),
        "Hello":("привіт", "здоров був", "салам", "саламуля"),
        "power_off":("вимкни комп'ютер", "виключи комп'ютер", "вимкни комп", "виключи комп"),
        "sleep":("сон", "введи комп'ютер у сон", "введи комп'ютер в сон"),
        "auto":("запусти пакет програм", "відкрий програми автозапуску", "увімкни програми автозапуску"),
        "close_petro":("пака", "допобачення", "до зустрічі", "уїбан, до зустрічі"),
        "random":("випадкове число від", "випадкова цифра від"),
        "volume_up":(
            "збільшити гучність на", "збільшувати гучність на", "збільшує гучність на", "збільши гучність на",
            "збільшити звук на", "збільши звук на", "збільшує звук на"
        ),
        "volume_down":(
            "зменшити гучність на", "зменшуй гучність на", "зменшує гучність на",
            "зменшити звук на", "зменшує звук на", "зменшуй звук на"
        ),
        "set_volume":(
            "встанови гучність на", "встанови звук на", "встанови бас на"
        ),
        "coin":('підкинь копійку',"підкинь монетку"),
        "server":('онови пакети','зроби оновлення','основи пакети','оновив пакети'),
        "stop_petro":("стоп", "зупинись", "пауза"),
        "servo":("сервопривод","градус"),
        "lamp":("лампочка","включи лампу","увімкни лампу","світло"),
        "lamp_off":("лампа","вимкни лампу","виключи лампу","вимкни світло"),
        "llm_test":(
            "перевір підключення до моделі",
            "перевір зв'язок з мовною моделлю",
            "перевір підключення до llm",
        ),
    }
}
# --- ваші девайси ---
#arduino = serial.Serial('COM3', 9600)
#time.sleep(2)

samplerate = 16000
# "small" – нормальний баланс якості/швидкості для української,
# "medium" – ще краще, якщо тягне залізо (у тебе RTX 3070 – тягне).
whisper_model = whisper.load_model("small")  # або "medium"

# --- tts init ---
mixer.init()

# BEGIN NLU MOD
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger(__name__)

DEFAULT_LLM_BASE_URL = "http://127.0.0.1:1234"
DEFAULT_LLM_MODEL = "phi-3.5-mini-instruct"

nlu_interpreter: Optional[NLUInterpreter] = None
structured_executor: Optional[CommandExecutor] = None
# END NLU MOD

# BEGIN VAD MOD
vad_recorder: Optional[VADUtteranceRecorder] = None
# END VAD MOD


def speak(text):
    print(f"[TTS] {text}")
    try:
        filename = "speech_output.mp3"
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


# === VAD-версія запису фрази ===
def record_phrase(seconds: float = 4.0) -> np.ndarray:
    """
    Записати одну фразу з мікрофона за допомогою VAD.
    Параметр seconds залишено для сумісності, але фактично не використовується:
    довжина фрази визначається VAD.
    """
    global vad_recorder
    if vad_recorder is None:
        vad_recorder = VADUtteranceRecorder(
            samplerate=samplerate,
            block_duration=0.1,        # 100 мс блок
            energy_threshold=0.02,     # поріг гучності, потім можна підібрати
            min_voice_blocks=3,
            max_silence_blocks=7,
            max_utterance_duration=10.0,
        )

    print("[AUDIO/VAD] Очікую на фразу...")
    audio = vad_recorder.record_utterance()

    if audio.size > 0:
        print(
            f"[AUDIO/VAD] Отримано {audio.shape[0]} семплів, "
            f"max={float(np.max(np.abs(audio))):.4f}"
        )
    else:
        print("[AUDIO/VAD] Фразу не зафіксовано.")

    return audio


def transcribe_whisper(audio: np.ndarray) -> str:
    """Розпізнати українську фразу через Whisper."""
    if audio is None or audio.size == 0:
        print("[Whisper] Порожнє аудіо, пропускаю транскрипцію.")
        return ""

    # 1) Гарантуємо 1D mono float32
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)

    # 2) Порог по гучності — якщо майже тиша, не ганяємо Whisper
    max_val = np.max(np.abs(audio)) if audio.size > 0 else 0.0
    if max_val < 0.02:
        print(f"[Whisper] Дуже тихий сигнал (max={max_val:.4f}), пропускаю.")
        return ""

    # 3) Нормалізація амплітуди до [-1, 1]
    audio = audio / max_val
    print(f"[Whisper] Audio shape={audio.shape}, max={max_val:.4f}")

    try:
        result = whisper_model.transcribe(
            audio,
            language="uk",        # фіксуємо українську
            task="transcribe",    # НЕ translate → просто розпізнання
            fp16=False,           # для CPU; якщо точно GPU+fp16 – можна True
            temperature=0.0,      # менше «галюцинацій»
            verbose=False,
        )
    except Exception as e:
        print(f"[Whisper] Помилка розпізнавання: {e}")
        return ""

    text = (result.get("text") or "").strip()
    print(f"[Whisper] Розпізнано: {text}")
    return text.lower()


def match_commands(text):
    """Повертає всі команди, що зустрілися у фразі, разом із відповідною частиною тексту."""
    found_cmds = []
    text = text.lower().strip()
    for alias in opts['alias']:
        if text.startswith(alias):
            text = text.replace(alias, "", 1).strip()
            for tbr in opts['tbr']:
                if text.startswith(tbr):
                    text = text.replace(tbr, "", 1).strip()
            break

    for cmd, phrases in opts['cmds'].items():
        for phrase in phrases:
            if phrase in text:
                found_cmds.append((cmd, phrase))
    return found_cmds, text


def extract_number(text):
    """Шукає перше число або словесне представлення числа в тексті."""
    nums = re.findall(r'\d+', text)
    if nums:
        return int(nums[0])
    # приклади для українських слів-чисел
    word_numbers = {
        'нуль': 0, 'один': 1, 'два': 2, 'три': 3, 'чотири': 4, 'п\'ять': 5,
        'десять': 10, 'двадцять': 20
    }
    for word, val in word_numbers.items():
        if word in text:
            return val
    return None


def execute_cmd(cmd, voice=None):
    keyboard = Controller()

    if cmd == "ctime":
        now = datetime.now().strftime("%H:%M:%S")
        speak(f"Поточний час {now}")

    elif cmd == "pogoda":
        speak("Перевіряю погоду...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get('https://meteofor.com.ua/weather-volodymyr-4927/now/')
        html = driver.page_source
        speak("станом на {datetime}")
        soup = BeautifulSoup(html, 'html.parser')
        divs = soup.find_all('div', class_='now-desc')
        temp = soup.find_all('div', class_='now-weather')
        titles = soup.find_all('div', class_='now-feel')
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
        # Додав свій код для SSH, як у твоєму проекті
        pass

    elif cmd == "Hello":
        speak("Привіт, салам, охайо, ола, хело")

    elif cmd == "youtube":
        if voice:
            plus_voice = voice.replace(" ", "+")
            url = "https://www.youtube.com/results?search_query=" + plus_voice
            webbrowser.open(url)
            speak("Ось відео, які вдалось знайти по даному запиту в ютуб")

    elif cmd == "llm_test":
        test_text = (
            "Це тестовий запит. Скажи коротко, що зв'язок з мовною моделлю працює."
        )
        if nlu_interpreter is None:
            speak("NLU наразі недоступний, перевір конфігурацію.")
            return
        try:
            structured_cmds = nlu_interpreter.interpret(test_text)
            if not structured_cmds:
                print("[LLM TEST] Connection FAILED: empty response")
                speak("Я не можу підключитися до мовної моделі.")
                return
            snippet = json.dumps(structured_cmds, ensure_ascii=False)[:100]
            print(f"[LLM TEST] Connection OK, received response: {snippet}")
            speak("Зв'язок з мовною моделлю працює.")
        except Exception as exc:  # pragma: no cover
            print(f"[LLM TEST] Connection FAILED: {exc}")
            speak("Я не можу підключитися до мовної моделі.")

#    elif cmd == "servo":
#        arduino.write(b'1')
#        print("Команда відправлена!")
#    elif cmd == "lamp":
#        arduino.write(b'2')
#        print("comand succes")
#    elif cmd == "lamp_off":
#        arduino.write(b'3')
#        print("off")

    elif cmd == "google":
        if voice:
            plus_voice = voice.replace(" ", "+")
            url = "https://www.google.com/search?q=" + plus_voice
            webbrowser.open(url)
            speak("Ось дані, які вдалось знайти по даному запиту у гугл")

    elif cmd == "power_off":
        speak("вимикаю комп'ютер")
        os.system('shutdown now -h')

    elif cmd == "sleep":
        speak("ввожу комп'ютер у сон")
        os.system("systemctl suspend")

    elif cmd == "volume_up":
        if voice:
            num = extract_number(voice)
            if num:
                for i in range(round(num/2)):
                    keyboard.press(Key.media_volume_up)
                    keyboard.release(Key.media_volume_up)
            else:
                speak("Не можу знайти число для зміни гучності!")

    elif cmd == "volume_down":
        if voice:
            num = extract_number(voice)
            if num:
                for i in range(round(num/2)):
                    keyboard.press(Key.media_volume_down)
                    keyboard.release(Key.media_volume_down)
            else:
                speak("Не можу знайти число для зміни гучності!")
    
    elif cmd == "set_volume":
        if voice:
            num = extract_number(voice)
            if num:
                for i in range(100):
                    keyboard.press(Key.media_volume_down)
                    keyboard.release(Key.media_volume_down)
                for n in range(round(num/2)):
                    keyboard.press(Key.media_volume_up)
                    keyboard.release(Key.media_volume_up)
            else:
                speak("Не можу знайти рівень гучності!")

    elif cmd == "close_petro":
        speak("До зустрічі!")
        os._exit(0)

    elif cmd == "random":
        if voice:
            import re
            match = re.findall(r"\d+", voice)
            if len(match) >= 2:
                int1, int2 = int(match[0]), int(match[1])
                random_integer = random.randint(int1, int2)
                speak(f"Випадкове число від {int1} до {int2}: {random_integer}")

    elif cmd == 'coin':
        if random.randint(1,2) == 1:
            speak("Випав герб")
        else:
            speak('Випала Копійка')


def listen_for_phrase(prompt: str = "Скажи фразу", seconds: float = 4.0) -> str:
    """
    Прослухати одну фразу.
    VAD сам вирішує, коли почати/закінчити запис;
    seconds залишено для сумісності, але фактично не використовується.
    """
    print(prompt)
    audio = record_phrase(seconds=seconds)
    if audio is None or audio.size == 0:
        return ""
    text = transcribe_whisper(audio)
    return text


def main_loop():
    print("Система уважно слухає… Скажи щось, що містить 'Петро' або інше звернення.")

    while True:
        # 1. Слухаємо загальну фразу (тепер довжина визначається VAD)
        text = listen_for_phrase("Слухаю фон...", seconds=4.0)
        if not text:
            continue

        if wait_for_alias(text):
            print(f"Активація: звернулись як '{text}'")
            speak("Я слухаю тебе.")

            # 2. Тепер окремо слухаємо саму команду (теж через VAD)
            cmd_text = listen_for_phrase("Слухаю команду...", seconds=4.0)
            if not cmd_text:
                speak("Я нічого не почув, повтори, будь ласка.")
                continue

            print(f"Отримано команду: {cmd_text}")
            cmds, extra = match_commands(cmd_text)

            if cmds:
                for cmd, _ in cmds:
                    execute_cmd(cmd, extra)
                    if cmd in ["stop_petro", "close_petro"]:
                        speak("Повертаюсь у режим очікування.")
                        return
            else:
                # NLU / LLM
                LOGGER.info("Rule-based parser не знайшов команд. Використовую NLU для: %s", cmd_text)
                if nlu_interpreter and structured_executor:
                    try:
                        structured_cmds = nlu_interpreter.interpret(cmd_text)
                    except Exception as exc:
                        LOGGER.error("[NLU] Error during LLM call: %s", exc)
                        structured_cmds = []

                    if not structured_cmds:
                        speak("Я не зрозумів команду, повтори, будь ласка.")
                    else:
                        for structured_cmd in structured_cmds:
                            handled = structured_executor.execute(structured_cmd)
                            if not handled:
                                speak("Поки що не можу виконати цю команду.")
                else:
                    speak("Я не зрозумів команду, повтори, будь ласка.")


def wait_for_alias(text):
    """Розпізнавання alias для активації."""
    for alias in opts['alias']:
        if alias in text.lower():
            return True
    return False


def main():
    global nlu_interpreter, structured_executor

    # 1. Ініціалізація NLU/LLM
    if nlu_interpreter is None:
        try:
            base_url = os.environ.get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
            model = os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL)
            LOGGER.info("Ініціалізація LLMClient: %s (model=%s)", base_url, model)
            llm_client = LLMClient(
                base_url=base_url,
                model=model,
            )
            nlu_interpreter = NLUInterpreter(llm_client)
        except Exception as exc:
            LOGGER.error("Не вдалося ініціалізувати NLU: %s", exc)
            nlu_interpreter = None

    if structured_executor is None:
        structured_executor = CommandExecutor(speak, execute_cmd)

    # 2. Основний цикл з Whisper + VAD
    print("[MAIN] Старт основного циклу")
    main_loop()


if __name__ == "__main__":
    main()
