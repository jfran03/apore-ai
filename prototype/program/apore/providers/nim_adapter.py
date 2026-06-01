"""NVIDIA NIM provider (OpenAI-compatible endpoint)."""

import os

from openai import OpenAI

from apore.providers.base import Provider

DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"
_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NIMProvider(Provider):
    """Calls NVIDIA NIM via the OpenAI-compatible endpoint. Reads NVIDIA_API_KEY from env."""

    _BASE_URL = _BASE_URL

    def invoke(
        self,
        system_prompt: str,
        messages: list[dict],
        model: str,
        config: dict,
    ) -> str:
        client = OpenAI(
            base_url=self._BASE_URL,
            api_key=os.environ["NVIDIA_API_KEY"],
        )
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        response = client.chat.completions.create(
            model=model,
            messages=all_messages,
            max_tokens=config.get("max_tokens", 1024),
        )
        return response.choices[0].message.content
