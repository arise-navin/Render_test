from services.database import fetch_cached
from ollama_client import ask_llm
from datetime import datetime
import re, json, ast

def run():
    data   = fetch_cached("syslog_transaction")
    total  = len(data)

    parsed  = [_safe_parse(r.get("data","")) for r in data]
    slow_tx = [p for p in parsed if _get_ms(p) > 2000]
    err_tx  = [p for p in parsed if "error" in str(p).lower()]

    errors  = _detect_errors(parsed)
    errors  = _enrich_perf_errors(errors, data)

    sample_text = str([_tx_summary(p) for p in parsed[:80]])

    prompt = f"""You are a ServiceNow Performance Expert. Analyze ALL transaction log data.

FULL SCAN — {total} transactions:
- Slow (>2s): {len(slow_tx)}
- Error transactions: {len(err_tx)}

Sample transactions:
{sample_text}

## Overview
Summarize performance health based on ALL {total} transactions.

## Risk Assessment
### Overall Risk Score: [X]/100 ([Level])

## Performance Issues Identified
1. **[Issue] (Score: X/100)** - Impact and root cause
2. **[Issue] (Score: X/100)** - Description
3. **[Issue] (Score: X/100)** - Description

## Key Bottlenecks
- **Database Queries** – Slow queries and missing indexes
- **Transaction Volume** – Peak load patterns
- **Memory/CPU** – Resource utilization

## Recommended Fixes
### Immediate Actions (Critical)
1. **[Action]** - Specific performance fix
2. **[Action]** - Specific performance fix

## Implementation Roadmap
- **Week 1:** Emergency fixes
- **Week 2-3:** Index and query optimization
- **Ongoing:** PA dashboards monitoring"""

    result = ask_llm(prompt)
    score  = _extract_score(result)

    return {
        "agent":             "performance",
        "title":             "Performance Analysis",
        "risk_score":        score,
        "total_records":     total,
        "slow_transactions": len(slow_tx),
        "error_transactions":len(err_tx),
        "timestamp":         datetime.utcnow().isoformat(),
        "analysis":          result,
        "errors":            errors,
    }

def _safe_parse(raw):
    if isinstance(raw, dict): return raw
    try: return json.loads(raw)
    except: pass
    try: return ast.literal_eval(str(raw))
    except: return {}

def _field(p, key):
    v = p.get(key,"")
    if isinstance(v, dict): return v.get("value","") or v.get("display_value","")
    return v or ""

def _get_ms(p):
    try: return int(_field(p,"response_time") or 0)
    except: return 0

def _tx_summary(p):
    return {"url": _field(p,"url"), "ms": _get_ms(p), "type": _field(p,"type")}

def _detect_errors(txs):
    errors = []
    eid = 0
    slow = [p for p in txs if _get_ms(p) > 3000]
    if slow:
        eid += 1
        errors.append({
            "id": f"perf_{eid:03d}", "title": f"{len(slow)} Transactions Exceed 3s",
            "severity": "critical", "script_type": "Transaction Log", "script_name": "Multiple",
            "description": f"{len(slow)} transactions exceeded 3000ms response time. Users experiencing severe slowdowns.",
            "affected": "Transaction Performance",
            "original_code": "// No query limit set\nnew GlideRecord('table').query();",
            "fix_prompt": "Add setLimit() to GlideRecord queries. Enable query plan analysis. Add database indexes on frequently queried fields. Use GlideAggregate instead of GlideRecord for counts."
        })
    err_txs = [p for p in txs if "error" in str(p).lower()]
    if err_txs:
        eid += 1
        errors.append({
            "id": f"perf_{eid:03d}", "title": f"{len(err_txs)} Error Transactions Detected",
            "severity": "high", "script_type": "Transaction Log", "script_name": "Multiple",
            "description": f"{len(err_txs)} transactions logged errors. May indicate script failures or timeouts.",
            "affected": "Error Rate",
            "original_code": "// Missing try-catch in scripts",
            "fix_prompt": "Review error logs. Add try/catch in business rules and script includes. Enable transaction quota rules to prevent runaway scripts."
        })
    return errors

def _enrich_perf_errors(errors, rows):
    """
    Enrich performance errors with table + sys_id so the frontend shows
    'Deploy to ServiceNow' and 'Save to MySQL' buttons.
    Performance errors are aggregated (not per-record), so we attach the
    first available sys_id from the transaction log as a reference.
    """
    first_sid = ""
    for row in rows:
        if not row or not isinstance(row, dict):
            continue
        sid = _field(row, "sys_id") or row.get("sys_id", "")
        if isinstance(sid, dict):
            sid = sid.get("value") or sid.get("display_value") or ""
        sid = str(sid).strip()
        if sid and len(sid) >= 10:
            first_sid = sid
            break

    for err in errors:
        err.setdefault("table", "syslog_transaction")
        err.setdefault("script_field", "script")
        if not err.get("sys_id"):
            err["sys_id"] = first_sid  # best-effort reference record

    return errors


def _extract_score(text):
    m = re.search(r'(\d{1,3})/100', text)
    return int(m.group(1)) if m else None
