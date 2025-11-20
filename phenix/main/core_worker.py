import threading
import logging
import datetime
import json
import re
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal

from config_manager import ConfigManager
from stt_providers import VoskSTT, OnlineSTT
from llm_providers import LocalLLMBackend, GeminiBackend
from audio_utils import TTSFactory
from nlu_interpreter import NLUInterpreter
from command_executor import CommandExecutor
from fast_commands import FastCommandMatcher
from system_controller import SystemController

LOGGER = logging.getLogger(__name__)

class LegacyExecutorAdapter:
    def __init__(self, worker):
        self.worker = worker
    def __call__(self, cmd: str, arg: str):
        LOGGER.info(f"Legacy command: {cmd}")

def normalize_text_response(raw) -> str:
    """
    Cleans up raw response (string, dict, JSON string) into a clean human text.
    Removes quotes, extracts 'value'/'message' fields, handles lists.
    """
    if raw is None:
        return ""

    # 1. If it's a dict, extract best text field
    if isinstance(raw, dict):
        for key in ["answer_uk", "value", "message", "text", "content", "response"]:
            if key in raw and isinstance(raw[key], str):
                return normalize_text_response(raw[key])
        # Fallback: join all string values
        return " ".join([str(v) for v in raw.values() if isinstance(v, (str, int, float))])

    # 2. If it's a list, join elements
    if isinstance(raw, list):
        return "\n\n".join([normalize_text_response(item) for item in raw])

    # 3. If it's a string, try to parse as JSON first
    text = str(raw).strip()
    
    # Check if it looks like JSON
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            parsed = json.loads(text)
            return normalize_text_response(parsed)
        except json.JSONDecodeError:
            pass # Not valid JSON, treat as string

    # 4. Cleanup string artifacts
    # Remove outer quotes if present (e.g. '"Hello"')
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    
    # Remove markdown code blocks if they wrap the whole text
    # e.g. ```json ... ```
    text = re.sub(r'^```[a-zA-Z]*\n', '', text)
    text = re.sub(r'\n```$', '', text)

    return text.strip()

