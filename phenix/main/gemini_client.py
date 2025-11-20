import os
import json
import requests
from typing import List, Dict, Optional


class GeminiClient:
    """
    Клієнт до Gemini API у режимі JSON-відповідей.
    - chat(...) повертає сирий текст (очікуємо JSON-рядок).
    - request_json(...) надає той самий інтерфейс, що й LLMClient.request_json().
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3.0-flash",
    ) -> None:
        self.api_key = api_key or os.environ.get("AIzaSyD8DK7-1AfKrgZEDlLTatZt15DRID87h2o")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY не заданий ні в коді, ні в оточенні.")
        self.model = model
        self.base_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )

    def chat(self, system_prompt: str, user_text: str) -> str:
        """
        Повертає сирий текст від моделі (очікуємо JSON-рядок).
        NLUInterpreter потім робить json.loads + валідацію.
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        body = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_text}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
            },
        }

        resp = requests.post(
            self.base_url,
            headers=headers,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            raise RuntimeError(f"Gemini: неочікуваний формат відповіді: {data}") from e

        return text

    def request_json(self, system_prompt: str, user_message: str, extra_messages=None) -> Optional[dict]:
        """
        Сумісний з інтерфейсом LLMClient.request_json:
        - викликає chat(...),
        - парсить JSON з тексту.
        """
        raw = self.chat(system_prompt, user_message)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemini повернув невалідний JSON: {raw}") from exc