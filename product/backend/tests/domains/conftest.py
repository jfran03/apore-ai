"""Shared fixtures for domain-workspace tests.

Re-exports the api conftest's autouse fixtures so all tests in this package
get the _pytest minimal chapter and the stub-provider wiring, plus a tmp
APORE_DATA_DIR for every test.
"""

import pytest

# Autouse fixtures activate by being importable from this conftest.
from tests.api.conftest import ensure_test_chapter, reset_app_state  # noqa: F401


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path
