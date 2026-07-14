import os
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.services.conversation_store import Message


class LLMConfigurationError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    pass


class LLMClient:
    """Small Gemini provider boundary used by the rest of the application."""

    def __init__(self) -> None:
        load_dotenv()
        # LLM_API_KEY remains as a migration fallback for existing local setups.
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        response_model: type[BaseModel] | None = None,
    ) -> str:
        if not self.api_key:
            raise LLMConfigurationError(
                "GEMINI_API_KEY must be set in the environment."
            )

        system_instruction = "\n\n".join(
            message.content for message in messages if message.role == "system"
        )
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part.from_text(text=message.content)],
            )
            for message in messages
            if message.role != "system"
        ]

        config_values: dict[str, Any] = {
            "system_instruction": system_instruction or None,
            "temperature": 0.2,
        }
        if response_model is not None:
            config_values.update(
                response_mime_type="application/json",
                response_schema=response_model,
            )

        client = genai.Client(api_key=self.api_key)
        try:
            async with client.aio as async_client:
                response = await async_client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(**config_values),
                )
        except Exception as exc:
            raise LLMProviderError(
                "The Gemini service is temporarily unavailable."
            ) from exc
        finally:
            client.close()

        if not response.text:
            raise LLMProviderError("Gemini returned an empty or blocked response.")
        return response.text.strip()
