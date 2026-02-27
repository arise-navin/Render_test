import requests
import os
from requests.auth import HTTPBasicAuth
from services.credentials import get_credentials


def fetch_table(table, last_sync=None, limit=None):
    """Fetch records from a ServiceNow table using live credentials."""
    creds    = get_credentials()
    instance = creds["instance"]
    user     = creds["user"]
    password = creds["password"]

    if not instance or not user:
        print(f"[sn_client] No credentials set — skipping {table}")
        return []

    if limit is not None:
        url    = f"{instance}/api/now/table/{table}"
        query  = f"sys_updated_on>{last_sync}" if last_sync else ""
        params = {"sysparm_limit": limit, "sysparm_display_value": "false"}
        if query:
            params["sysparm_query"] = query
        r = requests.get(url, auth=(user, password),
                         headers={"Accept": "application/json"},
                         params=params, timeout=60)
        r.raise_for_status()
        return r.json().get("result", [])

    # Full paginated fetch
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
            f"{instance}/api/now/table/{table}",
            auth=(user, password),
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
            break

    return records


def get_real_table_data(table, query=None, fields=None):
    """Helper used by some agents for targeted, filtered queries."""
    creds    = get_credentials()
    instance = creds["instance"]
    user     = creds["user"]
    password = creds["password"]

    if not instance or not user:
        return []

    url    = f"{instance}/api/now/table/{table}"
    params = {}
    if query:
        params["sysparm_query"] = query
    if fields:
        params["sysparm_fields"] = fields
    response = requests.get(url, auth=HTTPBasicAuth(user, password),
                             params=params, timeout=60)
    if response.status_code == 200:
        return response.json().get("result", [])
    return []
