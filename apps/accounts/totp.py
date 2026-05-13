"""TOTP helpers for the optional 2FA flow (FR-15.1). Wraps ``pyotp`` so the rest of the app doesn't
care about the library."""

from __future__ import annotations

import pyotp


def new_secret() -> str:
    """A fresh base32 TOTP secret."""
    return pyotp.random_base32()


def otpauth_uri(secret: str, *, account_name: str, issuer: str = "salesdee.") -> str:
    """An ``otpauth://`` URI for Google Authenticator / Authy / 1Password (paste-or-QR)."""
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)


def verify(secret: str, code: str) -> bool:
    """True if ``code`` is the current 6-digit TOTP for ``secret`` (with ±1 step tolerance)."""
    if not (secret and code and code.strip().isdigit()):
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
