from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from pydantic import BaseModel

import threading
import os
import uuid
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import re as _re
from datetime import datetime as _dt

from orchestrator import run_all
from agents import architecture, scripts, performance, security, integration, data_health, upgrade, license_optimization
from services.sync_service import start_sync_loop, get_sync_status
from ollama_client import ask_llm

# In-memory job store for async PDF generation
_pdf_jobs: dict = {}  # job_id -> {"status": "pending"|"done"|"error", "path": ..., "error": ...}


# =====================================================
# Lifespan
# =====================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.servicenow_client import SN_INSTANCE, SN_USER, SN_PASS
    threading.Thread(
        target=start_sync_loop,
        args=(SN_INSTANCE, SN_USER, SN_PASS),
        daemon=True
    ).start()
    print(f"✓ Delta Sync started → {SN_INSTANCE} (every 10s)")
    yield
    print("✓ Application shutdown")


app = FastAPI(
    title="ServiceNow AI Copilot",
    version="2.0",
    description="AI-powered ServiceNow instance analysis and optimization",
    lifespan=lifespan
)

# =====================================================
# CORS
# =====================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# Static & Templates
# =====================================================

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# =====================================================
# Models
# =====================================================

class ChatMessage(BaseModel):
    message: str
    history: list = []

class FixItRequest(BaseModel):
    error_id:      str
    title:         str
    description:   str
    affected:      str
    original_code: str = ""
    fix_prompt:    str
    agent:         str = ""
    script_type:   str = ""
    script_name:   str = ""

# =====================================================
# Routes
# =====================================================

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# =====================================================
# Agent Routes
# =====================================================

@app.get("/agent/architecture")
def architecture_agent():
    try:
        return architecture.run()
    except Exception as e:
        return {"error": str(e), "agent": "architecture"}


@app.get("/agent/scripts")
def scripts_agent():
    try:
        return scripts.run()
    except Exception as e:
        return {"error": str(e), "agent": "scripts"}


@app.get("/agent/performance")
def performance_agent():
    try:
        return performance.run()
    except Exception as e:
        return {"error": str(e), "agent": "performance"}


@app.get("/agent/security")
def security_agent():
    try:
        return security.run()
    except Exception as e:
        return {"error": str(e), "agent": "security"}


@app.get("/agent/integration")
def integration_agent():
    try:
        return integration.run()
    except Exception as e:
        return {"error": str(e), "agent": "integration"}


@app.get("/agent/data-health")
def data_health_agent():
    try:
        return data_health.run()
    except Exception as e:
        return {"error": str(e), "agent": "data_health"}


@app.get("/agent/upgrade")
def upgrade_agent():
    try:
        return upgrade.run()
    except Exception as e:
        return {"error": str(e), "agent": "upgrade"}


@app.get("/agent/license-optimization")
def license_optimization_agent():
    try:
        return license_optimization.run()
    except Exception as e:
        return {"error": str(e), "agent": "license_optimization"}


@app.get("/run-all")
def run_all_agents():
    try:
        return run_all()
    except Exception as e:
        return {"error": str(e)}

# =====================================================
# Chat
# =====================================================

@app.post("/chat")
def chat_endpoint(chat_message: ChatMessage):

    try:
        user_message = chat_message.message
        history = chat_message.history

        context = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in history[-5:]
        ])

        prompt = f"""
You are a ServiceNow AI Copilot assistant.

Context:
{context}

User: {user_message}

Provide a concise helpful answer.
"""

        response = ask_llm(prompt)

        return {"response": response}

    except Exception as e:
        return {"error": str(e)}

# =====================================================
# Health
# =====================================================


# =====================================================
# Fix It — Plain JSON AI auto-fix endpoint
# (SSE removed — was causing "Unexpected token d" JSON parse errors)
# =====================================================

