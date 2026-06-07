"""Anthropic Messages API provider."""

import anthropic

from apore.config.llm import get_anthropic_api_key
from apore.providers.base import Provider

DEFAULT_MODEL = "claude-sonnet-4-5"


class AnthropicProvider(Provider):
    """Calls Anthropic Messages API."""

    def __init__(self, api_key: str | None = None) -> None:
        resolved = api_key or get_anthropic_api_key()
        if not resolved:
            raise ValueError(
                "Anthropic API key is not configured. Set anthropic_api_key in "
                ".apore/config.json or ANTHROPIC_API_KEY in the environment."
            )
        self._client = anthropic.Anthropic(api_key=resolved)

    def invoke(
        self,
        system_prompt: str,
        messages: list[dict],
        model: str,
        config: dict,
    ) -> str:
        response = self._client.messages.create(
            model=model,
            max_tokens=config.get("max_tokens", 1024),
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
