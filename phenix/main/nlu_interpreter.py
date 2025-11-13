"""LLM-powered interpreter that transforms ASR text into structured commands."""
from __future__ import annotations

import logging
from typing import List

from llm_client import LLMClient
from nlu_prompt import NLU_SYSTEM_PROMPT

LOGGER = logging.getLogger(__name__)


class NLUInterpreter:
    """Convert noisy ASR text to structured command dictionaries."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def interpret(self, asr_text: str) -> List[dict]:
        if not asr_text:
            return []

        user_message = (
            "Це текст, який розпізнала система ASR (може містити помилки, суржик, іншомовні слова):\n"
            f"{asr_text}\n"
            "Виділи з нього структуровані команди й поверни JSON згідно з описаною схемою."
        )

        response = self._llm_client.request_json(
            system_prompt=NLU_SYSTEM_PROMPT,
            user_message=user_message,
        )
        if response is None:
            LOGGER.error("NLU LLM повернув порожній результат")
            return []

        commands = response.get("commands")
        if not isinstance(commands, list):
            LOGGER.error("NLU response does not contain a list of commands: %s", response)
            return []

        valid_commands: List[dict] = []
        for item in commands:
            if isinstance(item, dict) and item.get("intent"):
                valid_commands.append(item)
            else:
                LOGGER.warning("Skipping invalid command item: %s", item)
        print(
            f"[NLUInterpreter] Parsed {len(valid_commands)} commands, first intent: "
            f"{valid_commands[0].get('intent') if valid_commands else 'none'}"
        )
        return valid_commands
