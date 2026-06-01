"""Anthropic Messages API provider."""

import anthropic

from apore.providers.base import Provider

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicProvider(Provider):
    """Calls Anthropic Messages API. Reads ANTHROPIC_API_KEY from env."""

    def invoke(
        self,
        system_prompt: str,
        messages: list[dict],
        model: str,
        config: dict,
    ) -> str:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=config.get("max_tokens", 1024),
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
