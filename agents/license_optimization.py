"""
AUTONOMOUS SERVICENOW LICENSE INTELLIGENCE AGENT
Full 9-Layer Architecture:
  1. Data Collector         — All 6 data domains
  2. Normalization Engine   — Role → License mapping
  3. Behavioral Engine      — Activity + contribution scoring
  4. Classification Engine  — 5-tier user categorization
  5. Financial Engine       — Cost model + department allocation
  6. Decision Engine        — Per-user recommendations + confidence
  7. AI Summary             — Executive narrative
  8. Output Layer           — Structured rich payload
  9. Automation Ready       — ServiceNow API action hooks
"""

from datetime import datetime, timedelta
from collections import defaultdict
from services.servicenow_client import fetch_table
from services.database import fetch_cached
from agents._fetch import fetch_with_fallback
from ollama_client import ask_llm
import re

# ============================================================
# LAYER 6: LICENSE COST MODEL
# ============================================================

LICENSE_COSTS = {
    "admin":      150,
    "itil":       100,
    "csm":        120,
    "hr":          80,
    "itsm":       100,
    "sn_hr_core":  80,
    "requester":   20,
    "integration": 10,
    "fulfiller":   60,
    "approver":    25,
}

PAID_ROLES = {"admin", "itil", "csm", "hr", "sn_hr_core", "itsm",
              "fulfiller", "approver", "catalog_admin", "problem_admin",
              "change_manager", "knowledge_manager"}

INACTIVITY_THRESHOLDS = {
    "warn":     30,
    "moderate": 60,
    "critical": 90,
}

# ============================================================
# LAYER 1: DATA COLLECTOR — All 6 data domains
# ============================================================

def collect_data():
    """Fetch all required data domains from ServiceNow."""
    return {
        # Domain 1: User Core Data
        "users":        fetch_table("sys_user",           limit=20000) or [],
        # Domain 2: Role & License Mapping
        "roles":        fetch_table("sys_user_has_role",  limit=50000) or [],
        "role_defs":    fetch_table("sys_user_role",      limit=2000)  or [],
        # Domain 3: Group Membership
        "groups":       fetch_table("sys_user_grmember",  limit=50000) or [],
        # Domain 4A: Login & Transaction Activity
        "transactions": fetch_table("syslog_transaction", limit=100000) or [],
        # Domain 4B: Work Contribution
        "incidents":    fetch_table("incident",           limit=20000) or [],
        "tasks":        fetch_table("task",               limit=20000) or [],
        "changes":      fetch_table("change_request",     limit=20000) or [],
        "problems":     fetch_table("problem",            limit=10000) or [],
        "sc_tasks":     fetch_table("sc_task",            limit=10000) or [],
        # Domain 5: Admin Activity
        "sys_audit":    fetch_table("sys_audit",          limit=20000) or [],
        "sys_updates":  fetch_table("sys_update_xml",     limit=10000) or [],
    }


# ============================================================
# LAYER 2: NORMALIZATION ENGINE
# ============================================================

def normalize_ref(val):
    if isinstance(val, dict):
        return val.get("value") or val.get("display_value") or ""
    return val or ""

def build_role_map(roles_raw):
    """Map user_id → list of role names."""
    role_map = defaultdict(set)
    role_granted_on = defaultdict(dict)
    for r in roles_raw:
        if not isinstance(r, dict):
            continue
        user = normalize_ref(r.get("user"))
        role = normalize_ref(r.get("role"))
        granted_on = r.get("granted_on", "")
        inherited = r.get("inherited", False)
        if user and role:
            role_map[user].add(role)
            role_granted_on[user][role] = {
                "granted_on": granted_on,
                "inherited": inherited,
                "granted_by": normalize_ref(r.get("granted_by")),
            }
    return dict(role_map), role_granted_on

def build_group_map(groups_raw):
    """Map user_id → list of group names."""
    group_map = defaultdict(list)
    for g in groups_raw:
        if not isinstance(g, dict):
            continue
        user = normalize_ref(g.get("user"))
        group = normalize_ref(g.get("group"))
        if user and group:
            group_map[user].append(group)
    return dict(group_map)

