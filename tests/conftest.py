"""Shared fixtures for the share_chat test suite."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def plugin_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "usr" / "plugins" / "share_chat"
