"""Tests for learner intent classification."""

from apore.runtime.intent import is_help_request


def test_declarative_answer_is_not_help():
    assert not is_help_request("a set is a list of unordered elements")


def test_explicit_help_phrases():
    assert is_help_request("I need help understanding sets")
    assert is_help_request("can you explain what disjoint means?")
    assert is_help_request("not sure about this, can you explain disjoint?")
    assert is_help_request("I don't know")
    assert is_help_request("i dont know where to start")
    assert is_help_request("no idea")
    assert is_help_request("I'm lost")
    assert is_help_request("I'm confused")
    assert is_help_request("walk me through this")
    assert is_help_request("where do I start?")
    assert is_help_request("explain this")
    assert is_help_request("hint")
    assert is_help_request("tutor mode")


def test_hedged_answer_is_not_help():
    assert not is_help_request("I think it's 5, not sure")


def test_empty_message_is_not_help():
    assert not is_help_request("")
    assert not is_help_request("   ")