@app.post("/fix-it")
def fix_it(req: FixItRequest):
    """
    Calls the LLM and returns a plain JSON response.
    The UI shows a skeleton while waiting, then renders the result.
    """
    import json as _json, re as _re

    agent_context = {
        "architecture": "ServiceNow table/object definitions and schema",
        "scripts":      "ServiceNow business rules, client scripts, script includes, UI actions (GlideRecord JS)",
        "security":     "ServiceNow ACL rules and access control configurations",
        "performance":  "ServiceNow transaction optimisation and GlideRecord queries",
        "integration":  "ServiceNow REST messages and Integration Hub configs",
        "data_health":  "ServiceNow sys_dictionary field definitions",
        "upgrade":      "ServiceNow application scopes and upgrade-readiness configs",
    }.get(req.agent, "ServiceNow platform configuration")

    script_type_hint = f"\nScript Type: {req.script_type}" if req.script_type else ""
    script_name_hint = f"\nScript Name: {req.script_name}" if req.script_name else ""

    prompt = f"""You are an expert ServiceNow developer. Fix the following issue.

Context: {agent_context}{script_type_hint}{script_name_hint}

Error:
- Title: {req.title}
- Affected: {req.affected}
- Problem: {req.description}
- Fix Instructions: {req.fix_prompt}

Original code:
```javascript
{req.original_code or "// (no code snippet — apply fix generically)"}
```

You MUST respond with ONLY a valid JSON object. No markdown, no explanation outside JSON, no code fences.
The JSON must have exactly these keys:
{{
  "fixed_code": "// ORIGINAL (commented by AI Fix):\n// <original line>\n\n// NEW FIX by ServiceNow AI Copilot:\n<new code here>",
  "explanation": "step-by-step explanation of changes",
  "changes": ["change 1", "change 2"],
  "best_practice": "which ServiceNow best practice was applied",
  "estimated_impact": "expected improvement after applying this fix"
}}"""

    raw = ""
    try:
        raw = ask_llm(prompt)

        # Strip markdown fences if model added them
        clean = _re.sub(r"```json\s*|\s*```", "", raw.strip()).strip()

        # Find first complete JSON object
        m = _re.search(r"\{[\s\S]+\}", clean)
        if not m:
            raise ValueError("LLM did not return a JSON object")

        result = _json.loads(m.group(0))

        return {
            "status":    "success",
            "error_id":  req.error_id,
            "agent":     req.agent,
            "affected":  req.affected,
            **result
        }

    except Exception as e:
        import traceback
        return {
            "status":  "error",
            "error_id": req.error_id,
            "message": str(e),
            "raw_response": raw[:500] if raw else "",
            "trace":   traceback.format_exc()[-800:]
        }


# =====================================================
# Fix-It Push — Save fixed code to ServiceNow + Postgres
# =====================================================

class PushFixRequest(BaseModel):
    sys_id:      str
    table:       str
    field:       str = "script"
    fixed_code:  str
    agent:       str = ""
    script_name: str = ""

