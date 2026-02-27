// ===== GLOBALS =====
let chatHistory = [];
let currentAgent = null;

// Agent metadata: icon, color, title
const AGENT_META = {
    'architecture':         { icon: 'bi-diagram-3',      color: 'primary',  label: 'Architecture Analysis' },
    'scripts':              { icon: 'bi-file-code',       color: 'info',     label: 'Scripts Analysis' },
    'performance':          { icon: 'bi-speedometer2',    color: 'success',  label: 'Performance Analysis' },
    'security':             { icon: 'bi-shield-lock',     color: 'danger',   label: 'Security Analysis' },
    'integration':          { icon: 'bi-plugin',          color: 'warning',  label: 'Integration Analysis' },
    'data-health':          { icon: 'bi-heart-pulse',     color: 'pink',     label: 'Data Health Analysis' },
    'data_health':          { icon: 'bi-heart-pulse',     color: 'pink',     label: 'Data Health Analysis' },
    'upgrade':              { icon: 'bi-arrow-up-circle', color: 'teal',     label: 'Upgrade Analysis' },
    'license-optimization': { icon: 'bi-key',             color: 'purple',   label: 'License Optimization' },
    'license_optimization': { icon: 'bi-key',             color: 'purple',   label: 'License Optimization' },
};

const COLOR_MAP = {
    primary: { bg: '#0d6efd', light: 'rgba(13,110,253,0.08)' },
    info:    { bg: '#0dcaf0', light: 'rgba(13,202,240,0.08)' },
    success: { bg: '#198754', light: 'rgba(25,135,84,0.08)'  },
    danger:  { bg: '#dc3545', light: 'rgba(220,53,69,0.08)'  },
    warning: { bg: '#ffc107', light: 'rgba(255,193,7,0.08)'  },
    pink:    { bg: '#d63384', light: 'rgba(214,51,132,0.08)' },
    teal:    { bg: '#20c997', light: 'rgba(32,201,151,0.08)' },
    purple:  { bg: '#6f42c1', light: 'rgba(111,66,193,0.08)' },
};

// ===== INIT =====
document.addEventListener('DOMContentLoaded', function () {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar-wrapper');
    if (toggle) {
        toggle.addEventListener('click', () => sidebar.classList.toggle('show'));
    }
    document.addEventListener('click', function (e) {
        if (window.innerWidth <= 768 && sidebar && toggle) {
            if (!sidebar.contains(e.target) && !e.target.closest('#sidebarToggle')) {
                sidebar.classList.remove('show');
            }
        }
    });
});

// ===== SECTION TOGGLES =====
function showWelcome() {
    document.getElementById('welcomeSection').classList.remove('d-none');
    document.getElementById('chatSection').classList.add('d-none');
    document.getElementById('analysisSection').classList.add('d-none');
}

function showChat() {
    document.getElementById('welcomeSection').classList.add('d-none');
    document.getElementById('chatSection').classList.remove('d-none');
    document.getElementById('analysisSection').classList.add('d-none');
}

function showAnalysis() {
    document.getElementById('welcomeSection').classList.add('d-none');
    document.getElementById('chatSection').classList.add('d-none');
    document.getElementById('analysisSection').classList.remove('d-none');
}

// ===== NEW CHAT =====
function newChat() {
    chatHistory = [];
    document.getElementById('chatMessages').innerHTML = '';
    showChat();
    addChatMessage('assistant', 'Hello! I\'m your **ServiceNow AI Copilot**. How can I help you analyze your ServiceNow instance today?\n\nYou can ask me about:\n- Instance architecture and configuration\n- Security risks and ACL audits\n- Performance bottlenecks\n- License optimization opportunities');
}

// ===== CHAT FUNCTIONS =====
function renderChatMarkdown(text) {
    if (!text) return '';
    let t = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Bold
    t = t.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    // Inline code
    t = t.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');
    // Italic
    t = t.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');

    // Convert lines
    const lines = t.split('\n');
    const out = [];
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) {
            if (inList) { out.push('</ul>'); inList = false; }
            continue;
        }
        if (/^[-*•]\s/.test(line)) {
            if (!inList) { out.push('<ul class="chat-list">'); inList = true; }
            out.push(`<li>${line.replace(/^[-*•]\s*/, '')}</li>`);
        } else {
            if (inList) { out.push('</ul>'); inList = false; }
            out.push(`<p>${line}</p>`);
        }
    }
    if (inList) out.push('</ul>');
    return out.join('');
}

function addChatMessage(role, content) {
    const chatMessages = document.getElementById('chatMessages');
    const wrapper = document.createElement('div');
    wrapper.className = `chat-message ${role}`;

    const msgRow = document.createElement('div');
    msgRow.className = `message-row ${role}`;

    // Avatar
    if (role === 'assistant') {
        const avatar = document.createElement('div');
        avatar.className = 'chat-avatar assistant-avatar';
        avatar.innerHTML = '<i class="bi bi-robot"></i>';
        msgRow.appendChild(avatar);
    }

    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role}`;

    if (role === 'assistant') {
        bubble.innerHTML = renderChatMarkdown(content);
    } else {
        bubble.textContent = content;
    }

    msgRow.appendChild(bubble);

    if (role === 'user') {
        const avatar = document.createElement('div');
        avatar.className = 'chat-avatar user-avatar';
        avatar.innerHTML = '<i class="bi bi-person-fill"></i>';
        msgRow.appendChild(avatar);
    }

    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});

    wrapper.appendChild(msgRow);
    wrapper.appendChild(time);
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    chatHistory.push({ role, content, timestamp: new Date().toISOString() });
}

function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    addChatMessage('user', message);
    input.value = '';
    addTypingIndicator();

    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history: chatHistory })
    })
        .then(r => r.json())
        .then(data => {
            removeTypingIndicator();
            addChatMessage('assistant', data.response || 'Processing your request...');
        })
        .catch(() => {
            removeTypingIndicator();
            addChatMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        });
}

function handleChatKeyPress(e) { if (e.key === 'Enter') sendChatMessage(); }

function addTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.id = 'typingIndicator';
    div.className = 'chat-message assistant';
    div.innerHTML = `
        <div class="message-row assistant">
            <div class="chat-avatar assistant-avatar"><i class="bi bi-robot"></i></div>
            <div class="message-bubble assistant typing-bubble">
                <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>
            </div>
        </div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById('typingIndicator');
    if (el) el.remove();
}

function clearChat() {
    if (confirm('Clear chat history?')) {
        chatHistory = [];
        document.getElementById('chatMessages').innerHTML = '';
        addChatMessage('assistant', 'Chat cleared. How can I help you with your ServiceNow instance?');
    }
}

// ===== LOADING BAR =====
let _loadingInterval = null;

const LOADING_STEPS = [
    { pct: 15, text: 'Connecting to ServiceNow instance',   step: 1 },
    { pct: 40, text: 'Fetching instance data',              step: 2 },
    { pct: 70, text: 'Running AI analysis',                 step: 3 },
    { pct: 90, text: 'Preparing results',                   step: 4 },
];

function startLoading() {
    const spinner = document.getElementById('loadingSpinner');
    if (!spinner) return;
    spinner.classList.remove('d-none');

    setProgress(0, 'Initializing agent...', 1);
    resetStepDots();

    let stepIdx = 0;
    if (_loadingInterval) clearInterval(_loadingInterval);
    _loadingInterval = setInterval(() => {
        if (stepIdx < LOADING_STEPS.length) {
            const s = LOADING_STEPS[stepIdx];
            setProgress(s.pct, s.text, s.step);
            markStepDone(stepIdx);
            stepIdx++;
        }
    }, 900);
}

function stopLoading() {
    if (_loadingInterval) { clearInterval(_loadingInterval); _loadingInterval = null; }
    setProgress(100, 'Complete!', 4);
    markAllStepsDone();
    setTimeout(() => {
        const spinner = document.getElementById('loadingSpinner');
        if (spinner) spinner.classList.add('d-none');
        resetProgress();
    }, 400);
}

function setProgress(pct, text, stepNum) {
    const bar    = document.getElementById('loadingProgressBar');
    const pctEl  = document.getElementById('loadingPercent');
    const stepEl = document.getElementById('loadingStep');
    const textEl = document.getElementById('loadingStatusText');
    if (bar)    bar.style.width = pct + '%';
    if (pctEl)  pctEl.textContent = pct + '%';
    if (stepEl) stepEl.textContent = `Step ${stepNum} of 4`;
    if (textEl) textEl.textContent = text;

    // Update active step dot
    [1,2,3,4].forEach(n => {
        const el = document.getElementById('step' + n);
        if (!el) return;
        el.classList.remove('active');
        if (n === stepNum) el.classList.add('active');
    });
}

function resetProgress() {
    const bar = document.getElementById('loadingProgressBar');
    if (bar) bar.style.width = '0%';
}

function resetStepDots() {
    [1,2,3,4].forEach(n => {
        const el = document.getElementById('step' + n);
        if (el) { el.classList.remove('active','done'); }
    });
    document.querySelectorAll('.loading-step-line').forEach(l => l.classList.remove('done'));
}

function markStepDone(idx) {
    const stepNum = idx + 1;
    const prev = document.getElementById('step' + stepNum);
    if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }

    // Mark connecting line as done
    const lines = document.querySelectorAll('.loading-step-line');
    if (lines[idx]) lines[idx].classList.add('done');
}

function markAllStepsDone() {
    [1,2,3,4].forEach(n => {
        const el = document.getElementById('step' + n);
        if (el) { el.classList.remove('active'); el.classList.add('done'); }
    });
    document.querySelectorAll('.loading-step-line').forEach(l => l.classList.add('done'));
}


function callAgent(name) {
    currentAgent = name;
    showAnalysis();

    // Highlight sidebar
    document.querySelectorAll('.list-group-item').forEach(el => el.classList.remove('active'));
    const btn = document.querySelector(`[data-agent="${name}"]`);
    if (btn) btn.classList.add('active');

    const meta = AGENT_META[name] || { icon: 'bi-robot', color: 'primary', label: name };
    const col = COLOR_MAP[meta.color] || COLOR_MAP.primary;

    // Render header
    const agentHeader = document.getElementById('agentHeader');
    if (agentHeader) {
        agentHeader.innerHTML = `
            <div class="d-flex align-items-center gap-3 mb-3">
                <div class="p-2 rounded-3" style="background:${col.light}">
                    <i class="bi ${meta.icon} fs-4" style="color:${col.bg}"></i>
                </div>
                <div>
                    <h4 class="mb-0 fw-bold">${meta.label}</h4>
                    <small class="text-muted">Live analysis from your ServiceNow instance</small>
                </div>
            </div>`;
    }

    const output = document.getElementById('analysisOutput');
    if (!output) { console.error('analysisOutput not found'); return; }
    output.innerHTML = '';
    startLoading();

    fetch(`/agent/${name}`)
        .then(r => r.json())
        .then(data => {
            stopLoading();
            output.innerHTML = renderAgentResult(data, name, meta, col);
            // Initialise pagination controls for any agents that have >PAGE_SIZE errors
            if (_errPages[name]) _renderPagination(name);
        })
        .catch(err => {
            stopLoading();
            output.innerHTML = renderError(err.message);
        });
}

// ===== RUN ALL AGENTS =====
function callRunAll() {
    showAnalysis();
    document.getElementById('agentHeader').innerHTML = `
        <div class="d-flex align-items-center gap-3 mb-3">
            <div class="p-2 rounded-3 bg-primary bg-opacity-10">
                <i class="bi bi-play-circle fs-4 text-primary"></i>
            </div>
            <div>
                <h4 class="mb-0 fw-bold">All Agents — Full Analysis</h4>
                <small class="text-muted">Running all ServiceNow AI agents</small>
            </div>
        </div>`;

    const output = document.getElementById('analysisOutput');
    if (!output) return;
    output.innerHTML = '';
    startLoading();

    fetch('/run-all')
        .then(r => r.json())
        .then(data => {
            stopLoading();
            output.innerHTML = renderRunAll(data);
        })
        .catch(err => {
            stopLoading();
            output.innerHTML = renderError(err.message);
        });
}

// ===== RENDER: SINGLE AGENT =====
function renderAgentResult(data, agentName, meta, col) {
    if (data.error) return renderError(data.error);

    let html = '';

    // License optimization has rich structured data
    if (agentName === 'license-optimization' || agentName === 'license_optimization') {
        html = renderLicenseResult(data, meta, col);
    } else {
        // Standard agent: has "analysis" text field
        const analysis = data.analysis || JSON.stringify(data, null, 2);
        html = renderAnalysisText(analysis, meta, col);
    }

    // Append Fix It errors panel if errors were returned
    const errors = data.errors || [];
    if (errors.length > 0) {
        html += renderErrorsPanel(errors, agentName, col);
    }

    return html;
}

