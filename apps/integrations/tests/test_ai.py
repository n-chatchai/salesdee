"""Unit tests for the Anthropic-backed drafting helpers — the SDK client is faked."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.integrations.ai import AINotConfigured, draft_quotation_from_text, draft_reply_from_text


class _FakeMessages:
    def __init__(self, response: object) -> None:
        self._response = response
        self.kwargs: dict = {}

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return self._response


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.messages = _FakeMessages(response)


def _patch_anthropic(monkeypatch, response: object) -> _FakeClient:
    client = _FakeClient(response)
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda *, api_key: client)
    return client


def test_draft_reply_requires_api_key(settings) -> None:
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(AINotConfigured):
        draft_reply_from_text("สนใจโต๊ะ")


def test_draft_quotation_requires_api_key(settings) -> None:
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(AINotConfigured):
        draft_quotation_from_text("สนใจโต๊ะ", catalog=[])


def test_draft_reply_returns_text(settings, monkeypatch) -> None:
    import anthropic

    settings.ANTHROPIC_API_KEY = "test-key"
    response = SimpleNamespace(
        content=[anthropic.types.TextBlock(type="text", text="สวัสดีครับ ยินดีเสนอราคาให้")]
    )
    client = _patch_anthropic(monkeypatch, response)
    out = draft_reply_from_text("ลูกค้า: สนใจโต๊ะทำงาน", company_name="วัน.ดี.ดี.")
    assert out == "สวัสดีครับ ยินดีเสนอราคาให้"
    # the company name made it into the system prompt
    assert "วัน.ดี.ดี." in client.messages.kwargs["system"]


def test_draft_quotation_extracts_tool_input(settings, monkeypatch) -> None:
    settings.ANTHROPIC_API_KEY = "test-key"
    tool_input = {"customer_name": "คุณเอ", "lines": [{"description": "โต๊ะทำงาน", "quantity": 2}]}
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="(thinking)"),
            SimpleNamespace(type="tool_use", name="draft_quotation", input=tool_input),
        ]
    )
    client = _patch_anthropic(monkeypatch, response)
    out = draft_quotation_from_text(
        "ลูกค้า: ขอโต๊ะทำงาน 2 ตัว",
        catalog=[{"code": "TBL-01", "name": "โต๊ะทำงาน", "unit": "ตัว", "price": 3500}],
    )
    assert out == tool_input
    assert "TBL-01" in client.messages.kwargs["messages"][0]["content"]


def test_draft_quotation_no_tool_block_falls_back(settings, monkeypatch) -> None:
    settings.ANTHROPIC_API_KEY = "test-key"
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="ไม่มีรายการ")])
    _patch_anthropic(monkeypatch, response)
    assert draft_quotation_from_text("สวัสดี", catalog=[]) == {"lines": []}