@app.post("/fix-it/push")
def push_fix_to_servicenow(req: PushFixRequest):
    """
    1. Sanitize sys_id (handle Postgres-stored JSON dict values).
    2. PATCH the FULL fixed script to ServiceNow via REST API.
    3. Update Postgres immediately so agents read the new version.
    4. Advance sys_updated_on watermark so delta sync never overwrites the fix.
    """
    import requests as _req
    import json   as _json
    from datetime import datetime as _now
    from services.servicenow_client import SN_INSTANCE, SN_USER, SN_PASS
    from services.database import update_record_field

    # ── Sanitize sys_id — may be stored as JSON dict {"value":"abc..."} ──
    sys_id = (req.sys_id or "").strip()
    if sys_id.startswith("{"):
        try:
            sid_obj = _json.loads(sys_id)
            sys_id  = sid_obj.get("value") or sid_obj.get("display_value") or sys_id
        except Exception:
            pass
    sys_id = sys_id.strip()

    if not sys_id or len(sys_id) < 10:
        return {"status": "error", "message": f"Invalid sys_id '{sys_id}' — must be a 32-char SN sys_id"}
    if not req.table:
        return {"status": "error", "message": "table is required"}
    if not req.fixed_code.strip():
        return {"status": "error", "message": "fixed_code is empty"}

    sn_result     = {}
    sn_ok         = False
    pg_ok         = False
    sn_updated_on = None

    # ── 1. PATCH to ServiceNow ───────────────────────────────────────────────
    try:
        url  = f"{SN_INSTANCE}/api/now/table/{req.table}/{sys_id}"
        resp = _req.patch(
            url,
            auth=(SN_USER, SN_PASS),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={req.field: req.fixed_code},
            timeout=30,
        )
        sn_ok = resp.status_code in (200, 201)
        if sn_ok:
            result_data = resp.json().get("result", {})
            sn_result   = {
                "sys_id": result_data.get("sys_id"),
                "name":   result_data.get("name"),
            }
            # Capture sys_updated_on from SN response
            raw_ts = result_data.get("sys_updated_on")
            if isinstance(raw_ts, dict):
                raw_ts = raw_ts.get("value") or raw_ts.get("display_value")
            sn_updated_on = str(raw_ts)[:19] if raw_ts else None
        else:
            sn_result = {"http": resp.status_code, "body": resp.text[:500]}
            print(f"[push] ServiceNow PATCH failed {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        sn_result = {"error": str(e)}
        print(f"[push] ServiceNow PATCH exception: {e}")

    # ── 2. Update Postgres cache ────────────────────────────────────────────
    # Always update Postgres regardless of SN result so agents see the fix locally
    try:
        pg_ok = update_record_field(req.table, sys_id, req.field, req.fixed_code)
        # Advance watermark — update_record_field handles watermark when field == sys_updated_on
        ts_to_write = sn_updated_on or _now.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if pg_ok:
            update_record_field(req.table, sys_id, "sys_updated_on", ts_to_write)
    except Exception as e:
        pg_ok = False
        print(f"[push] Postgres update exception: {e}")

    overall = "success" if (sn_ok and pg_ok) else ("partial" if (sn_ok or pg_ok) else "error")
    name_label = req.script_name or sys_id

    return {
        "status":      overall,
        "sys_id":      sys_id,
        "table":       req.table,
        "field":       req.field,
        "script_name": req.script_name,
        "servicenow":  {"pushed": sn_ok, "detail": sn_result},
        "postgres":    {"updated": pg_ok},
        "message": (
            f"✅ Fix saved to ServiceNow + Postgres — {name_label}"
            if overall == "success"
            else f"⚠️ ServiceNow: {'✅' if sn_ok else '❌'}  Postgres: {'✅' if pg_ok else '❌'} — {name_label}"
        ),
    }


# =====================================================
# License — Deactivate User in ServiceNow
# =====================================================

class DeactivateUserRequest(BaseModel):
    user_sys_id:  str
    user_name:    str
    email:        str
    days_inactive: int = 0
    reason:       str  = ""

@app.post("/license/deactivate-user")
def deactivate_user(req: DeactivateUserRequest):
    """
    Sets sys_user.active = false in ServiceNow via REST API.
    Called when analyst clicks the Deactivate button in License UI.
    """
    import requests as _req
    from services.servicenow_client import SN_INSTANCE, SN_USER, SN_PASS

    if not req.user_sys_id or len(req.user_sys_id) < 10:
        return {"status": "error", "message": "Invalid user sys_id"}

    try:
        url  = f"{SN_INSTANCE}/api/now/table/sys_user/{req.user_sys_id}"
        resp = _req.patch(
            url,
            auth=(SN_USER, SN_PASS),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"active": "false"},
            timeout=15,
        )

        if resp.status_code in (200, 201):
            result = resp.json().get("result", {})
            return {
                "status":      "success",
                "user_sys_id": req.user_sys_id,
                "user_name":   req.user_name,
                "email":       req.email,
                "message":     f"User {req.user_name} deactivated successfully in ServiceNow",
                "sn_active":   result.get("active", "false"),
            }
        else:
            return {
                "status":  "error",
                "message": f"ServiceNow returned HTTP {resp.status_code}: {resp.text[:300]}",
            }

    except Exception as e:
        import traceback
        return {
            "status":  "error",
            "message": str(e),
            "trace":   traceback.format_exc()[-600:],
        }

@app.get("/health")
def health_check():
    return {"status": "running", "version": "2.0"}


@app.get("/sync/status")
def sync_status_endpoint():
    """Live sync status — called by the UI every 5s to show sync progress."""
    return get_sync_status()

# =====================================================
# PDF Report
# =====================================================

# =====================================================
# PDF Helpers
# =====================================================

def _strip_md(text):
    """Strip markdown syntax for plain PDF text."""
    if not text:
        return ""
    text = _re.sub(r"#{1,6}\s*", "", text)
    text = _re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = _re.sub(r"\*([^*]+)\*", r"\1", text)
    text = _re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()

