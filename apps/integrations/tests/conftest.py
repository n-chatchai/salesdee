"""Fixtures shared by the integrations tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_line_profile_calls(monkeypatch):
    """Don't hit the real LINE Messaging API during tests. The display-name enrichment task runs
    synchronously (ImmediateBackend) whenever a conversation is created; stub the network call so
    it's a no-op unless a test explicitly opts in by re-patching it."""
    monkeypatch.setattr("apps.integrations.line.fetch_line_profile_name", lambda _uid: "")
