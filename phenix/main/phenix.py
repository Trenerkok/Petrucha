import os
import json
import queue
import sounddevice as sd
import vosk
import threading
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
        "lamp_off":("лампа","вимкни лампу","виключи лампу","вимкни світло")
    }
}
# --- ваші девайси ---
arduino = serial.Serial('COM3', 9600)
time.sleep(2)

# --- vosk ---
model_path = "uk_v3/model"
samplerate = 16000
model = vosk.Model(model_path)
rec = vosk.KaldiRecognizer(model, samplerate)
q = queue.Queue()

# --- tts init ---
mixer.init()

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

    elif cmd == "servo":
        arduino.write(b'1')
        print("Команда відправлена!")
    elif cmd == "lamp":
        arduino.write(b'2')
        print("comand succes")
    elif cmd == "lamp_off":
        arduino.write(b'3')
        print("off")

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
        else :
            speak('Випала Копійка')

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    q.put(bytes(indata))

def wait_for_alias(text):
    """Розпізнавання alias для активації."""
    for alias in opts['alias']:
        if alias in text.lower():
            return True
    return False

def voice_mode():
    print("Система уважно слухає… Скажіть 'Петро' чи інше звернення для активації.")
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if text:
                if wait_for_alias(text):
                    print(f"Активація: звернулись як '{text}'")
                    speak("Я слухаю тебе.")
                    command_mode()
                else:
                    print(f"Ігнор — розпізнано '{text}'")

def command_mode():
    """Петро виконує всі розпізнані команди у реченні."""
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if text:
                print(f"Отримано фразу: {text}")
                cmds, extra = match_commands(text)
                if cmds:
                    for cmd, _ in cmds:
                        execute_cmd(cmd, extra)
                        if cmd in ["stop_petro", "close_petro"]:
                            speak("Повертаюсь у режим очікування.")
                            return
                else:
                    speak("Жодну команду не розпізнано, скажіть ще раз чи 'стоп' для виходу.")


def main():
    threading.Thread(target=voice_mode, daemon=True).start()
    with sd.RawInputStream(samplerate=samplerate, dtype='int16', channels=1, callback=audio_callback):
        while True:
            sd.sleep(1000)

if __name__ == "__main__":
    main()
