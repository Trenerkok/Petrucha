import os
import json
import queue
import logging
import threading
import sounddevice as sd
import vosk
import speech_recognition as sr
import numpy as np
from abc import ABC, abstractmethod

LOGGER = logging.getLogger(__name__)

class STTProvider(ABC):
    """
    Abstract base class for Speech-to-Text providers.
    """
    @abstractmethod
    def listen_loop(self, callback, stop_event: threading.Event, level_callback=None):
        """
        Main listening loop.
        :param callback: function(text: str) to call when speech is recognized.
        :param stop_event: threading.Event to signal when to stop listening.
        :param level_callback: function(level: int) 0-100 to visualize mic volume.
        """
        pass

class VoskSTT(STTProvider):
    """
    Offline STT using Vosk and SoundDevice.
    """
    def __init__(self, model_path="uk_v3/model"):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vosk model not found at: {model_path}")
        
        LOGGER.info(f"Loading Vosk model from {model_path}...")
        self.model = vosk.Model(model_path)
        self.samplerate = 16000
        LOGGER.info("Vosk model loaded.")

    def listen_loop(self, callback, stop_event: threading.Event, level_callback=None):
        q = queue.Queue()

        def audio_callback(indata, frames, time, status):
            if status:
                LOGGER.warning(f"Audio status: {status}")
            # Copy data to queue
            q.put(bytes(indata))
            
            # Calculate RMS for visualizer
            if level_callback:
                try:
                    # Convert to numpy array to calc RMS
                    audio_data = np.frombuffer(indata, dtype=np.int16)
                    rms = np.sqrt(np.mean(audio_data**2))
                    # Normalize roughly to 0-100 (assuming 16-bit audio)
                    # 32768 is max value. Let's say 5000 is "loud".
                    level = min(int((rms / 3000) * 100), 100)
                    level_callback(level)
                except Exception:
                    pass

        rec = vosk.KaldiRecognizer(self.model, self.samplerate)
        
        try:
            with sd.RawInputStream(samplerate=self.samplerate, blocksize=4000, 
                                   dtype='int16', channels=1, callback=audio_callback):
                LOGGER.info("Vosk listening started.")
                while not stop_event.is_set():
                    try:
                        data = q.get(timeout=0.5)
                        if rec.AcceptWaveform(data):
                            res = json.loads(rec.Result())
                            text = res.get("text", "")
                            if text:
                                callback(text)
                    except queue.Empty:
                        continue
        except Exception as e:
            LOGGER.error(f"Vosk stream error: {e}")
            callback(f"[System Error] Vosk failed: {e}")

class OnlineSTT(STTProvider):
    """
    Online STT using Google Speech Recognition.
    """
    def __init__(self, language="uk-UA"):
        self.recognizer = sr.Recognizer()
        self.language = language
        self.mic = sr.Microphone()
        LOGGER.info("Online STT initialized.")

    def listen_loop(self, callback, stop_event: threading.Event, level_callback=None):
        LOGGER.info("Online STT listening started.")
        
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

        while not stop_event.is_set():
            try:
                with self.mic as source:
                    # We can't easily get real-time RMS from recognize_google flow 
                    # without rewriting the library usage. 
                    # We will just pulse the level to show activity if needed, 
                    # or leave it at 0.
                    if level_callback: level_callback(10) # Idle indicator
                    
                    try:
                        audio = self.recognizer.listen(source, timeout=1.0, phrase_time_limit=10.0)
                        if level_callback: level_callback(50) # Processing indicator
                    except sr.WaitTimeoutError:
                        continue 

                if stop_event.is_set():
                    break

                try:
                    text = self.recognizer.recognize_google(audio, language=self.language)
                    if text:
                        callback(text.lower())
                except sr.UnknownValueError:
                    pass 
                except sr.RequestError as e:
                    LOGGER.error(f"Google API Error: {e}")
                    callback(f"[System Error] Google API: {e}")

            except Exception as e:
                LOGGER.error(f"Online STT Loop Error: {e}")
                stop_event.wait(1.0)