from __future__ import annotations
import json
import logging
import re
from typing import Iterable, Optional
import requests

LOGGER = logging.getLogger(__name__)


class LLMClient:
    """Minimal client for the OpenAI-compatible LM Studio API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url must be provided")
        if not model:
            raise ValueError("model must be provided")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = session or requests.Session()

    def _build_messages(
        self,
        system_prompt: str,
        user_message: str,
        extra_messages: Optional[Iterable[dict]] = None,
    ) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if extra_messages:
            for message in extra_messages:
                if not isinstance(message, dict):
                    raise TypeError("extra_messages must contain dictionaries")
                messages.append(message)
        messages.append({"role": "user", "content": user_message})
        return messages

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        extra_messages: Optional[Iterable[dict]] = None,
    ) -> Optional[str]:
        """Send a chat completion request and return the raw string content."""
        messages = self._build_messages(system_prompt, user_prompt, extra_messages)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }

        url = f"{self.base_url}/v1/chat/completions"

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            LOGGER.error("LLM request failed: %s", exc)
            LOGGER.error("Response text: %s", getattr(exc.response, "text", ""))
            return None
        except requests.RequestException as exc:
            LOGGER.error("LLM request failed: %s", exc)
            return None

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            LOGGER.error("Invalid JSON in LLM response body: %s", exc)
            return None

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            LOGGER.error("Unexpected LLM format: %s", exc)
            return None

    @staticmethod
    def extract_json_block(raw_text: str) -> Optional[str]:
        """Витягнути JSON-блок з відповіді LLM (```json ... ``` або просто {...})."""
        if raw_text is None:
            return None

        raw = raw_text.strip()

        fenced_match = re.search(
            r"```json\s*(\{.*?\})\s*```",
            raw,
            re.DOTALL | re.IGNORECASE,
        )
        if fenced_match:
            return fenced_match.group(1).strip()

        fenced_match = re.search(
            r"```\s*(\{.*?\})\s*```",
            raw,
            re.DOTALL,
        )
        if fenced_match:
            return fenced_match.group(1).strip()

        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            return m.group(0).strip()

        LOGGER.error("LLM output has no JSON block: %r", raw)
        return None

    def request_json(
        self,
        system_prompt: str,
        user_message: str,
        extra_messages: Optional[Iterable[dict]] = None,
    ) -> Optional[dict]:
        """Return the parsed JSON object from the LLM output."""
        content = self.complete(system_prompt, user_message, extra_messages)
        if content is None:
            return None

        json_text = self.extract_json_block(content)
        if not json_text:
            LOGGER.error("No JSON content extracted from LLM output")
            return None

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as exc:
            LOGGER.error("Failed to parse JSON from LLM output: %s", exc)
            LOGGER.debug("Raw LLM output: %s", content)
            return None
