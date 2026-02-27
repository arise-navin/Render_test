"""
services/credentials.py
─────────────────────────────────────────────────────────────────────────────
Single source of truth for ServiceNow credentials.

ALL modules must call get_credentials() at request time — never import
SN_INSTANCE / SN_USER / SN_PASS as values at module load time, because
Python caches those as local copies and patching the original module variable
afterward has no effect on already-imported names.

Usage:
    from services.credentials import get_credentials, set_credentials

    creds = get_credentials()
    creds['instance']   # https://dev.service-now.com
    creds['user']
    creds['password']
"""

import os

# Mutable dict — mutate in place so all references stay live
_CREDS: dict = {
    "instance": os.getenv("SN_INSTANCE", ""),
    "user":     os.getenv("SN_USERNAME", ""),
    "password": os.getenv("SN_PASSWORD", ""),
}


def get_credentials() -> dict:
    """Return current credentials dict (always live, never stale)."""
    return _CREDS


def set_credentials(instance: str, user: str, password: str) -> None:
    """Update credentials in place — all callers see the new values immediately."""
    _CREDS["instance"] = instance.rstrip("/")
    _CREDS["user"]     = user
    _CREDS["password"] = password


def is_configured() -> bool:
    """True if credentials have been set and look valid."""
    return bool(_CREDS.get("instance") and _CREDS.get("user") and _CREDS.get("password"))
