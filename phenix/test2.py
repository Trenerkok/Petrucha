import sounddevice as sd
import vosk
import queue
import json

# --- Параметри ---
model_path = "uk_v3\\model" # шлях до моделі
samplerate = 16000
commands = ["відкрий браузер", "запусти музику", "скажи час", "пошук в Google"]

# --- Завантаження моделі ---
model = vosk.Model(model_path)
rec = vosk.KaldiRecognizer(model, samplerate)

# --- Черга для аудіо ---
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print("⚠️", status)
    q.put(bytes(indata))

# --- Функція пошуку команд ---
def match_command(text):
    text = text.lower()
    for cmd in commands:
        if cmd in text:
            return cmd
    return None

# --- Основний цикл ---
with sd.RawInputStream(samplerate=samplerate, blocksize = 8000, dtype='int16',
                       channels=1, callback=callback):
    print("🎤 Говоріть команду... (Ctrl+C щоб завершити)")
    try:
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text:
                    cmd = match_command(text)
                    if cmd:
                        print(f"🗣️ Розпізнана команда: {cmd}")
                    else:
                        print(f"🗣️ Ви сказали: {text}")
            else:
                # Частковий результат (можна пропускати або показувати)
                pass

    except KeyboardInterrupt:
        print("\nЗавершено.")