class AssistantWorker(QThread):
    """
    Main background thread.
    Orchestrates: STT -> FastMatcher -> NLU -> LLM -> TTS.
    Manages: Chat Context, Notes Session, Offline Mode.
    """
    sig_user_text = pyqtSignal(str)
    sig_assistant_text = pyqtSignal(str)
    sig_status = pyqtSignal(str)
    sig_mic_level = pyqtSignal(int)
    sig_action_log = pyqtSignal(str, str, str)
    sig_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.stop_event = threading.Event()
        self.is_listening = False
        
        # Components
        self._init_tts()
        self._init_stt()
        self._init_llm()

        self.nlu = NLUInterpreter(self.llm_provider)
        self.fast_matcher = FastCommandMatcher()
        self.sys_ctrl = SystemController()
        
        self.executor = CommandExecutor(
            speak=self.speak_and_log,
            legacy_execute=LegacyExecutorAdapter(self)
        )

        # State
        self.chat_history = deque(maxlen=10)
        self.notes_active = False
        self.current_note_file = None
        self.offline_mode = False

    def _init_tts(self):
        engine_type = self.cfg.get("tts_engine", "gtts")
        self.tts = TTSFactory.create_engine(engine_type)

    def _init_stt(self):
        mode = self.cfg.get("stt_backend", "vosk")
        try:
            if mode == "online": self.stt_provider = OnlineSTT()
            else: self.stt_provider = VoskSTT()
        except Exception as e:
            self.sig_error.emit(f"STT Init Error: {e}")
            self.stt_provider = None

    def _init_llm(self):
        mode = self.cfg.get("llm_backend_default", "local")
        self.offline_mode = (mode == "local")
        
        try:
            if mode == "gemini": 
                self.llm_provider = GeminiBackend()
                self.offline_mode = False
            else: 
                self.llm_provider = LocalLLMBackend()
        except Exception as e:
            self.sig_error.emit(f"LLM Init Error: {e}")
            self.llm_provider = None

    def update_backends(self):
        self.stop_listening()
        self._init_tts()
        self._init_stt()
        self._init_llm()
        if self.llm_provider:
            self.nlu = NLUInterpreter(self.llm_provider)
        self.sig_status.emit("IDLE (Settings Updated)")

    def run(self):
        if not self.stt_provider:
            self.sig_error.emit("STT Provider missing.")
            return

        self.is_listening = True
        self.stop_event.clear()
        self.sig_status.emit("LISTENING")
        
        try:
            self.stt_provider.listen_loop(
                callback=self.process_text, 
                stop_event=self.stop_event,
                level_callback=self.update_mic_level
            )
        except Exception as e:
            self.sig_error.emit(str(e))
        
        self.is_listening = False
        self.sig_status.emit("IDLE")
        self.sig_mic_level.emit(0)

    def stop_listening(self):
        self.stop_event.set()
        self.wait()

    def update_mic_level(self, level: int):
        self.sig_mic_level.emit(level)

    def speak_and_log(self, raw_text: str):
        # Normalize text before showing/speaking
        clean_text = normalize_text_response(raw_text)
        if not clean_text: return

        self.sig_assistant_text.emit(clean_text)
        self.sig_status.emit("SPEAKING")
        
        self.chat_history.append({"role": "assistant", "text": clean_text})
        
        if not self.cfg.get("muted", False):
            self.tts.speak(clean_text)

    def process_text(self, text: str):
        text = text.strip()
        if not text: return

        self.sig_user_text.emit(text)
        self.sig_status.emit("PROCESSING")
        
        self.chat_history.append({"role": "user", "text": text})

        # --- 1. Fast Command Matcher (No LLM) ---
        fast_cmd = self.fast_matcher.match(text)
        if fast_cmd:
            intent = fast_cmd["intent"]
            self._log_action(intent, str(fast_cmd.get("params")))
            
            if intent == "START_NOTES_SESSION":
                self.notes_active = True
                self.current_note_file = self.sys_ctrl.create_note_file()
                self.executor.execute(fast_cmd)
                return
            
            elif intent == "STOP_NOTES_SESSION":
                self.notes_active = False
                self.executor.execute(fast_cmd)
                self.current_note_file = None
                return

            elif intent == "ANALYZE_NOTES":
                self.executor.execute(fast_cmd)
                self._analyze_notes()
                return

            if self.executor.execute(fast_cmd):
                return

        # --- 2. Notes Recording Mode ---
        if self.notes_active and self.current_note_file:
            self.sys_ctrl.append_to_note(self.current_note_file, text)
            self.sig_status.emit("RECORDING NOTE")
            self.sig_action_log.emit(self._get_time(), "NOTE_APPEND", "Text saved")
            return

        # --- 3. LLM-based NLU & Chat ---
        if not self.llm_provider:
            self.speak_and_log("LLM не налаштована.")
            return

        try:
            # Try NLU
            commands = self.nlu.interpret(text)
            handled = False
            
            if commands:
                for cmd in commands:
                    intent = cmd.get("intent", "UNKNOWN")
                    if intent != "UNKNOWN":
                        self._log_action(intent, str(cmd.get("params")))
                        if self.executor.execute(cmd):
                            handled = True
            
            # Fallback to Chat with Context
            if not handled:
                self._log_action("CHAT", "LLM Request")
                self._handle_chat(text)

        except Exception as e:
            LOGGER.error(f"Processing error: {e}")
            self.sig_error.emit(f"Error: {e}")
        
        if self.is_listening:
            self.sig_status.emit("LISTENING")

    def _handle_chat(self, text: str):
        if self.offline_mode and isinstance(self.llm_provider, GeminiBackend):
             self.speak_and_log("Я зараз в офлайн режимі і не можу звернутися до Gemini.")
             return

        history_str = ""
        for msg in list(self.chat_history)[-6:]:
            role = "Користувач" if msg['role'] == 'user' else "Асистент"
            history_str += f"{role}: {msg['text']}\n"
        
        system_prompt = (
            "Ти україномовний голосовий асистент Петруча. "
            "Ти НЕ є мовною моделлю Google. Ти локальний помічник. "
            "Відповідай коротко, живою мовою, без JSON. "
            "Використовуй контекст розмови нижче.\n\n"
            f"Історія діалогу:\n{history_str}\n"
            "Асистент:"
        )
        
        response = self.llm_provider.chat(
            system_prompt=system_prompt,
            user_message=text
        )
        self.speak_and_log(response)

    def _analyze_notes(self):
        path = self.sys_ctrl.get_latest_note()
        if not path:
            self.speak_and_log("Не знайшов файлів нотаток.")
            return

        content = self.sys_ctrl.read_note(path)
        if not content:
            self.speak_and_log("Файл нотаток порожній.")
            return

        if self.offline_mode:
             self.speak_and_log("Для аналізу нотаток потрібен онлайн режим (Gemini).")
             return

        prompt = (
            "Проаналізуй ці нотатки. "
            "Виділи головні думки, структуруй їх у список або пункти. "
            "Виправи помилки, якщо є.\n\n"
            f"Текст нотаток:\n{content}"
        )
        
        response = self.llm_provider.chat(
            system_prompt="Ти аналітик тексту. Структуруй нотатки українською.",
            user_message=prompt
        )
        
        self.speak_and_log("Ось результат аналізу:")
        self.speak_and_log(response)
        self.sys_ctrl.append_to_note(path, "\n\n--- ANALYSIS ---\n" + response)

    def _log_action(self, intent, details):
        self.sig_action_log.emit(self._get_time(), intent, details)

    def _get_time(self):
        return datetime.datetime.now().strftime("%H:%M:%S")

    def manual_input(self, text: str):
        threading.Thread(target=self.process_text, args=(text,)).start()