// ===== RENDER: ANALYSIS TEXT (standard agents) =====
function renderAnalysisText(text, meta, col) {
    const riskScore = extractRiskScore(text);
    const riskColor = riskScore >= 70 ? 'danger' : riskScore >= 40 ? 'warning' : 'success';
    const riskLabel = riskScore >= 70 ? 'High Risk' : riskScore >= 40 ? 'Medium Risk' : 'Low Risk';

    // Risk Score Card
    let scoreHtml = '';
    if (riskScore !== null) {
        scoreHtml = `
        <div class="card border-0 shadow-sm mb-4" style="border-radius:14px;overflow:hidden">
            <div class="card-body p-0">
                <div class="row g-0">
                    <div class="col-md-3 d-flex align-items-center justify-content-center p-4" style="background:${col.light}">
                        <div class="text-center">
                            <div class="display-3 fw-bold" style="color:${col.bg}">${riskScore}</div>
                            <div class="small text-muted fw-semibold mt-1">Risk Score</div>
                            <span class="badge bg-${riskColor} mt-2 px-3 py-2">${riskLabel}</span>
                        </div>
                    </div>
                    <div class="col-md-9 p-4 d-flex flex-column justify-content-center">
                        <h6 class="fw-bold mb-3" style="color:${col.bg}">
                            <i class="bi bi-bar-chart-fill me-2"></i>Risk Summary
                        </h6>
                        <div class="progress mb-2" style="height:12px;border-radius:8px;background:#e9ecef">
                            <div class="progress-bar bg-${riskColor}" style="width:${riskScore}%;border-radius:8px;transition:width 1s ease"></div>
                        </div>
                        <small class="text-muted">Score <strong>${riskScore}/100</strong> — ${riskLabel}</small>
                    </div>
                </div>
            </div>
        </div>`;
    }

    // Parse markdown into sections
    const sections = parseMarkdownIntoSections(text);

    const sectionsHtml = sections.map(s => {
        const sCol = COLOR_MAP[s.meta.color] || col;
        const itemsHtml = s.items.map(item => renderItem(item, sCol.bg)).join('');
        return `
        <div class="card border-0 shadow-sm mb-4" style="border-radius:14px">
            <div class="card-header border-0 py-3 px-4" style="background:${sCol.light};border-radius:14px 14px 0 0">
                <h6 class="mb-0 fw-bold" style="color:${sCol.bg}">
                    <i class="bi ${s.meta.icon} me-2"></i>${escapeHtml(s.title)}
                </h6>
            </div>
            <div class="card-body p-4">${itemsHtml}</div>
        </div>`;
    }).join('');

    return scoreHtml + sectionsHtml;
}