def detect_license_type(roles):
    """Map role set → primary license type."""
    roles_lower = " ".join(roles).lower()
    if "admin" in roles_lower:
        return "admin"
    if "itil" in roles_lower or "itsm" in roles_lower:
        return "itil"
    if "csm" in roles_lower:
        return "csm"
    if "sn_hr_core" in roles_lower or ("hr" in roles_lower and "hr_admin" not in roles_lower):
        return "hr"
    if "fulfiller" in roles_lower:
        return "fulfiller"
    if "approver" in roles_lower:
        return "approver"
    if "integration" in roles_lower:
        return "integration"
    return "requester"

def detect_paid_roles(roles):
    """Return list of paid roles held by this user."""
    return [r for r in roles if any(p in r.lower() for p in PAID_ROLES)]

def days_since(date_str):
    if not date_str:
        return 999
    try:
        raw = str(date_str).strip().split(".")[0].replace("T", " ")
        # Handle date-only (YYYY-MM-DD) — ServiceNow last_login stores date without time
        if len(raw) >= 19:
            dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
        elif len(raw) >= 10:
            dt = datetime.strptime(raw[:10], "%Y-%m-%d")
        else:
            return 999
        return max(0, (datetime.utcnow() - dt).days)
    except Exception:
        return 999


# ============================================================
# LAYER 3: BEHAVIORAL INTELLIGENCE ENGINE
# ============================================================

def build_activity_map(data):
    """
    Build per-user behavioral profile:
      work_score   — ticket/task contribution
      tx_count     — transaction volume (logins/actions)
      admin_actions — system modification count
      modules      — set of modules accessed
    """
    activity = defaultdict(lambda: {
        "work_score": 0,
        "tx_count": 0,
        "admin_actions": 0,
        "modules": set(),
        "last_tx": None,
    })

    # Work contribution — weight by table importance
    WORK_WEIGHTS = {
        "incidents": 2, "changes": 3, "problems": 3,
        "tasks": 1, "sc_tasks": 1,
    }
    for table, weight in WORK_WEIGHTS.items():
        for record in data.get(table, []):
            if not isinstance(record, dict):
                continue
            for field in ["assigned_to", "opened_by", "closed_by", "sys_updated_by"]:
                uid = normalize_ref(record.get(field))
                if uid:
                    activity[uid]["work_score"] += weight
                    break  # count once per record

    # Transaction activity
    for tx in data.get("transactions", []):
        if not isinstance(tx, dict):
            continue
        uid = normalize_ref(tx.get("sys_created_by")) or tx.get("user", "")
        if not uid:
            continue
        activity[uid]["tx_count"] += 1
        module = tx.get("transaction_name") or tx.get("url", "")
        if module:
            activity[uid]["modules"].add(str(module)[:50])
        created = tx.get("sys_created_on") or tx.get("created_on", "")
        if created and (activity[uid]["last_tx"] is None or created > activity[uid]["last_tx"]):
            activity[uid]["last_tx"] = created

    # Admin activity (system modifications)
    for audit in data.get("sys_audit", []):
        if not isinstance(audit, dict):
            continue
        uid = normalize_ref(audit.get("user"))
        if uid:
            activity[uid]["admin_actions"] += 1

    for upd in data.get("sys_updates", []):
        if not isinstance(upd, dict):
            continue
        uid = normalize_ref(upd.get("sys_created_by"))
        if uid:
            activity[uid]["admin_actions"] += 1

    return dict(activity)

def compute_scores(user_data, activity, license_type, days_inactive):
    """
    Compute two scores per user:
      efficiency_score  (0–100): how well the license is being used
      privilege_risk    (0–100): how risky the privilege level is
    """
    work   = activity.get("work_score", 0)
    tx     = activity.get("tx_count", 0)
    admin  = activity.get("admin_actions", 0)
    cost   = LICENSE_COSTS.get(license_type, 0)

    # --- Efficiency Score ---
    if days_inactive > 90 or (not user_data.get("active")):
        efficiency = 0
    else:
        base = min((work * 4) + (tx * 0.5), 100)
        recency_penalty = min(days_inactive * 0.8, 50)
        efficiency = max(0, min(100, int(base - recency_penalty)))

    # --- Privilege Risk Score ---
    risk = 0
    if license_type == "admin":
        risk += 40
        if admin < 5:
            risk += 30   # admin but not administering
        if days_inactive > 30:
            risk += 20
    elif license_type in ("itil", "itsm"):
        risk += 20
        if work == 0:
            risk += 40
        if days_inactive > 60:
            risk += 20
    elif cost > 20:
        risk += 10
        if work == 0 and tx == 0:
            risk += 50
        if days_inactive > 90:
            risk += 30
    risk = min(100, risk)

    return efficiency, risk


