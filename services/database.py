"""
services/database.py
PostgreSQL storage — full drop-in replacement for the original MySQL version.

Key differences from MySQL build:
  • Driver          : psycopg2-binary  (replaces mysql-connector-python)
  • Connection      : DATABASE_URL env var (Render injects this automatically)
  • Identifiers     : double-quoted  "table"  instead of back-ticked  `table`
  • Upsert          : INSERT … ON CONFLICT DO UPDATE  (replaces REPLACE INTO)
  • Duplicate key   : ON CONFLICT (…) DO UPDATE SET  (replaces ON DUPLICATE KEY)
  • Column inspect  : information_schema.columns  (replaces SHOW COLUMNS)
  • Dict cursor     : RealDictCursor  (replaces cursor(dictionary=True))
  • Charset clause  : removed  (Postgres is UTF-8 by default)
  • LONGTEXT        : replaced with TEXT  (Postgres has no LONGTEXT)
"""

import json
import os
import re
import psycopg2
import psycopg2.extras
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# Connection — reads DATABASE_URL injected by Render
# ─────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _fix_scheme(url: str) -> str:
    """
    Render provides  postgres://…  but psycopg2 requires  postgresql://…
    This one-liner makes both work.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def get_conn():
    url = _fix_scheme(DATABASE_URL)
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Add it in Render → your service → Environment."
        )
    return psycopg2.connect(url, sslmode="require")


# ─────────────────────────────────────────────────────────────
# Flatten nested ServiceNow reference fields
# ─────────────────────────────────────────────────────────────

def flatten_record(record: dict) -> dict:
    flat = {}
    for k, v in record.items():
        if isinstance(v, dict):
            flat[k] = v.get("value") or v.get("display_value") or ""
        elif isinstance(v, list):
            flat[k] = json.dumps(v, ensure_ascii=False)
        elif v is None:
            flat[k] = None
        else:
            flat[k] = v
    return flat


# ─────────────────────────────────────────────────────────────
# Column name safety
# ─────────────────────────────────────────────────────────────

def sanitize_col(name: str):
    """Return a safe, lowercase column name or None if invalid."""
    if not name:
        return None
    name = name.strip().lower()          # Postgres folds unquoted names to lower
    if not re.match(r"^[a-z0-9_]{1,63}$", name):
        return None
    return name


# ─────────────────────────────────────────────────────────────
# Sync-state table (watermark for incremental sync)
# ─────────────────────────────────────────────────────────────

def _ensure_sync_table(cursor):
    # No CHARACTER SET clause — Postgres is always UTF-8
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS table_sync_state (
            table_name          VARCHAR(128) PRIMARY KEY,
            last_sys_updated_on VARCHAR(32)
        )
    """)


def _update_watermark(cursor, table: str, timestamp: str):
    if not timestamp:
        return
    _ensure_sync_table(cursor)
    # ON CONFLICT … DO UPDATE replaces MySQL's ON DUPLICATE KEY UPDATE
    cursor.execute("""
        INSERT INTO table_sync_state (table_name, last_sys_updated_on)
        VALUES (%s, %s)
        ON CONFLICT (table_name)
        DO UPDATE SET last_sys_updated_on = EXCLUDED.last_sys_updated_on
    """, (table, timestamp))


# ─────────────────────────────────────────────────────────────
# Auto-create / auto-expand dynamic tables
# ─────────────────────────────────────────────────────────────

def _ensure_table(cursor, table: str, flat_row: dict):
    """
    Create the table if it doesn't exist yet.
    Uses double-quoted identifiers and TEXT columns (no LONGTEXT in Postgres).
    """
    col_defs = ['"sys_id" TEXT PRIMARY KEY']
    for k in flat_row:
        safe = sanitize_col(k)
        if safe and safe != "sys_id":
            col_defs.append(f'"{safe}" TEXT')
    cursor.execute(
        f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(col_defs)})'
    )


def _ensure_columns(cursor, table: str, flat_row: dict):
    """
    Add any columns that are present in flat_row but not yet in the table.
    Uses information_schema instead of MySQL's SHOW COLUMNS.
    """
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table,),
    )
    existing = {row[0] for row in cursor.fetchall()}

    for k in flat_row:
        safe = sanitize_col(k)
        if safe and safe not in existing:
            try:
                # ADD COLUMN IF NOT EXISTS is safe in Postgres 9.6+
                cursor.execute(
                    f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{safe}" TEXT'
                )
                existing.add(safe)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
# Upsert records + advance watermark
# ─────────────────────────────────────────────────────────────

