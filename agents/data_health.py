from services.database import fetch_cached
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
    data   = fetch_with_fallback("sys_dictionary", limit=1000)
    total  = len(data)

    orphaned   = [r for r in data if r and isinstance(r, dict) and '"active": false' in str(r.get("data","")).lower()
                                  or "'active': 'false'" in str(r.get("data","")).lower()]
    no_label   = [r for r in data if r and isinstance(r, dict) and '"column_label": ""' in str(r.get("data",""))
                                  or "'column_label': ''" in str(r.get("data",""))]
    large_str  = [r for r in data if r and isinstance(r, dict) and '"max_length": 4000' in str(r.get("data",""))
                                  or '"max_length": 8000' in str(r.get("data",""))]

    sample_size = min(total, 100)
    sample      = data[:sample_size]

    prompt = f"""You are a ServiceNow Data Quality Expert. Analyze ALL data dictionary entries.

Instance Stats (FULL SCAN — all {total} dictionary entries analyzed):
- Total dictionary entries: {total}
- Inactive/orphaned fields: {len(orphaned)}
- Fields missing labels: {len(no_label)}
- Oversized string fields (4000+ chars): {len(large_str)}
- Sample sent to AI: {sample_size}

Raw dictionary data sample:
{str(sample[:40])}

Provide a structured analysis with these EXACT sections using markdown:

## Overview
Summarize the overall data quality based on ALL {total} dictionary entries.

## Risk Assessment
### Overall Risk Score: [X]/100 ([Level])
Brief data health risk summary.

## Data Quality Issues Identified
1. **[Issue] (Score: X/100)** - Impact on reporting and operations
2. **[Issue] (Score: X/100)** - Description with table/field references
3. **[Issue] (Score: X/100)** - Description

## Errors & Issues Found
For each concrete data quality problem, output a JSON block:
```json
[
  {{
    "id": "data_001",
    "title": "Short data issue title",
    "severity": "critical|high|medium|low",
    "description": "What is wrong with this field or table definition",
    "affected": "table.field_name",
    "original_code": "// Current dictionary definition snippet",
    "fix_prompt": "Comment out the incorrect field definition and replace with: [correct definition]. Add proper validation, correct max_length, set mandatory flag. Apply ServiceNow data governance best practice."
  }}
]
```

## Dictionary Health Analysis
- **Missing Mandatory Fields** - Required fields without validation
- **Data Type Mismatches** - Incorrect type definitions
- **Orphaned Fields** - Unused or deprecated definitions
- **Duplicate Definitions** - Conflicting field configs

## Recommended Fixes
### Immediate Actions
1. **[Action]** - Specific data quality fix
2. **[Action]** - Field configuration correction

## Implementation Roadmap
- **Week 1-2:** Fix critical data integrity issues
- **Month 1:** Implement data validation rules
- **Quarterly:** Data quality audit and cleanup"""

    result = ask_llm(prompt)
    score  = _extract_score(result)
    errors = _extract_errors(result)
    errors = _enrich_errors(errors, data, "sys_dictionary", "default_value")

    return {
        "agent":         "data_health",
        "title":         "Data Health Analysis",
        "risk_score":    score,
        "total_records": total,
        "orphaned_count": len(orphaned),
        "no_label_count": len(no_label),
        "timestamp":     datetime.utcnow().isoformat(),
        "analysis":      result,
        "errors":        errors,
    }

def _enrich_errors(errors, rows, table_name, script_field="default_value"):
    """
    Enrich LLM-extracted errors with sys_id, table, and script_field so the
    frontend can show 'Deploy to ServiceNow' + 'Save to MySQL' buttons.
    Matches by element (field) name within the data dictionary.
    """
    name_map = {}
    for row in rows:
        if not row or not isinstance(row, dict):
            continue
        for key in ("element", "name", "sys_name", "column_label"):
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
