"""
Scripts Agent — analyzes ALL ServiceNow script types:
  Business Rules, Client Scripts, Script Includes,
  UI Actions, UI Policies, Script Processors, Scheduled Scripts

Reads directly from individual MySQL columns (not a JSON blob).
"""
from services.database import fetch_cached
from agents._fetch import fetch_with_fallback
from ollama_client import ask_llm
from datetime import datetime
import re, json

SCRIPT_TABLES = {
    "sys_script":          "Business Rule",
    "sys_script_client":   "Client Script",
    "sys_script_include":  "Script Include",
    "sys_ui_action":       "UI Action",
    "sys_ui_policy":       "UI Policy",
    "sys_processor":       "Script Processor",
    "sys_schedule_script": "Scheduled Script",
}

# The column name that holds the script body for each table
SCRIPT_FIELD = {
    "sys_script":          "script",
    "sys_script_client":   "script",
    "sys_script_include":  "script",
    "sys_ui_action":       "script",
    "sys_ui_policy":       "script_true",
    "sys_processor":       "script",
    "sys_schedule_script": "script",
}

def _col(row, *keys):
    """Safely read a column value from a row dict."""
    for k in keys:
        v = row.get(k)
        if v and str(v).strip() and str(v).strip().lower() not in ("none", "null"):
            return str(v).strip()
    return ""

def run():
    all_scripts = []
    type_counts = {}

    for table, type_label in SCRIPT_TABLES.items():
        rows = fetch_with_fallback(table, limit=1000)
        type_counts[type_label] = len(rows)

        for row in rows:
            if not row or not isinstance(row, dict):
                continue

            # Read directly from columns — no JSON blob parsing needed
            _raw_sid = _col(row, "sys_id")
            # MySQL may have stored sys_id as a JSON dict: {"value":"abc...","display_value":"..."}
            # Extract the plain 32-char value if so
            if _raw_sid and _raw_sid.startswith('{'):
                try:
                    import json as _json
                    _sid_obj = _json.loads(_raw_sid)
                    _raw_sid = _sid_obj.get("value") or _sid_obj.get("display_value") or _raw_sid
                except Exception:
                    pass
            sys_id = _raw_sid
            name   = _col(row, "name", "sys_name", "action_name", "job_name") or "Unknown"
            body   = _col(row, SCRIPT_FIELD.get(table, "script"), "script")
            sfield = SCRIPT_FIELD.get(table, "script")

            all_scripts.append({
                "table":        table,
                "type":         type_label,
                "name":         name,
                "sys_id":       sys_id,
                "script_field": sfield,
                "script_body":  body,
            })

    total  = len(all_scripts)
    errors = _detect_errors(all_scripts)

    sample_size = min(total, 60)
    summary_lines = [f"- {v} × {k}" for k, v in type_counts.items() if v > 0]

    prompt = f"""You are a ServiceNow Script Quality Expert. Analyze ALL script data.

FULL SCAN — {total} total scripts:
{chr(10).join(summary_lines)}

Top scripts sample (type, name, body preview):
{_build_sample_text(all_scripts[:sample_size])}

Write analysis with these EXACT markdown sections:

## Overview
2–3 sentences on overall script quality across ALL {total} scripts.

## Risk Assessment
### Overall Risk Score: [X]/100 ([Level])
Brief summary.

## Top Issues Identified
1. **[Issue] (Score: X/100)** – Impact with script type references
2. **[Issue] (Score: X/100)** – Description
3. **[Issue] (Score: X/100)** – Description

## Code Quality Problems
- **Performance Issues** – GlideRecord without setLimit, no index queries
- **Security Vulnerabilities** – Injection risks, hardcoded credentials
- **Maintainability** – Missing comments, dead code, duplicate logic

## Recommended Fixes
### Critical Fixes
1. **[Fix]** – Exact step with ServiceNow API reference
2. **[Fix]** – Exact step

## Implementation Roadmap
- **Week 1–2:** Critical security & performance fixes
- **Week 3–4:** Code quality
- **Ongoing:** Automated script scanning"""

    analysis = ask_llm(prompt)
    score    = _extract_score(analysis)

    return {
        "agent":            "scripts",
        "title":            "Scripts Analysis",
        "risk_score":       score,
        "total_records":    total,
        "type_counts":      type_counts,
        "timestamp":        datetime.utcnow().isoformat(),
        "analysis":         analysis,
        "errors":           errors,
        "script_inventory": _build_inventory(all_scripts),
    }

# ── Error detection ───────────────────────────────────────────────────────────

