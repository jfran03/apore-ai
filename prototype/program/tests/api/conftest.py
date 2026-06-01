import pytest
import apore.api.app as app_module


@pytest.fixture(autouse=True)
def reset_app_state():
    app_module.sessions.clear()
    app_module._provider_config = app_module.ProviderConfig(provider="stub", model="stub")
    yield
    app_module.sessions.clear()
