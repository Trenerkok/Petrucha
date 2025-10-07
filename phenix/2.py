import os
import sys
import time 
import pygame
from keyboard import wait
import webbrowser 
import pyautogui
from pygame import mixer
import random
import asyncio
from asyncio import WindowsSelectorEventLoopPolicy
from gtts import gTTS
import speech_recognition as sr
import pyttsx3
from pynput.keyboard import Key,Controller
from datetime import datetime
import pywhatkit as kit
import requests
from bs4 import BeautifulSoup
from g4f.client import Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options



letter_list = ["душ не баня", "кешбек", "мінет", "мудрість", "правая ручонка", "ровесники", "салам пацанам", "чорні і мило", "шкура", "метал"]

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

pygame.init()

mixer.init()

def speak(text):
    print(text)

    filename = "text.mp3"
    speech = gTTS(text=text, lang="uk", slow=False)
    speech.save(filename)

    mixer.music.load(filename)
    mixer.music.set_volume(1)
    mixer.music.play()

    while mixer.music.get_busy():
        time.sleep(0.1)  # щоб не грузити CPU

    mixer.music.unload()   # звільняємо файл
    os.remove(filename)    # тепер можна видалити
    
def callback(recognizer, audio):
    global voice

    try:
        voice = recognizer.recognize_google(audio, language = "uk-UA").lower()
        print("[log] розпізнано: " + voice)
    
        if voice.startswith(opts["alias"]):
            cmd = voice

            for x in opts['alias']:
                cmd = cmd.replace(x, "").strip()
            
            for x in opts['tbr']:
                cmd = cmd.replace(x, "").strip()
            
            cmd = recognize_cmd(cmd)
            execute_cmd(cmd['cmd'])
 
    except sr.UnknownValueError:
        print("[log] Голос не розпізнаний!") 
    except sr.RequestError as e:
        print("[log] нема мінета!!!")
 
def recognize_cmd(cmd):
    RC = {'cmd': '', 'percent': 0}
    for c,v in opts['cmds'].items():
 
        for x in v:
            vrt = fuzz.ratio(cmd, x)
            if vrt > RC['percent']:
                RC['cmd'] = c
                RC['percent'] = vrt
    
    return RC
 
def execute_cmd(cmd):
    global voice

    keyboard = Controller()

    ##if cmd == "letters":
    #    random_integer = random.randint(0,len(letter_list)-1) 
    #    print(random_integer) 
    #    
     #   pygame.mixer.music.load(letter_list[random_integer]+".mp3")
    #    pygame.mixer.music.play(0)
###############################################################################
    if cmd == "ctime":

        current_time = datetime.now()
        current_hms = str(current_time)[str(current_time).index(" "):str(current_time).index(".")-3]

        speak("Поточний час -" + str(current_hms))
###############################################################################
    elif cmd == "dota":
        os.system("start Steam://rungameid/570")
###############################################################################
    elif cmd == "Hello":
        speak("я твоя мама рот джаґа-джаґа")
###############################################################################
    elif cmd == "youtube":
        speak("Що би ви хотіли сьогодні подивитися?")
        with sr.Microphone(device_index=2) as source:
            r.adjust_for_ambient_noise(source)
            audio = r.listen(source)
            plus_voice = r.recognize_google(audio, language="uk-UA").lower()
        url = "https://www.youtube.com/results?search_query=" + plus_voice
        webbrowser.open(url)
        speak("Ось відео, які вдалось знайти по данному запиті в ютуб")

###############################################################################
    elif cmd == "music":
        speak("Яку пісню ви хочете почути?")
        try:
            # Розпізнавання голосу
            with sr.Microphone(device_index=2) as source:
                r.adjust_for_ambient_noise(source)
                audio = r.listen(source)
                plus_voice = r.recognize_google(audio, language="uk-UA").lower()

            # Формування URL пошуку на YouTube
            url = "https://www.youtube.com/results?search_query=" + plus_voice

            # Ініціалізація WebDriver
            driver = webdriver.Chrome()
            driver.get(url)  # Відкриваємо результати пошуку

            try:
                # Знаходимо перше відео
                first_result = driver.find_element(By.XPATH, "(//a[@id='video-title'])[1]")
                
                # Клік по відео для його відкриття
                first_result.click()
                print("Відтворення відео розпочато.")
            except Exception as e:
                print(f"Не вдалося знайти перше відео: {e}")
            finally:
                # Зачекайте кілька секунд перед закриттям, якщо потрібно
                input("Натисніть Enter, щоб закрити браузер...")
                driver.quit()  # Закриваємо WebDriver після завершення
        except Exception as e:
            print(f"Помилка розпізнавання голосу: {e}")
        
###############################################################################
    elif cmd == "google":
    
        new_voice = voice
        for i in range(2):
            new_voice = new_voice[:new_voice.index(" ")]+new_voice[new_voice.index(" ")+1:]

        new_voice = new_voice[new_voice.index(' '):]
        plus_voice = new_voice.replace(" ", "+")[1:]

        url = "https://www.google.com/search?q=" + plus_voice
        webbrowser.open(url)

        speak("Ось дані, які вдалось знайти по данному запиті у гугл")
        