# ============================================================
# LAYER 4: CLASSIFICATION ENGINE
# ============================================================

def classify_user(active, days_inactive, efficiency, privilege_risk,
                  license_type, work_score, tx_count, user_name):
    """
    5-tier classification:
      active         — legitimate usage
      underutilized  — some usage but not enough for license tier
      wasted         — paid license, zero contribution
      inactive       — no login / deactivated
      overlicensed   — high privilege, low/no admin activity
    """
    cost = LICENSE_COSTS.get(license_type, 0)
    is_integration = "integration" in (user_name or "").lower()

    if is_integration:
        return "integration"
    if not active or days_inactive > 90:
        return "inactive"
    if license_type == "admin" and privilege_risk >= 60:
        return "overlicensed"
    if cost > 20 and work_score == 0 and tx_count == 0:
        return "wasted"
    if cost > 20 and efficiency < 25:
        return "underutilized"
    return "active"


# ============================================================
# LAYER 5: FINANCIAL ENGINE
# ============================================================

def calculate_savings(categories, department_breakdown):
    """Compute financial impact per category and department."""
    current = sum(u["license_cost"] for cat in categories.values() for u in cat)
    recoverable_cats = ["inactive", "wasted", "overlicensed"]
    potential = sum(
        u["license_cost"]
        for cat in recoverable_cats
        for u in categories.get(cat, [])
    )
    underutil_partial = sum(
        u["license_cost"] * 0.5
        for u in categories.get("underutilized", [])
    )

    dept_sorted = sorted(
        [{"dept": k, **v} for k, v in department_breakdown.items()],
        key=lambda x: x["cost"], reverse=True
    )

    return {
        "current_monthly_cost":       round(current, 2),
        "monthly_savings_potential":  round(potential + underutil_partial, 2),
        "annual_savings_potential":   round((potential + underutil_partial) * 12, 2),
        "recoverable_from_inactive":  round(sum(u["license_cost"] for u in categories.get("inactive",    [])), 2),
        "recoverable_from_wasted":    round(sum(u["license_cost"] for u in categories.get("wasted",     [])), 2),
        "recoverable_from_overlic":   round(sum(u["license_cost"] for u in categories.get("overlicensed",[])), 2),
        "recoverable_from_underutil": round(underutil_partial, 2),
        "top_departments_by_waste":   dept_sorted[:10],
    }


# ============================================================
# LAYER 6: DECISION ENGINE
# ============================================================

