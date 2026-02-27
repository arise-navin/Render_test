from services.database import fetch_cached
from agents._fetch import fetch_with_fallback
from ollama_client import ask_llm
from datetime import datetime
import re, json, ast

def run():
    data   = fetch_with_fallback("sys_security_acl", limit=1000)
    total  = len(data)

    parsed_acls    = [_safe_parse(r.get("data","")) for r in data]
    public_access  = [p for p in parsed_acls if p and isinstance(p, dict) and _field(p,"operation") == "public"
                      or "public" in str(_field(p,"roles")).lower()]
    admin_only     = [p for p in parsed_acls if p and isinstance(p, dict) and "admin" in str(_field(p,"roles")).lower()]
    no_role        = [p for p in parsed_acls if p and isinstance(p, dict) and not _field(p,"roles") or _field(p,"roles") == ""]
    script_acls    = [p for p in parsed_acls if p and isinstance(p, dict) and _field(p,"advanced") in (True,"true","1")]

    # Fast rule-based errors — then enrich with sys_id/table for deploy buttons
    errors = _detect_errors(parsed_acls)
    errors = _enrich_errors(errors, data)

    sample_size = min(total, 80)
    sample_text = str([_acl_summary(p) for p in parsed_acls[:sample_size]])

    prompt = f"""You are a ServiceNow Security Expert. Analyze ALL ACL rules.

FULL SCAN — {total} ACL rules:
- Public-accessible rules: {len(public_access)}
- Admin-only rules: {len(admin_only)}
- Rules with NO role requirement: {len(no_role)}
- Advanced scripted ACLs: {len(script_acls)}

Sample ACL summary (table, operation, roles):
{sample_text}

## Overview
Summarize security posture based on ALL {total} ACL rules.

## Risk Assessment
### Overall Risk Score: [X]/100 ([Level])

## Top Security Vulnerabilities
1. **[Vulnerability] (Critical - Score: X/100)** - Description
2. **[Vulnerability] (High - Score: X/100)** - Description
3. **[Vulnerability] (Medium - Score: X/100)** - Description

## Access Control Analysis
- **Over-permissive ACLs** – Tables with excessive access
- **Missing Role Restrictions** – Rules without role requirements
- **Public Access Risks** – Data exposed without auth

## Recommended Fixes
### Immediate Actions (Critical)
1. **[Action]** - Exact ACL change
2. **[Action]** - Security control

## Implementation Roadmap
- **This Week:** Patch critical ACL vulnerabilities
- **Month 1:** Complete access control review"""

    result = ask_llm(prompt)
    score  = _extract_score(result)

    return {
        "agent":               "security",
        "title":               "Security Analysis",
        "risk_score":          score,
        "total_records":       total,
        "public_access_count": len(public_access),
        "no_role_count":       len(no_role),
        "timestamp":           datetime.utcnow().isoformat(),
        "analysis":            result,
        "errors":              errors,
    }

def _safe_parse(raw):
    if isinstance(raw, dict): return raw
    try: return json.loads(raw)
    except: pass
    try: return ast.literal_eval(str(raw))
    except: return {}

def _field(parsed, key):
    val = parsed.get(key, "")
    if isinstance(val, dict): return val.get("value","") or val.get("display_value","")
    return val or ""

def _acl_summary(p):
    return {"table": _field(p,"name"), "operation": _field(p,"operation"), "roles": _field(p,"roles")}

def _enrich_errors(errors, rows):
    """
    Add sys_id, table, and script_field to each error so the frontend
    can show the 'Deploy to ServiceNow' and 'Save to MySQL' buttons.
    Matches errors to DB rows by ACL name.
    """
    # Build lookup: name -> row
    name_map = {}
    for row in rows:
        if not row or not isinstance(row, dict):
            continue
        rname = _field(row, "name") or _field(row, "sys_name") or str(row.get("name", ""))
        if rname:
            name_map[rname] = row

    for err in errors:
        if err.get("sys_id") and err.get("table"):
            continue  # already enriched
        # Try to match by script_name or affected field
        candidates = [err.get("script_name", ""), err.get("affected", "")]
        matched_row = None
        for candidate in candidates:
            # Try exact or partial match
            if candidate in name_map:
                matched_row = name_map[candidate]
                break
            for rname, row in name_map.items():
                if rname and (rname in str(candidate) or str(candidate) in rname):
                    matched_row = row
                    break
            if matched_row:
                break

        if matched_row:
            raw_sid = matched_row.get("sys_id", "")
            if isinstance(raw_sid, dict):
                raw_sid = raw_sid.get("value") or raw_sid.get("display_value") or ""
            err["sys_id"]       = str(raw_sid).strip()
            err["table"]        = "sys_security_acl"
            err["script_field"] = "script"  # ACL script condition field
        else:
            # No match — provide table hint so deploy is still possible if user has sys_id
            err.setdefault("table", "sys_security_acl")
            err.setdefault("script_field", "script")

    return errors


def _detect_errors(acls):
    errors = []
    eid = 0
    for p in acls:
        name   = _field(p, "name") or "Unknown"
        op     = _field(p, "operation") or "read"
        roles  = _field(p, "roles")
        active = str(_field(p, "active")).lower() not in ("false","0","")

        if not active:
            continue

        if not roles or roles.strip() == "":
            eid += 1
            errors.append({
                "id": f"sec_{eid:03d}", "title": "ACL Rule Has No Role Restriction",
                "severity": "critical", "script_type": "ACL Rule", "script_name": name,
                "description": f"ACL on '{name}' ({op}) has no role restriction — accessible to any authenticated user.",
                "affected": f"ACL → {name} ({op})",
                "original_code": f"// Table: {name}\n// Operation: {op}\n// Roles: (empty)",
                "fix_prompt": f"Add role restriction to ACL '{name}'. Set roles field to 'itil' or a specific role. Apply principle of least privilege."
            })
        if "public" in str(roles).lower():
            eid += 1
            errors.append({
                "id": f"sec_{eid:03d}", "title": "Public ACL Detected",
                "severity": "critical", "script_type": "ACL Rule", "script_name": name,
                "description": f"ACL on '{name}' grants public access — data visible without login.",
                "affected": f"ACL → {name} ({op})",
                "original_code": f"// Table: {name}\n// Roles: public",
                "fix_prompt": "Remove 'public' from roles. Replace with a specific role or require authentication."
            })
        if eid >= 500: break
    return errors

def _extract_score(text):
    m = re.search(r'(\d{1,3})/100', text)
    return int(m.group(1)) if m else None
