"""Create E2E test user for Playwright tests."""

from django.core.management.base import BaseCommand

from apps.accounts.models import Membership, User
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Create E2E test user for Playwright tests"

    def handle(self, *args, **options):
        # Get or create test tenant
        tenant, _ = Tenant.objects.get_or_create(
            slug="e2e-test", defaults={"name": "E2E Test Tenant"}
        )

        # Get or create test user
        user, created = User.objects.get_or_create(
            email="e2e@test.com",
            defaults={
                "full_name": "E2E Test User",
                "is_active": True,
            },
        )

        if created:
            user.set_password("TestPass123!")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created user: e2e@test.com"))
        else:
            self.stdout.write("User already exists: e2e@test.com")

        # Create membership with OWNER role
        membership, _ = Membership.objects.get_or_create(
            user=user, tenant=tenant, defaults={"role": "owner"}
        )
        if membership.role != "owner":
            membership.role = "owner"
            membership.save()
        self.stdout.write(
            self.style.SUCCESS(f"Membership created with owner role for tenant: {tenant.slug}")
        )

        self.stdout.write(self.style.SUCCESS("E2E credentials: e2e@test.com / TestPass123!"))
