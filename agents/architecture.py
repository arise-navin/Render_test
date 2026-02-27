from services.database import fetch_cached, get_table_count
from agents._fetch import fetch_with_fallback
from ollama_client import ask_llm
from datetime import datetime
import re, json


def _safe_row_get(row, key, default=""):
    """Safely get a value from a DB row dict, guarding against None."""
    if not row or not isinstance(row, dict):
        return default
    val = row.get(key, default)
    if isinstance(val, dict):
        return val.get("value","") or val.get("display_value","") or default
    return val if val is not None else default

def run():
    data      = fetch_with_fallback("sys_db_object", limit=2000)   # DB cache or direct SN
    total     = len(data)

    # Build meaningful stats from full dataset
    custom_tables   = [r for r in data if r and isinstance(r, dict) and '"u_"' in str(r.get("data","")) or "'u_'" in str(r.get("data",""))]
    extended_tables = [r for r in data if r and isinstance(r, dict) and '"extends"' in str(r.get("data","")).lower()]
    large_tables    = [r for r in data if r and isinstance(r, dict) and '"count"' in str(r.get("data","")).lower()]

    # Send a representative sample to LLM (not all, to stay within context)
    sample_size = min(total, 100)
    sample      = data[:sample_size]

    prompt = f"""You are a ServiceNow Architecture Expert. Analyze the FULL instance data below.

Instance Stats (FULL SCAN — all {total} records analyzed):
- Total tables in instance: {total}
- Custom tables (u_ prefix): {len(custom_tables)}
- Extended tables: {len(extended_tables)}
- Records in sample sent to AI: {sample_size}

Raw data sample (representative):
{str(sample[:40])}

Provide a structured analysis with these EXACT sections using markdown:

## Overview
Write 2-3 sentences summarizing the overall architecture health based on ALL {total} tables.

## Risk Assessment
### Overall Risk Score: [X]/100 ([Level])
List the top risks found.

## Top Risks Identified
1. **[Risk Name] (Score: X/100)** - Description of the risk and its impact
2. **[Risk Name] (Score: X/100)** - Description of the risk and its impact
3. **[Risk Name] (Score: X/100)** - Description

## Errors & Issues Found
For each error or issue found, output a JSON block like this (inside ```json ... ``` fences):
```json
[
  {{
    "id": "arch_001",
    "title": "Short error title",
    "severity": "critical|high|medium|low",
    "description": "What the error is and why it matters",
    "affected": "table or component name",
    "fix_prompt": "Detailed instruction for AI to fix this: what to comment out, what new code to write, what ServiceNow best practice to apply"
  }}
]
```

## Recommended Fixes
### Immediate Actions (Critical)
1. **[Action]** - Specific step to take
2. **[Action]** - Specific step to take

### Short-Term Actions (High Priority)
1. **[Action]** - Specific step to take

### Long-Term Actions (Medium Priority)
1. **[Action]** - Specific step to take

## Implementation Roadmap
- **Week 1-2:** Critical fixes
- **Week 3-4:** High priority items
- **Ongoing:** Monitoring and reviews

Be specific and reference ServiceNow best practices."""

    result = ask_llm(prompt)
    score  = _extract_score(result)
    errors = _extract_errors(result)
    errors = _enrich_errors(errors, data, "sys_db_object", "script")

    return {
        "agent":         "architecture",
        "title":         "Architecture Analysis",
        "risk_score":    score,
        "total_records": total,
        "custom_tables": len(custom_tables),
        "timestamp":     datetime.utcnow().isoformat(),
        "analysis":      result,
        "errors":        errors,
    }

def _enrich_errors(errors, rows, table_name, script_field="script"):
    """
    Enrich LLM-extracted errors with sys_id, table, and script_field so the
    frontend can show 'Deploy to ServiceNow' + 'Save to MySQL' buttons.
    """
    name_map = {}
    for row in rows:
        if not row or not isinstance(row, dict):
            continue
        for key in ("name", "sys_name", "label"):
            rname = row.get(key)
            if isinstance(rname, dict):
                rname = rname.get("value") or rname.get("display_value") or ""
            if rname:
                name_map[str(rname).strip()] = row
                break

    for err in errors:
        if err.get("sys_id") and err.get("table"):
            continue

        matched_row = None
        for candidate in [err.get("script_name", ""), err.get("affected", ""), err.get("title", "")]:
            candidate = str(candidate).strip()
            if not candidate:
                continue
            if candidate in name_map:
                matched_row = name_map[candidate]
                break
            for rname, row in name_map.items():
                if rname and (rname in candidate or candidate in rname):
                    matched_row = row
                    break
            if matched_row:
                break

        if matched_row:
            raw_sid = matched_row.get("sys_id", "")
            if isinstance(raw_sid, dict):
                raw_sid = raw_sid.get("value") or raw_sid.get("display_value") or ""
            err["sys_id"]       = str(raw_sid).strip()
            err["table"]        = table_name
            err["script_field"] = script_field
        else:
            for row in rows:
                if not row or not isinstance(row, dict):
                    continue
                sid = row.get("sys_id", "")
                if isinstance(sid, dict):
                    sid = sid.get("value") or sid.get("display_value") or ""
                sid = str(sid).strip()
                if sid and len(sid) >= 10:
                    err.setdefault("sys_id", sid)
                    break
            err.setdefault("table", table_name)
            err.setdefault("script_field", script_field)

    return errors


def _extract_score(text):
    m = re.search(r'(\d{1,3})/100', text)
    return int(m.group(1)) if m else None

def _extract_errors(text):
    """Pull JSON error blocks out of the AI response."""
    errors = []
    for block in re.finditer(r'```json\s*([\s\S]*?)```', text):
        try:
            parsed = json.loads(block.group(1).strip())
            if isinstance(parsed, list):
                errors.extend(parsed)
            elif isinstance(parsed, dict):
                errors.append(parsed)
        except Exception:
            pass
    return errors
