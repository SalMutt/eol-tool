"""Shared pytest fixtures for eol-tool tests."""

import pytest

from eol_tool.models import HardwareModel


@pytest.fixture
def sample_model():
    """A sample HardwareModel for testing."""
    return HardwareModel(
        model="EX4300-48T",
        manufacturer="Juniper",
        category="switch",
    )


@pytest.fixture
def sample_models():
    """A list of sample HardwareModels for testing."""
    return [
        HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch"),
        HardwareModel(model="E5-2680V4", manufacturer="Intel", category="cpu"),
        HardwareModel(model="MX204", manufacturer="Juniper", category="router"),
    ]
