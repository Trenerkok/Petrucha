import os
import threading
import queue
import json
import re
import logging
import requests
import time
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

import sounddevice as sd
import vosk
import speech_recognition as sr

from config import Config
from system_io import SystemIO
from fast_commands import FastCommandMatcher
from memory import Memory
from audio_utils import TTSEngine
from command_executor import CommandExecutor

LOGGER = logging.getLogger(__name__)

def normalize_text(raw) -> str:
    if not raw: return ""
    if isinstance(raw, dict):
        for k in ["answer_uk", "value", "message", "text", "content"]:
            if k in raw and isinstance(raw[k], str): return normalize_text(raw[k])
        return " ".join([str(v) for v in raw.values() if isinstance(v, str)])
    text = str(raw).strip()
    text = re.sub(r'^```[a-zA-Z]*\n', '', text)
    text = re.sub(r'\n```$', '', text)
    if text.startswith("{") or text.startswith("["):
        try: return normalize_text(json.loads(text))
        except: pass
    if len(text) > 1 and text[0] == '"' and text[-1] == '"': text = text[1:-1]
    return text.strip()

class AssistantCore(QObject):
    sig_user_text = pyqtSignal(str)
    sig_bot_text = pyqtSignal(str)
    sig_status = pyqtSignal(str)
    sig_mic_level = pyqtSignal(int)
    sig_timer_update = pyqtSignal(str)
    sig_timer_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.sys = SystemIO()
        self.matcher = FastCommandMatcher()
        self.mem = Memory()
        self.tts = TTSEngine(self.cfg)
        
        # Pass speak callback to executor
        self.executor = CommandExecutor(self.speak_and_log, None)

        self.is_listening = False
        self.stop_event = threading.Event()
        self.chat_history = deque(maxlen=6)
        self.last_interaction_time = 0
        self.active_conversation_timeout = 15
        
        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self._on_timer_tick)
        self.timer_seconds_left = 0
        
        self.vosk_model = None
        if os.path.exists("uk_v3/model"):
            try: self.vosk_model = vosk.Model("uk_v3/model")
            except: pass

    # --- Timer ---
    def start_timer(self, minutes):
        self.timer_seconds_left = minutes * 60
        self.focus_timer.start(1000)
        self.sig_status.emit(f"Таймер: {minutes} хв")
        self.tts.speak(f"Таймер на {minutes} хвилин запущено.")

    def stop_timer(self):
        self.focus_timer.stop()
        self.sig_timer_update.emit("")
        self.tts.speak("Таймер зупинено.")

    def _on_timer_tick(self):
        self.timer_seconds_left -= 1
        mins, secs = divmod(self.timer_seconds_left, 60)
        self.sig_timer_update.emit(f"{mins:02d}:{secs:02d}")
        if self.timer_seconds_left <= 0:
            self.focus_timer.stop()
            self.sig_timer_finished.emit()
            self.tts.speak("Час вийшов!")

    # --- Output ---
    def speak_and_log(self, text):
        self.sig_bot_text.emit(text)
        if not self.cfg.get("muted", False):
            self.tts.speak(text)

    # --- Input ---
    def start_listening(self):
        self.stop_event.clear()
        self.is_listening = True
        self.sig_status.emit("Слухаю...")
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop_listening(self):
        self.is_listening = False
        self.stop_event.set()
        self.sig_status.emit("Очікую")

    def manual_input(self, text):
        threading.Thread(target=self.process_input, args=(text,), daemon=True).start()

    def _listen_loop(self):
        mode = self.cfg.get("stt_backend", "vosk")
        if mode == "online":
            r = sr.Recognizer()
            m = sr.Microphone()
            try:
                with m as src: r.adjust_for_ambient_noise(src)
            except: pass
            while not self.stop_event.is_set():
                try:
                    with m as src:
                        audio = r.listen(src, timeout=1, phrase_time_limit=5)
                    text = r.recognize_google(audio, language="uk-UA")
                    if text: self._check_wake_word_and_process(text)
                except: pass
        else:
            if not self.vosk_model:
                self.sig_status.emit("Vosk Error")
                return
            q = queue.Queue()
            def cb(indata, frames, time, status):
                q.put(bytes(indata))
                import numpy as np
                vol = int(np.linalg.norm(np.frombuffer(indata, dtype=np.int16)) / 300)
                self.sig_mic_level.emit(min(vol, 100))
            try:
                rec = vosk.KaldiRecognizer(self.vosk_model, 16000)
                with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype='int16', channels=1, callback=cb):
                    while not self.stop_event.is_set():
                        try:
                            data = q.get(timeout=1)
                            if rec.AcceptWaveform(data):
                                res = json.loads(rec.Result())
                                t = res.get("text", "")
                                if t: self._check_wake_word_and_process(t)
                        except queue.Empty: pass
            except: pass

    def _check_wake_word_and_process(self, text):
        text = text.strip()
        lower_text = text.lower()
        wake_word_enabled = self.cfg.get("wake_word_enabled", True)
        
        if not wake_word_enabled:
            self.process_input(text)
            return

        time_since_last = time.time() - self.last_interaction_time
        is_conversation_active = time_since_last < self.active_conversation_timeout
        aliases = ["петро", "петруча", "асистент", "привіт"]
        has_alias = any(a in lower_text for a in aliases)

        if is_conversation_active or has_alias:
            if has_alias:
                for a in aliases:
                    if lower_text.startswith(a):
                        text = text[len(a):].strip()
                        break
            if text: self.process_input(text)
        else:
            print(f"[Ignored] {text}")

    def process_input(self, text):
        self.last_interaction_time = time.time()
        text = text.strip()
        if not text: return

        self.sig_user_text.emit(text)
        self.sig_status.emit("Думаю...")
        self.chat_history.append({"role": "user", "content": text})
        
        fast_cmd = self.matcher.match(text)
        response = None
        
        if fast_cmd:
            intent = fast_cmd["intent"]
            p = fast_cmd.get("params", {})
            
            if intent == "START_TIMER":
                self.start_timer(p.get("minutes", 5))
                return
            elif intent == "STOP_TIMER":
                self.stop_timer()
                return
            
            if self.executor.execute(fast_cmd):
                return

        if not response:
            lower_text = text.lower()
            if "знайди" in lower_text or "погугли" in lower_text:
                self.sig_status.emit("Шукаю в інтернеті...")
                response = self._web_search_agent(text)

        if not response:
            memory_context = self.mem.search_facts(text)
            response = self._llm_chat(text, memory_context=memory_context)

        clean = normalize_text(response)
        self.sig_bot_text.emit(clean)
        self.chat_history.append({"role": "assistant", "content": clean})
        
        if not self.cfg.get("muted", False):
            self.sig_status.emit("Говорю...")
            self.tts.speak(clean)
        
        if self.is_listening: self.sig_status.emit("Слухаю...")
        else: self.sig_status.emit("Очікую")

    # --- Modules ---
    def _ask_gemini_vision(self, text):
        key = self.cfg.get("gemini_key")
        if not key: return "Потрібен Gemini API Key."
        b64_img = self.sys.get_screenshot_base64()
        if not b64_img: return "Помилка скріншоту."
        model = self.cfg.get("gemini_model", "gemini-1.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": f"{text}"}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}]}]}
        try:
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code == 200: return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return f"Gemini Error: {r.status_code}"
        except Exception as e: return f"Error: {e}"

    def _web_search_agent(self, query):
        res = self.sys.web_search(query)
        return self._llm_chat(f"Query: {query}\nResults:\n{res}\nSummarize in Ukrainian.", system_override="Search Agent")

    def _llm_chat(self, text, system_override=None, memory_context=""):
        mode = self.cfg.get("llm_backend", "local")
        context = "\n".join([f"{m['role']}: {m['content']}" for m in list(self.chat_history)[-6:]])
        mem_str = f"\nFact: {memory_context}" if memory_context else ""
        sys_prompt = system_override or f"Ти асистент Петруча.{mem_str}"
        
        if mode == "local":
            url = f"{self.cfg.get('local_llm_url')}/v1/chat/completions"
            try:
                payload = {"messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"{context}\nUser: {text}"}]}
                r = requests.post(url, json=payload, timeout=10)
                return r.json()["choices"][0]["message"]["content"]
            except: return "Local LLM Error"
        elif mode == "gemini":
            key = self.cfg.get("gemini_key")
            if not key: return "No Gemini Key."
            model = self.cfg.get("gemini_model", "gemini-1.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": f"{sys_prompt}\n{context}\nUser: {text}"}]}]}
            try:
                r = requests.post(url, json=payload, timeout=10)
                if r.status_code == 200: return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return f"Error {r.status_code}"
            except Exception as e: return f"Net Error: {e}"
        return "Unknown Backend"