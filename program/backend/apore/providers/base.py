"""Abstract provider interface."""

from abc import ABC, abstractmethod


class Provider(ABC):
    @abstractmethod
    def invoke(
        self,
        system_prompt: str,
        messages: list[dict],  # content: str | list[multimodal parts]
        model: str,
        config: dict,
    ) -> str:
        ...
