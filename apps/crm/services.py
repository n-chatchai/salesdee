"""CRM domain services (logic that doesn't belong in views or models)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.core.current_tenant import tenant_context

from .models import (
    Contact,
    Customer,
    Deal,
    DealStatus,
    Lead,
    LeadStatus,
    PipelineStage,
    StageKind,
)

if TYPE_CHECKING:
    from apps.tenants.models import Tenant

# Default pipeline for a furniture sales business — used to seed a new tenant.
# (name, order, kind, default_probability)
DEFAULT_PIPELINE_STAGES: list[tuple[str, int, str, int]] = [
    ("ลูกค้าใหม่ / สอบถาม", 10, StageKind.OPEN, 10),
    ("คัดกรอง / นัดดูหน้างาน", 20, StageKind.OPEN, 25),
    ("ส่งใบเสนอราคา", 30, StageKind.OPEN, 40),
    ("ต่อรอง / รออนุมัติ", 40, StageKind.OPEN, 65),
    ("ปิดได้ (รับ PO)", 50, StageKind.WON, 100),
    ("ปิดไม่ได้", 60, StageKind.LOST, 0),
]


def seed_default_pipeline(tenant: Tenant) -> None:
    """Create the default pipeline stages for a tenant if it has none yet. Idempotent."""
    with tenant_context(tenant):
        if PipelineStage.objects.exists():
            return
        for name, order, kind, prob in DEFAULT_PIPELINE_STAGES:
            PipelineStage.objects.create(
                name=name, order=order, kind=kind, default_probability=prob
            )


def move_deal_to_stage(deal: Deal, stage: PipelineStage) -> None:
    """Move a deal to a stage; sync status/closed_at when entering a WON/LOST stage."""
    from django.utils import timezone

    deal.stage = stage
    deal.probability = stage.default_probability
    if stage.kind == StageKind.WON:
        deal.status = DealStatus.WON
        deal.closed_at = deal.closed_at or timezone.now()
    elif stage.kind == StageKind.LOST:
        deal.status = DealStatus.LOST
        deal.closed_at = deal.closed_at or timezone.now()
    else:
        deal.status = DealStatus.OPEN
        deal.closed_at = None
    deal.save()


def convert_lead(lead: Lead, *, owner=None) -> Deal:
    """Turn a lead into a Customer (+ Contact) and an open Deal. Run inside the lead's tenant."""
    first_open = PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order").first()
    customer = lead.customer or Customer.objects.create(
        name=lead.company_name or lead.name,
        billing_address="",
    )
    if not Contact.objects.filter(customer=customer, name=lead.name).exists():
        Contact.objects.create(
            customer=customer,
            name=lead.name,
            phone=lead.phone,
            email=lead.email,
            line_id=lead.line_id,
            is_primary=not customer.contacts.exists(),
        )
    deal = Deal.objects.create(
        name=lead.product_interest or f"ดีลจาก lead: {lead.name}",
        customer=customer,
        stage=first_open,
        owner=owner,
        estimated_value=lead.budget or 0,
        probability=first_open.default_probability if first_open else 0,
        channel=lead.channel,
        source=lead.source,
        notes=lead.message,
    )
    lead.status = LeadStatus.CONVERTED
    lead.customer = customer
    lead.deal = deal
    lead.save()
    return deal
