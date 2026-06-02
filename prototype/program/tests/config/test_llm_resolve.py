from __future__ import annotations

from apore.config.llm import LLMConfig, NoLLMConfigured, load_llm_config, resolve_active, save_llm_config


def test_resolve_prefers_anthropic_when_both_keys_present():
    config = LLMConfig(
        anthropic_api_key="sk-ant-example",
        nim_api_key="nvapi-example",
        model="",
    )
    resolved = resolve_active(config)
    assert resolved.provider_name == "anthropic"
    assert resolved.model == "claude-sonnet-4-5"


def test_resolve_uses_nim_when_anthropic_missing():
    config = LLMConfig(
        anthropic_api_key=None,
        nim_api_key="nvapi-example",
        model="",
    )
    resolved = resolve_active(config)
    assert resolved.provider_name == "nim"
    assert resolved.model == "meta/llama-3.3-70b-instruct"


def test_resolve_uses_model_override():
    config = LLMConfig(
        anthropic_api_key="sk-ant-example",
        nim_api_key=None,
        model="claude-override",
    )
    resolved = resolve_active(config)
    assert resolved.model == "claude-override"


def test_resolve_raises_when_no_keys():
    config = LLMConfig()
    try:
        resolve_active(config)
        assert False, "Expected NoLLMConfigured"
    except NoLLMConfigured:
        pass


def test_load_from_disk_then_env_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-env")

    save_llm_config(
        LLMConfig(anthropic_api_key=None, nim_api_key="nvapi-disk", model=""),
        program_root=tmp_path,
    )
    loaded = load_llm_config(program_root=tmp_path)
    assert loaded.anthropic_api_key == "sk-ant-env"
    assert loaded.nim_api_key == "nvapi-disk"
