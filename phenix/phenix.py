import os
import sys
import pygame
from fuzzywuzzy import fuzz
import json
import queue
import sounddevice as sd   
import vosk                           # розпізнавання голосу офлайн
import threading                      # запуск потоків для відокремленої обробки
from datetime import datetime         # отримання поточного часу
import random   
from thefuzz import fuzz, process

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
    speech.save("text.mp3")
    mixer.init()
    mixer.music.load("text.mp3")
    mixer.music.set_volume(1)
    mixer.music.play()
    mixer.music.get_endevent()
    while mixer.music.get_busy():
        continue
    os.remove("text.mp3")

opts = {
    "alias":("петруча", "петро", "петр", "петре", "петруче", "пєтька","петька","петросян", "пьотрік", "петя пяточкін", "пєтя", "петя", "пєтя пяточкін", "петруша"),
    "tbr":("розкажи","яка зараз", "покажи","скільки","скажи", "увімкни програму", "увімкни", "запусти", "запусти програму", "ввімкни програму", "увімкни гру", "запусти гру", "ввімкни гру"),
    "cmds":{
        "ctime": ("поточний час", "котрий час", "яка година", "котра година", "скільки годин", "поточна година", "час"),
        "youtube": ("увімкни відео", "ввімкни відео", "включи відео", "знайди відео"),
        "google":("загугли", "подивись у гугл", "знайди у гугл", "подивись в гугл", "знайди в гугл", "подивись у google", "знайди у google", "подивись в google", "знайди в google"),
        "dota":("Дота", "dota", "Доту", "дота", "доту", "дода", "гойда"),
        ##"letters":("скажи цитату", "скажи цитатку", "рубани цитату"),
        "Hello":("привіт", "здоров був", "салам", "саламуля"),
        # "google_chek":("подивись в гугл","відкрий сайт"),
        "cs":("го кейса","рубани кейса","кейс","запусти протокол кейс","го в кеесочку"),
        "rugachka":("ригани", "раскумарь", "навали рига", "покажи як лев ричить", "покажи як лев верещить"),
        "power_off":("вимкни комп'ютер", "виключи комп'ютер", "вимкни комп", "виключи комп"),
        "sleep":("сон", "введи комп'ютер у сон", "введи комп'ютер в сон"),
        "close_petro":("пака", "допобачення", "до зустрічі", "уїбан, до зустрічі"),
        "wiki":("вікіпедія","вікі","wiki","знайди у вікіпедії"),
        #"random":("випадкове число від", "випадкова цифра від"),
        "volume_up":("збільшити гучніть на", "збільшити звук на", "збільшити басок на", "збільшити бас на","збільши бас на"),
        "volume_down":("зменшити гучність на", "зменшити звук на", "зменшити басок на", "зменшити бас на"),
        "set_volume":("встанови гучність на", "встанови звук на", "встанови бас на"),
        "coin":('підкинь копійку',"підкинь монетку"),
        "pogoda":("погода","іти гуляти"),
        "film_search":("увімкни фільм","рубани фільм","включи фільм"),
        "film":("знайди фільм на вечір","фільм"),
        "music":("навали музла","рубани музику","включи музику","включи пісню","рубани пісню","увімкни пісню","увімкни музику"),
        "newYear":("новий рік","з новим роком","приотокол новий рік"),
        #"language":("зміни мову","поміняй мову","лангуагє"),   
        "gpt":('дай відповідь на питання',"гпт","gpt"),
        "stop_petro":("стоп", "зупинись", "пауза")
    }
}

def recognize_command(text):
    # Створимо список усіх можливих ключових фраз
    variants = []
    mapping = {}

    for cmd, phrases in opts["cmds"].items():
        for phrase in phrases:
            variants.append(phrase)
            mapping[phrase] = cmd

    # Знайдемо найближчий збіг
    best_match, score = process.extractOne(text, variants, scorer=fuzz.ratio)

    if score >= 70:  # поріг схожості (можна змінити)
        return mapping[best_match], score
    else:
        return None, score

# Тест
print(recognize_command("скільки часу"))   # -> ('ctime', ~80+)
print(recognize_command("привітик"))       # -> ('Hello', ~75+)
print(recognize_command("увімкни ютуб"))   # -> ('youtube', ~70+)
