"""Smoke tests: the project boots, settings are sane, basic routing works."""

from __future__ import annotations

import pytest
from django.urls import reverse


def test_django_check_passes() -> None:
    from django.core.management import call_command

    call_command("check")  # raises SystemCheckError on problems


def test_home_redirects_anonymous_to_login(client) -> None:
    resp = client.get("/")
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp.url


def test_login_page_renders(client) -> None:
    resp = client.get(reverse("accounts:login"))
    assert resp.status_code == 200
    assert "เข้าสู่ระบบ" in resp.content.decode()


@pytest.mark.django_db
def test_home_renders_for_logged_in_user(client, user, membership) -> None:
    client.force_login(user)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "วันดีดี" in resp.content.decode()  # tenant resolved via membership


def test_money_decimal_settings_present() -> None:
    from django.conf import settings

    assert settings.LANGUAGE_CODE == "th-th"
    assert settings.TIME_ZONE == "Asia/Bangkok"
    assert settings.AUTH_USER_MODEL == "accounts.User"
