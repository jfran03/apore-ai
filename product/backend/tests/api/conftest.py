import shutil

import pytest
import apore.api.app as app_module
from apore.config.llm import LLMConfig
from apore.providers.stub import StubProvider

TEST_KNOWLEDGE_SOURCE = "domain:_pytest/01-intro"


@pytest.fixture(autouse=True)
def ensure_test_chapter():
    src = (
        app_module.PROGRAM_ROOT
        / "tests"
        / "fixtures"
        / "minimal_chapter"
    )
    dest = app_module.PROGRAM_ROOT / "domains" / "_pytest" / "chapters" / "01-intro"
    if not dest.exists():
        shutil.copytree(src, dest)
    bank_src = src / "question-bank.json"
    bank_dest = dest / "question-bank.json"
    if bank_src.is_file() and not bank_dest.is_file():
        shutil.copy2(bank_src, bank_dest)
    yield


@pytest.fixture(autouse=True)
def reset_app_state(monkeypatch: pytest.MonkeyPatch):
    app_module.sessions.clear()
    config_holder: dict[str, LLMConfig] = {
        "config": LLMConfig(anthropic_api_key="test-anthropic-key", model="")
    }

    def _fake_load_llm_config(program_root=None):
        return config_holder["config"]

    def _fake_save_llm_config(config, program_root=None):
        config_holder["config"] = config

    monkeypatch.setattr("apore.config.llm.load_llm_config", _fake_load_llm_config)
    monkeypatch.setattr("apore.config.llm.save_llm_config", _fake_save_llm_config)
    monkeypatch.setattr(app_module, "get_active_provider", lambda: "stub")
    monkeypatch.setattr(app_module, "get_active_model", lambda: "stub-model")
    monkeypatch.setattr(app_module, "get_provider", lambda provider_name: StubProvider())

    yield
    app_module.sessions.clear()
