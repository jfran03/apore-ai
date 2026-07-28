"""NVIDIA NIM provider (OpenAI-compatible endpoint)."""

from openai import OpenAI

from apore.config.llm import get_nim_api_key
from apore.providers.base import Provider


class NIMProvider(Provider):
    """Calls NVIDIA NIM via the OpenAI-compatible endpoint."""

    _BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(self, api_key: str | None = None) -> None:
        resolved = api_key or get_nim_api_key()
        if not resolved:
            raise ValueError(
                "NVIDIA NIM API key is not configured. Set nim_api_key in "
                ".apore/config.json or NVIDIA_API_KEY in the environment."
            )
        self._client = OpenAI(base_url=self._BASE_URL, api_key=resolved)

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
            temperature=1,
            top_p=0.95,
            max_tokens=16384,
            stream=False,
        )
        content = response.choices[0].message.content
        return content if content is not None else ""
