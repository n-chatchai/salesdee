from __future__ import annotations

import pyotp
import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_login_without_2fa_is_unchanged(client, user) -> None:
    resp = client.post(
        "/accounts/login/", {"username": user.email, "password": "testpass-12345"}, follow=True
    )
    assert resp.status_code == 200
    assert client.session.get("_auth_user_id") == str(user.pk)


def test_login_with_confirmed_2fa_requires_totp_code(client, user) -> None:
    from apps.accounts.models import TwoFactorDevice

    secret = pyotp.random_base32()
    TwoFactorDevice.objects.create(
        user=user, secret=secret, confirmed=True, confirmed_at=timezone.now()
    )
    # password OK but user is *not* logged in yet — gated by /accounts/login/2fa/
    resp = client.post(
        "/accounts/login/", {"username": user.email, "password": "testpass-12345"}, follow=False
    )
    assert resp.status_code == 302
    assert resp.url.endswith("/accounts/login/2fa/")
    assert client.session.get("_auth_user_id") is None
    # wrong code → still not logged in
    resp = client.post("/accounts/login/2fa/", {"code": "000000"})
    assert client.session.get("_auth_user_id") is None
    # right code → logged in
    code = pyotp.TOTP(secret).now()
    resp = client.post("/accounts/login/2fa/", {"code": code}, follow=False)
    assert resp.status_code == 302
    assert client.session.get("_auth_user_id") == str(user.pk)


def test_enable_disable_2fa(client, user) -> None:
    from apps.accounts.models import TwoFactorDevice

    client.force_login(user)
    resp = client.get("/accounts/security/enable/")
    assert resp.status_code == 200
    device = TwoFactorDevice.objects.get(user=user)
    assert not device.confirmed
    # confirm
    code = pyotp.TOTP(device.secret).now()
    resp = client.post("/accounts/security/enable/", {"code": code})
    assert resp.status_code == 302
    device.refresh_from_db()
    assert device.confirmed
    # disable — wrong password
    resp = client.post("/accounts/security/disable/", {"password": "wrong"})
    assert TwoFactorDevice.objects.filter(user=user).exists()
    # disable — right password
    resp = client.post("/accounts/security/disable/", {"password": "testpass-12345"})
    assert not TwoFactorDevice.objects.filter(user=user).exists()
