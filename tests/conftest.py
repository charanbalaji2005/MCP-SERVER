"""Shared pytest fixtures.

`workspace` points every test at its own temporary directory by
mutating the single shared `Settings` instance in-place (it's a frozen
dataclass, so we bypass immutability via object.__setattr__ -- every
module imported `SETTINGS` as a direct reference to this one object,
so mutating it here is visible everywhere).
"""

from __future__ import annotations

import pytest

from ubuntu_mcp.config import SETTINGS


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_WORKSPACE", str(tmp_path))
    object.__setattr__(SETTINGS, "workspace_root", tmp_path)
    yield tmp_path
