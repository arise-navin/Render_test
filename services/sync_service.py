"""
services/sync_service.py

Sync flow:
  1. On startup → FULL SYNC of every table (all records, no timestamp filter).
  2. After full sync → DELTA every DELTA_INTERVAL seconds using sys_updated_on watermark.
  3. Agents always read from Postgres (never hit ServiceNow directly for reads).
  4. When an agent fixes a record → /fix-it/push PATCHes ServiceNow, then updates
     Postgres immediately AND advances the watermark so delta sync never overwrites the fix.

Note: All MySQL references have been replaced with Postgres equivalents.
      The sync logic itself is database-agnostic; only the imported helpers changed.
"""

import time
import copy
import threading
import requests
import os
from datetime import datetime
from .database import upsert_records, get_last_timestamp, get_table_count

# =====================================================
# SERVICENOW CONFIG — reads from live credentials store
# =====================================================
from services.credentials import get_credentials as _get_creds

def _inst():  return _get_creds()["instance"]
def _user():  return _get_creds()["user"]
def _pass_(): return _get_creds()["password"]

# Legacy aliases patched by _inject_credentials in main.py (no-op now)
SN_INSTANCE = ""
SN_USER     = ""
SN_PASS     = ""

# =====================================================
# TABLES TO SYNC
# =====================================================
TABLES = {
    # Architecture
    "sys_db_object":       {"label": "Table Definitions",      "category": "architecture"},
    # Scripts
    "sys_script":          {"label": "Business Rules",          "category": "scripts"},
    "sys_script_client":   {"label": "Client Scripts",          "category": "scripts"},
    "sys_script_include":  {"label": "Script Includes",         "category": "scripts"},
    "sys_ui_action":       {"label": "UI Actions",              "category": "scripts"},
    "sys_ui_policy":       {"label": "UI Policies",             "category": "scripts"},
    "sys_processor":       {"label": "Script Processors",       "category": "scripts"},
    # Performance
    "syslog_transaction":  {"label": "Transaction Logs",        "category": "performance"},
    # Security
    "sys_security_acl":    {"label": "ACL Rules",               "category": "security"},
    # Integration
    "sys_rest_message":    {"label": "REST Messages",           "category": "integration"},
    # Data Health
    "sys_dictionary":      {"label": "Data Dictionary",         "category": "data_health"},
    # Upgrade
    "sys_scope":           {"label": "App Scopes",              "category": "upgrade"},
    # License — Users
    "sys_user":            {"label": "Users",                   "category": "license"},
    "sys_user_has_role":   {"label": "User Roles",              "category": "license"},
    "sys_user_role":       {"label": "Role Definitions",        "category": "license"},
    "sys_user_grmember":   {"label": "Group Members",           "category": "license"},
    # License — Work records
    "incident":            {"label": "Incidents",               "category": "license"},
    "task":                {"label": "Tasks",                   "category": "license"},
    "change_request":      {"label": "Change Requests",         "category": "license"},
    "problem":             {"label": "Problems",                "category": "license"},
    "sc_task":             {"label": "Service Catalog Tasks",   "category": "license"},
    # License — Admin
    "sys_audit":           {"label": "Audit Logs",              "category": "license"},
    "sys_update_xml":      {"label": "Update Set XML",          "category": "license"},
}

SKIP_TABLES    = {"sys_hub_action_type"}
DELTA_INTERVAL = 30   # seconds between delta cycles

# =====================================================
# SHARED SYNC STATUS  (thread-safe)
# =====================================================
_sync_lock = threading.Lock()

sync_status = {
    "running":        False,
    "phase":          "IDLE",
    "last_completed": None,
    "next_run_in":    DELTA_INTERVAL,
    "cycle":          0,
    "full_sync_done": False,
    "tables": {}
}

def _init_table_status():
    for tbl, meta in TABLES.items():
        sync_status["tables"][tbl] = {
            "label":       meta["label"],
            "category":    meta["category"],
            "records":     0,
            "new_records": 0,
            "mode":        "PENDING",
            "status":      "pending",
            "last_synced": None,
            "error":       None,
        }

_init_table_status()


def _update(table, **kw):
    with _sync_lock:
        if table in sync_status["tables"]:
            sync_status["tables"][table].update(kw)


def get_sync_status():
    with _sync_lock:
        return copy.deepcopy(sync_status)

# =====================================================
# HELPERS
# =====================================================
def _ts_to_str(ts):
    if ts is None:
        return None
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)[:19]

