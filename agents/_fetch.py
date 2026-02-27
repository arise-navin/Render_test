"""
agents/_fetch.py
Shared helper: fetch from Postgres cache; if empty/missing, fall back to
a direct ServiceNow REST call so agents work even before the first sync.
"""
from services.database import fetch_cached as _fetch_cached
import requests as _req


def fetch_with_fallback(table: str, limit: int = 500) -> list:
    """
    1. Try Postgres (fast, cached).
    2. If empty → hit ServiceNow directly (first run / sync not done yet).
    Returns a list of dicts each guaranteed to have a 'data' key.
    """
    rows = []
    try:
        rows = _fetch_cached(table) or []
    except Exception as e:
        print(f"[fetch] DB error on {table}: {e}")

    if rows:
        return rows

    # Fallback: direct ServiceNow fetch
    try:
        from services.servicenow_client import SN_INSTANCE, SN_USER, SN_PASS
        if not SN_INSTANCE or not SN_USER:
            return []
        r = _req.get(
            f"{SN_INSTANCE}/api/now/table/{table}",
            auth=(SN_USER, SN_PASS),
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
            print(f"[fetch] fallback SN fetch {table}: {len(rows)} records")
    except Exception as e:
        print(f"[fetch] fallback SN error on {table}: {e}")

    return rows
