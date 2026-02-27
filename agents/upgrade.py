from services.database import fetch_cached
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
    data   = fetch_cached("sys_scope")
    total  = len(data)

    global_scope   = [r for r in data if r and isinstance(r, dict) and '"scope": "global"' in str(r.get("data",""))
                                       or "'scope': 'global'" in str(r.get("data",""))]
    old_js         = [r for r in data if r and isinstance(r, dict) and '"js_level": "es5"' in str(r.get("data","")).lower()
                                       or '"javascript_mode": "es5"' in str(r.get("data","")).lower()]
    high_mod_count = [r for r in data if r and isinstance(r, dict) and '"customization_count"' in str(r.get("data",""))]

    sample_size = min(total, 100)
    sample      = data[:sample_size]

    prompt = f"""You are a ServiceNow Upgrade & Release Expert. Analyze ALL application scope data.

Instance Stats (FULL SCAN — all {total} scopes analyzed):
- Total application scopes: {total}
- Global scope apps (upgrade risk): {len(global_scope)}
- Outdated JavaScript level (ES5): {len(old_js)}
- Apps with high modification counts: {len(high_mod_count)}
- Sample sent to AI: {sample_size}

Raw scope data sample:
{str(sample[:40])}

Provide a structured analysis with these EXACT sections using markdown:

## Overview
Summarize upgrade readiness based on ALL {total} application scopes.

## Risk Assessment
### Overall Risk Score: [X]/100 ([Level])
Brief upgrade readiness risk summary.

## Upgrade Risks Identified
1. **[Risk] (Score: X/100)** - How this blocks or complicates upgrades
2. **[Risk] (Score: X/100)** - Customization or scope conflict
3. **[Risk] (Score: X/100)** - Description

## Errors & Issues Found
For each concrete upgrade blocker or risky customization, output a JSON block:
```json
[
  {{
    "id": "upg_001",
    "title": "Short upgrade risk title",
    "severity": "critical|high|medium|low",
    "description": "Why this is a problem for upgrades",
    "affected": "application scope or component name",
    "original_code": "// Problematic customization or config",
    "fix_prompt": "Comment out the global-scope customization and move to: [scoped app]. Update JS from ES5 to ES6+. Reduce customization count by: [specific steps]. Apply ServiceNow upgrade best practice."
  }}
]
```

## Upgrade Readiness Assessment
- **Custom Scopes** - Apps that may conflict with platform upgrades
- **Global Scope Customizations** - Risky direct platform modifications
- **Deprecated APIs** - Code using removed APIs
- **Plugin Dependencies** - Version-specific plugin issues

## Recommended Fixes
### Pre-Upgrade Actions (Critical)
1. **[Action]** - Specific preparation step
2. **[Action]** - Code or configuration change

## Implementation Roadmap
- **Month 1:** Pre-upgrade cleanup and testing
- **Month 2:** Upgrade test environment
- **Month 3:** Production upgrade with monitoring"""

    result = ask_llm(prompt)
    score  = _extract_score(result)
    errors = _extract_errors(result)
    errors = _enrich_errors(errors, data, "sys_scope", "js_level")

    return {
        "agent":           "upgrade",
        "title":           "Upgrade Readiness Analysis",
        "risk_score":      score,
        "total_records":   total,
        "global_scope_count": len(global_scope),
        "old_js_count":    len(old_js),
        "timestamp":       datetime.utcnow().isoformat(),
        "analysis":        result,
        "errors":          errors,
    }

def _enrich_errors(errors, rows, table_name, script_field="js_level"):
    """
    Enrich LLM-extracted errors with sys_id, table, and script_field so the
    frontend can show 'Deploy to ServiceNow' + 'Save to MySQL' buttons.
    """
    name_map = {}
    for row in rows:
        if not row or not isinstance(row, dict):
            continue
        for key in ("name", "sys_name", "scope"):
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