###############################################################################
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
####################################################################################
    elif cmd =="film_search":
        recognizer = sr.Recognizer()
        speak("Який фільм ви хочете знайти?")
        
        with sr.Microphone(device_index=2) as source:
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source)
            
        try:
            # Розпізнавання голосу
            film_name = recognizer.recognize_google(audio, language="uk-UA").lower()
            search_query = f"https://uakino.me/search/{film_name.replace(' ', '%20')}"
            
            # Запуск браузера
            driver = webdriver.Chrome()
            driver.get(search_query)
            
            # Клік на перший результат
            try:
                first_result = driver.find_element(By.XPATH, "(//a[contains(@href, 'film')])[1]")
                first_result.click()
                print("Відтворення відео розпочато.")
            except Exception as e:
                print(f"Не вдалося знайти перше відео: {e}")
            finally:
                input("Натисніть Enter, щоб закрити браузер...")
                driver.quit()
                
        except sr.UnknownValueError:
            print("Не вдалося розпізнати голос. Спробуйте ще раз.")
        except sr.RequestError as e:
            print(f"Помилка з'єднання: {e}")
####################################################################################
    elif cmd =="film":
        with open('film.txt', 'r', encoding='utf-8') as file:
            movies = file.readlines()
        random_movies = random.sample(movies, 10)

        for movie in random_movies:
            speak(movie)
####################################################################################
    elif cmd == "rugachka":

        speak("тут має бути відриг воробйова, але мій разраб - даун")   
####################################################################################

    elif cmd == "power_off":
        speak("вимикаю комп'ютер") 
        os.system('shutdown /p /f')    
####################################################################################
    elif cmd == "sleep":
        speak("ввожу комп'ютер у сон") 
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
####################################################################################
    elif cmd == "dota":
        os.system("start Steam://rungameid/570")
####################################################################################
    elif cmd == "cs":
        speak("Колька-Го-кейса")
        os.system("start Steam://rungameid/730")
####################################################################################
    elif cmd == "wiki":
        speak("що вас цікавить")
        speak("відповідь буде англійською")
        try:
            with sr.Microphone(device_index=2) as source:
                r.adjust_for_ambient_noise(source)
                audio = r.listen(source)
                plus_voice = r.recognize_google(audio, language="uk-UA").lower()
            try:
                info = kit.info(plus_voice, lines=3)
                speak("ось що вдалося знайти")
                speak(info)
            except Exception as e:
                print("Виникла помилка:", e)
        except Exception as e:
            print(f"Помилка розпізнавання голосу: {e}")

####################################################################################
    elif cmd == "volume_up":
        random_voice = voice

        x_volumeup = int(random_voice[random_voice.index("на")+3:])
        for i in range(round(x_volumeup/2)):
            keyboard.press(Key.media_volume_up)
            keyboard.release(Key.media_volume_up)
####################################################################################
    elif cmd == "volume_down":
        random_voice = voice

        x_volumedown = int(random_voice[random_voice.index("на")+3:])
        for i in range(round(x_volumedown/2)):
            keyboard.press(Key.media_volume_down)
            keyboard.release(Key.media_volume_down)
####################################################################################
    elif cmd == 'set_volume':
        random_voice = voice
        x_volumeset = int(random_voice[random_voice.index('на')+3:])
        for i in range(100):
            keyboard.press(Key.media_volume_down)
            keyboard.release(Key.media_volume_down)
        for n in range(round(x_volumeset/2)):
            keyboard.press(Key.media_volume_up)
            keyboard.release(Key.media_volume_up)
####################################################################################
    elif cmd == "close_petro":
        speak("пішов нахуй, силюк єбаний")
        os._exit(0)
####################################################################################
    elif cmd == 'coin':
        if random.randint(1,2) == 1:
            speak("Випав герб")
        else :
            speak('Випала Копійка')
####################################################################################
    elif cmd == "newYear":
        speak("з новим роком та різдвом христовим")
        url = "https://www.youtube.com/watch?v=E8gmARGvPlI"
        webbrowser.open(url)
#####################################################################################
    elif cmd == "gpt":
        speak("Задайте своє запитання.")
        with sr.Microphone(device_index=2) as source:
            r.adjust_for_ambient_noise(source)
            speak("Я вас слухаю.")
            try:
                audio = r.listen(source, timeout=10, phrase_time_limit=20)
                question = r.recognize_google(audio, language="uk-UA").lower()
                print(f"[log] Питання користувача: {question}")
                
                # Взаємодія з GPT
                client = Client()
                speak('зачекайте')
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": question}],
                    )
                    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
                    answer = response.choices[0].message.content
                    speak(answer)
                except Exception as e:
                    print(f"Помилка отримання відповіді від GPT: {e}")
                    speak("На жаль, не вдалося отримати відповідь. Спробуйте пізніше.")
            except sr.UnknownValueError:
                speak("Не вдалося розпізнати запитання.")
            except sr.WaitTimeoutError:
                speak("Час на відповідь вичерпано.")
            except sr.RequestError as e:
                speak(f"Помилка сервера розпізнавання мовлення: {e}")


####################################################################################
    elif cmd == "stop_petro":
        speak("Перехожу в режим очікування")
        wait("win + esc")
        speak("Вихід з режиму очікування")
r = sr.Recognizer()
m = sr.Microphone(device_index = 1)
 
with m as source:
    r.adjust_for_ambient_noise(source)
 
speak_engine = pyttsx3.init()
 
voices = speak_engine.getProperty('voices')
speak_engine.setProperty('voice', voices[1].id)
 
speak("Доброго дня, Петруча слухає")
 
stop_listening = r.listen_in_background(m, callback)
while True: time.sleep(0.40) # infinity loop