"""Default public-site content when tenant has no CMS rows yet (matches design/tenant-site.html frame a)."""

from __future__ import annotations

from typing import Any


def default_hero_slides() -> list[dict[str, Any]]:
    """Fallback carousel when no HeroBanner rows — copy from deck frame a."""
    return [
        {
            "gradient": "linear-gradient(135deg, #2A1F0F 0%, #4A3C2C 60%, #8B7355 100%)",
            "tag": "Bulk request · ส่งครั้งเดียว ครบทั้งห้อง",
            "headline_html": "เปิดออฟฟิศใหม่ครึ่งห้อง?<br><em>อัปโหลด floorplan · proposal ใน 48 ชม.</em>",
            "subline": "ส่งผังห้อง + จำนวนคน + งบ · ทีมเซลส์จัดเซ็ตเฟอร์นิเจอร์ครบ · spec + รูป + ราคารวม",
            "cta_primary_label": "อัปโหลด floorplan →",
            "cta_primary_url_name": "public_bulk",
            "cta_ghost_label": "หรือทักไลน์ก่อน",
            "cta_ghost_line": True,
        },
        {
            "gradient": "linear-gradient(135deg, #1A2F1F 0%, #2D4A35 50%, #5F7A65 100%)",
            "tag": "ลีดไทม์สั้น · ส่งทันใช้",
            "headline_html": "ส่งภายใน 3-7 วัน<br><em>กรุงเทพ-ปริมณฑล · ติดตั้งฟรี ≥ ฿50K</em>",
            "subline": "เก้าอี้ ergonomic · โต๊ะ · ตู้ · workstation · ลีดไทม์ผู้ผลิตจริง",
            "cta_primary_label": "ดูสินค้าลีดไทม์สั้น →",
            "cta_primary_url_name": "public_catalog",
            "cta_primary_query": "?fast=1",
        },
        {
            "gradient": "linear-gradient(135deg, #0F1715 0%, #1F2C28 50%, #4A7C4E 100%)",
            "tag": "Showroom · ปทุมธานี",
            "headline_html": "มาดูของจริง · 200 ตร.ม.<br><em>80+ รุ่น · 6 office mock-up</em>",
            "subline": "นัดเวลาก่อนได้ · มีเซลส์พาดู · ที่จอดรถฟรี",
            "cta_primary_label": "นัดเวลามาดู →",
            "cta_primary_url_name": "public_showroom",
        },
        {
            "gradient": "linear-gradient(135deg, #0A1B2A 0%, #1F3A5F 60%, #4A6B8F 100%)",
            "tag": "ผลงานล่าสุด",
            "headline_html": "ผลงานติดตั้งจริง<br><em>spec + รูป + ราคารวม</em>",
            "subline": "ดูเคสจากลูกค้าองค์กร · ส่ง+ติดตั้งครบในนัดเดียว",
            "cta_primary_label": "ดูผลงาน →",
            "cta_primary_url_name": "public_home",
            "cta_primary_fragment": "#cases",
        },
    ]


def hero_slides_for_home(
    banners: list,
    tenant,
    reverse,
) -> list[dict[str, Any]]:
    """Slides for frame-a carousel: DB banners or deck defaults with resolved URLs."""
    if banners:
        return [{"kind": "db", "banner": b} for b in banners]

    out: list[dict[str, Any]] = []
    for slide in default_hero_slides():
        url = ""
        name = slide.get("cta_primary_url_name")
        if name:
            url = reverse(name, kwargs={"tenant_slug": tenant.slug})
            url += slide.get("cta_primary_query") or ""
            url += slide.get("cta_primary_fragment") or ""
        out.append({**slide, "kind": "default", "cta_primary_url": url})
    return out