def build_decision(user, category, efficiency, privilege_risk, license_type):
    """Generate per-user recommendation with confidence."""
    cost = user["license_cost"]
    name = user.get("name") or user.get("user_name", "Unknown")

    if category == "inactive":
        action = "deactivate"
        reason = f"No login for {user['days_inactive']} days. Immediate cost recovery: ${cost}/mo."
        confidence = min(99, 60 + min(user['days_inactive'] // 3, 39))

    elif category == "wasted":
        action = "remove_paid_roles"
        reason = f"Paid {license_type.upper()} license with zero work activity. Downgrade to Requester."
        confidence = 92

    elif category == "overlicensed":
        action = "downgrade_license"
        reason = f"Admin role with only {user.get('admin_actions', 0)} system modifications. Reduce privilege."
        confidence = 75

    elif category == "underutilized":
        action = "review_and_downgrade"
        reason = f"Efficiency score {efficiency}/100. Consider downgrading from {license_type.upper()}."
        confidence = 60

    else:
        action = "no_action"
        reason = "User is active and license is justified."
        confidence = 95

    # Include all fields the UI needs for the Deactivate button + activity display
    activity = user.get("_activity", {})
    return {
        "user_name":     name,
        "email":         user.get("email", ""),
        "user_sys_id":   user.get("sys_id", ""),
        "action":        action,
        "reason":        reason,
        "confidence_pct": confidence,
        "monthly_saving": cost if action != "no_action" else 0,
        "current_license": license_type,
        # Activity log fields for UI display
        "days_inactive": user.get("days_inactive", 0),
        "tx_count":      activity.get("tx_count", 0),
        "last_login":    activity.get("last_login", None),
        "work_count":    activity.get("work_items", 0),
    }


# ============================================================
# MAIN ANALYSIS ENGINE
# ============================================================

def analyze(data):
    role_map, role_granted_on = build_role_map(data["roles"])
    group_map = build_group_map(data["groups"])
    activity_map = build_activity_map(data)

    categories      = defaultdict(list)
    dept_breakdown  = defaultdict(lambda: {"count": 0, "cost": 0, "waste": 0})
    role_usage      = defaultdict(lambda: {"total": 0, "active": 0, "cost": 0})
    decisions       = []
    duplicate_map   = defaultdict(list)
    behavioral_profiles = []

    for user in data["users"]:
        if not isinstance(user, dict):
            continue

        uid       = user.get("sys_id", "")
        email     = user.get("email", "")
        user_name = user.get("user_name", "")
        active    = user.get("active") in [True, "true", "True", 1]
        last_login = user.get("last_login") or user.get("last_login_time", "")
        dept      = normalize_ref(user.get("department")) or "Unknown"
        title     = user.get("title", "")

        roles     = list(role_map.get(uid, set()))
        activity  = activity_map.get(uid, {"work_score": 0, "tx_count": 0,
                                            "admin_actions": 0, "modules": set()})

        lic_type  = detect_license_type(roles)
        cost      = LICENSE_COSTS.get(lic_type, 0)
        paid      = detect_paid_roles(roles)
        days_in   = days_since(last_login)

        efficiency, priv_risk = compute_scores(
            {"active": active}, activity, lic_type, days_in
        )

        category = classify_user(
            active, days_in, efficiency, priv_risk,
            lic_type, activity["work_score"], activity["tx_count"], user_name
        )

        profile = {
            "sys_id":          uid,
            "name":            user.get("name", ""),
            "user_name":       user_name,
            "email":           email,
            "title":           title,
            "department":      dept,
            "active":          active,
            "license_type":    lic_type,
            "license_cost":    cost,
            "paid_roles":      paid,
            "all_roles":       roles,
            "days_inactive":   days_in,
            "last_login":      last_login or activity.get("last_tx"),
            "work_score":      activity["work_score"],
            "tx_count":        activity["tx_count"],
            "admin_actions":   activity["admin_actions"],
            "modules_used":    len(activity.get("modules", set())),
            "efficiency_score": efficiency,
            "privilege_risk":  priv_risk,
            "category":        category,
            "groups":          group_map.get(uid, []),
            "locked_out":      user.get("locked_out", False),
            # Keep reference so build_decision can read activity details
            "_activity":       activity,
        }

        categories[category].append(profile)
        behavioral_profiles.append(profile)

        # Department allocation
        dept_breakdown[dept]["count"] += 1
        dept_breakdown[dept]["cost"]  += cost
        if category in ("inactive", "wasted", "overlicensed"):
            dept_breakdown[dept]["waste"] += cost

        # Role usage stats
        for r in roles:
            role_usage[r]["total"] += 1
            role_usage[r]["cost"]  += cost
            if activity["work_score"] > 0:
                role_usage[r]["active"] += 1

        # Duplicate detection
        if email:
            duplicate_map[email.lower()].append(uid)

        # Decision
        dec = build_decision(profile, category, efficiency, priv_risk, lic_type)
        if dec["action"] != "no_action":
            decisions.append(dec)

    duplicates = [
        {"email": e, "account_count": len(ids)}
        for e, ids in duplicate_map.items() if len(ids) > 1
    ]

    # Top risky users (highest privilege_risk, not active)
    top_risky = sorted(
        [p for p in behavioral_profiles if p["privilege_risk"] >= 50],
        key=lambda x: x["privilege_risk"], reverse=True
    )[:20]

    # Top decisions by saving
    top_decisions = sorted(decisions, key=lambda x: x["monthly_saving"], reverse=True)[:50]

    return {
        "total_users":         len(data["users"]),
        "categories":          dict(categories),
        "department_breakdown": dict(dept_breakdown),
        "role_usage":          dict(role_usage),
        "duplicate_users":     duplicates,
        "top_risky_users":     top_risky,
        "decisions":           top_decisions,
        "all_decisions":       decisions,
    }


# ============================================================
# LAYER 7: AI SUMMARY
# ============================================================

def generate_ai_summary(analysis, savings):
    try:
        cats = analysis["categories"]
        prompt = f"""You are a ServiceNow License Optimization Expert writing an executive briefing.

## Instance Data
- Total Users: {analysis['total_users']}
- Active: {len(cats.get('active', []))}
- Underutilized: {len(cats.get('underutilized', []))}
- Wasted (paid license, no work): {len(cats.get('wasted', []))}
- Inactive (90+ days): {len(cats.get('inactive', []))}
- Over-licensed (admin with no admin work): {len(cats.get('overlicensed', []))}
- Integration Accounts: {len(cats.get('integration', []))}
- Duplicate Email Accounts: {len(analysis.get('duplicate_users', []))}

## Financial Impact
- Current Monthly Cost: ${savings['current_monthly_cost']:,.2f}
- Monthly Savings Potential: ${savings['monthly_savings_potential']:,.2f}
- Annual Savings Potential: ${savings['annual_savings_potential']:,.2f}
- From Inactive Users: ${savings['recoverable_from_inactive']:,.2f}/mo
- From Wasted Licenses: ${savings['recoverable_from_wasted']:,.2f}/mo
- From Over-licensed: ${savings['recoverable_from_overlic']:,.2f}/mo

Write a structured executive summary with these sections:

## Overview
2-3 sentences on the overall license health.

## Key Findings
- Finding 1 with specific numbers
- Finding 2 with specific numbers
- Finding 3 with specific numbers

## Financial Opportunity
Explain the savings potential in business terms.

## Recommended Immediate Actions
1. **Action** - Specific step with expected impact
2. **Action** - Specific step with expected impact
3. **Action** - Specific step with expected impact

## Risk Highlights
Key risks if no action is taken."""
        return ask_llm(prompt)
    except Exception as e:
        return f"AI summary unavailable: {str(e)}"


# ============================================================
# LAYER 8: OUTPUT BUILDER
# ============================================================

def build_summary(analysis, savings):
    cats = analysis["categories"]
    return {
        "total_users":             analysis["total_users"],
        "active_users":            len(cats.get("active",        [])),
        "underutilized_users":     len(cats.get("underutilized", [])),
        "wasted_licenses":         len(cats.get("wasted",        [])),
        "inactive_users":          len(cats.get("inactive",      [])),
        "overlicensed_users":      len(cats.get("overlicensed",  [])),
        "integration_accounts":    len(cats.get("integration",   [])),
        "duplicate_users":         len(analysis.get("duplicate_users", [])),
        "current_monthly_cost":    savings["current_monthly_cost"],
        "monthly_savings_potential": savings["monthly_savings_potential"],
        "annual_savings_potential":  savings["annual_savings_potential"],
        "decisions_pending":       len(analysis.get("all_decisions", [])),
    }


# ============================================================
# LAST LOGIN AUDIT  (reads from MySQL cached sys_user table)
# ============================================================

ONE_YEAR_AGO = 365  # days

def build_last_login_audit():
    """
    Read sys_user from MySQL cache and classify every user by last_login:
      - never_logged_in : last_login is empty / null / never set
      - stale           : last_login exists but > 1 year ago
      - active          : last_login within the last 365 days

    Returns a dict with counts + per-user lists for the UI.
    """
    rows = fetch_with_fallback("sys_user", limit=5000) or []

    never_logged_in = []
    stale_users     = []
    active_users    = []

    for row in rows:
        if not row or not isinstance(row, dict):
            continue

        # Extract raw field values (SN may store as dict or plain string)
        def _get(key):
            v = row.get(key, "")
            if isinstance(v, dict):
                return v.get("value") or v.get("display_value") or ""
            return str(v).strip() if v else ""

        sys_id     = _get("sys_id")
        name       = _get("name") or _get("user_name") or "Unknown"
        user_name  = _get("user_name")
        email      = _get("email")
        active_raw = _get("active")
        is_active  = active_raw.lower() in ("true", "1", "yes") if active_raw else False

        last_login = _get("last_login") or _get("last_login_time") or ""

        # Skip pure service / integration accounts (no email, name contains "integration")
        if "integration" in user_name.lower() and not email:
            continue

        entry = {
            "sys_id":     sys_id,
            "name":       name,
            "user_name":  user_name,
            "email":      email,
            "active":     is_active,
            "last_login": last_login or None,
        }

        if not last_login or last_login.lower() in ("none", "null", ""):
            entry["last_login_label"] = "Never"
            entry["days_since_login"] = None
            never_logged_in.append(entry)
        else:
            d = days_since(last_login)
            entry["days_since_login"] = d
            entry["last_login_label"] = last_login[:10]   # YYYY-MM-DD
            if d >= ONE_YEAR_AGO:
                stale_users.append(entry)
            else:
                active_users.append(entry)

    # Sort stale by longest inactive first
    stale_users.sort(key=lambda x: (x["days_since_login"] or 0), reverse=True)
    # Sort never by name
    never_logged_in.sort(key=lambda x: x["name"].lower())
    active_users.sort(key=lambda x: (x["days_since_login"] or 0), reverse=True)

    return {
        "total":             len(rows),
        "active_count":      len(active_users),
        "stale_count":       len(stale_users),
        "never_count":       len(never_logged_in),
        "active_users":      active_users[:200],
        "stale_users":       stale_users[:200],
        "never_logged_in":   never_logged_in[:200],
    }


# ============================================================
# MAIN ENTRY
# ============================================================

def run():
    data          = collect_data()
    analysis      = analyze(data)
    savings       = calculate_savings(analysis["categories"], analysis["department_breakdown"])
    ai_summary    = generate_ai_summary(analysis, savings)
    last_login_audit = build_last_login_audit()

    cats = analysis["categories"]

    return {
        "agent":           "License Intelligence Agent",
        "version":         "2.0",
        "status":          "success",
        "timestamp":       datetime.utcnow().isoformat(),
        "risk_score":      _compute_overall_risk(analysis, savings),

        # Layer 8: Structured output
        "summary":         build_summary(analysis, savings),
        "financials":      savings,

        # Behavioral profiles per category
        "categories": {
            "active":        cats.get("active",        [])[:100],
            "underutilized": cats.get("underutilized", [])[:100],
            "wasted":        cats.get("wasted",        [])[:100],
            "inactive":      cats.get("inactive",      [])[:100],
            "overlicensed":  cats.get("overlicensed",  [])[:50],
            "integration":   cats.get("integration",   [])[:50],
        },

        # Intelligence outputs
        "top_risky_users":   analysis["top_risky_users"],
        "decisions":         analysis["decisions"],
        "duplicate_users":   analysis["duplicate_users"],
        "department_breakdown": dict(list(analysis["department_breakdown"].items())[:20]),
        "role_usage":        dict(list(analysis["role_usage"].items())[:30]),

        # Last Login Audit — sys_user.last_login based classification
        "last_login_audit":  last_login_audit,

        # Layer 7: AI narrative
        "ai_insights":     ai_summary,

        # Layer 9: Automation hooks
        "automation": {
            "ready":             True,
            "actions_available": ["deactivate_user", "remove_role", "downgrade_license"],
            "pending_approvals": len([d for d in analysis.get("all_decisions", [])
                                      if d["confidence_pct"] >= 80]),
            "auto_eligible":     len([d for d in analysis.get("all_decisions", [])
                                      if d["confidence_pct"] >= 95]),
        }
    }


def _compute_overall_risk(analysis, savings):
    """Derive a 0-100 risk score for the license landscape."""
    total = max(analysis["total_users"], 1)
    cats  = analysis["categories"]
    waste_ratio    = len(cats.get("wasted",       [])) / total
    inactive_ratio = len(cats.get("inactive",     [])) / total
    overlic_ratio  = len(cats.get("overlicensed", [])) / total
    dup_penalty    = min(len(analysis.get("duplicate_users", [])) * 2, 15)
    score = int((waste_ratio * 40) + (inactive_ratio * 35) +
                (overlic_ratio * 25) + dup_penalty)
    return min(score, 100)
