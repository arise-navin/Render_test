import requests
import os
from datetime import datetime
from requests.auth import HTTPBasicAuth

# ── Credentials ───────────────────────────────────────────────────────────────
# Prefer environment variables; fall back to dev defaults
SN_INSTANCE = os.getenv("SN_INSTANCE", "https://dev229640.service-now.com")
SN_USER     = os.getenv("SN_USERNAME", "admin")
SN_PASS     = os.getenv("SN_PASSWORD", "^Iu8XizJm6P%")


def fetch_table(table, last_sync=None, limit=None):
    """
    Fetch records from a ServiceNow table.
    If limit is None we fetch ALL records using offset pagination (no cap).
    Pass limit=N for a single-page bounded fetch (backwards-compatible).
    """
    if limit is not None:
        url   = f"{SN_INSTANCE}/api/now/table/{table}"
        query = f"sys_updated_on>{last_sync}" if last_sync else ""
        params = {"sysparm_limit": limit, "sysparm_display_value": "false"}
        if query:
            params["sysparm_query"] = query
        r = requests.get(url, auth=(SN_USER, SN_PASS),
                         headers={"Accept": "application/json"},
                         params=params, timeout=60)
        r.raise_for_status()
        return r.json().get("result", [])

    # ── Full paginated fetch — scans ALL data, no artificial limit ────────────
    records = []
    offset  = 0
    page_sz = 1000
    query   = f"sys_updated_on>{last_sync}" if last_sync else ""

    while True:
        params = {
            "sysparm_limit":  page_sz,
            "sysparm_offset": offset,
            "sysparm_display_value": "false",
        }
        if query:
            params["sysparm_query"] = query

        r = requests.get(
            f"{SN_INSTANCE}/api/now/table/{table}",
            auth=(SN_USER, SN_PASS),
            headers={"Accept": "application/json"},
            params=params,
            timeout=60,
        )
        if r.status_code in (401, 403, 404):
            break
        r.raise_for_status()
        batch = r.json().get("result", [])
        if not batch:
            break
        records.extend(batch)
        offset += page_sz
        if len(batch) < page_sz:
            break   # reached last page

    return records


def get_real_table_data(table, query=None, fields=None):
    """Helper used by some agents for targeted, filtered queries."""
    url    = f"{SN_INSTANCE}/api/now/table/{table}"
    params = {}
    if query:
        params["sysparm_query"] = query
    if fields:
        params["sysparm_fields"] = fields
    response = requests.get(url, auth=HTTPBasicAuth(SN_USER, SN_PASS),
                             params=params, timeout=60)
    if response.status_code == 200:
        return response.json().get("result", [])
    return []
