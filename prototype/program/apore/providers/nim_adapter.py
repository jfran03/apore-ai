"""NVIDIA NIM provider (OpenAI-compatible endpoint)."""

import os

from openai import OpenAI

from apore.providers.base import Provider

DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"


class NIMProvider(Provider):
    """Calls NVIDIA NIM via the OpenAI-compatible endpoint. Reads NVIDIA_API_KEY from env."""

    _BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(self) -> None:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY environment variable is not set")
        self._client = OpenAI(base_url=self._BASE_URL, api_key=api_key)

    def invoke(
        self,
        system_prompt: str,
        messages: list[dict],
        model: str,
        config: dict,
    ) -> str:
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        response = self._client.chat.completions.create(
            model=model,
            messages=all_messages,
            max_tokens=config.get("max_tokens", 1024),
        )
        return response.choices[0].message.content
