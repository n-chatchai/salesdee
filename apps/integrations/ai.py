"""AI-assisted drafting via the Anthropic API (Claude).

Optional — every entry point degrades gracefully when ``settings.ANTHROPIC_API_KEY`` is blank
(``ai_is_configured()`` is False; views hide the AI buttons; ``draft_quotation_from_text`` raises
``AINotConfigured``). The ``anthropic`` package is imported lazily so the app runs without it.
"""

from __future__ import annotations

from django.conf import settings


class AINotConfigured(Exception):
    """``ANTHROPIC_API_KEY`` isn't set, so AI features are unavailable."""


def ai_is_configured() -> bool:
    return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))


_DRAFT_QUOTATION_TOOL = {
    "name": "draft_quotation",
    "description": "ส่งร่างใบเสนอราคาเฟอร์นิเจอร์ที่สกัดจากบทสนทนากับลูกค้า",
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "ชื่อลูกค้า/บริษัทที่ปรากฏในบทสนทนา (เว้นว่างถ้าไม่มี)",
            },
            "notes": {
                "type": "string",
                "description": "สรุปความต้องการ/เงื่อนไข/กำหนดส่ง/หมายเหตุที่ลูกค้าระบุ (ภาษาไทย; เว้นว่างได้)",
            },
            "lines": {
                "type": "array",
                "description": "รายการสินค้าที่ลูกค้าสนใจ",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_code": {
                            "type": "string",
                            "description": "รหัสสินค้าจากแคตตาล็อกที่ตรงที่สุด (เว้นว่างถ้าไม่ตรงกับรายการใด)",
                        },
                        "description": {"type": "string", "description": "ชื่อ/รายละเอียดของรายการ"},
                        "quantity": {"type": "number", "description": "จำนวน (อย่างน้อย 1)"},
                        "unit_price": {
                            "type": "number",
                            "description": "ราคาต่อหน่วยที่จะเสนอ; ใส่ 0 ถ้าไม่ทราบ — ระบบจะเติมจากแคตตาล็อกให้",
                        },
                    },
                    "required": ["description", "quantity"],
                },
            },
        },
        "required": ["lines"],
    },
}

_SYSTEM = (
    "คุณเป็นผู้ช่วยฝ่ายขายของธุรกิจเฟอร์นิเจอร์ในไทย หน้าที่ของคุณคืออ่านบทสนทนากับลูกค้า (จาก LINE/อีเมล/โทร) "
    "แล้วร่างใบเสนอราคา โดยจับคู่สินค้าที่ลูกค้าสนใจกับแคตตาล็อกที่ให้มา (ระบุรหัสสินค้าเมื่อจับคู่ได้) "
    "ห้ามแต่งราคาขึ้นเองถ้าสินค้านั้นมีราคาในแคตตาล็อก ใช้ภาษาไทยในคำตอบ และเรียกใช้ tool draft_quotation เสมอ"
)


def draft_quotation_from_text(conversation: str, *, catalog: list[dict]) -> dict:
    """Ask Claude to extract a draft quotation from a customer conversation, matching ``catalog``
    (a list of ``{code, name, unit, price}`` dicts). Returns the tool input dict
    (``{customer_name?, notes?, lines: [...]}``). Raises ``AINotConfigured`` or the SDK's errors."""
    key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not key:
        raise AINotConfigured("ยังไม่ได้ตั้งค่า ANTHROPIC_API_KEY — ใช้ฟีเจอร์ AI ไม่ได้")
    import anthropic

    catalog_text = "\n".join(
        f"- {c.get('code') or '(ไม่มีรหัส)'} | {c.get('name', '')} | {c.get('unit', '')} | {c.get('price', '')} บาท"
        for c in catalog[:300]
    )
    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(  # type: ignore[call-overload]  # SDK's typed overloads reject plain dict literals; valid at runtime
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=2048,
        system=_SYSTEM,
        tools=[_DRAFT_QUOTATION_TOOL],
        tool_choice={"type": "tool", "name": "draft_quotation"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"แคตตาล็อกสินค้า:\n{catalog_text or '(ไม่มีข้อมูลแคตตาล็อก)'}\n\n"
                    f"---\nบทสนทนากับลูกค้า:\n{conversation}\n\n"
                    "ร่างใบเสนอราคาจากบทสนทนานี้"
                ),
            }
        ],
    )
    for block in response.content:
        if (
            getattr(block, "type", None) == "tool_use"
            and getattr(block, "name", None) == "draft_quotation"
        ):
            return dict(block.input)
    return {"lines": []}


def draft_reply_from_text(conversation: str, *, company_name: str = "") -> str:
    """Ask Claude to draft the next reply to the customer from the conversation. Returns plain Thai
    text (the salesperson edits before sending). Raises ``AINotConfigured`` or the SDK's errors."""
    key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not key:
        raise AINotConfigured("ยังไม่ได้ตั้งค่า ANTHROPIC_API_KEY — ใช้ฟีเจอร์ AI ไม่ได้")
    import anthropic

    on_behalf = f"ในนามของ {company_name} " if company_name else ""
    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=1024,
        system=(
            f"คุณเป็นพนักงานขายเฟอร์นิเจอร์ในไทย {on_behalf}ช่วยร่างข้อความตอบกลับลูกค้าจากบทสนทนาที่ให้มา "
            "น้ำเสียงสุภาพ เป็นกันเอง กระชับ ตอบคำถามที่ลูกค้าค้างไว้ และเสนอขั้นถัดไปเมื่อเหมาะสม "
            "(เช่น ส่งใบเสนอราคา นัดดูหน้างาน) ตอบเป็นข้อความล้วน ไม่ต้องใส่หัวข้อหรือสัญลักษณ์ markdown"
        ),
        messages=[
            {"role": "user", "content": f"บทสนทนากับลูกค้า:\n{conversation}\n\nร่างข้อความตอบกลับถัดไป"}
        ],
    )
    text_parts = [b.text for b in response.content if isinstance(b, anthropic.types.TextBlock)]
    return "\n".join(text_parts).strip()
