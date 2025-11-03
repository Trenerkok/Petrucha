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
import asyncio
from pynput.keyboard import Key, Controller
import pywhatkit as kit
import requests
from bs4 import BeautifulSoup
from g4f.client import Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import uuid
from gtts import gTTS
import paramiko

opts = {
    "alias":("петруча", "петро", "петр", "петре", "петруче", "пєтька","петька","петросян", "пьотрік", "петя пяточкін", "пєтя", "петя", "пєтя пяточкін", "петруша"),
    "tbr":("розкажи","покажи","скільки","скажи", "увімкни програму", "увімкни", "запусти", "запусти програму", "ввімкни програму", "увімкни гру", "запусти гру", "ввімкни гру"),
    "cmds":{
        "ctime": ("поточний час", "котрий час", "яка година", "котра година", "скільки годин", "поточна година", "час"),
        "youtube": ("увімкни відео", "ввімкни відео", "включи відео", "знайди відео"),
        "pogoda":("погода","гуляти"),
        "google":("загугли", "подивись у гугл", "знайди у гугл", "подивись в google", "знайди в google"),
        "Hello":("привіт", "здоров був", "салам", "саламуля"),
        "power_off":("вимкни комп'ютер", "виключи комп'ютер", "вимкни комп", "виключи комп"),
        "sleep":("сон", "введи комп'ютер у сон", "введи комп'ютер в сон"),
        "auto":("запусти пакет програм", "відкрий програми автозапуску", "увімкни програми автозапуску"),
        "close_petro":("пака", "допобачення", "до зустрічі", "уїбан, до зустрічі"),
        "random":("випадкове число від", "випадкова цифра від"),
        "volume_up":("збільшити гучніть на", "збільшити звук на", "збільшити басок на", "збільшити бас на"),
        "volume_down":("зменшити гучність на", "зменшити звук на", "зменшити басок на", "зменшити бас на",'зменшує гучність'),
        "set_volume":("встанови гучність на", "встанови звук на", "встанови бас на"),
        "coin":('підкинь копійку',"підкинь монетку"),
        "server":('онови пакети','зроби оновлення','основи пакети','оновив пакети'),
        "stop_petro":("стоп", "зупинись", "пауза")
    }
}

model_path = "uk_v3/model"
samplerate = 16000
model = vosk.Model(model_path)
rec = vosk.KaldiRecognizer(model, samplerate)
q = queue.Queue()

mixer.init()

