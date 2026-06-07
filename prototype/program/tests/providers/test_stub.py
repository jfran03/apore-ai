"""Tests for the provider interface and stub."""

import json

import pytest

from apore.providers.base import Provider
from apore.providers.stub import StubProvider
from apore.providers.throttle import Throttle

_REQUIRED_SIGNAL_FIELDS = {"explicit_rating", "correct", "hint_count", "turn_count", "hedging_count"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke_stub(system_prompt="", content="", model="stub", config=None):
    stub = StubProvider()
    messages = [{"role": "user", "content": content}]
    return stub.invoke(system_prompt, messages, model, config or {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_stub_returns_string():
    result = _invoke_stub()
    assert isinstance(result, str)


def test_stub_generate_mode():
    """No 'extract-signals' keyword → returns question block, not JSON."""
    result = _invoke_stub(system_prompt="generate-question protocol", content="Please give a question.")
    # Should not be parseable as JSON
    with pytest.raises((json.JSONDecodeError, ValueError)):
        json.loads(result)
    assert "concept:" in result


def test_stub_extract_mode():
    """'extract-signals' in content → returns JSON string."""
    result = _invoke_stub(content="extract-signals from this conversation")
    # Should be valid JSON
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


def test_stub_extract_json_parseable():
    """json.loads succeeds when extract-signals keyword is present."""
    result = _invoke_stub(system_prompt="extract-signals")
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


def test_stub_extract_required_fields():
    """All 5 signal fields must be present."""
    result = _invoke_stub(content="extract-signals please")
    parsed = json.loads(result)
    assert _REQUIRED_SIGNAL_FIELDS.issubset(parsed.keys())


def test_contract_same_interface():
    """Both StubProvider and a second minimal implementation satisfy Provider."""

    class DummyProvider(Provider):
        def invoke(self, system_prompt, messages, model, config) -> str:
            return "dummy"

    stub = StubProvider()
    dummy = DummyProvider()

    assert isinstance(stub, Provider)
    assert isinstance(dummy, Provider)

    # Both return str
    assert isinstance(stub.invoke("", [], "m", {}), str)
    assert isinstance(dummy.invoke("", [], "m", {}), str)


def test_throttle_instantiates():
    """Throttle instantiates without error — no timing assertions."""
    t = Throttle(rpm=60)
    assert t is not None