def _build_pdf_styles():
    base = getSampleStyleSheet()
    
    BRAND   = colors.HexColor("#0d6efd")
    DARK    = colors.HexColor("#1a1d23")
    GREY    = colors.HexColor("#6c757d")
    LIGHT   = colors.HexColor("#f0f4ff")
    SUCCESS = colors.HexColor("#198754")
    DANGER  = colors.HexColor("#dc3545")
    WARNING = colors.HexColor("#ffc107")

    styles = {
        "cover_title": ParagraphStyle("cover_title",
            fontName="Helvetica-Bold", fontSize=28, textColor=colors.white,
            alignment=TA_CENTER, spaceAfter=6),
        "cover_sub": ParagraphStyle("cover_sub",
            fontName="Helvetica", fontSize=13, textColor=colors.HexColor("#c8d6f7"),
            alignment=TA_CENTER, spaceAfter=4),
        "cover_meta": ParagraphStyle("cover_meta",
            fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#adb5bd"),
            alignment=TA_CENTER),
        "section_heading": ParagraphStyle("section_heading",
            fontName="Helvetica-Bold", fontSize=16, textColor=BRAND,
            spaceBefore=18, spaceAfter=6),
        "agent_title": ParagraphStyle("agent_title",
            fontName="Helvetica-Bold", fontSize=13, textColor=DARK,
            spaceBefore=12, spaceAfter=4),
        "h2": ParagraphStyle("h2",
            fontName="Helvetica-Bold", fontSize=11, textColor=DARK,
            spaceBefore=10, spaceAfter=3),
        "h3": ParagraphStyle("h3",
            fontName="Helvetica-Bold", fontSize=10, textColor=GREY,
            spaceBefore=6, spaceAfter=2),
        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=9.5, textColor=DARK,
            leading=15, spaceAfter=4),
        "bullet": ParagraphStyle("bullet",
            fontName="Helvetica", fontSize=9.5, textColor=DARK,
            leading=14, leftIndent=14, spaceAfter=2,
            bulletIndent=4, bulletText="•"),
        "numbered": ParagraphStyle("numbered",
            fontName="Helvetica", fontSize=9.5, textColor=DARK,
            leading=14, leftIndent=20, spaceAfter=3),
        "bold_inline": ParagraphStyle("bold_inline",
            fontName="Helvetica-Bold", fontSize=9.5, textColor=DARK,
            leading=14, leftIndent=20, spaceAfter=2),
        "footer": ParagraphStyle("footer",
            fontName="Helvetica", fontSize=8, textColor=GREY,
            alignment=TA_CENTER),
        "toc_agent": ParagraphStyle("toc_agent",
            fontName="Helvetica", fontSize=10, textColor=DARK,
            leading=16, leftIndent=12),
        "risk_high": ParagraphStyle("risk_high",
            fontName="Helvetica-Bold", fontSize=10, textColor=DANGER),
        "risk_med": ParagraphStyle("risk_med",
            fontName="Helvetica-Bold", fontSize=10, textColor=WARNING),
        "risk_low": ParagraphStyle("risk_low",
            fontName="Helvetica-Bold", fontSize=10, textColor=SUCCESS),
        "BRAND": BRAND, "DARK": DARK, "GREY": GREY,
        "LIGHT": LIGHT, "SUCCESS": SUCCESS, "DANGER": DANGER, "WARNING": WARNING,
    }
    return styles


def _risk_color(score, styles):
    if score is None:
        return styles["GREY"]
    if score >= 70:
        return styles["DANGER"]
    if score >= 40:
        return styles["WARNING"]
    return styles["SUCCESS"]


def _risk_label(score):
    if score is None:
        return "N/A"
    if score >= 70:
        return "High Risk"
    if score >= 40:
        return "Medium Risk"
    return "Low Risk"


def _parse_md_line(line, styles):
    """Convert a markdown line into a ReportLab Paragraph."""
    line = line.strip()
    if not line:
        return None

    # Bold inline replacement for ReportLab XML
    def md_to_rl(t):
        t = _re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
        t = _re.sub(r"`([^`]+)`", r"<font name=\'Courier\'><b>\1</b></font>", t)
        # Escape bare & not part of entity
        t = _re.sub(r"&(?!amp;|lt;|gt;|#)", "&amp;", t)
        return t

    # H1
    if _re.match(r"^#\s+", line):
        text = md_to_rl(line.lstrip("# ").strip())
        return Paragraph(text, styles["section_heading"])
    # H2
    if _re.match(r"^##\s+", line):
        text = md_to_rl(line.lstrip("# ").strip())
        return Paragraph(text, styles["h2"])
    # H3
    if _re.match(r"^###\s+", line):
        text = md_to_rl(line.lstrip("# ").strip())
        return Paragraph(text, styles["h3"])
    # Numbered list
    if _re.match(r"^\d+\.\s", line):
        text = md_to_rl(_re.sub(r"^\d+\.\s*", "", line))
        return Paragraph(text, styles["numbered"])
    # Bullet
    if _re.match(r"^[-*•]\s", line):
        text = md_to_rl(_re.sub(r"^[-*•]\s*", "", line))
        return Paragraph(f"• {text}", styles["bullet"])
    # Regular paragraph
    text = md_to_rl(line)
    try:
        return Paragraph(text, styles["body"])
    except Exception:
        safe = _re.sub(r"[<>&]+", "", text)
        return Paragraph(safe, styles["body"])


