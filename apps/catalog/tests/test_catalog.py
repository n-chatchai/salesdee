from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.catalog.models import Product, TaxType
from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_product_create(client, user, membership, tenant) -> None:
    client.force_login(user)
    resp = client.post(
        reverse("catalog:product_create"),
        {
            "name": "โต๊ะผู้บริหาร",
            "code": "EXE-01",
            "unit": "ตัว",
            "default_price": "12000",
            "tax_type": TaxType.VAT7,
        },
    )
    assert resp.status_code == 302
    with tenant_context(tenant):
        p = Product.objects.get(code="EXE-01")
        assert p.name == "โต๊ะผู้บริหาร"
        assert p.default_price == Decimal("12000")
    assert resp.url == reverse("catalog:product_detail", args=[p.pk])


def test_product_list_renders(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        Product.objects.create(name="ตู้รางเลื่อน 5 ตู้", default_price=Decimal("45000"))
    client.force_login(user)
    resp = client.get(reverse("catalog:products"))
    assert resp.status_code == 200
    assert "ตู้รางเลื่อน 5 ตู้" in resp.content.decode()


def test_product_tenant_isolation(tenant, other_tenant) -> None:
    with tenant_context(tenant):
        Product.objects.create(name="ของ tenant A")
        assert Product.objects.count() == 1
    with tenant_context(other_tenant):
        assert Product.objects.count() == 0


def test_product_detail_renders(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        p = Product.objects.create(name="เก้าอี้สำนักงาน", code="CHR-9", width_mm=600)
    client.force_login(user)
    resp = client.get(reverse("catalog:product_detail", args=[p.pk]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "เก้าอี้สำนักงาน" in body
    assert "CHR-9" in body


def _make_xlsx(path) -> str:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["code", "name", "unit", "price", "category", "width_mm", "tax"])
    ws.append(["TBL-01", "โต๊ะทำงาน", "ตัว", "3,500", "โต๊ะ", "1200", "7"])
    ws.append(["", "ตู้เซฟ", "ตู้", "8900", "ตู้เซฟ", "", "vat7"])
    ws.append(["", "", "ตัว", "100", "", "", ""])  # no name -> skipped
    out = str(path / "catalog.xlsx")
    wb.save(out)
    return out


def test_import_catalog_command(tenant, tmp_path) -> None:
    path = _make_xlsx(tmp_path)
    call_command("import_catalog", path, tenant_slug=tenant.slug)
    with tenant_context(tenant):
        assert Product.objects.count() == 2
        tbl = Product.objects.get(code="TBL-01")
        assert tbl.name == "โต๊ะทำงาน"
        assert tbl.width_mm == 1200
        assert tbl.default_price == Decimal("3500")
        assert tbl.category is not None and tbl.category.name == "โต๊ะ"
        assert Product.objects.filter(name="ตู้เซฟ").exists()
    # re-import updates rather than duplicates
    call_command("import_catalog", path, tenant_slug=tenant.slug)
    with tenant_context(tenant):
        assert Product.objects.count() == 3  # the no-code "ตู้เซฟ" row creates a second one each run


def test_import_catalog_unknown_tenant_raises(tenant, tmp_path) -> None:
    path = _make_xlsx(tmp_path)
    with pytest.raises(CommandError):
        call_command("import_catalog", path, tenant_slug="no-such-tenant")
