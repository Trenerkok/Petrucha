import os
import time
import threading
import logging
from abc import ABC, abstractmethod
from pygame import mixer
from gtts import gTTS

LOGGER = logging.getLogger(__name__)

class BaseTTSEngine(ABC):
    """Abstract base class for TTS engines."""
    
    @abstractmethod
    def speak(self, text: str):
        pass

class GTTSEngine(BaseTTSEngine):
    """Google Text-to-Speech (Online). Good quality, requires internet."""
    
    def __init__(self):
        try:
            mixer.init()
        except Exception as e:
            LOGGER.error(f"Failed to init mixer: {e}")
        self.lock = threading.Lock()

    def speak(self, text: str):
        if not text: return
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text: str):
        with self.lock:
            filename = "temp_tts.mp3"
            try:
                tts = gTTS(text=text, lang="uk")
                tts.save(filename)

                mixer.music.load(filename)
                mixer.music.play()

                while mixer.music.get_busy():
                    time.sleep(0.1)

                mixer.music.unload()
            except Exception as e:
                LOGGER.error(f"gTTS Error: {e}")
            finally:
                if os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except Exception:
                        pass

class Pyttsx3Engine(BaseTTSEngine):
    """Offline TTS using pyttsx3 (System voices)."""
    
    def __init__(self):
        self.engine = None
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            # Try to set a Ukrainian voice if available, otherwise default
            voices = self.engine.getProperty('voices')
            for voice in voices:
                if "ukraine" in voice.name.lower() or "ukr" in voice.id.lower():
                    self.engine.setProperty('voice', voice.id)
                    break
        except ImportError:
            LOGGER.error("pyttsx3 not installed.")
        except Exception as e:
            LOGGER.error(f"pyttsx3 init error: {e}")

    def speak(self, text: str):
        if not self.engine or not text:
            return
        # pyttsx3 runAndWait blocks, so we run it in a thread
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text: str):
        try:
            # Re-initializing inside thread is sometimes safer for pyttsx3 on some platforms
            # but usually sharing the engine instance with locking is preferred.
            # Here we use a simple lock approach if needed, but pyttsx3 has its own loop.
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            LOGGER.error(f"pyttsx3 speak error: {e}")

class TTSFactory:
    """Factory to create the appropriate TTS engine based on config."""
    
    @staticmethod
    def create_engine(engine_type: str) -> BaseTTSEngine:
        LOGGER.info(f"Initializing TTS Engine: {engine_type}")
        if engine_type == "pyttsx3":
            return Pyttsx3Engine()
        else:
            return GTTSEngine()