def _agent_section(agent_name, data, styles, elements):
    """Render one agent's results into PDF elements."""
    AGENT_LABELS = {
        "architecture": ("Architecture Analysis", ""),
        "scripts": ("Scripts & Code Quality", ""),
        "performance": ("Performance Analysis", ""),
        "security": ("Security Analysis", ""),
        "integration": ("Integration Health", ""),
        "data_health": ("Data Health Analysis", ""),
        "upgrade": ("Upgrade Readiness", ""),
        "license_optimization": ("License Optimization", ""),
    }

    label, _ = AGENT_LABELS.get(agent_name, (agent_name.replace("_", " ").title(), "•"))

    # Section divider
    elements.append(HRFlowable(width="100%", thickness=2,
                                color=styles["BRAND"], spaceAfter=6))

    # Agent title row with risk score
    score = data.get("risk_score") or data.get("summary", {}).get("risk_score")
    risk_col = _risk_color(score, styles)
    risk_lbl = _risk_label(score)
    score_str = f"{score}/100 — {risk_lbl}" if score is not None else "See analysis"

    title_data = [[
        Paragraph(f"<b>{label}</b>", styles["agent_title"]),
        Paragraph(f"<b>Risk Score: {score_str}</b>",
                  ParagraphStyle("rs", fontName="Helvetica-Bold", fontSize=10,
                                 textColor=risk_col, alignment=TA_RIGHT))
    ]]
    title_table = Table(title_data, colWidths=[4*inch, 2.5*inch])
    title_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elements.append(title_table)

    # Risk score visual bar
    if score is not None:
        bar_filled = int(score * 3.5)   # scale to ~350pt wide
        bar_empty  = 350 - bar_filled
        bar_data = [[""]]
        bar_table = Table(bar_data, colWidths=[bar_filled + bar_empty], rowHeights=[8])
        bar_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,0), colors.HexColor("#e9ecef")),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ]))

        filled_data = [[""]]
        filled_table = Table(filled_data, colWidths=[max(bar_filled, 1)], rowHeights=[8])
        filled_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,0), risk_col),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ]))

        combined = Table([[filled_table]], colWidths=[350], rowHeights=[8])
        combined.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,0), colors.HexColor("#e9ecef")),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ]))
        elements.append(combined)
        elements.append(Spacer(1, 8))

    # Metadata row
    ts = data.get("timestamp", "")
    total = data.get("total_records", "")
    meta_parts = []
    if ts:
        meta_parts.append(f"Generated: {ts[:19].replace('T', ' ')}")
    if total:
        meta_parts.append(f"Records analyzed: {total}")
    if meta_parts:
        elements.append(Paragraph(" | ".join(meta_parts), styles["footer"]))
        elements.append(Spacer(1, 6))

    # Parse and render the analysis text
    analysis = data.get("analysis", "")
    if isinstance(data.get("ai_insights"), str):
        analysis = data["ai_insights"]

    if analysis:
        for line in analysis.split("\n"):
            elem = _parse_md_line(line, styles)
            if elem:
                elements.append(elem)

    elements.append(Spacer(1, 14))