def speak(text):
    print(f"[TTS] {text}")
    try:
        filename = "text.mp3"
        tts = gTTS(text=text, lang="uk")
        tts.save(filename)

        mixer.init()
        mixer.music.load(filename)
        mixer.music.play()

        while mixer.music.get_busy():
            time.sleep(0.1)

        mixer.music.unload()
        mixer.quit()
        os.remove(filename)
    except Exception as e:
        print(f"[Помилка TTS] {e}")

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

    elif cmd == "pogoda":
        speak("Перевіряю погоду...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get('https://meteofor.com.ua/weather-volodymyr-4927/now/')
        html = driver.page_source
        speak(f"станом на {datetime}")
        soup = BeautifulSoup(html, 'html.parser')
        divs = soup.find_all('div', class_='now-desc')
        titles = soup.find_all('div', class_='now-feel')
        temp = soup.find_all('div', class_='now-weather')
        pot = soup.find_all('div', class_='now-localdate')
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
        SU_PASSWORD = "123456"  # пароль для su
        
        def ssh_interactive_su_command(cmd):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(HOST, port=PORT, username=USERNAME, password=PASSWORD, timeout=10)
            except Exception as e:
                print("Connect failed:", e)
                return
        
            channel = client.invoke_shell()
            time.sleep(1)  # початковий вивід
            while channel.recv_ready():
                print(channel.recv(1024).decode(errors='ignore'), end='')
        
            # Надсилаємо команду переходу в su
            channel.send("su\n")
            time.sleep(1)
        
            # Чекаємо запит пароля su і відправляємо пароль
            if channel.recv_ready():
                output = channel.recv(1024).decode(errors='ignore')
                print(output, end='')
                if "Password:" in output or "password:" in output:
                    channel.send(SU_PASSWORD + "\n")
        
            time.sleep(1)
            # Читаємо відповідь після вводу пароля su
            while channel.recv_ready():
                print(channel.recv(1024).decode(errors='ignore'), end='')
        
            # Тепер виконуємо вашу команду від імені суперкористувача
            print(f"Executing as su: {cmd}")
            channel.send(cmd + "\n")
        
            # Виводимо відповідь
            while True:
                time.sleep(0.1)
                if channel.recv_ready():
                    output = channel.recv(1024).decode(errors='ignore')
                    print(output, end='')
                if channel.exit_status_ready():
                    break
                channel.close()
                client.close()
        if __name__ == "__main__":
            ssh_interactive_su_command("systemctl reboot -i")

    elif cmd == "Hello":
        speak("Привіт, я уважно тебе слухаю")

    elif cmd == "youtube":
    
        new_voice = voice
        for i in range(2):
            new_voice = new_voice[:new_voice.index(" ")]+new_voice[new_voice.index(" ")+1:]

        new_voice = new_voice[new_voice.index(' '):]
        plus_voice = new_voice.replace(" ", "+")[1:]

        url = "https://www.youtube.com/results?search_query=" + plus_voice
        webbrowser.open(url)

        speak("Ось відео, які вдалось знайти по даному запиті в ютуб")

    elif cmd == "google":
    
        new_voice = voice
        for i in range(2):
            new_voice = new_voice[:new_voice.index(" ")]+new_voice[new_voice.index(" ")+1:]

        new_voice = new_voice[new_voice.index(' '):]
        plus_voice = new_voice.replace(" ", "+")[1:]

        url = "https://www.google.com/search?q=" + plus_voice
        webbrowser.open(url)

        speak("Ось дані, які вдалось знайти по даному запиті у гугл")

    elif cmd == "rugachka":

        speak("тут має бути відриг воробйова, але мій разраб - даун")   

    elif cmd == "power_off":
        speak("вимикаю комп'ютер") 
        os.system('shutdown now -h')    

    elif cmd == "sleep":
        speak("ввожу комп'ютер у сон") 
        os.system("systemctl suspend")

    elif cmd == "volume_up":
        random_voice = voice

        x_volumeup = int(random_voice[random_voice.index("на")+3:])
        for i in range(round(x_volumeup/2)):
            keyboard.press(Key.media_volume_up)
            keyboard.release(Key.media_volume_up)
            
    elif cmd == "volume_down":
        random_voice = voice

        x_volumedown = int(random_voice[random_voice.index("на")+3:])
        for i in range(round(x_volumedown/2)):
            keyboard.press(Key.media_volume_down)
            keyboard.release(Key.media_volume_down)

    elif cmd == 'set_volume':
        random_voice = voice
        x_volumeset = int(random_voice[random_voice.index('на')+3:])
        for i in range(100):
            keyboard.press(Key.media_volume_down)
            keyboard.release(Key.media_volume_down)
        for n in range(round(x_volumeset/2)):
            keyboard.press(Key.media_volume_up)
            keyboard.release(Key.media_volume_up)

    elif cmd == "close_petro":

        speak("до нових зустрічей")
        os._exit(0)

    elif cmd == "random":

        random_voice = voice
        int1 = random_voice[:random_voice.index(" до ")]

        for i in range(3):
            int1 = int1[:int1.index(" ")]+int1[int1.index(" ")+1:]
        int1 = int(int1[int1.index(' ')+1:])

        int2 = int(random_voice[random_voice.index("до")+3:])

        print(str(int1))
        print(str(int2))
        random_integer = random.randint(int1, int2)

        speak("випадкове число від " + str(int1) + " до " + str(int2) + ": ")
        speak(str(random_integer))

    elif cmd == 'coin':
        
        if random.randint(1,2) == 1:
            speak("Випав герб")
        else :
            speak('Випала Копійка')

    elif cmd == "stop_petro":
        speak("Перехожу в режим очікування")
        wait("ctrl + alt + del")
        speak("Вихід з режиму очікування")

def audio_callback(indata, frames, time_info, status):
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
    try:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except Exception:
        pass

    main()
