import pytest

from agent.tools import build_default_registry


@pytest.fixture
def registry():
    return build_default_registry()