def _cover_page(styles):
    """Build the cover page elements."""
    BRAND = styles["BRAND"]
    elements = []

    # Blue header banner (simulate with table)
    header_data = [[
        Paragraph("ServiceNow AI Copilot", styles["cover_title"]),
    ]]
    header_table = Table(header_data, colWidths=[6.5*inch], rowHeights=[1.2*inch])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,0), BRAND),
        ("VALIGN", (0,0), (0,0), "MIDDLE"),
        ("TOPPADDING", (0,0), (0,0), 20),
        ("BOTTOMPADDING", (0,0), (0,0), 20),
        ("LEFTPADDING", (0,0), (0,0), 20),
        ("RIGHTPADDING", (0,0), (0,0), 20),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 30))

    # Report title
    elements.append(Paragraph(
        "<b>Instance Health &amp; Optimization Report</b>",
        ParagraphStyle("rt", fontName="Helvetica-Bold", fontSize=20,
                       textColor=styles["DARK"], alignment=TA_CENTER, spaceAfter=8)
    ))

    now = _dt.utcnow().strftime("%B %d, %Y at %H:%M UTC")
    elements.append(Paragraph(
        f"Generated on {now}",
        ParagraphStyle("gen", fontName="Helvetica", fontSize=11,
                       textColor=styles["GREY"], alignment=TA_CENTER, spaceAfter=40)
    ))

    # Summary box
    summary_items = [
        ["8", "AI Agents Run"],
        ["Full", "Instance Analysis"],
        ["Live", "ServiceNow Data"],
    ]
    kpi_rows = []
    for val, lbl in summary_items:
        kpi_rows.append([
            Paragraph(f"<b>{val}</b>",
                ParagraphStyle("kv", fontName="Helvetica-Bold", fontSize=22,
                               textColor=BRAND, alignment=TA_CENTER)),
            Paragraph(lbl,
                ParagraphStyle("kl", fontName="Helvetica", fontSize=10,
                               textColor=styles["GREY"], alignment=TA_CENTER)),
        ])

    kpi_data = [[
        Table(kpi_rows, colWidths=[0.8*inch, 1.2*inch]),
    ] * 3]
    # 3-column layout
    flat = []
    for val, lbl in summary_items:
        cell = [
            Paragraph(f"<b>{val}</b>",
                ParagraphStyle("kv2", fontName="Helvetica-Bold", fontSize=24,
                               textColor=BRAND, alignment=TA_CENTER, spaceAfter=2)),
            Paragraph(lbl,
                ParagraphStyle("kl2", fontName="Helvetica", fontSize=10,
                               textColor=styles["GREY"], alignment=TA_CENTER)),
        ]
        flat.append(cell)

    kpi_table_data = [[
        [flat[0][0], flat[0][1]],
        [flat[1][0], flat[1][1]],
        [flat[2][0], flat[2][1]],
    ]]

    box_table = Table(
        [[
            Table([[flat[0][0]], [flat[0][1]]], colWidths=[2*inch]),
            Table([[flat[1][0]], [flat[1][1]]], colWidths=[2*inch]),
            Table([[flat[2][0]], [flat[2][1]]], colWidths=[2*inch]),
        ]],
        colWidths=[2.1*inch, 2.1*inch, 2.1*inch]
    )
    box_table.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 1, colors.HexColor("#dee2e6")),
        ("INNERGRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f0f4ff")),
        ("TOPPADDING", (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 16),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    elements.append(box_table)
    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dee2e6")))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Confidential — Internal Use Only",
        ParagraphStyle("conf", fontName="Helvetica-Oblique", fontSize=9,
                       textColor=styles["GREY"], alignment=TA_CENTER)))
    elements.append(PageBreak())
    return elements



def _build_pdf_in_background(job_id: str):
    """Runs in a background thread: builds PDF and updates job store."""
    try:
        file_path = f"/tmp/ServiceNow_AI_Report_{job_id}.pdf"
        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            title="ServiceNow AI Copilot Report",
            author="ServiceNow AI Copilot",
        )

        styles = _build_pdf_styles()
        elements = []

        # --- Cover Page ---
        elements.extend(_cover_page(styles))

        # --- Table of Contents ---
        elements.append(Paragraph("Table of Contents", styles["section_heading"]))
        elements.append(HRFlowable(width="100%", thickness=1,
                                    color=styles["BRAND"], spaceAfter=8))

        toc_agents = [
            ("Architecture Analysis", "Instance structure & table risks"),
            ("Scripts & Code Quality", "Business rules & script analysis"),
            ("Performance Analysis", "Transaction speed & bottlenecks"),
            ("Security Analysis", "ACL & access control review"),
            ("Integration Health", "REST & external connection health"),
            ("Data Health Analysis", "Dictionary & data quality"),
            ("Upgrade Readiness", "Scope & upgrade risk assessment"),
            ("License Optimization", "User license cost savings"),
        ]
        for i, (name, desc) in enumerate(toc_agents, 1):
            elements.append(Paragraph(
                f"<b>{i}.</b> {name} <font color='#6c757d'>— {desc}</font>",
                styles["toc_agent"]
            ))
        elements.append(PageBreak())

        # --- Run all agents in parallel ---
        results = run_all()

        AGENT_ORDER = [
            "architecture", "scripts", "performance", "security",
            "integration", "data_health", "upgrade", "license_optimization"
        ]

        # --- Executive Summary Table ---
        elements.append(Paragraph("Executive Summary", styles["section_heading"]))
        elements.append(HRFlowable(width="100%", thickness=2,
                                    color=styles["BRAND"], spaceAfter=8))

        summary_data = [
            [
                Paragraph("<b>Agent</b>", ParagraphStyle("th", fontName="Helvetica-Bold",
                          fontSize=10, textColor=colors.white, alignment=TA_CENTER)),
                Paragraph("<b>Risk Score</b>", ParagraphStyle("th2", fontName="Helvetica-Bold",
                          fontSize=10, textColor=colors.white, alignment=TA_CENTER)),
                Paragraph("<b>Level</b>", ParagraphStyle("th3", fontName="Helvetica-Bold",
                          fontSize=10, textColor=colors.white, alignment=TA_CENTER)),
                Paragraph("<b>Records</b>", ParagraphStyle("th4", fontName="Helvetica-Bold",
                          fontSize=10, textColor=colors.white, alignment=TA_CENTER)),
            ]
        ]

        AGENT_LABELS_SUM = {
            "architecture": "Architecture",
            "scripts": "Scripts",
            "performance": "Performance",
            "security": "Security",
            "integration": "Integration",
            "data_health": "Data Health",
            "upgrade": "Upgrade",
            "license_optimization": "Licenses",
        }

        for key in AGENT_ORDER:
            val = results.get(key, {})
            score = val.get("risk_score")
            lbl = _risk_label(score)
            rcol = _risk_color(score, styles)
            agent_lbl = AGENT_LABELS_SUM.get(key, key)
            records = str(val.get("total_records", val.get("summary", {}).get("total_users", "—")))
            score_str = f"{score}/100" if score is not None else "—"

            summary_data.append([
                Paragraph(agent_lbl, ParagraphStyle("td", fontName="Helvetica", fontSize=9.5,
                          textColor=styles["DARK"])),
                Paragraph(score_str, ParagraphStyle("td2", fontName="Helvetica-Bold", fontSize=9.5,
                          textColor=rcol, alignment=TA_CENTER)),
                Paragraph(lbl, ParagraphStyle("td3", fontName="Helvetica-Bold", fontSize=9.5,
                          textColor=rcol, alignment=TA_CENTER)),
                Paragraph(records, ParagraphStyle("td4", fontName="Helvetica", fontSize=9.5,
                          textColor=styles["GREY"], alignment=TA_CENTER)),
            ])

        summary_table = Table(summary_data,
                               colWidths=[2.2*inch, 1.3*inch, 1.3*inch, 1.3*inch])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), styles["BRAND"]),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
             [colors.white, colors.HexColor("#f8f9fa")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS", (0,0), (-1,0), [styles["BRAND"]]),
        ]))
        elements.append(summary_table)
        elements.append(PageBreak())

        # --- Detailed Agent Sections ---
        for key in AGENT_ORDER:
            val = results.get(key, {})
            if val:
                _agent_section(key, val, styles, elements)

        # --- Footer note ---
        elements.append(HRFlowable(width="100%", thickness=1,
                                    color=colors.HexColor("#dee2e6"), spaceBefore=20))
        elements.append(Paragraph(
            f"Report generated by ServiceNow AI Copilot v2.0 | {_dt.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | Confidential",
            styles["footer"]
        ))

        doc.build(elements)
        _pdf_jobs[job_id] = {"status": "done", "path": file_path}

    except Exception as e:
        import traceback as _tb
        _pdf_jobs[job_id] = {"status": "error", "error": str(e), "trace": _tb.format_exc()}


