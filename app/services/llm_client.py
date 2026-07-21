import os
from collections.abc import Sequence

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.services.conversation_store import Message


class LLMConfigurationError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    pass


class LLMClient:
    """Small OpenAI provider boundary used by the rest of the application."""

    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        response_model: type[BaseModel] | None = None,
    ) -> str:
        if not self.api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY must be set in the environment."
            )

        instructions = "\n\n".join(
            message.content for message in messages if message.role == "system"
        )
        input_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role != "system"
        ]

        try:
            async with AsyncOpenAI(
                api_key=self.api_key,
                timeout=60.0,
                max_retries=2,
            ) as client:
                if response_model is not None:
                    response = await client.responses.parse(
                        model=self.model,
                        instructions=instructions,
                        input=input_messages,
                        store=False,
                        text_format=response_model,
                    )
                    if response.output_parsed is None:
                        raise LLMProviderError(
                            "OpenAI returned an empty, refused, or invalid "
                            "structured response."
                        )
                    return response.output_parsed.model_dump_json()

                response = await client.responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=input_messages,
                    store=False,
                )
                if not response.output_text:
                    raise LLMProviderError(
                        "OpenAI returned an empty or refused response."
                    )
                return response.output_text.strip()
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                "The OpenAI service is temporarily unavailable."
            ) from exc