// ===== RENDER: LICENSE OPTIMIZATION =====
function renderLicenseResult(data, meta, col) {
    const summary  = data.summary    || {};
    const fin      = data.financials || {};
    const cats     = data.categories || {};
    const decisions= data.decisions  || [];
    const risky    = data.top_risky_users || [];
    const depts    = data.department_breakdown || {};
    const roles    = data.role_usage || {};
    const dups     = data.duplicate_users || [];
    const auto     = data.automation || {};
    const ai       = data.ai_insights || '';

    const totalUsers    = summary.total_users          || 0;
    const activeUsers   = summary.active_users         || 0;
    const inactiveUsers = summary.inactive_users       || 0;
    const wastedUsers   = summary.wasted_licenses      || 0;
    const underutil     = summary.underutilized_users  || 0;
    const overlic       = summary.overlicensed_users   || 0;
    const integrations  = summary.integration_accounts || 0;
    const dupCount      = summary.duplicate_users      || 0;
    const monthly       = fin.monthly_savings_potential || 0;
    const annual        = fin.annual_savings_potential  || 0;
    const current       = fin.current_monthly_cost      || 0;
    const riskScore     = data.risk_score               || 0;
    const riskCol       = riskScore >= 70 ? '#dc3545' : riskScore >= 40 ? '#ffc107' : '#198754';
    const riskLbl       = riskScore >= 70 ? 'High Risk' : riskScore >= 40 ? 'Medium Risk' : 'Low Risk';

    // ── KPI Row ──────────────────────────────────────────────────────────────
    const kpiRow = `
    <div class="row g-3 mb-4">
        <div class="col-md-2 col-sm-4 col-6">
            <div class="card border-0 shadow-sm text-center p-3" style="border-radius:12px">
                <div class="fs-2 fw-bold text-primary">${totalUsers.toLocaleString()}</div>
                <div class="text-muted" style="font-size:.75rem;font-weight:600">Total Users</div>
            </div>
        </div>
        <div class="col-md-2 col-sm-4 col-6">
            <div class="card border-0 shadow-sm text-center p-3" style="border-radius:12px">
                <div class="fs-2 fw-bold text-success">${activeUsers.toLocaleString()}</div>
                <div class="text-muted" style="font-size:.75rem;font-weight:600">Active</div>
            </div>
        </div>
        <div class="col-md-2 col-sm-4 col-6">
            <div class="card border-0 shadow-sm text-center p-3" style="border-radius:12px">
                <div class="fs-2 fw-bold text-danger">${inactiveUsers.toLocaleString()}</div>
                <div class="text-muted" style="font-size:.75rem;font-weight:600">Inactive</div>
            </div>
        </div>
        <div class="col-md-2 col-sm-4 col-6">
            <div class="card border-0 shadow-sm text-center p-3" style="border-radius:12px">
                <div class="fs-2 fw-bold text-warning">${wastedUsers.toLocaleString()}</div>
                <div class="text-muted" style="font-size:.75rem;font-weight:600">Wasted</div>
            </div>
        </div>
        <div class="col-md-2 col-sm-4 col-6">
            <div class="card border-0 shadow-sm text-center p-3" style="border-radius:12px">
                <div class="fs-2 fw-bold text-info">${underutil.toLocaleString()}</div>
                <div class="text-muted" style="font-size:.75rem;font-weight:600">Underutilized</div>
            </div>
        </div>
        <div class="col-md-2 col-sm-4 col-6">
            <div class="card border-0 shadow-sm text-center p-3" style="border-radius:12px">
                <div class="fs-2 fw-bold" style="color:#6f42c1">${overlic.toLocaleString()}</div>
                <div class="text-muted" style="font-size:.75rem;font-weight:600">Over-licensed</div>
            </div>
        </div>
    </div>`;

    // ── Financial + Risk Row ─────────────────────────────────────────────────
    const finRow = `
    <div class="row g-3 mb-4">
        <div class="col-md-3">
            <div class="card border-0 shadow-sm text-white p-3" style="border-radius:12px;background:linear-gradient(135deg,${riskCol},${riskCol}bb)">
                <div class="small opacity-75 fw-semibold">License Risk Score</div>
                <div class="display-5 fw-bold">${riskScore}/100</div>
                <span class="badge bg-white bg-opacity-25">${riskLbl}</span>
                <div class="progress mt-2" style="height:5px;background:rgba(255,255,255,0.2)">
                    <div class="progress-bar bg-white" style="width:${riskScore}%"></div>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card border-0 shadow-sm text-white p-3" style="border-radius:12px;background:linear-gradient(135deg,#6f42c1,#4e2d8a)">
                <div class="small opacity-75 fw-semibold">Current Monthly Cost</div>
                <div class="display-5 fw-bold">$${current.toLocaleString()}</div>
                <div class="small opacity-75 mt-1">${totalUsers} licensed users</div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card border-0 shadow-sm text-white p-3" style="border-radius:12px;background:linear-gradient(135deg,#198754,#157347)">
                <div class="small opacity-75 fw-semibold">Monthly Savings Possible</div>
                <div class="display-5 fw-bold">$${monthly.toLocaleString()}</div>
                <div class="small opacity-75 mt-1">$${annual.toLocaleString()} annually</div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card border-0 shadow-sm text-white p-3" style="border-radius:12px;background:linear-gradient(135deg,#0d6efd,#0a58ca)">
                <div class="small opacity-75 fw-semibold">Automation Ready</div>
                <div class="display-5 fw-bold">${auto.pending_approvals || 0}</div>
                <div class="small opacity-75 mt-1">${auto.auto_eligible || 0} auto-eligible actions</div>
            </div>
        </div>
    </div>`;

    // ── Savings Breakdown ────────────────────────────────────────────────────
    const savingsBreakdown = `
    <div class="card border-0 shadow-sm mb-4" style="border-radius:12px">
        <div class="card-header border-0 py-3 px-4" style="background:rgba(25,135,84,0.08);border-radius:12px 12px 0 0">
            <h6 class="mb-0 fw-bold text-success"><i class="bi bi-piggy-bank-fill me-2"></i>Financial Savings Breakdown</h6>
        </div>
        <div class="card-body p-4">
            <div class="row g-3">
                ${[
                    {label:'From Inactive Users',   val: fin.recoverable_from_inactive || 0,  col:'#dc3545', icon:'bi-person-x-fill'},
                    {label:'From Wasted Licenses',  val: fin.recoverable_from_wasted   || 0,  col:'#ffc107', icon:'bi-tag-fill'},
                    {label:'From Over-licensed',    val: fin.recoverable_from_overlic  || 0,  col:'#6f42c1', icon:'bi-person-gear'},
                    {label:'From Underutilized (50%)',val:fin.recoverable_from_underutil||0,  col:'#0dcaf0', icon:'bi-dash-circle-fill'},
                ].map(item => `
                <div class="col-md-3 col-sm-6">
                    <div class="d-flex align-items-center gap-3 p-3 rounded-3" style="background:${item.col}12;border-left:4px solid ${item.col}">
                        <i class="bi ${item.icon} fs-4" style="color:${item.col}"></i>
                        <div>
                            <div class="fw-bold" style="color:${item.col}">$${item.val.toLocaleString()}<span class="text-muted fw-normal">/mo</span></div>
                            <div style="font-size:.75rem;color:#6c757d">${item.label}</div>
                        </div>
                    </div>
                </div>`).join('')}
            </div>
        </div>
    </div>`;

    // ── Decision Engine Output ───────────────────────────────────────────────
    const ACTION_META = {
        deactivate:           { label:'Deactivate',       col:'#dc3545', icon:'bi-person-x-fill' },
        remove_paid_roles:    { label:'Remove Paid Roles',col:'#ffc107', icon:'bi-tag-fill' },
        downgrade_license:    { label:'Downgrade',        col:'#6f42c1', icon:'bi-arrow-down-circle-fill' },
        review_and_downgrade: { label:'Review',           col:'#0dcaf0', icon:'bi-eye-fill' },
    };

    const decisionsHtml = decisions.slice(0,50).map((d, idx) => {
        const am      = ACTION_META[d.action] || {label: d.action, col:'#6c757d', icon:'bi-gear'};
        const saving  = d.monthly_saving || 0;
        const confCol = d.confidence_pct >= 85 ? '#198754' : d.confidence_pct >= 65 ? '#ffc107' : '#6c757d';
        const rowId   = `dec_row_${idx}`;

        // Activity log pill — based on days_inactive + tx_count from agent
        const daysInactive = d.days_inactive || 0;
        const txCount      = d.tx_count      || 0;
        const lastLogin    = d.last_login     || null;
        const actPill = daysInactive > 90
            ? `<span class="act-pill inactive"><i class="bi bi-moon-fill me-1"></i>${daysInactive}d inactive</span>`
            : daysInactive > 30
            ? `<span class="act-pill warning"><i class="bi bi-exclamation-circle me-1"></i>${daysInactive}d ago</span>`
            : txCount > 0
            ? `<span class="act-pill active"><i class="bi bi-activity me-1"></i>${txCount} logins</span>`
            : `<span class="act-pill inactive"><i class="bi bi-moon-fill me-1"></i>No activity</span>`;

        const lastLoginStr = lastLogin
            ? `<div style="font-size:.68rem;color:#adb5bd">Last login: ${escapeHtml(String(lastLogin).slice(0,10))}</div>`
            : `<div style="font-size:.68rem;color:#adb5bd">Last login: never</div>`;

        // Action button — Deactivate gets a red one-click button
        const actionBtn = d.action === 'deactivate'
            ? `<button class="deactivate-btn" id="deact_${rowId}"
                onclick="deactivateUser(${JSON.stringify(d.user_sys_id||'')}, ${JSON.stringify(d.user_name||'')}, ${JSON.stringify(d.email||'')}, ${daysInactive}, ${JSON.stringify(d.reason||'')}, '${rowId}')"
                title="Deactivate this user in ServiceNow immediately">
                    <i class="bi bi-person-x-fill me-1"></i>Deactivate User
               </button>`
            : `<span class="badge rounded-pill" style="background:${am.col}20;color:${am.col};font-weight:600;font-size:.75rem">
                <i class="bi ${am.icon} me-1"></i>${am.label}
               </span>`;

        return `
        <tr id="${rowId}">
            <td class="py-2 ps-3">
                <div class="fw-semibold small">${escapeHtml(d.user_name || 'Unknown')}</div>
                <div class="text-muted" style="font-size:.72rem">${escapeHtml(d.email || '')}</div>
                ${lastLoginStr}
            </td>
            <td class="py-2">${actPill}</td>
            <td class="py-2">${actionBtn}</td>
            <td class="py-2 small text-muted" style="max-width:200px">
                ${escapeHtml((d.reason||'').slice(0,90))}${(d.reason||'').length>90?'…':''}
            </td>
            <td class="py-2 text-end pe-3">
                <div class="fw-bold text-success small">$${saving}/mo</div>
                <div class="small" style="color:${confCol};font-weight:600">${d.confidence_pct}% conf.</div>
            </td>
        </tr>`;
    }).join('');

    const deactivateCount = decisions.filter(d => d.action === 'deactivate').length;

    const decisionsCard = decisions.length > 0 ? `
    <div class="card border-0 shadow-sm mb-4" style="border-radius:12px">
        <div class="card-header border-0 py-3 px-4 d-flex justify-content-between align-items-center flex-wrap gap-2"
             style="background:rgba(220,53,69,0.07);border-radius:12px 12px 0 0">
            <div class="d-flex align-items-center gap-2 flex-wrap">
                <h6 class="mb-0 fw-bold text-danger"><i class="bi bi-lightning-charge-fill me-2"></i>Decision Engine — Recommendations</h6>
                <span class="badge bg-danger">${decisions.length} actions</span>
                ${deactivateCount > 0 ? `<span class="badge" style="background:#dc3545">${deactivateCount} inactive users</span>` : ''}
            </div>
            <div class="d-flex align-items-center gap-2">
                <span style="font-size:.75rem;color:#6c757d">
                    <i class="bi bi-info-circle me-1"></i>Activity based on transaction logs
                </span>
                ${deactivateCount > 0 ? `
                <button class="deactivate-all-btn" onclick="deactivateAllInactive(this)">
                    <i class="bi bi-person-x-fill me-1"></i>Deactivate All Inactive (${deactivateCount})
                </button>` : ''}
            </div>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover mb-0" style="font-size:.85rem">
                    <thead class="table-light">
                        <tr>
                            <th class="ps-3">User</th>
                            <th>Activity Log</th>
                            <th>Action</th>
                            <th>Reason</th>
                            <th class="text-end pe-3">Impact</th>
                        </tr>
                    </thead>
                    <tbody>${decisionsHtml}</tbody>
                </table>
            </div>
        </div>
    </div>` : '';

    // ── Behavioral Profiles — Top Risky ──────────────────────────────────────
    const riskyRows = risky.slice(0,10).map(u => {
        const rCol = u.privilege_risk >= 70 ? '#dc3545' : u.privilege_risk >= 40 ? '#ffc107' : '#198754';
        const eCol = u.efficiency_score >= 60 ? '#198754' : u.efficiency_score >= 30 ? '#ffc107' : '#dc3545';
        return `
        <tr>
            <td class="py-2 ps-4">
                <div class="fw-semibold small">${escapeHtml(u.name || u.user_name)}</div>
                <div class="text-muted" style="font-size:.72rem">${escapeHtml(u.department)}</div>
            </td>
            <td class="py-2"><span class="badge bg-secondary bg-opacity-10 text-secondary">${escapeHtml(u.license_type.toUpperCase())}</span></td>
            <td class="py-2">
                <div class="d-flex align-items-center gap-1">
                    <div class="progress flex-grow-1" style="height:6px;border-radius:3px">
                        <div class="progress-bar" style="width:${u.privilege_risk}%;background:${rCol}"></div>
                    </div>
                    <span style="font-size:.72rem;color:${rCol};font-weight:700;width:28px">${u.privilege_risk}</span>
                </div>
            </td>
            <td class="py-2">
                <div class="d-flex align-items-center gap-1">
                    <div class="progress flex-grow-1" style="height:6px;border-radius:3px">
                        <div class="progress-bar" style="width:${u.efficiency_score}%;background:${eCol}"></div>
                    </div>
                    <span style="font-size:.72rem;color:${eCol};font-weight:700;width:28px">${u.efficiency_score}</span>
                </div>
            </td>
            <td class="py-2 small text-muted">${u.days_inactive < 900 ? u.days_inactive + ' days' : 'Never'}</td>
            <td class="py-2 text-end pe-4 fw-bold text-danger small">$${u.license_cost}/mo</td>
        </tr>`;
    }).join('');

    const riskyCard = risky.length > 0 ? `
    <div class="card border-0 shadow-sm mb-4" style="border-radius:12px">
        <div class="card-header border-0 py-3 px-4" style="background:rgba(111,66,193,0.07);border-radius:12px 12px 0 0">
            <h6 class="mb-0 fw-bold" style="color:#6f42c1"><i class="bi bi-person-exclamation me-2"></i>Behavioral Intelligence — High Risk Users</h6>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover mb-0" style="font-size:.88rem">
                    <thead class="table-light">
                        <tr>
                            <th class="ps-4">User</th><th>License</th>
                            <th>Privilege Risk ▼</th><th>Efficiency</th>
                            <th>Last Active</th><th class="text-end pe-4">Cost</th>
                        </tr>
                    </thead>
                    <tbody>${riskyRows}</tbody>
                </table>
            </div>
        </div>
    </div>` : '';

    // ── Department Cost Allocation ────────────────────────────────────────────
    const deptEntries = Object.entries(depts)
        .sort((a,b) => b[1].cost - a[1].cost).slice(0,8);
    const maxDeptCost = deptEntries.length ? deptEntries[0][1].cost : 1;

    const deptRows = deptEntries.map(([dept, d]) => {
        const wasteRatio = d.cost > 0 ? Math.round((d.waste / d.cost) * 100) : 0;
        const barPct     = Math.round((d.cost / maxDeptCost) * 100);
        const wCol       = wasteRatio >= 40 ? '#dc3545' : wasteRatio >= 20 ? '#ffc107' : '#198754';
        return `
        <tr>
            <td class="py-2 ps-4 fw-semibold small">${escapeHtml(dept)}</td>
            <td class="py-2 small text-muted text-center">${d.count}</td>
            <td class="py-2">
                <div class="d-flex align-items-center gap-2">
                    <div class="progress flex-grow-1" style="height:8px;border-radius:4px">
                        <div class="progress-bar bg-primary" style="width:${barPct}%"></div>
                    </div>
                    <span class="small fw-bold" style="width:60px;text-align:right">$${d.cost.toLocaleString()}</span>
                </div>
            </td>
            <td class="py-2 text-end pe-4">
                <span class="badge rounded-pill" style="background:${wCol}20;color:${wCol};font-weight:600">${wasteRatio}% waste</span>
            </td>
        </tr>`;
    }).join('');

    const deptCard = deptEntries.length > 0 ? `
    <div class="card border-0 shadow-sm mb-4" style="border-radius:12px">
        <div class="card-header border-0 py-3 px-4" style="background:rgba(13,110,253,0.07);border-radius:12px 12px 0 0">
            <h6 class="mb-0 fw-bold text-primary"><i class="bi bi-building me-2"></i>Department Cost Allocation</h6>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover mb-0" style="font-size:.88rem">
                    <thead class="table-light">
                        <tr><th class="ps-4">Department</th><th class="text-center">Users</th><th>Monthly Cost</th><th class="text-end pe-4">Waste %</th></tr>
                    </thead>
                    <tbody>${deptRows}</tbody>
                </table>
            </div>
        </div>
    </div>` : '';

    // ── Duplicate Accounts ────────────────────────────────────────────────────
    const dupCard = dups.length > 0 ? `
    <div class="card border-0 shadow-sm mb-4" style="border-radius:12px">
        <div class="card-header border-0 py-3 px-4" style="background:rgba(255,193,7,0.1);border-radius:12px 12px 0 0">
            <h6 class="mb-0 fw-bold text-warning"><i class="bi bi-files me-2"></i>Duplicate Accounts Detected — ${dups.length} emails</h6>
        </div>
        <div class="card-body p-3">
            <div class="row g-2">
                ${dups.slice(0,12).map(d => `
                <div class="col-md-4">
                    <div class="d-flex align-items-center gap-2 p-2 rounded-3 bg-warning bg-opacity-10">
                        <i class="bi bi-exclamation-triangle-fill text-warning"></i>
                        <div>
                            <div class="small fw-semibold">${escapeHtml(d.email)}</div>
                            <div style="font-size:.72rem;color:#6c757d">${d.account_count} accounts</div>
                        </div>
                    </div>
                </div>`).join('')}
            </div>
        </div>
    </div>` : '';

    // ── Automation Status ─────────────────────────────────────────────────────
    const autoCard = `
    <div class="card border-0 shadow-sm mb-4" style="border-radius:12px">
        <div class="card-header border-0 py-3 px-4" style="background:rgba(32,201,151,0.08);border-radius:12px 12px 0 0">
            <h6 class="mb-0 fw-bold" style="color:#20c997"><i class="bi bi-robot me-2"></i>Layer 9 — Automation Engine Status</h6>
        </div>
        <div class="card-body p-4">
            <div class="row g-3">
                <div class="col-md-4">
                    <div class="d-flex align-items-center gap-3 p-3 rounded-3" style="background:rgba(32,201,151,0.08)">
                        <i class="bi bi-check-circle-fill fs-3" style="color:#20c997"></i>
                        <div>
                            <div class="fw-bold" style="color:#20c997">Ready</div>
                            <div class="small text-muted">Automation engine online</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="d-flex align-items-center gap-3 p-3 rounded-3" style="background:rgba(13,110,253,0.08)">
                        <i class="bi bi-hourglass-split fs-3 text-primary"></i>
                        <div>
                            <div class="fw-bold text-primary">${auto.pending_approvals || 0} actions</div>
                            <div class="small text-muted">Awaiting approval (≥80% conf.)</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="d-flex align-items-center gap-3 p-3 rounded-3" style="background:rgba(25,135,84,0.08)">
                        <i class="bi bi-lightning-charge-fill fs-3 text-success"></i>
                        <div>
                            <div class="fw-bold text-success">${auto.auto_eligible || 0} auto-eligible</div>
                            <div class="small text-muted">Can run without approval (≥95%)</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="mt-3 p-3 rounded-3" style="background:#f8f9fa;font-size:.85rem">
                <strong><i class="bi bi-info-circle text-primary me-1"></i>Available Automation Actions:</strong>
                ${(auto.actions_available || []).map(a =>
                    `<span class="badge bg-secondary bg-opacity-10 text-secondary me-1 mt-1">${a}</span>`
                ).join('')}
            </div>
        </div>
    </div>`;

    // ── AI Executive Summary ──────────────────────────────────────────────────
    const aiCard = ai ? `
    <div class="card border-0 shadow-sm" style="border-radius:12px">
        <div class="card-header border-0 py-3 px-4" style="background:rgba(13,110,253,0.07);border-radius:12px 12px 0 0">
            <h6 class="mb-0 fw-bold text-primary"><i class="bi bi-robot me-2"></i>AI Executive Summary</h6>
        </div>
        <div class="card-body p-4">
            ${parseMarkdownIntoSections(ai).map(s =>
                `<div class="mb-3">
                    <h6 class="fw-bold" style="color:#0d6efd"><i class="bi ${s.meta.icon} me-2"></i>${escapeHtml(s.title)}</h6>
                    ${s.items.map(item => renderItem(item, '#0d6efd')).join('')}
                </div>`
            ).join('') || `<p class="text-muted">${escapeHtml(ai)}</p>`}
        </div>
    </div>` : '';

    // ── Last Login Audit — sys_user.last_login classification ────────────────
    const lla        = data.last_login_audit || {};
    const llaNever   = lla.never_logged_in  || [];
    const llaStale   = lla.stale_users      || [];
    const llaActive  = lla.active_users     || [];
    const llaTotalScanned = lla.total || 0;

    function llaDeactivateBtn(u, tag) {
        if (!u.sys_id || u.active === false || u.active === 'false') return '';
        const rowId   = `llarow_${escapeHtml(u.sys_id)}`;
        const btnId   = `deact_${rowId}`;
        const daysVal = u.days_since_login != null ? u.days_since_login : 9999;
        const reason  = tag === 'never'
            ? 'User has never logged in to ServiceNow.'
            : `User last logged in ${u.last_login_label} — over 1 year ago (${daysVal} days).`;
        return `<button class="deactivate-btn" style="padding:2px 10px;font-size:.72rem"
            id="${btnId}"
            onclick="deactivateUser(${JSON.stringify(u.sys_id)}, ${JSON.stringify(u.name)}, ${JSON.stringify(u.email||'')}, ${daysVal}, ${JSON.stringify(reason)}, '${rowId}')"
            title="Deactivate this user in ServiceNow">
            <i class="bi bi-person-x-fill me-1"></i>Deactivate
        </button>`;
    }

    function llaActiveStatus(u) {
        if (u.active === false || u.active === 'false') {
            return `<span class="badge rounded-pill" style="background:#6c757d20;color:#6c757d;font-weight:600;font-size:.7rem"><i class="bi bi-circle me-1"></i>Inactive</span>`;
        }
        return `<span class="badge rounded-pill" style="background:#19875420;color:#198754;font-weight:600;font-size:.7rem"><i class="bi bi-circle-fill me-1"></i>Active</span>`;
    }

    // Build rows for each group
    function llaRows(users, tag) {
        return users.slice(0, 100).map(u => {
            const loginDisp = u.last_login_label === 'Never'
                ? `<span style="color:#dc3545;font-weight:600">Never logged in</span>`
                : `<span style="color:#fd7e14;font-weight:600">${escapeHtml(u.last_login_label)}</span>
                   <span class="text-muted" style="font-size:.68rem"> (${u.days_since_login}d ago)</span>`;
            const rowId2 = `llarow_${escapeHtml(u.sys_id)}`;
            return `<tr id="${rowId2}">
                <td class="py-2 ps-3">
                    <div class="fw-semibold small">${escapeHtml(u.name)}</div>
                    <div class="text-muted" style="font-size:.7rem">${escapeHtml(u.user_name)}</div>
                </td>
                <td class="py-2 small">${escapeHtml(u.email || '—')}</td>
                <td class="py-2">${loginDisp}</td>
                <td class="py-2">${llaActiveStatus(u)}</td>
                <td class="py-2 text-end pe-3">${llaDeactivateBtn(u, tag)}</td>
            </tr>`;
        }).join('');
    }

    // Active users sub-table
    function llaActiveRows(users) {
        return users.slice(0, 100).map(u => {
            const dVal = u.days_since_login != null ? u.days_since_login : 0;
            const pill = dVal < 30
                ? `<span class="act-pill active"><i class="bi bi-activity me-1"></i>${dVal}d ago</span>`
                : dVal < 180
                ? `<span class="act-pill warning"><i class="bi bi-clock me-1"></i>${dVal}d ago</span>`
                : `<span class="act-pill warning"><i class="bi bi-exclamation-circle me-1"></i>${dVal}d ago</span>`;
            return `<tr>
                <td class="py-2 ps-3">
                    <div class="fw-semibold small">${escapeHtml(u.name)}</div>
                    <div class="text-muted" style="font-size:.7rem">${escapeHtml(u.user_name)}</div>
                </td>
                <td class="py-2 small">${escapeHtml(u.email || '—')}</td>
                <td class="py-2">${pill}</td>
                <td class="py-2">${llaActiveStatus(u)}</td>
                <td class="py-2 text-end pe-3 text-muted" style="font-size:.75rem">${escapeHtml(u.last_login_label || '—')}</td>
            </tr>`;
        }).join('');
    }

    const llaCard = llaTotalScanned > 0 ? `
    <div class="card border-0 shadow-sm mb-4" style="border-radius:12px">
        <div class="card-header border-0 py-3 px-4" style="background:rgba(220,53,69,0.07);border-radius:12px 12px 0 0">
            <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
                <h6 class="mb-0 fw-bold text-danger">
                    <i class="bi bi-calendar-x-fill me-2"></i>Last Login Audit — sys_user.last_login
                </h6>
                <div class="d-flex gap-2 flex-wrap">
                    <span class="badge rounded-pill" style="background:#19875420;color:#198754;font-weight:600">
                        <i class="bi bi-check-circle-fill me-1"></i>${llaActive.length} Active (< 1yr)
                    </span>
                    <span class="badge rounded-pill" style="background:#fd7e1420;color:#fd7e14;font-weight:600">
                        <i class="bi bi-clock-fill me-1"></i>${llaStale.length} Stale (> 1yr)
                    </span>
                    <span class="badge rounded-pill" style="background:#dc354520;color:#dc3545;font-weight:600">
                        <i class="bi bi-x-circle-fill me-1"></i>${llaNever.length} Never Logged In
                    </span>
                </div>
            </div>
        </div>
        <div class="card-body p-0">
            <!-- Nav tabs -->
            <ul class="nav nav-tabs px-3 pt-2 border-0" style="background:#fafbfc;border-radius:0" id="llaTabs">
                <li class="nav-item">
                    <button class="nav-link active fw-semibold" style="font-size:.82rem"
                        onclick="llaShowTab(event,'llaTabNever')">
                        <i class="bi bi-x-circle-fill text-danger me-1"></i>
                        Never Logged In <span class="badge bg-danger ms-1">${llaNever.length}</span>
                    </button>
                </li>
                <li class="nav-item">
                    <button class="nav-link fw-semibold" style="font-size:.82rem"
                        onclick="llaShowTab(event,'llaTabStale')">
                        <i class="bi bi-clock-fill me-1" style="color:#fd7e14"></i>
                        Stale &gt; 1 Year <span class="badge ms-1" style="background:#fd7e14">${llaStale.length}</span>
                    </button>
                </li>
                <li class="nav-item">
                    <button class="nav-link fw-semibold" style="font-size:.82rem"
                        onclick="llaShowTab(event,'llaTabActive')">
                        <i class="bi bi-check-circle-fill text-success me-1"></i>
                        Active Users <span class="badge bg-success ms-1">${llaActive.length}</span>
                    </button>
                </li>
            </ul>

            <!-- Never logged in -->
            <div id="llaTabNever" class="lla-tab-pane">
                ${llaNever.length === 0
                    ? `<div class="text-center text-muted p-4"><i class="bi bi-check-circle fs-3 text-success d-block mb-2"></i>No users without a login record.</div>`
                    : `<div class="table-responsive">
                        <table class="table table-hover mb-0" style="font-size:.83rem">
                            <thead class="table-light">
                                <tr>
                                    <th class="ps-3">User</th>
                                    <th>Email</th>
                                    <th>Last Login</th>
                                    <th>Status</th>
                                    <th class="text-end pe-3">Action</th>
                                </tr>
                            </thead>
                            <tbody>${llaRows(llaNever, 'never')}</tbody>
                        </table>
                       </div>
                       ${llaNever.length > 100 ? `<div class="text-center text-muted py-2" style="font-size:.78rem">Showing 100 of ${llaNever.length}</div>` : ''}`
                }
            </div>

            <!-- Stale > 1yr -->
            <div id="llaTabStale" class="lla-tab-pane" style="display:none">
                ${llaStale.length === 0
                    ? `<div class="text-center text-muted p-4"><i class="bi bi-check-circle fs-3 text-success d-block mb-2"></i>No stale users found.</div>`
                    : `<div class="table-responsive">
                        <table class="table table-hover mb-0" style="font-size:.83rem">
                            <thead class="table-light">
                                <tr>
                                    <th class="ps-3">User</th>
                                    <th>Email</th>
                                    <th>Last Login</th>
                                    <th>Status</th>
                                    <th class="text-end pe-3">Action</th>
                                </tr>
                            </thead>
                            <tbody>${llaRows(llaStale, 'stale')}</tbody>
                        </table>
                       </div>
                       ${llaStale.length > 100 ? `<div class="text-center text-muted py-2" style="font-size:.78rem">Showing 100 of ${llaStale.length}</div>` : ''}`
                }
            </div>

            <!-- Active users -->
            <div id="llaTabActive" class="lla-tab-pane" style="display:none">
                ${llaActive.length === 0
                    ? `<div class="text-center text-muted p-4"><i class="bi bi-info-circle fs-3 d-block mb-2"></i>No active users found.</div>`
                    : `<div class="table-responsive">
                        <table class="table table-hover mb-0" style="font-size:.83rem">
                            <thead class="table-light">
                                <tr>
                                    <th class="ps-3">User</th>
                                    <th>Email</th>
                                    <th>Last Login Activity</th>
                                    <th>Status</th>
                                    <th class="text-end pe-3">Last Login Date</th>
                                </tr>
                            </thead>
                            <tbody>${llaActiveRows(llaActive)}</tbody>
                        </table>
                       </div>
                       ${llaActive.length > 100 ? `<div class="text-center text-muted py-2" style="font-size:.78rem">Showing 100 of ${llaActive.length}</div>` : ''}`
                }
            </div>
        </div>
    </div>` : '';

    return kpiRow + finRow + savingsBreakdown + decisionsCard + riskyCard + llaCard + deptCard + dupCard + autoCard + aiCard;
}

