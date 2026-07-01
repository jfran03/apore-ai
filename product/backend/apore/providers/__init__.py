from apore.providers.anthropic_adapter import AnthropicProvider
from apore.providers.base import Provider
from apore.providers.nim_adapter import NIMProvider
from apore.providers.stub import StubProvider
from apore.providers.throttle import Throttle


def get_provider(provider_name: str, *, api_key: str | None = None) -> Provider:
    if provider_name == "anthropic":
        return AnthropicProvider(api_key=api_key)
    elif provider_name == "nim":
        return NIMProvider(api_key=api_key)
    elif provider_name == "stub":
        return StubProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name!r}")


__all__ = ["Provider", "Throttle", "AnthropicProvider", "NIMProvider", "get_provider"]