# =====================================================
# FETCH — cursor-based pagination (avoids offset drift)
# =====================================================
def _fetch_paginated(table, last_ts_str, page_size=1000):
    """
    Full sync  → last_ts_str=None  → fetch ALL records ordered by sys_id.
    Delta sync → last_ts_str set   → fetch only records where sys_updated_on > watermark.

    Cursor pagination via sys_id bookmark avoids SN's 10,000-offset limit.
    Returns: (records: list[dict], max_seen_ts: str | None)
    """
    records     = []
    last_sys_id = None
    max_seen_ts = last_ts_str

    while True:
        if not last_ts_str:
            query = (
                f"sys_id>{last_sys_id}^ORDERBYsys_id"
                if last_sys_id else "ORDERBYsys_id"
            )
        else:
            base  = f"sys_updated_on>{last_ts_str}"
            query = (
                f"{base}^sys_id>{last_sys_id}^ORDERBYsys_updated_on^ORDERBYsys_id"
                if last_sys_id
                else f"{base}^ORDERBYsys_updated_on^ORDERBYsys_id"
            )

        params = {
            "sysparm_limit":                  page_size,
            "sysparm_query":                  query,
            "sysparm_display_value":          "false",
            "sysparm_exclude_reference_link": "true",
        }

        try:
            r = requests.get(
                f"{_inst()}/api/now/table/{table}",
                auth=(_user(), _pass_()),
                headers={"Accept": "application/json"},
                params=params,
                timeout=120,
            )
        except requests.RequestException as e:
            print(f"  [sync] {table} request error: {e}")
            break

        if r.status_code in (401, 403, 404):
            print(f"  [sync] {table} skipped — HTTP {r.status_code}")
            break

        try:
            r.raise_for_status()
        except Exception as e:
            print(f"  [sync] {table} HTTP error: {e}")
            break

        batch = r.json().get("result", [])
        if not batch:
            break

        last_sys_id = batch[-1].get("sys_id")

        for rec in batch:
            raw = rec.get("sys_updated_on")
            ts  = (raw if isinstance(raw, str)
                   else raw.get("value") if isinstance(raw, dict) else None)
            if ts and (max_seen_ts is None or ts > max_seen_ts):
                max_seen_ts = ts

        records.extend(batch)
        print(f"    [sync] {table}: +{len(batch)} records (total: {len(records)})")

        if len(batch) < page_size:
            break

    return records, max_seen_ts

# =====================================================
# SYNC ALL TABLES  (full or delta pass)
# =====================================================
def _sync_all_tables(force_full=False):
    with _sync_lock:
        sync_status["running"] = True
        sync_status["cycle"]  += 1
        sync_status["phase"]   = "FULL_SYNC" if force_full else "DELTA"

    total_new = 0

    for table in TABLES:
        if table in SKIP_TABLES:
            _update(table, status="skipped", error="restricted")
            continue

        _update(table, status="running", error=None, new_records=0)

        try:
            if force_full:
                last_ts_str = None
                mode        = "FULL"
            else:
                last_ts     = get_last_timestamp(table)
                last_ts_str = _ts_to_str(last_ts)
                mode        = "DELTA" if last_ts_str else "FULL"

            _update(table, mode=mode)
            suffix = f" since {last_ts_str}" if last_ts_str else ""
            print(f"  [sync] {table} [{mode}]{suffix}")

            records, max_seen_ts = _fetch_paginated(table, last_ts_str)

            if records:
                # upsert_records also advances watermark in table_sync_state
                upsert_records(table, records, max_seen_ts)
                total_new += len(records)
                _update(
                    table,
                    records     = get_table_count(table),
                    new_records = len(records),
                    status      = "ok",
                    last_synced = datetime.utcnow().isoformat(),
                    error       = None,
                )
                print(f"  [sync] {table} ✅ +{len(records):,} upserted")
            else:
                _update(
                    table,
                    new_records = 0,
                    status      = "ok",
                    last_synced = datetime.utcnow().isoformat(),
                )
                print(f"  [sync] {table} — no changes")

        except Exception as e:
            _update(table, status="error", error=str(e))
            print(f"  [sync] {table} ERROR: {e}")

    with _sync_lock:
        sync_status["running"]        = False
        sync_status["last_completed"] = datetime.utcnow().isoformat()
        sync_status["phase"]          = "IDLE"
        if force_full:
            sync_status["full_sync_done"] = True

    print(f"  [sync] ✔ cycle done — {total_new:,} total new/updated records")
    return total_new

# =====================================================
# BACKGROUND SYNC LOOP  (daemon thread from main.py)
# =====================================================
def start_sync_loop():
    """
    Phase 1 — FULL SYNC: pull every record into Postgres.
    Phase 2 — DELTA loop: every DELTA_INTERVAL seconds pull only updated records.
    Credentials are read live from the credentials store at each request.
    """
    print(f"[sync] ▶ Phase 1 — FULL SYNC → {_inst()}")
    _sync_all_tables(force_full=True)
    print(f"[sync] ✅ Full sync done. Phase 2 — DELTA every {DELTA_INTERVAL}s.")

    while True:
        for remaining in range(DELTA_INTERVAL, 0, -1):
            with _sync_lock:
                sync_status["next_run_in"] = remaining
            time.sleep(1)

        print("[sync] 🔄 DELTA cycle …")
        _sync_all_tables(force_full=False)