@app.get("/generate-report")
def generate_report(background_tasks: BackgroundTasks):
    """
    Kicks off async PDF generation and returns a job_id immediately.
    Poll /report-status/{job_id} to check progress.
    Download from /download-report/{job_id} when status == 'done'.
    """
    job_id = uuid.uuid4().hex
    _pdf_jobs[job_id] = {"status": "pending"}
    background_tasks.add_task(_build_pdf_in_background, job_id)
    return JSONResponse({"job_id": job_id, "status": "pending",
                         "message": f"PDF generation started. Poll /report-status/{job_id}"})


@app.get("/report-status/{job_id}")
def report_status(job_id: str):
    """Check the status of a PDF generation job."""
    job = _pdf_jobs.get(job_id)
    if not job:
        return JSONResponse({"status": "not_found"}, status_code=404)
    if job["status"] == "done":
        return JSONResponse({"status": "done", "download_url": f"/download-report/{job_id}"})
    return JSONResponse(job)


@app.get("/download-report/{job_id}")
def download_report(job_id: str):
    """Download the completed PDF."""
    job = _pdf_jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] == "pending":
        return JSONResponse({"status": "pending", "message": "Still generating..."})
    if job["status"] == "error":
        return JSONResponse({"error": job.get("error"), "trace": job.get("trace")}, status_code=500)
    file_path = job["path"]
    if not os.path.exists(file_path):
        return JSONResponse({"error": "PDF file missing on disk"}, status_code=500)
    return FileResponse(
        file_path,
        filename=f"ServiceNow_AI_Report_{_dt.utcnow().strftime('%Y%m%d_%H%M')}.pdf",
        media_type="application/pdf",
    )


# =====================================================
# CFO DASHBOARD
# =====================================================