def _detect_errors(scripts):
    errors = []
    eid    = 0

    for s in scripts:
        body   = s["script_body"]
        name   = s["name"]
        stype  = s["type"]
        stbl   = s["table"]
        ssid   = s["sys_id"]
        sfield = s["script_field"]

        if not body or len(body) < 10:
            continue

        # 1. GlideRecord without setLimit
        if re.search(r'new GlideRecord\s*\(', body) and "setLimit" not in body:
            eid += 1
            errors.append({
                "id": f"script_{eid:03d}", "title": "Unlimited GlideRecord Query",
                "severity": "high", "script_type": stype, "script_name": name,
                "sys_id": ssid, "table": stbl, "script_field": sfield,
                "description": f"{stype} '{name}' uses GlideRecord without setLimit() — can scan entire table and timeout.",
                "affected": f"{stype} → {name}",
                "original_code": body,
                "fix_prompt": "Add gr.setLimit(200) after GlideRecord instantiation. Use addQuery() for filtering. Apply ServiceNow GlideRecord best practice to avoid full table scans."
            })

        # 2. current.update() in Business Rule — infinite recursion
        if stype == "Business Rule" and "current.update()" in body:
            eid += 1
            errors.append({
                "id": f"script_{eid:03d}", "title": "current.update() in Business Rule (Recursion Risk)",
                "severity": "critical", "script_type": stype, "script_name": name,
                "sys_id": ssid, "table": stbl, "script_field": sfield,
                "description": f"Business Rule '{name}' calls current.update() causing infinite recursion.",
                "affected": f"Business Rule → {name}",
                "original_code": body,
                "fix_prompt": "Remove current.update(). Use current.setValue() — the platform auto-saves. Use a separate GlideRecord if an update is truly needed."
            })

        # 3. Query injection via addEncodedQuery + string concat
        if re.search(r'addEncodedQuery\s*\(\s*["\'].*\+', body):
            eid += 1
            errors.append({
                "id": f"script_{eid:03d}", "title": "Query Injection Risk",
                "severity": "critical", "script_type": stype, "script_name": name,
                "sys_id": ssid, "table": stbl, "script_field": sfield,
                "description": f"{stype} '{name}' builds addEncodedQuery with string concatenation.",
                "affected": f"{stype} → {name}",
                "original_code": body,
                "fix_prompt": "Replace addEncodedQuery with individual addQuery('field','value') calls. Never concatenate user input into encoded queries."
            })

        # 4. Debug logging in production
        if "gs.log(" in body or "gs.print(" in body:
            eid += 1
            errors.append({
                "id": f"script_{eid:03d}", "title": "Debug Logging in Production Script",
                "severity": "low", "script_type": stype, "script_name": name,
                "sys_id": ssid, "table": stbl, "script_field": sfield,
                "description": f"{stype} '{name}' uses gs.log() or gs.print() polluting system logs.",
                "affected": f"{stype} → {name}",
                "original_code": body,
                "fix_prompt": "Remove gs.log() and gs.print(). Use gs.debug() wrapped in if(gs.isDebugging()) for conditional logging."
            })

        # 5. Missing try/catch in async scripts
        if stype in ("UI Action", "Script Processor", "Scheduled Script") and "try" not in body and len(body) > 80:
            eid += 1
            errors.append({
                "id": f"script_{eid:03d}", "title": "Missing Error Handling",
                "severity": "high", "script_type": stype, "script_name": name,
                "sys_id": ssid, "table": stbl, "script_field": sfield,
                "description": f"{stype} '{name}' has no try/catch block. Unhandled exceptions break workflows silently.",
                "affected": f"{stype} → {name}",
                "original_code": body,
                "fix_prompt": "Wrap the entire script in try { ... } catch(e) { gs.error(name + ' failed: ' + e.message); }"
            })

        # 6. Hardcoded sys_id
        if re.search(r'\b[0-9a-f]{32}\b', body):
            eid += 1
            errors.append({
                "id": f"script_{eid:03d}", "title": "Hardcoded sys_id",
                "severity": "medium", "script_type": stype, "script_name": name,
                "sys_id": ssid, "table": stbl, "script_field": sfield,
                "description": f"{stype} '{name}' contains a hardcoded sys_id that differs across environments.",
                "affected": f"{stype} → {name}",
                "original_code": body,
                "fix_prompt": "Replace the hardcoded sys_id with a dynamic GlideRecord lookup or gs.getProperty()."
            })

        if eid >= 500:
            break

    return errors

# ── Helpers ───────────────────────────────────────────────────────────────────

def _snippet(body, keyword, chars=280):
    idx = body.find(keyword)
    if idx < 0: return body[:chars]
    return body[max(0, idx-40):idx+chars]

def _snippet_regex(body, pattern, chars=280):
    m = re.search(pattern, body)
    if not m: return body[:chars]
    return body[max(0, m.start()-40):m.start()+chars]

def _build_sample_text(scripts):
    lines = []
    for s in scripts:
        preview = (s["script_body"] or "")[:100].replace("\n", " ")
        lines.append(f"[{s['type']}] {s['name']}: {preview}")
    return "\n".join(lines)

def _build_inventory(scripts):
    return [
        {
            "type":     s["type"],
            "name":     s["name"],
            "table":    s["table"],
            "sys_id":   s["sys_id"],
            "has_body": bool(s["script_body"]),
            "body_len": len(s["script_body"]),
        }
        for s in scripts
    ]

def _extract_score(text):
    m = re.search(r'(\d{1,3})/100', text or "")
    return int(m.group(1)) if m else None
