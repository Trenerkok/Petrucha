import os
import threading
import logging
import time
from pygame import mixer
from gtts import gTTS

LOGGER = logging.getLogger(__name__)

# Спроба імпорту Torch
HAS_TORCH = False
try:
    import torch
    import torchaudio
    HAS_TORCH = True
except (ImportError, OSError) as e:
    LOGGER.warning(f"Silero/Torch недоступні: {e}")
    HAS_TORCH = False

# Спроба імпорту Scipy (резервний метод збереження)
try:
    import scipy.io.wavfile
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

class TTSEngine:
    def __init__(self, config):
        self.cfg = config
        try: mixer.init()
        except: pass
        self.lock = threading.Lock()
        self.silero_model = None
        self.silero_device = None

        # Preload Silero if selected
        if self.cfg.get("tts_engine") == "silero" and HAS_TORCH:
            self._init_silero()

    def _init_silero(self):
        if self.silero_model: return
        LOGGER.info("Ініціалізація Silero TTS...")
        try:
            self.silero_device = torch.device('cpu')
            # Завантажуємо модель (вона вже має бути в кеші після вашого тесту)
            self.silero_model, _ = torch.hub.load(repo_or_dir='snakers4/silero-models',
                                                  model='silero_tts',
                                                  language='ua',
                                                  speaker='v4_ua')
            self.silero_model.to(self.silero_device)
            LOGGER.info("Silero TTS успішно завантажено.")
        except Exception as e:
            LOGGER.error(f"Silero Init Failed: {e}")
            global HAS_TORCH
            HAS_TORCH = False

    def speak(self, text):
        if not text: return
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text):
        engine_type = self.cfg.get("tts_engine", "gtts")
        
        with self.lock:
            filename = "out.wav"
            # Очистка попереднього файлу
            if os.path.exists(filename):
                try: os.remove(filename)
                except: pass

            try:
                # --- SILERO ---
                if engine_type == "silero" and HAS_TORCH:
                    if not self.silero_model: self._init_silero()
                    
                    if self.silero_model:
                        # Генеруємо тензор аудіо
                        audio_tensor = self.silero_model.apply_tts(
                            text=text,
                            speaker='mykyta', # 'mykyta' або 'lada'
                            sample_rate=48000,
                            put_accent=True,
                            put_yo=True
                        )

                        # СПРОБА 1: Torchaudio (стандарт)
                        saved = False
                        try:
                            # Явно вказуємо backend, якщо soundfile встановлено
                            if os.name == 'nt': # Windows fix
                                import soundfile # Перевірка наявності
                                torchaudio.set_audio_backend("soundfile")
                            
                            torchaudio.save(filename, audio_tensor.unsqueeze(0), 48000)
                            saved = True
                        except Exception as e:
                            LOGGER.warning(f"Torchaudio save failed ({e}), trying Scipy...")

                        # СПРОБА 2: Scipy (Резерв)
                        if not saved and HAS_SCIPY:
                            try:
                                audio_np = audio_tensor.squeeze().numpy()
                                scipy.io.wavfile.write(filename, 48000, audio_np)
                                saved = True
                            except Exception as e:
                                LOGGER.error(f"Scipy save failed: {e}")

                        if not saved:
                            raise RuntimeError("Не вдалося зберегти файл жодним методом.")

                    else:
                        # Fallback
                        self._gtts_speak(text, "out.mp3")
                        filename = "out.mp3"

                # --- PYTTSX3 ---
                elif engine_type == "pyttsx3":
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.save_to_file(text, filename)
                    engine.runAndWait()
                
                # --- GTTS (Default) ---
                else: 
                    filename = "out.mp3"
                    self._gtts_speak(text, filename)

                # --- PLAYBACK ---
                if os.path.exists(filename):
                    mixer.music.load(filename)
                    mixer.music.play()
                    while mixer.music.get_busy():
                        time.sleep(0.1)
                    mixer.music.unload()
                    try: os.remove(filename)
                    except: pass
                else:
                    LOGGER.error("Файл аудіо не створено.")
                
            except Exception as e:
                LOGGER.error(f"TTS Error ({engine_type}): {e}")
                # Остання надія - gTTS
                if engine_type == "silero":
                    try:
                        self._gtts_speak(text, "fallback.mp3")
                        mixer.music.load("fallback.mp3")
                        mixer.music.play()
                        while mixer.music.get_busy(): time.sleep(0.1)
                        mixer.music.unload()
                    except: pass

    def _gtts_speak(self, text, filename):
        tts = gTTS(text, lang="uk")
        tts.save(filename)