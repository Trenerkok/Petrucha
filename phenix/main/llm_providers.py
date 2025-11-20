from abc import ABC, abstractmethod
import logging
from config_manager import ConfigManager
from gemini_client import GeminiClient
from llm_client import LLMClient

LOGGER = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, user_message: str) -> str:
        pass

    @abstractmethod
    def request_json(self, system_prompt: str, user_message: str) -> dict:
        pass


class LocalLLMBackend(LLMProvider):
    def __init__(self):
        cfg = ConfigManager()
        base_url = cfg.get("llm_base_url", "http://127.0.0.1:1234")
        model = cfg.get("llm_model", "phi-3.5-mini-instruct")

        LOGGER.info(f"Initializing Local LLM: {base_url} ({model})")
        self.client = LLMClient(base_url=base_url, model=model)

    def chat(self, system_prompt: str, user_message: str) -> str:
        return self.client.complete(system_prompt, user_message) or ""

    def request_json(self, system_prompt: str, user_message: str) -> dict:
        return self.client.request_json(system_prompt, user_message)


class GeminiBackend(LLMProvider):
    def __init__(self):
        cfg = ConfigManager()
        api_key = cfg.get("gemini_api_key")
        model = cfg.get("gemini_model", "gemini-1.5-flash")

        if not api_key:
            LOGGER.warning("Gemini API Key is missing in config!")

        LOGGER.info(f"Initializing Gemini: {model}")
        self.client = GeminiClient(api_key=api_key, model=model)

    def chat(self, system_prompt: str, user_message: str) -> str:
        try:
            return self.client.chat(system_prompt, user_message)
        except Exception as e:
            LOGGER.error(f"Gemini Chat Error: {e}")
            return f"Помилка Gemini: {e}"

    def request_json(self, system_prompt: str, user_message: str) -> dict:
        try:
            return self.client.request_json(system_prompt, user_message)
        except Exception as e:
            LOGGER.error(f"Gemini JSON Error: {e}")
            return {}
