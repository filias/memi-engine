"""Shared fixtures: every test starts from an empty provider registry."""

import pytest

from memi_engine import registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the global registry before and after each test."""
    registry.clear()
    yield
    registry.clear()
