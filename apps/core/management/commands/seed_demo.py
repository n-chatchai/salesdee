"""Populate a tenant with realistic Thai office-furniture demo data (for local dev / demos).

    uv run python manage.py seed_demo --tenant wandeedee

Idempotent-ish: skips if the tenant already has customers, unless --force is given.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from apps.catalog.models import Product, ProductCategory, TaxType
from apps.core.current_tenant import tenant_context
from apps.crm.models import (
    Activity,
    ActivityKind,
    Contact,
    Customer,
    Deal,
    DealStatus,
    Lead,
    LeadChannel,
    LeadStatus,
    PipelineStage,
    Task,
    TaskKind,
)
from apps.quotes.models import DocStatus, LineType, SalesDocLine
from apps.quotes.services import apply_catalog_defaults, create_quotation_from_deal
from apps.tenants.models import BankAccount, Branch, CompanyProfile, Tenant

CATEGORIES = ["โต๊ะ", "เก้าอี้", "ตู้เซฟ", "ตู้รางเลื่อน", "ล็อกเกอร์", "ชุดประชุม"]
# (code, name, category, price, unit, W, D, H, material)
PRODUCTS = [
    ("EXE-150", "โต๊ะผู้บริหาร 1.5 ม.", "โต๊ะ", 12000, "ตัว", 1500, 750, 750, "ลามิเนต สีโอ๊ค"),
    ("WD-120", "โต๊ะทำงาน 1.2 ม.", "โต๊ะ", 3500, "ตัว", 1200, 600, 750, "เมลามีน สีเทา"),
    ("CH-EXE", "เก้าอี้ผู้บริหาร หนังแท้", "เก้าอี้", 8500, "ตัว", None, None, None, "หนังแท้/อะลูมิเนียม"),
    ("CH-OFF", "เก้าอี้สำนักงาน ตาข่าย", "เก้าอี้", 3200, "ตัว", None, None, None, "ตาข่าย/ไนลอน"),
    ("CH-ROW3", "เก้าอี้แถว 3 ที่นั่ง", "เก้าอี้", 4800, "ชุด", 1700, 700, 800, "เหล็ก/เบาะ PVC"),
    ("SF-90", "ตู้เซฟดิจิทัล 90 กก. (มอก.)", "ตู้เซฟ", 9800, "ตู้", 450, 480, 600, "เหล็กกล้า"),
    ("MC-5", "ตู้รางเลื่อน 5 ตู้", "ตู้รางเลื่อน", 45000, "ชุด", None, None, None, "เหล็ก พ่นสีฝุ่น"),
    ("MC-3", "ตู้รางเลื่อน 3 ตู้", "ตู้รางเลื่อน", 28000, "ชุด", None, None, None, "เหล็ก พ่นสีฝุ่น"),
    ("LK-12", "ล็อกเกอร์ 12 ช่อง", "ล็อกเกอร์", 8900, "ตู้", 900, 450, 1800, "เหล็ก พ่นสีฝุ่น"),
    ("CONF-12", "ชุดโต๊ะประชุม 12 ที่นั่ง", "ชุดประชุม", 38000, "ชุด", None, None, None, "ไม้วีเนียร์"),
]
# (name, kind, contact_name, contact_title, credit_days)
CUSTOMERS = [
    ("บริษัท ไอที โซลูชัน จำกัด", "company", "คุณสมชาย ใจดี", "ฝ่ายจัดซื้อ", 30),
    ("โรงแรม เดอะ การ์เด้น", "company", "คุณวิภา รักงาน", "ฝ่ายอาคาร", 45),
    ("โรงเรียนวัดสวนผัก", "company", "อ.ประยุทธ์ ตั้งใจ", "งานพัสดุ", 0),
    ("บริษัท เอ็นจิเนียริ่ง พลัส จำกัด", "company", "คุณนภา สดใส", "ธุรการ", 30),
]
# (name, customer_idx, stage_kind/order, value, status)  -- stage chosen by 'order'
DEALS = [
    ("เฟอร์นิเจอร์ออฟฟิศ ชั้น 3", 0, 30, 280000, DealStatus.OPEN),
    ("ชุดโต๊ะประชุม โรงแรม", 1, 40, 120000, DealStatus.OPEN),
    ("ตู้รางเลื่อน ห้องเอกสาร", 0, 20, 45000, DealStatus.OPEN),
    ("ล็อกเกอร์ ห้องพนักงาน", 2, 10, 18000, DealStatus.OPEN),
    ("เฟอร์นิเจอร์ห้องประชุมใหญ่", 3, 50, 95000, DealStatus.WON),
]


class Command(BaseCommand):
    help = "Seed a tenant with demo data. --tenant <slug>"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--tenant", dest="slug", default="wandeedee")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **opts) -> None:
        tenant, _ = Tenant.objects.get_or_create(
            slug=opts["slug"], defaults={"name": "วันดีดี เฟอร์นิเจอร์"}
        )
        with tenant_context(tenant):
            if Customer.objects.exists() and not opts["force"]:
                self.stdout.write(
                    self.style.WARNING(
                        "tenant already has data — use --force to add more; skipping"
                    )
                )
                return
            self._seed(tenant)
        self.stdout.write(self.style.SUCCESS(f"seeded demo data for tenant '{tenant.slug}'"))

    def _seed(self, tenant: Tenant) -> None:
        from django.contrib.auth import get_user_model

        owner = (
            get_user_model()
            .objects.filter(memberships__tenant=tenant, memberships__is_active=True)
            .first()
        )

        # company profile + bank account
        cp, _ = CompanyProfile.objects.get_or_create(
            tenant=tenant, defaults={"name_th": tenant.name}
        )
        cp.name_th = "บริษัท วัน.ดี.ดี.บิสซิเนส จำกัด"
        cp.name_en = "Wan Dee Dee Business Co., Ltd."
        cp.tax_id = "0125565099999"
        cp.branch_kind = Branch.HEAD_OFFICE
        cp.address = "99/9 หมู่ 9 ต.บางพูด อ.ปากเกร็ด จ.นนทบุรี 11120"
        cp.phone = "098-256-4151"
        cp.email = "sales@wandeedeefurniture.com"
        cp.save()
        bank, _ = BankAccount.objects.get_or_create(
            account_number="123-4-56789-0",
            defaults={
                "bank_name": "กสิกรไทย",
                "branch_name": "ปากเกร็ด",
                "account_name": "บริษัท วัน.ดี.ดี.บิสซิเนส จำกัด",
                "account_type": "ออมทรัพย์",
                "is_default": True,
            },
        )

        # catalog
        cats = {name: ProductCategory.objects.get_or_create(name=name)[0] for name in CATEGORIES}
        products: dict[str, Product] = {}
        for code, name, cat, price, unit, w, d, h, material in PRODUCTS:
            products[code] = Product.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": cats[cat],
                    "default_price": Decimal(price),
                    "unit": unit,
                    "width_mm": w,
                    "depth_mm": d,
                    "height_mm": h,
                    "material": material,
                    "tax_type": TaxType.VAT7,
                    "is_bundle": code == "CONF-12",
                },
            )[0]

        # customers + contacts
        customers: list[Customer] = []
        for name, kind, cname, ctitle, credit in CUSTOMERS:
            c = Customer.objects.create(
                name=name, kind=kind, default_credit_days=credit, billing_address="กรุงเทพฯ"
            )
            Contact.objects.create(
                customer=c, name=cname, title=ctitle, phone="02-000-0000", is_primary=True
            )
            customers.append(c)

        # pipeline stages already seeded by the tenant-provision signal
        stages = {s.order: s for s in PipelineStage.objects.all()}

        # leads
        Lead.objects.create(
            name="คุณก้อง สนใจ",
            company_name="หจก. เฟอร์ฯ ก้อง",
            channel=LeadChannel.WEB_FORM,
            product_interest="ตู้รางเลื่อน 5 ตู้",
            budget=Decimal("50000"),
            status=LeadStatus.NEW,
        )
        Lead.objects.create(
            name="คุณมาลี",
            company_name="โรงแรม X",
            channel=LeadChannel.PHONE,
            product_interest="เก้าอี้แถว 50 ที่นั่ง",
            status=LeadStatus.QUALIFIED,
            assigned_to=owner,
        )
        Lead.objects.create(
            name="คุณวิชัย",
            channel=LeadChannel.REFERRAL,
            product_interest="โต๊ะทำงาน 10 ตัว",
            status=LeadStatus.NEW,
        )

        # deals
        deals: list[Deal] = []
        for dname, ci, order, value, status in DEALS:
            deal = Deal.objects.create(
                name=dname,
                customer=customers[ci],
                stage=stages.get(order),
                owner=owner,
                estimated_value=Decimal(value),
                probability=(stages[order].default_probability if order in stages else 0),
                status=status,
                channel=LeadChannel.PHONE,
                closed_at=timezone.now() if status == DealStatus.WON else None,
            )
            deals.append(deal)

        # activities + tasks on a couple of deals
        Activity.objects.create(
            deal=deals[0],
            customer=customers[0],
            kind=ActivityKind.CALL,
            body="โทรคุยกับฝ่ายจัดซื้อ — ขอให้ส่งใบเสนอราคาภายในสัปดาห์นี้",
            created_by=owner,
        )
        Activity.objects.create(
            deal=deals[0],
            customer=customers[0],
            kind=ActivityKind.SITE_VISIT,
            body="ไปวัดพื้นที่ชั้น 3 — มี 1 ห้องผู้บริหาร + พื้นที่ทำงานรวม 8 ที่",
            created_by=owner,
        )
        Activity.objects.create(
            deal=deals[1],
            customer=customers[1],
            kind=ActivityKind.NOTE,
            body="ลูกค้าขอตัวอย่างผ้าหุ้มเก้าอี้ 3 สี",
            created_by=owner,
        )
        now = timezone.now()
        Task.objects.create(
            deal=deals[0],
            customer=customers[0],
            kind=TaskKind.SEND_QUOTE,
            description="ส่งใบเสนอราคาออฟฟิศชั้น 3",
            due_at=now + timedelta(days=1),
            assignee=owner,
        )
        Task.objects.create(
            deal=deals[1],
            customer=customers[1],
            kind=TaskKind.SEND_SAMPLE,
            description="ส่งตัวอย่างผ้า 3 สี โรงแรม",
            due_at=now + timedelta(days=3),
            assignee=owner,
        )
        Task.objects.create(
            deal=deals[3],
            customer=customers[2],
            kind=TaskKind.SITE_SURVEY,
            description="นัดสำรวจหน้างาน ห้องพนักงาน โรงเรียน",
            due_at=now - timedelta(days=2),
            assignee=owner,
        )

        # quotation 1 — from deal[0], grouped by room
        q1 = create_quotation_from_deal(deals[0], salesperson=owner)
        q1.bank_account = bank
        q1.payment_terms = "มัดจำ 50% เมื่อยืนยันสั่งซื้อ · ส่วนที่เหลือ 50% ก่อนติดตั้ง"
        q1.lead_time = "30-45 วันหลังรับมัดจำ"
        q1.warranty = "รับประกันสินค้า 1 ปี"
        q1.end_discount_value = Decimal("5000")
        q1.status = DocStatus.SENT
        q1.sent_at = now - timedelta(days=2)
        q1.save()
        rooms = [
            ("ชั้น 3 - ห้องผู้บริหาร", [("EXE-150", 1), ("CH-EXE", 1)]),
            ("ชั้น 3 - พื้นที่ทำงานรวม", [("WD-120", 8), ("CH-OFF", 8)]),
            ("ชั้น 3 - ส่วนกลาง", [("MC-5", 1), ("LK-12", 2), ("SF-90", 1)]),
        ]
        pos = 0
        for room, items in rooms:
            for code, qty in items:
                pos += 1
                ln = SalesDocLine(
                    document=q1,
                    group_label=room,
                    position=pos,
                    line_type=LineType.ITEM,
                    product=products[code],
                    quantity=Decimal(qty),
                )
                apply_catalog_defaults(ln)
                ln.save()

        self.stdout.write(
            f"  customers={len(customers)} products={len(products)} deals={len(deals)} q1_lines={pos}"
        )
