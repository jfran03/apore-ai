"""Tests for learner intent classification."""

from apore.runtime.intent import is_help_request


def test_declarative_answer_is_not_help():
    assert not is_help_request("a set is a list of unordered elements")


def test_explicit_help_phrases():
    assert is_help_request("I need help understanding sets")
    assert is_help_request("can you explain what disjoint means?")
    assert is_help_request("not sure about this, can you explain disjoint?")


def test_empty_message_is_not_help():
    assert not is_help_request("")
    assert not is_help_request("   ")