@app.get("/dashboard/cfo")
def cfo_dashboard():
    try:
        # Run ALL agents to collect scores
        import concurrent.futures

        agent_runners = {
            "architecture":         architecture.run,
            "scripts":              scripts.run,
            "performance":          performance.run,
            "security":             security.run,
            "integration":          integration.run,
            "data_health":          data_health.run,
            "upgrade":              upgrade.run,
            "license_optimization": license_optimization.run,
        }

        agent_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            future_map = {ex.submit(fn): name for name, fn in agent_runners.items()}
            for future in concurrent.futures.as_completed(future_map):
                name = future_map[future]
                try:
                    agent_results[name] = future.result()
                except Exception as e:
                    agent_results[name] = {"error": str(e), "risk_score": None}

        # License data
        lic = agent_results.get("license_optimization", {})
        summary = lic.get("summary", {})
        financials = lic.get("financials", {})

        total_users        = summary.get("total_users", 0)
        inactive           = summary.get("inactive_users", 0)
        wasted             = summary.get("wasted_licenses", 0)
        overlicensed       = summary.get("overlicensed_users", 0)
        monthly_savings    = financials.get("monthly_savings_potential", summary.get("monthly_savings_potential", 0))
        annual_savings     = financials.get("annual_savings_potential", summary.get("annual_savings_potential", 0))
        current_cost       = financials.get("current_monthly_cost", summary.get("current_monthly_cost", 0))
        optimized_cost     = max(current_cost - monthly_savings, 0)

        # Agent risk scores
        AGENT_LABELS = {
            "architecture":         "Architecture",
            "scripts":              "Scripts",
            "performance":          "Performance",
            "security":             "Security",
            "integration":          "Integration",
            "data_health":          "Data Health",
            "upgrade":              "Upgrade",
            "license_optimization": "Licenses",
        }

        import re as _re2

        def _safe_extract_score(res):
            # Direct field first
            score = res.get("risk_score")
            if isinstance(score, (int, float)):
                return int(score)
            # Try analysis text - must be string
            for field in ["analysis", "ai_insights"]:
                val = res.get(field, "")
                if isinstance(val, dict):
                    val = str(val)
                if isinstance(val, str) and val:
                    m = _re2.search(r"(\d{1,3})/100", val)
                    if m:
                        n = int(m.group(1))
                        if 0 <= n <= 100:
                            return n
            # Try summary sub-dict
            sm = res.get("summary", {})
            if isinstance(sm, dict):
                rs = sm.get("risk_score")
                if isinstance(rs, (int, float)):
                    return int(rs)
            return None

        agent_scores = []
        for key, label in AGENT_LABELS.items():
            res = agent_results.get(key, {})
            if not isinstance(res, dict):
                res = {}
            score = _safe_extract_score(res)
            has_error = bool(res.get("error")) and not res.get("analysis") and not res.get("summary")
            records = res.get("total_records") or (res.get("summary") or {}).get("total_users", 0) or 0
            agent_scores.append({
                "key":     key,
                "label":   label,
                "score":   score,
                "error":   has_error,
                "records": records,
            })

        scores_only = [a["score"] for a in agent_scores if a["score"] is not None]
        overall_risk = round(sum(scores_only) / len(scores_only)) if scores_only else 0

        high_risk  = [a for a in agent_scores if a["score"] is not None and a["score"] >= 70]
        med_risk   = [a for a in agent_scores if a["score"] is not None and 40 <= a["score"] < 70]
        low_risk   = [a for a in agent_scores if a["score"] is not None and a["score"] < 40]

        return {
            "kpis": {
                "total_users":        total_users,
                "inactive_users":     inactive,
                "wasted_licenses":    wasted,
                "overlicensed_users": overlicensed,
                "monthly_savings":    monthly_savings,
                "annual_savings":     annual_savings,
                "current_cost":       current_cost,
                "optimized_cost":     optimized_cost,
                "overall_risk":       overall_risk,
                "high_risk_agents":   len(high_risk),
                "med_risk_agents":    len(med_risk),
                "low_risk_agents":    len(low_risk),
            },
            "agent_scores": agent_scores,
            "charts": {
                "license_distribution": {
                    "labels": ["Active", "Inactive", "Wasted", "Over-licensed"],
                    "values": [
                        max(total_users - inactive - wasted - overlicensed, 0),
                        inactive, wasted, overlicensed
                    ]
                },
                "savings_chart": {
                    "labels": ["Current Cost", "Optimized Cost", "Monthly Savings"],
                    "values": [current_cost, optimized_cost, monthly_savings]
                },
                "risk_radar": {
                    "labels": [a["label"] for a in agent_scores],
                    "values": [a["score"] if a["score"] is not None else 0 for a in agent_scores],
                },
            }
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}
# =====================================================
# Startup
# =====================================================

@app.on_event("startup")
async def startup_event():
    print("🚀 ServiceNow AI Copilot Started")
    print("Dashboard: http://127.0.0.1:8000/")
    print("Docs: http://127.0.0.1:8000/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)