// ===== RENDER: RUN ALL =====
function renderRunAll(data) {
    if (data.error) return renderError(data.error);

    const cards = Object.entries(data).map(([key, value]) => {
        const meta = AGENT_META[key] || { icon: 'bi-robot', color: 'primary', label: key };
        const col = COLOR_MAP[meta.color] || COLOR_MAP.primary;
        const analysis = typeof value === 'object' ? (value.analysis || JSON.stringify(value, null, 2)) : String(value);
        const riskScore = extractRiskScore(analysis);
        const riskColor = riskScore !== null ? (riskScore >= 70 ? 'danger' : riskScore >= 40 ? 'warning' : 'success') : 'secondary';
        const riskLabel = riskScore !== null ? `Risk: ${riskScore}/100` : 'Completed';

        // Get first meaningful paragraph as preview
        const previewText = analysis.split('\n').find(l => l.trim().length > 40 && !l.startsWith('#')) || analysis.slice(0, 200);
        const previewHtml = renderMarkdown(escapeHtml(previewText.slice(0, 220) + (previewText.length > 220 ? '...' : '')));

        return `
        <div class="card border-0 shadow-sm mb-3" style="border-radius:12px">
            <div class="card-header border-0 d-flex align-items-center justify-content-between py-3 px-4"
                 style="background:${col.light};border-radius:12px 12px 0 0">
                <div class="d-flex align-items-center gap-2">
                    <i class="bi ${meta.icon} fs-5" style="color:${col.bg}"></i>
                    <span class="fw-bold" style="color:${col.bg}">${meta.label}</span>
                </div>
                <span class="badge bg-${riskColor}">${riskLabel}</span>
            </div>
            <div class="card-body px-4 py-3">
                <p class="mb-0 text-muted" style="font-size:.9rem;line-height:1.6">${previewHtml}</p>
            </div>
        </div>`;
    });

    return `<div>${cards.join('')}</div>`;
}

// ===== RENDER: ERROR =====
function renderError(msg) {
    return `
    <div class="card border-0 shadow-sm" style="border-radius:12px;overflow:hidden">
        <div class="card-body p-4 text-center">
            <i class="bi bi-exclamation-triangle-fill text-danger fs-1 mb-3 d-block"></i>
            <h5 class="fw-bold text-danger">Something went wrong</h5>
            <p class="text-muted mb-0">${escapeHtml(msg || 'Unknown error occurred')}</p>
        </div>
    </div>`;
}

// ===== HELPERS =====

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Convert raw markdown text to clean HTML
function renderMarkdown(text) {
    if (!text) return '';
    let t = escapeHtml(text);

    // Bold: **text** or __text__
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    // Italic: *text* or _text_
    t = t.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    // Inline code: `code`
    t = t.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    return t;
}

function extractRiskScore(text) {
    if (!text) return null;
    const match = text.match(/risk\s*score[:\s]*(\d{1,3})/i) ||
                  text.match(/overall\s*risk[:\s]*(\d{1,3})/i) ||
                  text.match(/score[:\s]*(\d{1,3})\s*\/\s*100/i) ||
                  text.match(/(\d{1,3})\s*\/\s*100/);
    if (match) {
        const n = parseInt(match[1]);
        if (n >= 0 && n <= 100) return n;
    }
    return null;
}

