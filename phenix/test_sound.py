import queue
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
from fuzzywuzzy import fuzz

# --- Завантаження моделі ---
# tiny - максимально швидко, small - точніше, але трохи повільніше
model = WhisperModel("tiny", device="cpu", compute_type="int8")

# --- Черга для аудіо ---
audio_queue = queue.Queue()
samplerate = 16000
blocksize = 512  # маленькі блоки для мінімальної затримки

# --- Список ключових команд ---
commands = ["відкрий браузер", "запусти музику", "скажи час", "пошук в Google"]

# --- Функція колбек для мікрофона ---
def audio_callback(indata, frames, time, status):
    if status:
        print("⚠️", status)
    audio_queue.put(indata.copy())

# --- Функція для пошуку найближчої команди ---
def match_command(text):
    text = text.lower()
    best_score = 0
    best_cmd = None
    for cmd in commands:
        score = fuzz.ratio(text, cmd)
        if score > best_score:
            best_score = score
            best_cmd = cmd
    if best_score > 60:  # поріг відповідності
        return best_cmd
    return None

# --- Основний цикл ---
with sd.InputStream(samplerate=samplerate, channels=1, blocksize=blocksize, callback=audio_callback):
    print("🎤 Говоріть команду... (Ctrl+C щоб зупинити)")
    audio_buffer = np.zeros(0, dtype=np.float32)

    try:
        while True:
            while not audio_queue.empty():
                chunk = audio_queue.get()
                audio_buffer = np.concatenate((audio_buffer, chunk[:, 0]))

            # Якщо накопичилося 0.5 секунди аудіо → обробляємо
            if len(audio_buffer) > samplerate * 0.5:
                # Нормалізація
                audio_input = audio_buffer / np.max(np.abs(audio_buffer))

                # Розпізнавання
                segments, info = model.transcribe(audio_input, language="uk")
                text = " ".join([seg.text for seg in segments]).strip()
                if text:
                    cmd = match_command(text)
                    if cmd:
                        print(f"🗣️ Розпізнана команда: {cmd}")
                    else:
                        print(f"🗣️ Ви сказали: {text}")

                # Очищуємо буфер
                audio_buffer = np.zeros(0, dtype=np.float32)

    except KeyboardInterrupt:
        print("\nЗавершено.")
