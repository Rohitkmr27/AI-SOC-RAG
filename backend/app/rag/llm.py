"""LLM provider abstraction and Google Gemini implementation."""

from abc import ABC, abstractmethod
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from app.rag.config import DEFAULT_LLM_MODEL

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM generation providers."""

    @abstractmethod
    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        """Generate response text from the LLM."""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider using the Google AI REST API."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", DEFAULT_LLM_MODEL)
        self.timeout = timeout

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        if not self.api_key or not self.api_key.strip():
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Please configure GEMINI_API_KEY to generate answers with Google Gemini."
            )

        contents: list[dict[str, Any]] = [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ]

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
            },
        }

        if system_instruction:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key.strip(),
        }

        fallback_models = [self.model_name]
        for candidate in ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
            if candidate not in fallback_models:
                fallback_models.append(candidate)

        import time

        last_error = None
        response_data = None

        for model in fallback_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                try:
                    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=self.timeout) as response:
                        response_text = response.read().decode("utf-8")
                        response_data = json.loads(response_text)
                        break
                except urllib.error.HTTPError as error:
                    last_error = error
                    if error.code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                        logger.warning("Gemini API (%s) HTTP %d error (attempt %d/%d). Retrying in 1s...", model, error.code, attempt, max_attempts)
                        time.sleep(1.0 * attempt)
                        continue
                    if error.code in (404, 429, 500, 502, 503, 504):
                        logger.warning("Gemini API (%s) HTTP %d (%s). Trying fallback model...", model, error.code, error.reason)
                        time.sleep(0.5)
                        break
                    error_body = error.read().decode("utf-8", errors="replace")
                    logger.error("Gemini API error (HTTP %d): %s", error.code, error.reason)
                    raise RuntimeError(
                        f"Gemini API request failed with HTTP {error.code}: {error.reason}."
                    ) from error
                except (urllib.error.URLError, TimeoutError, OSError) as error:
                    last_error = error
                    if attempt < max_attempts:
                        logger.warning("Gemini network error (%s) (attempt %d/%d). Retrying...", model, attempt, max_attempts)
                        time.sleep(0.5 * attempt)
                        continue
                    break

            if response_data is not None:
                break

        if response_data is None:
            reason = getattr(last_error, "reason", str(last_error))
            code = getattr(last_error, "code", "network_error")
            raise RuntimeError(f"Gemini API request failed with HTTP {code}: {reason}.")

        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                prompt_feedback = response_data.get("promptFeedback", {})
                raise RuntimeError(
                    f"Gemini returned no candidates. Prompt feedback: {prompt_feedback}"
                )
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts)
            if not text.strip():
                raise RuntimeError("Gemini returned an empty candidate text.")
            return text.strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Failed to parse Gemini API response: {response_data}") from exc