// Parse markdown into structured sections
function parseMarkdownIntoSections(text) {
    if (!text || typeof text !== 'string') return [];

    const lines = text.split('\n');
    const sections = [];
    let currentSection = null;
    let currentItems = [];

    const SECTION_ICONS = {
        'risk': { icon: 'bi-exclamation-triangle-fill', color: 'danger' },
        'issue': { icon: 'bi-exclamation-triangle-fill', color: 'danger' },
        'critical': { icon: 'bi-exclamation-octagon-fill', color: 'danger' },
        'recommend': { icon: 'bi-lightbulb-fill', color: 'warning' },
        'fix': { icon: 'bi-wrench-adjustable-circle-fill', color: 'success' },
        'action': { icon: 'bi-lightning-fill', color: 'primary' },
        'implement': { icon: 'bi-gear-fill', color: 'primary' },
        'overview': { icon: 'bi-info-circle-fill', color: 'info' },
        'summary': { icon: 'bi-card-text', color: 'info' },
        'specific': { icon: 'bi-list-check', color: 'secondary' },
        'roadmap': { icon: 'bi-map-fill', color: 'purple' },
        'short': { icon: 'bi-clock-fill', color: 'warning' },
        'long': { icon: 'bi-calendar-check-fill', color: 'teal' },
        'immediate': { icon: 'bi-alarm-fill', color: 'danger' },
        'table': { icon: 'bi-table', color: 'secondary' },
        'assessment': { icon: 'bi-clipboard2-data-fill', color: 'primary' },
        'top': { icon: 'bi-bar-chart-fill', color: 'danger' },
    };

    function getSectionMeta(title) {
        const lower = title.toLowerCase();
        for (const [key, val] of Object.entries(SECTION_ICONS)) {
            if (lower.includes(key)) return val;
        }
        return { icon: 'bi-card-list', color: 'secondary' };
    }

    function pushSection() {
        if (currentSection && currentItems.length > 0) {
            sections.push({ title: currentSection, items: [...currentItems], meta: getSectionMeta(currentSection) });
        }
        currentItems = [];
    }

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        // H1 heading: # Title
        if (/^#\s+/.test(line)) {
            pushSection();
            currentSection = line.replace(/^#+\s*/, '').trim();
            continue;
        }
        // H2 heading: ## Title
        if (/^##\s+/.test(line)) {
            pushSection();
            currentSection = line.replace(/^#+\s*/, '').trim();
            continue;
        }
        // H3 heading: ### Title
        if (/^###\s+/.test(line)) {
            pushSection();
            currentSection = line.replace(/^#+\s*/, '').trim();
            continue;
        }

        // Numbered list item: "1. **Title** - detail"
        if (/^\d+\.\s/.test(line)) {
            currentItems.push({ type: 'numbered', text: line.replace(/^\d+\.\s*/, '').trim() });
            continue;
        }

        // Bullet list: "- item" or "* item"
        if (/^[-*•]\s/.test(line)) {
            currentItems.push({ type: 'bullet', text: line.replace(/^[-*•]\s*/, '').trim() });
            continue;
        }

        // Regular paragraph
        if (line.length > 5) {
            currentItems.push({ type: 'paragraph', text: line });
        }
    }
    pushSection();

    // If nothing parsed with headings, fall back to a single section
    if (!sections.length && text.trim()) {
        const fallback = [];
        lines.forEach(l => {
            const t = l.trim();
            if (!t) return;
            if (/^\d+\.\s/.test(t)) fallback.push({ type: 'numbered', text: t.replace(/^\d+\.\s*/, '') });
            else if (/^[-*•]\s/.test(t)) fallback.push({ type: 'bullet', text: t.replace(/^[-*•]\s*/, '') });
            else if (t.length > 5) fallback.push({ type: 'paragraph', text: t });
        });
        if (fallback.length) sections.push({ title: 'Analysis', items: fallback, meta: { icon: 'bi-bar-chart-fill', color: 'primary' } });
    }

    return sections;
}

// Render a single item (numbered/bullet/paragraph) as formatted HTML
function renderItem(item, colBg) {
    const html = renderMarkdown(item.text);

    if (item.type === 'numbered') {
        // Try to split "Title - rest" at first " - "
        const dashIdx = item.text.indexOf(' - ');
        if (dashIdx > 0 && item.text.startsWith('**')) {
            const titleRaw = item.text.slice(0, dashIdx).trim();
            const rest = item.text.slice(dashIdx + 3).trim();
            const titleHtml = renderMarkdown(titleRaw);
            const restHtml = renderMarkdown(rest);
            return `<div class="numbered-item mb-3">
                        <div class="numbered-title">${titleHtml}</div>
                        <div class="numbered-body">${restHtml}</div>
                    </div>`;
        }
        return `<div class="numbered-item mb-2"><div class="numbered-body">${html}</div></div>`;
    }

    if (item.type === 'bullet') {
        return `<div class="bullet-item mb-2">
                    <i class="bi bi-check2-circle bullet-icon" style="color:${colBg}"></i>
                    <span>${html}</span>
                </div>`;
    }

    // paragraph
    return `<p class="analysis-para">${html}</p>`;
}

// ===== GENERATE REPORT =====
function generateReport() {
    const btn = event && event.target ? event.target.closest('button') : null;
    let origHTML = '';
    if (btn) {
        origHTML = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Starting...';
    }

    fetch('/generate-report')
        .then(r => r.json())
        .then(data => {
            if (!data.job_id) {
                alert('Failed to start report generation.');
                if (btn) { btn.disabled = false; btn.innerHTML = origHTML; }
                return;
            }
            const jobId = data.job_id;
            if (btn) btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Generating...';

            // Poll every 3 seconds
            const poll = setInterval(() => {
                fetch(`/report-status/${jobId}`)
                    .then(r => r.json())
                    .then(status => {
                        if (status.status === 'done') {
                            clearInterval(poll);
                            if (btn) { btn.disabled = false; btn.innerHTML = origHTML; }
                            window.location.href = `/download-report/${jobId}`;
                        } else if (status.status === 'error') {
                            clearInterval(poll);
                            if (btn) { btn.disabled = false; btn.innerHTML = origHTML; }
                            alert('Report generation failed: ' + (status.error || 'Unknown error'));
                        }
                        // else still pending — keep polling
                    })
                    .catch(() => {
                        clearInterval(poll);
                        if (btn) { btn.disabled = false; btn.innerHTML = origHTML; }
                        alert('Error checking report status.');
                    });
            }, 3000);
        })
        .catch(() => {
            if (btn) { btn.disabled = false; btn.innerHTML = origHTML; }
            alert('Failed to connect to server.');
        });
}

// ===== CFO DASHBOARD =====
function loadCFODashboard() {
    showAnalysis();

    const agentHeader = document.getElementById('agentHeader');
    if (agentHeader) {
        agentHeader.innerHTML = `
        <div class="d-flex align-items-center gap-3 mb-1">
            <div class="p-2 rounded-3" style="background:rgba(25,135,84,0.1)">
                <i class="bi bi-bar-chart-line fs-4 text-success"></i>
            </div>
            <div>
                <h4 class="mb-0 fw-bold">CFO Executive Dashboard</h4>
                <small class="text-muted">All-agent risk scores, financial overview & optimization insights</small>
            </div>
        </div>`;
    }

    const output = document.getElementById('analysisOutput');
    if (!output) return;
    output.innerHTML = '';
    startLoading();

    fetch('/dashboard/cfo')
        .then(r => r.json())
        .then(data => {
            stopLoading();
            if (data.error) { output.innerHTML = renderError(data.error); return; }
            output.innerHTML = buildCFOUI(data);
            renderAllCharts(data);
        })
        .catch(err => {
            stopLoading();
            output.innerHTML = renderError(err.message);
        });
}

// ─── CFO UI BUILDER ───────────────────────────────────────────────────────────
function buildCFOUI(data) {
    const kpis         = data.kpis         || {};
    const agentScores  = data.agent_scores  || [];
    const charts       = data.charts        || {};

    const overallRisk  = kpis.overall_risk  || 0;
    const riskBg       = overallRisk >= 70 ? '#dc3545' : overallRisk >= 40 ? '#ffc107' : '#198754';
    const riskLabel    = overallRisk >= 70 ? 'High Risk' : overallRisk >= 40 ? 'Medium Risk' : 'Low Risk';

    // ── Row 1: Top KPI cards ──────────────────────────────────────────────────
    const kpiRow = `
    <div class="row g-3 mb-4">
        <div class="col-md-3 col-sm-6">
            <div class="cfo-kpi-card text-white" style="border-radius:14px;padding:1.25rem;background:linear-gradient(135deg,${riskBg},${riskBg}cc)">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <div class="small opacity-75 fw-semibold mb-1">Overall Risk Score</div>
                        <div class="display-6 fw-bold">${overallRisk}/100</div>
                        <span class="badge bg-white bg-opacity-25 mt-1">${riskLabel}</span>
                    </div>
                    <i class="bi bi-shield-exclamation fs-1 opacity-25"></i>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6">
            <div class="cfo-kpi-card text-white" style="border-radius:14px;padding:1.25rem;background:linear-gradient(135deg,#6f42c1,#563d7c)">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <div class="small opacity-75 fw-semibold mb-1">Current Monthly Cost</div>
                        <div class="display-6 fw-bold">$${(kpis.current_cost||0).toLocaleString()}</div>
                        <div class="small opacity-75 mt-1">${(kpis.total_users||0).toLocaleString()} licensed users</div>
                    </div>
                    <i class="bi bi-credit-card fs-1 opacity-25"></i>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6">
            <div class="cfo-kpi-card text-white" style="border-radius:14px;padding:1.25rem;background:linear-gradient(135deg,#198754,#157347)">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <div class="small opacity-75 fw-semibold mb-1">Monthly Savings Potential</div>
                        <div class="display-6 fw-bold">$${(kpis.monthly_savings||0).toLocaleString()}</div>
                        <div class="small opacity-75 mt-1">$${(kpis.annual_savings||0).toLocaleString()} annually</div>
                    </div>
                    <i class="bi bi-piggy-bank fs-1 opacity-25"></i>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6">
            <div class="cfo-kpi-card text-white" style="border-radius:14px;padding:1.25rem;background:linear-gradient(135deg,#0d6efd,#0a58ca)">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <div class="small opacity-75 fw-semibold mb-1">Optimized Monthly Cost</div>
                        <div class="display-6 fw-bold">$${(kpis.optimized_cost||0).toLocaleString()}</div>
                        <div class="small opacity-75 mt-1">${kpis.inactive_users||0} inactive · ${kpis.wasted_licenses||0} wasted</div>
                    </div>
                    <i class="bi bi-graph-down-arrow fs-1 opacity-25"></i>
                </div>
            </div>
        </div>
    </div>`;

    // ── Row 2: Risk summary badges ────────────────────────────────────────────
    const riskSummaryRow = `
    <div class="row g-3 mb-4">
        <div class="col-md-4">
            <div class="card border-0 shadow-sm p-3 d-flex flex-row align-items-center gap-3" style="border-radius:12px;border-left:4px solid #dc3545 !important">
                <div class="rounded-circle d-flex align-items-center justify-content-center bg-danger bg-opacity-10" style="width:48px;height:48px;flex-shrink:0">
                    <i class="bi bi-exclamation-triangle-fill text-danger fs-5"></i>
                </div>
                <div>
                    <div class="fs-3 fw-bold text-danger">${kpis.high_risk_agents||0}</div>
                    <div class="small text-muted fw-semibold">High Risk Agents (≥70)</div>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card border-0 shadow-sm p-3 d-flex flex-row align-items-center gap-3" style="border-radius:12px;border-left:4px solid #ffc107 !important">
                <div class="rounded-circle d-flex align-items-center justify-content-center bg-warning bg-opacity-10" style="width:48px;height:48px;flex-shrink:0">
                    <i class="bi bi-dash-circle-fill text-warning fs-5"></i>
                </div>
                <div>
                    <div class="fs-3 fw-bold text-warning">${kpis.med_risk_agents||0}</div>
                    <div class="small text-muted fw-semibold">Medium Risk Agents (40–69)</div>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card border-0 shadow-sm p-3 d-flex flex-row align-items-center gap-3" style="border-radius:12px;border-left:4px solid #198754 !important">
                <div class="rounded-circle d-flex align-items-center justify-content-center bg-success bg-opacity-10" style="width:48px;height:48px;flex-shrink:0">
                    <i class="bi bi-check-circle-fill text-success fs-5"></i>
                </div>
                <div>
                    <div class="fs-3 fw-bold text-success">${kpis.low_risk_agents||0}</div>
                    <div class="small text-muted fw-semibold">Low Risk Agents (&lt;40)</div>
                </div>
            </div>
        </div>
    </div>`;

    // ── Row 3: All Agent Score Cards ─────────────────────────────────────────
    const agentIconMap = {
        architecture:         { icon: 'bi-diagram-3',       color: '#0d6efd' },
        scripts:              { icon: 'bi-file-code',        color: '#0dcaf0' },
        performance:          { icon: 'bi-speedometer2',     color: '#198754' },
        security:             { icon: 'bi-shield-lock',      color: '#dc3545' },
        integration:          { icon: 'bi-plugin',           color: '#ffc107' },
        data_health:          { icon: 'bi-heart-pulse',      color: '#d63384' },
        upgrade:              { icon: 'bi-arrow-up-circle',  color: '#20c997' },
        license_optimization: { icon: 'bi-key',              color: '#6f42c1' },
    };

    const agentCards = agentScores.map(a => {
        const score    = a.score;
        const pct      = score !== null ? score : 0;
        const barCol   = pct >= 70 ? '#dc3545' : pct >= 40 ? '#ffc107' : '#198754';
        const badgeCls = pct >= 70 ? 'danger' : pct >= 40 ? 'warning' : 'success';
        const lbl      = pct >= 70 ? 'High' : pct >= 40 ? 'Medium' : 'Low';
        const meta     = agentIconMap[a.key] || { icon: 'bi-robot', color: '#6c757d' };
        const scoreStr = score !== null ? score : '—';

        return `
        <div class="col-md-3 col-sm-6">
            <div class="card border-0 shadow-sm h-100" style="border-radius:14px;cursor:pointer;transition:transform 0.2s,box-shadow 0.2s"
                 onmouseover="this.style.transform='translateY(-3px)';this.style.boxShadow='0 8px 24px rgba(0,0,0,0.12)'"
                 onmouseout="this.style.transform='';this.style.boxShadow=''"
                 onclick="callAgent('${a.key.replace('_','-')}')">
                <div class="card-body p-3">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <div class="rounded-3 d-flex align-items-center justify-content-center"
                                 style="width:38px;height:38px;background:${meta.color}18;flex-shrink:0">
                                <i class="bi ${meta.icon}" style="color:${meta.color};font-size:1.1rem"></i>
                            </div>
                            <div class="fw-semibold small">${a.label}</div>
                        </div>
                        <span class="badge bg-${badgeCls} bg-opacity-${pct >= 70 ? '100' : '75'}">${lbl}</span>
                    </div>
                    <div class="d-flex align-items-end justify-content-between mb-2">
                        <div class="fs-2 fw-bold" style="color:${barCol};line-height:1">${scoreStr}</div>
                        <div class="text-muted" style="font-size:0.75rem">/ 100</div>
                    </div>
                    <div class="progress" style="height:6px;border-radius:4px;background:#e9ecef">
                        <div class="progress-bar" style="width:${pct}%;background:${barCol};border-radius:4px;transition:width 1s ease"></div>
                    </div>
                    <div class="text-muted mt-2" style="font-size:0.72rem">${a.records ? a.records.toLocaleString() + ' records' : 'Click to analyze'}</div>
                </div>
            </div>
        </div>`;
    }).join('');

    const agentScoreSection = `
    <div class="mb-2 d-flex align-items-center gap-2">
        <i class="bi bi-grid-3x3-gap-fill text-primary"></i>
        <h6 class="fw-bold mb-0">All Agent Risk Scores</h6>
        <span class="badge bg-primary bg-opacity-10 text-primary ms-1">${agentScores.length} agents</span>
    </div>
    <div class="row g-3 mb-4">${agentCards}</div>`;

    // ── Row 4: Charts row ─────────────────────────────────────────────────────
    const chartsRow = `
    <div class="row g-4 mb-4">
        <div class="col-md-5">
            <div class="card border-0 shadow-sm p-4" style="border-radius:14px">
                <h6 class="fw-bold mb-3"><i class="bi bi-radar me-2 text-primary"></i>Risk Radar — All Agents</h6>
                <canvas id="radarChart" height="260"></canvas>
            </div>
        </div>
        <div class="col-md-7">
            <div class="card border-0 shadow-sm p-4" style="border-radius:14px">
                <h6 class="fw-bold mb-3"><i class="bi bi-bar-chart-fill me-2 text-danger"></i>Agent Risk Score Comparison</h6>
                <canvas id="agentBarChart" height="180"></canvas>
            </div>
        </div>
    </div>`;

    // ── Row 5: Financial charts ───────────────────────────────────────────────
    const financialRow = `
    <div class="row g-4">
        <div class="col-md-5">
            <div class="card border-0 shadow-sm p-4" style="border-radius:14px">
                <h6 class="fw-bold mb-3"><i class="bi bi-pie-chart-fill me-2 text-success"></i>License Distribution</h6>
                <canvas id="licenseDonut" height="200"></canvas>
            </div>
        </div>
        <div class="col-md-7">
            <div class="card border-0 shadow-sm p-4" style="border-radius:14px">
                <h6 class="fw-bold mb-3"><i class="bi bi-currency-dollar me-2 text-success"></i>Cost Analysis</h6>
                <canvas id="costChart" height="160"></canvas>
            </div>
        </div>
    </div>`;

    return kpiRow + riskSummaryRow + agentScoreSection + chartsRow + financialRow;
}

// ─── CHART RENDERER ───────────────────────────────────────────────────────────
function renderAllCharts(data) {
    const kpis        = data.kpis        || {};
    const charts      = data.charts      || {};
    const agentScores = data.agent_scores || [];

    const radarLabels = (charts.risk_radar && charts.risk_radar.labels) || agentScores.map(a => a.label);
    const radarValues = (charts.risk_radar && charts.risk_radar.values) || agentScores.map(a => a.score || 0);

    // Radar chart
    const radarCtx = document.getElementById('radarChart');
    if (radarCtx) {
        new Chart(radarCtx, {
            type: 'radar',
            data: {
                labels: radarLabels,
                datasets: [{
                    label: 'Risk Score',
                    data: radarValues,
                    backgroundColor: 'rgba(220,53,69,0.15)',
                    borderColor: '#dc3545',
                    borderWidth: 2,
                    pointBackgroundColor: radarValues.map(v =>
                        v >= 70 ? '#dc3545' : v >= 40 ? '#ffc107' : '#198754'),
                    pointRadius: 5,
                }]
            },
            options: {
                responsive: true,
                scales: {
                    r: {
                        min: 0, max: 100,
                        ticks: { stepSize: 25, font: { size: 10 }, color: '#6c757d' },
                        grid: { color: 'rgba(0,0,0,0.06)' },
                        pointLabels: { font: { size: 11, weight: 'bold' }, color: '#343a40' },
                        angleLines: { color: 'rgba(0,0,0,0.06)' },
                    }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    // Horizontal bar chart — agent scores
    const barCtx = document.getElementById('agentBarChart');
    if (barCtx) {
        const sorted = [...agentScores].sort((a,b) => (b.score||0) - (a.score||0));
        new Chart(barCtx, {
            type: 'bar',
            data: {
                labels: sorted.map(a => a.label),
                datasets: [{
                    label: 'Risk Score',
                    data: sorted.map(a => a.score || 0),
                    backgroundColor: sorted.map(a => {
                        const s = a.score || 0;
                        return s >= 70 ? 'rgba(220,53,69,0.85)'
                             : s >= 40 ? 'rgba(255,193,7,0.85)'
                                       : 'rgba(25,135,84,0.85)';
                    }),
                    borderRadius: 6,
                    borderSkipped: false,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` Risk Score: ${ctx.raw}/100`
                        }
                    }
                },
                scales: {
                    x: { min: 0, max: 100, grid: { color: 'rgba(0,0,0,0.04)' },
                         ticks: { callback: v => v + '/100', font: { size: 10 } } },
                    y: { grid: { display: false }, ticks: { font: { size: 11, weight: 'bold' } } }
                }
            }
        });
    }

    // License donut
    const donutCtx = document.getElementById('licenseDonut');
    if (donutCtx) {
        const dist = charts.license_distribution || {};
        new Chart(donutCtx, {
            type: 'doughnut',
            data: {
                labels: dist.labels || ['Active', 'Inactive', 'Wasted', 'Over-licensed'],
                datasets: [{
                    data: dist.values || [0, kpis.inactive_users||0, kpis.wasted_licenses||0, kpis.overlicensed_users||0],
                    backgroundColor: ['#198754', '#dc3545', '#ffc107', '#6f42c1'],
                    borderWidth: 0,
                    hoverOffset: 6,
                }]
            },
            options: {
                responsive: true,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { padding: 16, font: { size: 11 } } },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.label}: ${ctx.raw.toLocaleString()} users`
                        }
                    }
                }
            }
        });
    }

    // Cost bar chart
    const costCtx = document.getElementById('costChart');
    if (costCtx) {
        const sc = charts.savings_chart || {};
        new Chart(costCtx, {
            type: 'bar',
            data: {
                labels: sc.labels || ['Current Cost', 'Optimized Cost', 'Monthly Savings'],
                datasets: [{
                    label: 'Amount (USD)',
                    data: sc.values || [kpis.current_cost||0, kpis.optimized_cost||0, kpis.monthly_savings||0],
                    backgroundColor: ['rgba(111,66,193,0.85)', 'rgba(13,110,253,0.85)', 'rgba(25,135,84,0.85)'],
                    borderRadius: 8,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` $${ctx.raw.toLocaleString()}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: v => '$' + v.toLocaleString(), font: { size: 10 } },
                        grid: { color: 'rgba(0,0,0,0.04)' }
                    },
                    x: { grid: { display: false }, ticks: { font: { size: 11, weight: 'bold' } } }
                }
            }
        });
    }
}

// ============================================================
// FIX IT — Error panel with script type/name + SSE streaming
// ============================================================

const SEV_META = {
    critical: { bg: '#dc3545', light: 'rgba(220,53,69,0.09)', icon: 'bi-exclamation-octagon-fill', label: 'CRITICAL' },
    high:     { bg: '#fd7e14', light: 'rgba(253,126,20,0.09)',  icon: 'bi-exclamation-triangle-fill', label: 'HIGH' },
    medium:   { bg: '#ffc107', light: 'rgba(255,193,7,0.09)',   icon: 'bi-dash-circle-fill',           label: 'MEDIUM' },
    low:      { bg: '#20c997', light: 'rgba(32,201,151,0.09)',  icon: 'bi-info-circle-fill',           label: 'LOW' },
};

const SCRIPT_TYPE_ICONS = {
    'Business Rule':     { icon: 'bi-file-code-fill',   color: '#0d6efd' },
    'Client Script':     { icon: 'bi-browser-chrome',   color: '#fd7e14' },
    'Script Include':    { icon: 'bi-box-fill',          color: '#6f42c1' },
    'UI Action':         { icon: 'bi-cursor-fill',       color: '#20c997' },
    'UI Policy':         { icon: 'bi-layout-text-window-reverse', color: '#0dcaf0' },
    'Script Processor':  { icon: 'bi-cpu-fill',          color: '#dc3545' },
    'Scheduled Script':  { icon: 'bi-clock-fill',        color: '#ffc107' },
    'ACL Rule':          { icon: 'bi-shield-lock-fill',  color: '#dc3545' },
    'Transaction Log':   { icon: 'bi-graph-up',          color: '#198754' },
};

/**
 * Render the Errors & Issues panel.
 * Shows script type badge + name for each error.
 */
// ── Per-agent pagination state ────────────────────────────────────────────
const _errPages = {};   // agentName → { sorted: [], page: 0, perPage: 10 }
const PAGE_SIZE  = 10;

function _buildErrorRow(err, agentName) {
    const sm     = SEV_META[err.severity] || SEV_META.medium;
    const stMeta = SCRIPT_TYPE_ICONS[err.script_type] || { icon:'bi-file-code', color:'#6c757d' };
    const uid    = `err_${agentName}_${(err.id||Math.random().toString(36).slice(2))}`;
    const errEnc = encodeURIComponent(JSON.stringify(err));

    return `
    <div class="error-item" id="${uid}" data-err="${errEnc}">
        <div class="error-item-header">
            <div class="d-flex align-items-center gap-2 flex-grow-1 min-w-0 overflow-hidden">
                <span class="sev-badge" style="background:${sm.bg}18;color:${sm.bg};border:1px solid ${sm.bg}35;flex-shrink:0">
                    <i class="bi ${sm.icon}" style="font-size:.65rem"></i> ${sm.label}
                </span>
                ${err.script_type ? `
                <span class="script-type-badge" style="background:${stMeta.color}14;color:${stMeta.color};border:1px solid ${stMeta.color}30;flex-shrink:0">
                    <i class="bi ${stMeta.icon}" style="font-size:.65rem"></i> ${escapeHtml(err.script_type)}
                </span>` : ''}
                <div class="error-title-group min-w-0">
                    <span class="error-title">${escapeHtml(err.title)}</span>
                    ${err.script_name && err.script_name !== 'Unknown' && err.script_name !== 'Multiple' ? `
                    <span class="error-script-name">
                        <i class="bi bi-chevron-right" style="font-size:.6rem"></i>
                        ${escapeHtml(err.script_name)}
                    </span>` : ''}
                </div>
            </div>
            <div class="d-flex align-items-center gap-2 flex-shrink-0">
                <button class="fixit-main-btn" id="btn_${uid}"
                        onclick="triggerFixIt('${uid}','${agentName}')"
                        title="AI will fix this issue automatically">
                    <i class="bi bi-magic"></i><span> Fix It</span>
                </button>
                <button class="err-chevron-btn" onclick="toggleErrorDetail('${uid}')">
                    <i class="bi bi-chevron-down" id="chev_${uid}"></i>
                </button>
            </div>
        </div>
        <div class="error-detail d-none" id="detail_${uid}">
            <p class="error-desc">${escapeHtml(err.description)}</p>
            ${err.original_code ? `
            <div class="code-block">
                <div class="code-block-label"><i class="bi bi-code-slash me-1"></i>Problematic Code</div>
                <pre class="code-pre before-code"><code>${escapeHtml(err.original_code)}</code></pre>
            </div>` : ''}
        </div>
        <div class="fixit-output d-none" id="fixout_${uid}"></div>
    </div>`;
}

function _renderPagination(agentName) {
    const state    = _errPages[agentName];
    if (!state) return;
    const total    = state.sorted.length;
    const perPage  = state.perPage;
    const page     = state.page;
    const totalPgs = Math.ceil(total / perPage);
    if (totalPgs <= 1) {
        const pg = document.getElementById(`errPager_${agentName}`);
        if (pg) pg.innerHTML = '';
        return;
    }

    const start = page * perPage + 1;
    const end   = Math.min((page + 1) * perPage, total);
    const pgEl  = document.getElementById(`errPager_${agentName}`);
    if (!pgEl) return;

    // Build page buttons — show up to 7 around current page
    let btns = '';
    const maxBtns = 7;
    let startPg = Math.max(0, page - Math.floor(maxBtns / 2));
    let endPg   = Math.min(totalPgs - 1, startPg + maxBtns - 1);
    if (endPg - startPg < maxBtns - 1) startPg = Math.max(0, endPg - maxBtns + 1);

    if (startPg > 0)
        btns += `<button class="err-pg-btn err-pg-ellipsis" onclick="errGoPage('${agentName}',0)">1</button><span class="err-pg-dots">…</span>`;

    for (let i = startPg; i <= endPg; i++) {
        btns += `<button class="err-pg-btn${i===page?' active':''}" onclick="errGoPage('${agentName}',${i})">${i+1}</button>`;
    }

    if (endPg < totalPgs - 1)
        btns += `<span class="err-pg-dots">…</span><button class="err-pg-btn err-pg-ellipsis" onclick="errGoPage('${agentName}',${totalPgs-1})">${totalPgs}</button>`;

    pgEl.innerHTML = `
    <div class="err-pagination">
        <span class="err-pg-info">Showing <strong>${start}–${end}</strong> of <strong>${total}</strong> issues</span>
        <div class="err-pg-controls">
            <button class="err-pg-btn err-pg-nav" onclick="errGoPage('${agentName}',${page-1})" ${page===0?'disabled':''}>
                <i class="bi bi-chevron-left"></i>
            </button>
            ${btns}
            <button class="err-pg-btn err-pg-nav" onclick="errGoPage('${agentName}',${page+1})" ${page===totalPgs-1?'disabled':''}>
                <i class="bi bi-chevron-right"></i>
            </button>
        </div>
        <div class="err-pg-size-wrap">
            <span class="err-pg-info">Per page:</span>
            <select class="err-pg-size-select" onchange="errChangePageSize('${agentName}',this.value)">
                <option value="10"  ${perPage===10 ?'selected':''}>10</option>
                <option value="25"  ${perPage===25 ?'selected':''}>25</option>
                <option value="50"  ${perPage===50 ?'selected':''}>50</option>
                <option value="100" ${perPage===100?'selected':''}>100</option>
            </select>
        </div>
    </div>`;
}

function errGoPage(agentName, page) {
    const state    = _errPages[agentName];
    if (!state) return;
    const totalPgs = Math.ceil(state.sorted.length / state.perPage);
    state.page     = Math.max(0, Math.min(page, totalPgs - 1));
    _renderCurrentPage(agentName);
}

function errChangePageSize(agentName, size) {
    const state   = _errPages[agentName];
    if (!state) return;
    state.perPage = parseInt(size, 10);
    state.page    = 0;
    _renderCurrentPage(agentName);
}

function _renderCurrentPage(agentName) {
    const state   = _errPages[agentName];
    if (!state) return;
    const { sorted, page, perPage } = state;
    const slice   = sorted.slice(page * perPage, (page + 1) * perPage);
    const listEl  = document.getElementById(`errList_${agentName}`);
    if (!listEl) return;

    listEl.innerHTML = slice.map(err => _buildErrorRow(err, agentName)).join('');
    _renderPagination(agentName);

    // Scroll to top of panel
    const panel = document.getElementById(`errPanel_${agentName}`);
    if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderErrorsPanel(errors, agentName, col) {
    if (!errors || errors.length === 0) return '';

    const sevOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    const sorted   = [...errors].sort((a,b) => (sevOrder[a.severity]??9) - (sevOrder[b.severity]??9));

    const critCount = sorted.filter(e => e.severity === 'critical').length;
    const highCount = sorted.filter(e => e.severity === 'high').length;

    // Init pagination state for this agent
    _errPages[agentName] = { sorted, page: 0, perPage: PAGE_SIZE };

    // Render first page
    const firstPage = sorted.slice(0, PAGE_SIZE);
    const rows      = firstPage.map(err => _buildErrorRow(err, agentName)).join('');

    // Build pagination only if needed
    const totalPgs = Math.ceil(sorted.length / PAGE_SIZE);

    return `
    <div class="errors-panel card border-0 shadow-sm mb-4" id="errPanel_${agentName}">
        <div class="errors-panel-header">
            <div class="d-flex align-items-center gap-2 flex-wrap">
                <i class="bi bi-bug-fill text-danger"></i>
                <h6 class="mb-0 fw-bold text-danger">Errors &amp; Issues Found</h6>
                <span class="badge bg-danger">${errors.length}</span>
                ${critCount ? `<span class="badge" style="background:#dc3545">${critCount} critical</span>` : ''}
                ${highCount ? `<span class="badge" style="background:#fd7e14">${highCount} high</span>`    : ''}
                ${totalPgs > 1 ? `<span class="badge bg-secondary">${totalPgs} pages</span>` : ''}
            </div>
            <div class="d-flex align-items-center gap-3">
                <span class="fixit-hint"><i class="bi bi-magic me-1 text-primary"></i>Click <strong>Fix It</strong> for AI auto-fix</span>
                <button class="fix-all-btn" id="fixAllBtn_${agentName}"
                        onclick="fixAllErrors('${agentName}',this)">
                    <i class="bi bi-magic me-1"></i>Fix All (${errors.length})
                </button>
            </div>
        </div>
        <div class="errors-list" id="errList_${agentName}">${rows}</div>
        <div id="errPager_${agentName}"></div>
    </div>`;
}

function toggleErrorDetail(uid) {
    const d = document.getElementById(`detail_${uid}`);
    const c = document.getElementById(`chev_${uid}`);
    if (!d) return;
    d.classList.toggle('d-none');
    if (c) c.className = d.classList.contains('d-none') ? 'bi bi-chevron-down' : 'bi bi-chevron-up';
}

/**
 * Trigger streaming Fix It via SSE.
 */
async function triggerFixIt(uid, agentName) {
    const itemEl = document.getElementById(uid);
    const outEl  = document.getElementById(`fixout_${uid}`);
    const btn    = document.getElementById(`btn_${uid}`);
    if (!itemEl || !outEl || !btn) return;

    const err = JSON.parse(decodeURIComponent(itemEl.dataset.err));

    // Auto-expand detail
    const detail = document.getElementById(`detail_${uid}`);
    if (detail && detail.classList.contains('d-none')) toggleErrorDetail(uid);

    // Loading state
    btn.disabled  = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span><span> AI Fixing…</span>`;
    btn.classList.add('loading');

    // Skeleton
    outEl.classList.remove('d-none');
    outEl.innerHTML = `
    <div class="fixit-skeleton p-3">
        <div class="d-flex align-items-center gap-2 mb-3">
            <div class="fixit-pulse"></div>
            <span class="text-primary fw-semibold" style="font-size:.85rem">
                AI is analysing <strong>${escapeHtml(err.script_type || '')}${err.script_name && err.script_name!=='Unknown' ? ' → '+escapeHtml(err.script_name) : ''}</strong> and writing the fix…
            </span>
        </div>
        <div class="skel-line w-90"></div>
        <div class="skel-line w-75"></div>
        <div class="skel-line w-60"></div>
        <div class="skel-line w-80"></div>
    </div>`;

    try {
        // Plain JSON fetch — no SSE stream reading
        const resp = await fetch('/fix-it', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                error_id:      err.id            || uid,
                title:         err.title         || '',
                description:   err.description   || '',
                affected:      err.affected       || '',
                original_code: err.original_code  || '',
                fix_prompt:    err.fix_prompt     || '',
                agent:         agentName,
                script_type:   err.script_type   || '',
                script_name:   err.script_name   || '',
            })
        });

        if (!resp.ok) throw new Error(`Server error HTTP ${resp.status}`);

        const data = await resp.json();   // plain JSON — no SSE parsing needed

        if (data.status === 'error') throw new Error(data.message || 'AI returned an error');

        renderFixResult(outEl, data, err);
        btn.innerHTML = `<i class="bi bi-check2-circle"></i><span> Fixed ✓</span>`;
        btn.classList.remove('loading');
        btn.classList.add('done');
        btn.disabled = false;

    } catch (e) {
        outEl.innerHTML = `
        <div class="fixit-error-msg p-3">
            <i class="bi bi-exclamation-triangle-fill text-danger me-2"></i>
            <strong>Fix failed:</strong> ${escapeHtml(e.message)}
            <div class="mt-1 text-muted" style="font-size:.75rem">Check that the AI model (Ollama) is running.</div>
        </div>`;
        btn.innerHTML = `<i class="bi bi-magic"></i><span> Retry</span>`;
        btn.classList.remove('loading');
        btn.disabled  = false;
    }
}

function renderFixResult(container, data, err) {
    const changes = (data.changes || []).map(c =>
        `<li><i class="bi bi-check2 text-success me-1" style="font-size:.8rem"></i>${escapeHtml(c)}</li>`
    ).join('');

    container.innerHTML = `
    <div class="fixit-result">
        <!-- Result header -->
        <div class="fixit-res-header">
            <div class="d-flex align-items-center gap-2">
                <div class="fixit-ok-icon"><i class="bi bi-check-lg"></i></div>
                <div>
                    <div class="fw-bold" style="color:#198754;font-size:.9rem">AI Fix Applied</div>
                    <div class="text-muted" style="font-size:.75rem">Review before deploying to ServiceNow</div>
                </div>
            </div>
            <button class="copy-btn" onclick="copyCode(${JSON.stringify(escapeHtml(data.fixed_code||''))})">
                <i class="bi bi-clipboard me-1"></i>Copy
            </button>
        </div>

        <!-- Before / After split view -->
        <div class="code-diff-grid">
            <div class="diff-pane diff-before">
                <div class="diff-pane-label">
                    <i class="bi bi-x-circle-fill text-danger me-1"></i>
                    Original${err.script_type ? ' · <span style="color:#fd7e14">'+escapeHtml(err.script_type)+'</span>' : ''}
                    ${err.script_name && err.script_name !== 'Unknown' ? ' · <strong>'+escapeHtml(err.script_name)+'</strong>' : ''}
                </div>
                <pre class="code-pre diff-code-before"><code>${escapeHtml(err.original_code || '// (no original code)')}</code></pre>
            </div>
            <div class="diff-pane diff-after">
                <div class="diff-pane-label">
                    <i class="bi bi-check-circle-fill text-success me-1"></i>
                    AI Fixed Version
                </div>
                <pre class="code-pre diff-code-after"><code>${escapeHtml(data.fixed_code||'')}</code></pre>
            </div>
        </div>

        <!-- Explanation -->
        <div class="fixit-explanation">
            <div class="fixit-section-title"><i class="bi bi-lightbulb-fill text-warning me-1"></i>What was changed & why</div>
            <p style="font-size:.86rem;color:#495057;margin:0">${escapeHtml(data.explanation||'')}</p>
        </div>

        ${changes ? `
        <div class="fixit-changes">
            <div class="fixit-section-title mb-1"><i class="bi bi-list-check text-primary me-1"></i>Changes Made</div>
            <ul style="list-style:none;padding:0;margin:0;font-size:.83rem">${changes}</ul>
        </div>` : ''}

        <div class="fixit-meta">
            ${data.best_practice ? `
            <div class="meta-chip" style="background:rgba(13,110,253,.07);border-color:rgba(13,110,253,.2)">
                <i class="bi bi-award-fill text-primary me-1"></i>
                <strong>Best Practice:</strong> ${escapeHtml(data.best_practice)}
            </div>` : ''}
            ${data.estimated_impact ? `
            <div class="meta-chip" style="background:rgba(25,135,84,.07);border-color:rgba(25,135,84,.2)">
                <i class="bi bi-graph-up-arrow text-success me-1"></i>
                <strong>Impact:</strong> ${escapeHtml(data.estimated_impact)}
            </div>` : ''}
        </div>

        <!-- Push to ServiceNow button -->
        ${err.sys_id && err.table ? `
        <div class="fixit-push-row mt-2 d-flex align-items-center gap-2">
            <button class="btn btn-sm btn-success push-sn-btn"
                id="pushBtn_${escapeHtml(data.error_id || '')}"
                data-push-key="${escapeHtml(data.error_id || '')}">
                <i class="bi bi-cloud-upload-fill me-1"></i>Deploy Fix to ServiceNow
            </button>
            <span class="push-status text-muted" style="font-size:.78rem"></span>
        </div>` : ''}
    </div>`;

    // Store push payload safely in JS map (avoids escaping issues in onclick)
    if (err.sys_id && err.table) {
        const pushKey = data.error_id || '';

        // sys_id might be a JSON dict string {"value":"abc...","display_value":"..."}
        // if MySQL stored it that way — extract the plain value
        let cleanSysId = err.sys_id || '';
        if (cleanSysId.startsWith('{')) {
            try {
                const sidObj = JSON.parse(cleanSysId);
                cleanSysId = sidObj.value || sidObj.display_value || cleanSysId;
            } catch(e) {}
        }

        _pushPayloadStore[pushKey] = {
            sys_id:      cleanSysId,
            table:       err.table        || '',
            field:       err.script_field || 'script',
            fixed_code:  data.fixed_code  || '',   // FULL fixed script from AI
            script_name: err.script_name  || '',
        };
        // Attach click handler after DOM settles
        setTimeout(() => {
            const btn = document.getElementById('pushBtn_' + pushKey);
            if (btn) btn.addEventListener('click', () => pushFixToServiceNow(btn, pushKey));
        }, 50);
    }
}

// Safe storage for push payloads — keyed by error_id
const _pushPayloadStore = {};

async function pushFixToServiceNow(btn, pushKey) {
    const payload   = _pushPayloadStore[pushKey];
    if (!payload) { console.error('No push payload for', pushKey); return; }

    const statusEl = btn.parentElement.querySelector('.push-status');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Pushing…';
    if (statusEl) statusEl.textContent = '';
    try {
        const resp = await fetch('/fix-it/push', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload)
        });
        const data = await resp.json();
        if (data.status === 'success') {
            btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Pushed ✓';
            btn.classList.replace('btn-success', 'btn-outline-success');
            if (statusEl) statusEl.innerHTML = `<span class="text-success">${escapeHtml(data.message)}</span>`;
        } else if (data.status === 'partial') {
            btn.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i>Partial';
            btn.classList.replace('btn-success', 'btn-warning');
            if (statusEl) statusEl.innerHTML = `<span class="text-warning">${escapeHtml(data.message)}</span>`;
            btn.disabled = false;
        } else {
            throw new Error(data.message || 'Push failed');
        }
    } catch(e) {
        btn.innerHTML = '<i class="bi bi-cloud-upload-fill me-1"></i>Retry Deploy';
        btn.disabled = false;
        if (statusEl) statusEl.innerHTML = `<span class="text-danger">Error: ${escapeHtml(e.message)}</span>`;
    }
}

async function fixAllErrors(agentName, btn) {
    // Get ALL errors across ALL pages from the pagination state
    const state = _errPages[agentName];
    const allErrors = state ? state.sorted : [];
    const total = allErrors.length;
    if (total === 0) return;

    btn.disabled  = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Fixing 0/${total}…`;

    let done = 0;

    for (let i = 0; i < allErrors.length; i++) {
        const err = allErrors[i];
        const perPage = state.perPage;

        // Navigate to the page that contains this error
        const targetPage = Math.floor(i / perPage);
        if (state.page !== targetPage) {
            state.page = targetPage;
            _renderCurrentPage(agentName);
            await new Promise(r => setTimeout(r, 80)); // let DOM settle
        }

        const uid = `err_${agentName}_${(err.id||'')}`;
        const itemEl = document.getElementById(uid);
        if (!itemEl) continue; // uid might have random suffix — fallback

        const fixBtn = document.getElementById(`btn_${uid}`);
        if (fixBtn && !fixBtn.classList.contains('done')) {
            await triggerFixIt(uid, agentName);
        }

        done++;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${done}/${total}`;
    }

    btn.disabled  = false;
    btn.className = 'fix-all-btn done';
    btn.innerHTML = `<i class="bi bi-check2-all me-1"></i>All Fixed ✓ (${total})`;
}

function copyCode(code) {
    // unescape html entities before copying
    const txt = document.createElement('textarea');
    txt.innerHTML = code;
    const raw = txt.value;
    navigator.clipboard.writeText(raw).then(() => {
        const t = document.createElement('div');
        t.className = 'copy-toast';
        t.innerHTML = '<i class="bi bi-check2 me-1"></i>Copied to clipboard!';
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 2000);
    });
}

// ===== SYNC STATUS POLLER (10-second interval) =====
(function startSyncPoller() {
    function updateBadge(data) {
        const badge = document.getElementById('syncStatusBadge');
        const icon  = document.getElementById('syncIcon');
        const label = document.getElementById('syncLabel');
        if (!badge) return;

        // Count table states
        const tables = Object.values(data.tables || {});
        const running = tables.filter(t => t.status === 'running').length;
        const errors  = tables.filter(t => t.status === 'error').length;
        const newRecs = tables.reduce((a,t) => a + (t.new_records||0), 0);

        if (data.running) {
            badge.className = 'sync-badge syncing';
            icon.className  = 'bi bi-arrow-repeat spin-icon';
            label.textContent = running ? `Syncing (${running} tables)…` : 'Syncing…';
        } else if (errors > 0) {
            badge.className = 'sync-badge error';
            icon.className  = 'bi bi-exclamation-triangle-fill';
            label.textContent = `${errors} sync error${errors>1?'s':''}`;
        } else if (data.last_completed) {
            badge.className = 'sync-badge ok';
            icon.className  = 'bi bi-check-circle-fill';
            const nxt = data.next_run_in || 0;
            const tag = newRecs > 0 ? `+${newRecs} · ` : '';
            label.textContent = nxt > 0 ? `${tag}next in ${nxt}s` : `${tag}synced`;
        } else {
            badge.className = 'sync-badge idle';
            icon.className  = 'bi bi-arrow-repeat';
            label.textContent = 'Syncing…';
        }
    }

    function poll() {
        fetch('/sync/status').then(r=>r.json()).then(updateBadge).catch(()=>{});
    }
    poll();
    setInterval(poll, 3000);   // poll every 3s — syncs every 10s
})();

// ============================================================
// LICENSE — Deactivate User (one-click → ServiceNow API)
// ============================================================

async function deactivateUser(userSysId, userName, email, daysInactive, reason, rowId) {
    const btn = document.getElementById(`deact_${rowId}`);
    const row = document.getElementById(rowId);
    if (!btn || !userSysId) return;

    // Confirm
    if (!confirm(
        `Deactivate user "${userName}" (${email})?\n\n` +
        `Inactive for: ${daysInactive} days\n` +
        `Reason: ${reason}\n\n` +
        `This will set the user to INACTIVE in ServiceNow immediately.`
    )) return;

    // Loading state
    btn.disabled  = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Deactivating…`;

    try {
        const resp = await fetch('/license/deactivate-user', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_sys_id:   userSysId,
                user_name:     userName,
                email:         email,
                days_inactive: daysInactive,
                reason:        reason,
            })
        });

        const data = await resp.json();

        if (data.status === 'success') {
            // Mark row with visual feedback then fade out and remove after a moment
            if (row) {
                row.style.transition    = 'opacity 0.4s ease, background 0.3s';
                row.style.background    = 'rgba(25,135,84,0.10)';
                row.style.opacity       = '0.7';
                row.style.textDecoration = 'line-through';
                // Remove the row from the DOM after 1.5s so the list stays clean
                setTimeout(() => {
                    row.style.opacity = '0';
                    setTimeout(() => row.remove(), 400);
                }, 1500);
            }
            btn.className = 'deactivate-btn done';
            btn.innerHTML = `<i class="bi bi-check2-circle me-1"></i>Deactivated ✓`;
            btn.disabled  = true;

            // Toast
            _showToast(`✓ ${userName} deactivated in ServiceNow`, 'success');

        } else {
            btn.disabled  = false;
            btn.innerHTML = `<i class="bi bi-person-x-fill me-1"></i>Retry`;
            _showToast(`Failed: ${data.message || 'Unknown error'}`, 'error');
        }

    } catch (e) {
        btn.disabled  = false;
        btn.innerHTML = `<i class="bi bi-person-x-fill me-1"></i>Retry`;
        _showToast(`Network error: ${e.message}`, 'error');
    }
}

