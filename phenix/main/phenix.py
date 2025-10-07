import os
import json
import queue
import sounddevice as sd               # захоплення аудіо з мікрофона
import vosk                           # розпізнавання голосу офлайн
import threading                      # запуск потоків для відокремленої обробки
from datetime import datetime         # отримання поточного часу
import random                        # генерація випадкових чисел
import pyttsx3                       # синтез мови офлайн
import sys
import time 
import webbrowser                    # відкриття веб-браузера
import pyautogui                     # керування мишкою/клавіатурою
from pygame import mixer            # для відтворення аудіо файлів (альтернатива pyttsx3)
import asyncio                      # асинхронна робота
from asyncio import WindowsSelectorEventLoopPolicy
from pynput.keyboard import Key, Controller   # емулювання клавіатури
import pywhatkit as kit             # керування медіа і веб-сервісами
import requests                    # HTTP-запити
from bs4 import BeautifulSoup      # парсинг веб-сторінок
from g4f.client import Client      # доступ до GPT-4o mini
from selenium import webdriver     # автоматизація веб-браузера
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import uuid                       # генерація унікальних ідентифікаторів
from gtts import gTTS

# Ваші команди та налаштування
opts = {
    "alias": ("петруча", "петро", "петр", "петре", "петруче"),
    "tbr": ("скажи", "покажи", "розкажи", "запусти"),
    "cmds": {
        "ctime": ("час", "година", "котрий час"),
        #"power_off": ("вимкни комп'ютер", "виключи комп'ютер"),
        # Додайте інші команди тут
        "pogoda":("погода","іти гуляти"),
    }
}

# Параметри vosk
model_path = "uk_v3/model"  # шлях до моделі
samplerate = 16000

# Ініціалізація моделі та розпізнавача
model = vosk.Model(model_path)
rec = vosk.KaldiRecognizer(model, samplerate)

# Черга з аудіо
q = queue.Queue()

def speak(text):
    print(text)

    speech = gTTS(text=text, lang="uk", slow=False)
    filename = "text.mp3"
    speech.save(filename)
    mixer.init()
    mixer.music.load(filename)
    mixer.music.set_volume(1)
    mixer.music.play()

    while mixer.music.get_busy():
        time.sleep(0.1)
    os.remove(filename)  # видаляємо файл після відтворення

def match_command(text):
    text = text.lower()
    for alias in opts['alias']:
        if text.startswith(alias):
            text = text.replace(alias, "").strip()
            for tbr in opts['tbr']:
                if text.startswith(tbr):
                    text = text.replace(tbr, "").strip()
            break

    for cmd, phrases in opts['cmds'].items():
        for phrase in phrases:
            if phrase in text:
                return cmd
    return None

def execute_cmd(cmd):
    if cmd == "ctime":
        now = datetime.now().strftime("%H:%M:%S")
        speak(f"Поточний час {now}")
    #elif cmd == "power_off":
    #    speak("Вимикаю комп'ютер")
    #    os.system("shutdown /p /f")
    elif cmd == "pogoda":
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get('https://meteofor.com.ua/weather-volodymyr-4927/now/')
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        divs = soup.find_all('div', class_='now-desc')
        titles = soup.find_all('div', class_='now-feel')
        temp = soup.find_all('div', class_='now-weather')
        pot = soup.find_all('div', class_='now-localdate')
        for poto in pot:
            speak("станом на")
            speak(poto.get_text())
        for div in divs:
            speak("зараз у місті Володимир")
            speak(div.get_text())
        for tempe in temp:
            speak("температура")
            speak(tempe.get_text())
        for title in titles:
            speak(title.get_text())
        driver.quit()
    else:
        speak(f"Команда {cmd} не реалізована")

def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(bytes(indata))

def recognition_loop():
    print("Система очікує команд...")
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if text:
                print(f"Розпізнано: {text}")
                cmd = match_command(text)
                if cmd:
                    execute_cmd(cmd)
                else:
                    print("Команда не розпізнана")

def main():
    threading.Thread(target=recognition_loop, daemon=True).start()
    with sd.RawInputStream(samplerate=samplerate, dtype='int16', channels=1, callback=audio_callback):
        while True:
            sd.sleep(1000)

if __name__ == "__main__":
    main()
