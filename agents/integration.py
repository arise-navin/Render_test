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
    data   = fetch_with_fallback("sys_rest_message", limit=500)
    total  = len(data)

    basic_auth = [r for r in data if r and isinstance(r, dict) and "basic" in str(r.get("data","")).lower()]
    no_auth    = [r for r in data if r and isinstance(r, dict) and '"authentication_type": "no_authentication"' in str(r.get("data",""))
                                  or "'authentication_type': 'no_authentication'" in str(r.get("data",""))]
    legacy     = [r for r in data if r and isinstance(r, dict) and "http://" in str(r.get("data",""))]   # non-HTTPS

    sample_size = min(total, 100)
    sample      = data[:sample_size]

    prompt = f"""You are a ServiceNow Integration Expert. Analyze ALL REST message and integration data.

Instance Stats (FULL SCAN — all {total} integration endpoints analyzed):
- Total integration endpoints: {total}
- Basic Auth (potentially insecure): {len(basic_auth)}
- No authentication configured: {len(no_auth)}
- Non-HTTPS endpoints (legacy): {len(legacy)}
- Sample sent to AI: {sample_size}

Raw integration data sample:
{str(sample[:40])}

Provide a structured analysis with these EXACT sections using markdown:

## Overview
Summarize the integration landscape based on ALL {total} endpoints.

## Risk Assessment
### Overall Risk Score: [X]/100 ([Level])
Brief integration risk summary.

## Integration Issues Identified
1. **[Issue] (Score: X/100)** - Impact on reliability and data integrity
2. **[Issue] (Score: X/100)** - Description of risk
3. **[Issue] (Score: X/100)** - Description

## Errors & Issues Found
For each concrete integration problem, output a JSON block:
```json
[
  {{
    "id": "int_001",
    "title": "Short integration issue title",
    "severity": "critical|high|medium|low",
    "description": "What the integration issue is",
    "affected": "REST endpoint or integration name",
    "original_code": "// Current problematic config or code",
    "fix_prompt": "Comment out the insecure/broken config and replace with: [new config]. Switch to OAuth2, add retry logic, use HTTPS. Apply ServiceNow Integration Hub best practices."
  }}
]
```

## Integration Health Check
- **Authentication & Security** - OAuth tokens, Basic Auth risks
- **Error Handling** - Missing retry logic, unhandled failures
- **Data Mapping** - Field mapping issues
- **Rate Limiting** - API throttling concerns

## Recommended Fixes
### Critical Fixes
1. **[Fix]** - Specific integration configuration change
2. **[Fix]** - Security improvement

## Implementation Roadmap
- **Week 1:** Secure all authentication credentials
- **Week 2-3:** Add error handling and retry logic
- **Month 2:** Full integration monitoring setup"""

    result = ask_llm(prompt)
    score  = _extract_score(result)
    errors = _extract_errors(result)
    errors = _enrich_errors(errors, data, "sys_rest_message", "rest_message_fn")

    return {
        "agent":         "integration",
        "title":         "Integration Analysis",
        "risk_score":    score,
        "total_records": total,
        "no_auth_count": len(no_auth),
        "legacy_count":  len(legacy),
        "timestamp":     datetime.utcnow().isoformat(),
        "analysis":      result,
        "errors":        errors,
    }

def _enrich_errors(errors, rows, table_name, script_field="rest_message_fn"):
    """
    Enrich LLM-extracted errors with sys_id, table, and script_field so the
    frontend can show 'Deploy to ServiceNow' + 'Save to MySQL' buttons.
    Matches by name against the affected/script_name field in each error.
    """
    # Build name -> row lookup
    name_map = {}
    for row in rows:
        if not row or not isinstance(row, dict):
            continue
        for key in ("name", "sys_name", "action_name"):
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
            # Fallback: attach first available sys_id so deploy can still work
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