async function deactivateAllInactive(masterBtn) {
    const btns = document.querySelectorAll('.deactivate-btn:not(.done)');
    if (!btns.length) return;

    if (!confirm(
        `Deactivate ALL ${btns.length} inactive users?\n\n` +
        `This will immediately set them to inactive in ServiceNow.\n` +
        `Only users with 90+ days of inactivity are included.`
    )) return;

    masterBtn.disabled  = true;
    masterBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Deactivating 0/${btns.length}…`;

    let done = 0;
    for (const btn of btns) {
        // Extract rowId from button id: deact_dec_row_N
        const rowId = btn.id.replace('deact_', '');
        btn.click && btn.click();   // trigger individual deactivate (includes confirm skipped here)
        // wait a tick
        await new Promise(r => setTimeout(r, 300));
        done++;
        masterBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${done}/${btns.length}…`;
    }

    masterBtn.disabled  = false;
    masterBtn.className = 'deactivate-all-btn done';
    masterBtn.innerHTML = `<i class="bi bi-check2-all me-1"></i>All Deactivated ✓`;
}

// ── Last Login Audit tab switcher ────────────────────────────────────────────
function llaShowTab(evt, tabId) {
    // Hide all panes
    document.querySelectorAll('.lla-tab-pane').forEach(p => p.style.display = 'none');
    // Deactivate all tab buttons
    evt.target.closest('ul').querySelectorAll('.nav-link').forEach(b => b.classList.remove('active'));
    // Show selected pane
    const pane = document.getElementById(tabId);
    if (pane) pane.style.display = 'block';
    // Mark button active
    evt.target.classList.add('active');
}

function _showToast(msg, type = 'success') {
    const t = document.createElement('div');
    t.className = `copy-toast ${type === 'error' ? 'toast-error' : ''}`;
    t.innerHTML = `<i class="bi bi-${type === 'error' ? 'exclamation-triangle-fill' : 'check2'} me-1"></i>${escapeHtml(msg)}`;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
}
