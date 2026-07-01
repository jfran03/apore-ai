"""Abstract provider interface."""

from abc import ABC, abstractmethod


class Provider(ABC):
    @abstractmethod
    def invoke(
        self,
        system_prompt: str,
        messages: list[dict],  # [{"role": "user"|"assistant", "content": str}]
        model: str,
        config: dict,
    ) -> str:
        ...
