"""
agents/_fetch.py
Shared helper: fetch from Postgres cache; if empty, fall back to a direct
ServiceNow REST call so agents work even before the first sync completes.

IMPORTANT: credentials are read via get_credentials() at CALL TIME, not at
import time, so they always reflect the logged-in user's session credentials.
"""
from services.database import fetch_cached as _fetch_cached
from services.credentials import get_credentials
import requests as _req


def fetch_with_fallback(table: str, limit: int = 500) -> list:
    """
    1. Try Postgres cache (fast path — data from background sync).
    2. If empty → hit ServiceNow directly using live session credentials.
    Returns list of dicts, each with a 'data' key for backward compat.
    """
    rows = []
    try:
        rows = _fetch_cached(table) or []
    except Exception as e:
        print(f"[fetch] DB error on {table}: {e}")

    if rows:
        return rows

    # ── Fallback: direct live fetch from ServiceNow ──────────────────────────
    creds    = get_credentials()   # always reads the current live value
    instance = creds.get("instance", "")
    user     = creds.get("user", "")
    password = creds.get("password", "")

    if not instance or not user or not password:
        print(f"[fetch] No credentials available for direct fetch of {table}")
        return []

    try:
        r = _req.get(
            f"{instance}/api/now/table/{table}",
            auth=(user, password),
            headers={"Accept": "application/json"},
            params={
                "sysparm_limit": limit,
                "sysparm_display_value": "false",
                "sysparm_exclude_reference_link": "true",
            },
            timeout=30,
        )
        if r.status_code == 200:
            batch = r.json().get("result", [])
            rows = []
            for rec in batch:
                row = dict(rec)
                if "data" not in row:
                    row["data"] = str(rec)
                rows.append(row)
            print(f"[fetch] direct SN fetch {table}: {len(rows)} records")
        else:
            print(f"[fetch] direct SN fetch {table}: HTTP {r.status_code}")
    except Exception as e:
        print(f"[fetch] direct SN error on {table}: {e}")

    return rows