def upsert_records(table: str, records: list, max_seen_ts=None):
    """
    Upsert a batch of ServiceNow records into Postgres.

    MySQL used:   REPLACE INTO `table` (…) VALUES (…)
    Postgres uses: INSERT INTO "table" (…) VALUES (…)
                   ON CONFLICT ("sys_id") DO UPDATE SET col = EXCLUDED.col, …
    """
    if not records:
        return

    db     = get_conn()
    cursor = db.cursor()
    highest_ts = max_seen_ts

    for record in records:
        if not record or not isinstance(record, dict):
            continue

        flat = flatten_record(record)
        _ensure_table(cursor, table, flat)
        _ensure_columns(cursor, table, flat)

        cols         = []
        placeholders = []
        values       = []

        for k, v in flat.items():
            safe = sanitize_col(k)
            if not safe:
                continue
            cols.append(f'"{safe}"')
            placeholders.append("%s")

            if isinstance(v, (dict, list)):
                values.append(json.dumps(v, ensure_ascii=False))
            elif isinstance(v, bool):
                # Postgres has a real BOOLEAN type; keep as string for TEXT col
                values.append("true" if v else "false")
            else:
                values.append(v)

        if not cols:
            continue

        # Build the ON CONFLICT update list for all columns except the PK
        update_cols = [c for c in cols if c != '"sys_id"']
        if update_cols:
            set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
            sql = (
                f'INSERT INTO "{table}" ({", ".join(cols)}) '
                f'VALUES ({", ".join(placeholders)}) '
                f'ON CONFLICT ("sys_id") DO UPDATE SET {set_clause}'
            )
        else:
            sql = (
                f'INSERT INTO "{table}" ({", ".join(cols)}) '
                f'VALUES ({", ".join(placeholders)}) '
                f'ON CONFLICT ("sys_id") DO NOTHING'
            )

        try:
            cursor.execute(sql, values)
        except Exception as e:
            print(f"[db] upsert error in {table}: {e}")

        # Track the highest sys_updated_on seen in this batch
        if not highest_ts:
            ts = flat.get("sys_updated_on")
            if ts and (not highest_ts or ts > highest_ts):
                highest_ts = ts

    if highest_ts:
        _update_watermark(cursor, table, highest_ts)

    db.commit()
    cursor.close()
    db.close()


# ─────────────────────────────────────────────────────────────
# Watermark reader  (used by sync_service)
# ─────────────────────────────────────────────────────────────

def get_last_timestamp(table: str):
    try:
        db     = get_conn()
        cursor = db.cursor()
        _ensure_sync_table(cursor)
        db.commit()   # make sure CREATE TABLE IF NOT EXISTS is visible

        cursor.execute(
            "SELECT last_sys_updated_on FROM table_sync_state WHERE table_name = %s",
            (table,),
        )
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if not row or not row[0]:
            return None
        return datetime.strptime(row[0][:19], "%Y-%m-%d %H:%M:%S")

    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Read helpers
# ─────────────────────────────────────────────────────────────

def fetch_cached(table: str, limit=None):
    """
    Return all (or limited) rows from a synced table as a list of dicts.
    Uses RealDictCursor instead of MySQL's  cursor(dictionary=True).
    """
    try:
        db     = get_conn()
        # RealDictCursor returns rows as real Python dicts
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Double-quote the table name; %s placeholder for the LIMIT value
        if limit is not None:
            cursor.execute(f'SELECT * FROM "{table}" LIMIT %s', (limit,))
        else:
            cursor.execute(f'SELECT * FROM "{table}"')

        rows = cursor.fetchall()
        cursor.close()
        db.close()

        result = []
        for row in rows:
            if not row:
                continue
            row_dict = dict(row)
            if "data" not in row_dict:
                row_dict["data"] = json.dumps(row_dict, ensure_ascii=False, default=str)
            result.append(row_dict)
        return result

    except Exception as e:
        print(f"[db] fetch_cached error on {table}: {e}")
        return []


# ─────────────────────────────────────────────────────────────
# Row count
# ─────────────────────────────────────────────────────────────

def get_table_count(table: str) -> int:
    try:
        db     = get_conn()
        cursor = db.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cursor.fetchone()[0]
        cursor.close()
        db.close()
        return count or 0
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────
# Single-field update  (used by /fix-it/push)
# ─────────────────────────────────────────────────────────────

def update_record_field(table: str, sys_id: str, field: str, value) -> bool:
    """
    Update one column in a cached Postgres row.
    When field == 'sys_updated_on' the watermark is also advanced so the next
    delta sync does NOT pull the old version back and overwrite the agent fix.
    """
    safe = sanitize_col(field)
    if not safe:
        return False
    try:
        db     = get_conn()
        cursor = db.cursor()

        # Make sure the column exists before writing
        _ensure_columns(cursor, table, {field: value})

        cursor.execute(
            f'UPDATE "{table}" SET "{safe}" = %s WHERE sys_id = %s',
            (value, sys_id),
        )

        if safe == "sys_updated_on" and value:
            _update_watermark(cursor, table, str(value)[:19])

        db.commit()
        cursor.close()
        db.close()
        return True

    except Exception as e:
        print(f"[db] update_record_field error: {e}")
        return False
