/* ═══════════════════════════════════════
   TSC Dashboard — Client-Side JavaScript
   ═══════════════════════════════════════ */

const API = '/api/tsc';

// ─── Common causes for dropdowns ───
const CAUSES = [
    "GIC Crack","Abnormal Sound","Jumper Bolt Broken","Oil Throwing",
    "Blade Broken","Gear Train Broken","Idle Gear Play Lost",
    "Shaft Broken","Block Crack","Surging","Clutch Defective",
    "Flange Crack","Overdue","6 YLY Schedule","3 YLY Schedule",
    "12 YLY Schedule","BAP Less","Oil Seal Leakage","Other"
];

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    populateCauseDropdowns();
    initFYButtons(); // Initialize buttons
    loadDashboard();
});

// ─── Navigation ───
function initNavigation() {
    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const target = link.dataset.target;
            document.querySelectorAll('.nav-links a').forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active-view'));
            const el = document.getElementById(target);
            if (el) el.classList.add('active-view');

            if (target === 'tsc-dashboard') loadDashboard();
            if (target === 'tsc-registers') loadRegister(); // Load registers view
        });
    });

    // Buttons
    document.getElementById('btn-refresh-running')?.addEventListener('click', loadRunningTSCs);
    document.getElementById('btn-loco-hist')?.addEventListener('click', loadLocoHistory);
    document.getElementById('btn-load-pf')?.addEventListener('click', loadPrematureFailures);
    document.getElementById('btn-load-avail')?.addEventListener('click', loadAvailableTSCs);
    document.getElementById('btn-load-wait')?.addEventListener('click', loadWaitingDispatch);

    // Register tabs
    document.querySelectorAll('#reg-tabs .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#reg-tabs .tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadRegister(); // Automatically load data for the new tab
        });
    });

    // Forms
    document.getElementById('form-receive')?.addEventListener('submit', handleReceive);
    document.getElementById('form-issue')?.addEventListener('submit', handleIssue);
    document.getElementById('form-remove')?.addEventListener('submit', handleRemove);
    document.getElementById('form-send-blw')?.addEventListener('submit', handleSendBLW);

    // Enter key for search
    document.getElementById('loco-hist-input')?.addEventListener('keypress', e => { if(e.key==='Enter') loadLocoHistory(); });
}

function populateCauseDropdowns() {
    ['i_cause','rm_cause'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        CAUSES.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c; opt.textContent = c;
            sel.appendChild(opt);
        });
    });
}

// ─── API Helper ───
async function api(endpoint, method = 'GET', body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API}${endpoint}`, opts);
    return res.json();
}

// ─── Dashboard ───
async function loadDashboard() {
    try {
        const [stats, alerts, blw] = await Promise.all([
            api('/dashboard'), api('/alerts'), api('/blw_account')
        ]);

        const setT = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val ?? '—';
        };

        setT('s-total', stats.total);
        setT('s-service', stats.in_service);
        setT('s-available', stats.available);
        setT('s-waiting', stats.waiting_dispatch);
        setT('s-at-blw', stats.at_blw);
        setT('s-warranty', stats.warranty_cases);
        setT('s-premature', stats.premature_failures);

        // BLW Account
        setT('blw-sent', blw.total_sent ?? 0);
        setT('blw-recv', blw.total_received ?? 0);
        setT('blw-bal', blw.balance_at_blw ?? 0);

        // Alerts
        const alertCard = document.getElementById('alerts-card');
        const alertBody = document.getElementById('alerts-body');
        if (alerts.data && alerts.data.length > 0) {
            alertCard.style.display = 'block';
            alertBody.innerHTML = alerts.data.map(a =>
                `<div class="alert-item alert-${a.severity}"><i class="fa-solid fa-${a.severity==='critical'?'circle-exclamation':a.severity==='warning'?'triangle-exclamation':'circle-info'}"></i>${a.msg}</div>`
            ).join('');
        } else {
            alertCard.style.display = 'none';
        }

        loadRunningTSCs();
        loadWaitingDispatch();
    } catch (err) {
        console.error('Dashboard load error:', err);
    }
}

async function loadRunningTSCs() {
    try {
        const data = await api('/running');
        const rows = data.data || [];
        const tbody = document.querySelector('#running-table tbody');

        if (rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10"><div class="empty-state"><i class="fa-solid fa-fan"></i><p>No TSCs currently in service</p></div></td></tr>';
            return;
        }

        tbody.innerHTML = rows.map(r => {
            const badgeClass = r.status_color === 'GREEN' ? 'badge-green'
                : r.status_color === 'YELLOW' ? 'badge-yellow'
                : r.status_color === 'RED' ? 'badge-red' : 'badge-overdue';
            const icon = r.status_color === 'GREEN' ? '🟢'
                : r.status_color === 'YELLOW' ? '🟡'
                : r.status_color === 'RED' ? '🔴' : '⚫';
            const remText = r.remaining_days >= 0
                ? `${r.remaining_days}d`
                : `OVERDUE ${Math.abs(r.remaining_days)}d`;
            const warBadge = r.is_warranty === 'YES'
                ? '<span class="badge badge-blue">Under Warranty</span>'
                : '<span class="badge badge-purple">Out of Warranty</span>';

            return `<tr>
                <td><strong>${r.loco_no}</strong></td>
                <td>${r.loco_type}</td>
                <td>${r.tsc_no}</td>
                <td>${r.fitment_date}</td>
                <td>${r.doc}</td>
                <td>${r.age_years} yr</td>
                <td>${r.working_life} yr</td>
                <td><span class="badge ${badgeClass}">${icon} ${remText}</span></td>
                <td><span class="badge ${badgeClass}">${r.status_color}</span></td>
                <td>${warBadge}</td>
                <td>
                    <button class="btn-secondary btn-sm" onclick="openRemoval('${r.tsc_no}')" title="Quick Remove">
                        <i class="fa-solid fa-eject" style="color:var(--red)"></i>
                    </button>
                </td>
            </tr>`;
        }).join('');
    } catch (err) {
        console.error('Running TSCs error:', err);
    }
}

// ─── Loco History ───
async function loadLocoHistory() {
    const loco = document.getElementById('loco-hist-input').value.trim();
    if (!loco) return;

    try {
        const data = await api(`/loco_history/${loco}`);
        document.getElementById('loco-hist-result').style.display = 'block';

        // Current TSC
        const curDiv = document.getElementById('loco-hist-current');
        if (data.current_tsc) {
            const c = data.current_tsc;
            curDiv.innerHTML = `<div class="card-header"><span class="card-title"><i class="fa-solid fa-fan"></i> Currently Fitted</span></div>
                <div class="card-body"><strong>${c.TSC_No || c.tsc_no || '—'}</strong> — Fitted: ${c.Fitment_Date || c.fitment_date || '—'} — DOC: ${c.DOC || c.doc || '—'}
                — Type: ${data.loco_type || '—'}</div>`;
        } else {
            curDiv.innerHTML = `<div class="card-header"><span class="card-title"><i class="fa-solid fa-fan"></i> Currently Fitted</span></div>
                <div class="card-body text-muted">No TSC currently fitted on Loco ${loco}</div>`;
        }

        // Fit history
        const fitTbody = document.querySelector('#loco-fit-table tbody');
        const fits = data.fit_history || [];
        fitTbody.innerHTML = fits.length > 0
            ? fits.map(f => `<tr><td>${f.TSC_No||''}</td><td>${f.Issue_Date||''}</td><td>${f.DOC||''}</td><td>${f.Loco_Type||''}</td><td>${f.Cause_of_Change||''}</td><td>${f.Remarks||''}</td></tr>`).join('')
            : '<tr><td colspan="6" class="text-muted">No fitment history</td></tr>';

        // Removal history
        const remTbody = document.querySelector('#loco-rem-table tbody');
        const rems = data.removal_history || [];
        remTbody.innerHTML = rems.length > 0
            ? rems.map(r => `<tr><td>${r.TSC_No||''}</td><td>${r.Removal_Date||''}</td><td>${r.Cause||''}</td><td>${r.Condition||''}</td><td>${r.Is_Warranty==='YES'?'<span class="badge badge-blue">Yes</span>':'No'}</td><td>${r.Remarks||''}</td></tr>`).join('')
            : '<tr><td colspan="6" class="text-muted">No removal history</td></tr>';

    } catch (err) {
        console.error('Loco history error:', err);
    }
}

// ─── Premature Failures ───
async function loadPrematureFailures() {
    try {
        const data = await api('/premature_failures');
        const rows = data.data || [];
        const tbody = document.querySelector('#pf-table tbody');

        if (rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11"><div class="empty-state"><i class="fa-solid fa-check-circle"></i><p>No premature failures recorded</p></div></td></tr>';
            return;
        }

        tbody.innerHTML = rows.map(r => `<tr>
            <td>${r.Sr_No||''}</td>
            <td>${r.TSC_No||''}</td>
            <td>${r.Loco_No||''}</td>
            <td>${r.Loco_Type||''}</td>
            <td>${r.Fitted_Date||''}</td>
            <td>${r.DOC||''}</td>
            <td>${r.Removed_Date||''}</td>
            <td><span class="badge badge-red">${r.Age_At_Failure_Years||''} yr</span></td>
            <td>${r.Working_Life_Years||''} yr</td>
            <td>${r.Failure_Reason||''}</td>
            <td>${r.Is_Warranty==='YES'?'<span class="badge badge-blue">Yes</span>':'No'}</td>
        </tr>`).join('');
    } catch (err) {
        console.error('Premature failures error:', err);
    }
}

// ─── Available TSCs ───
async function loadAvailableTSCs() {
    try {
        const data = await api('/available');
        const rows = data.data || [];
        const tbody = document.getElementById('avail-tbody');

        if (rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-muted text-center">No TSCs currently available</td></tr>';
            return;
        }

        tbody.innerHTML = rows.map(r => `<tr>
            <td><strong>${r.tsc_no}</strong></td>
            <td><span class="badge ${r.source==='FROM BLW'?'badge-blue':'badge-purple'}">${r.source}</span></td>
            <td>${r.doc||'—'}</td>
            <td>${r.age_used ? `<span class="badge badge-orange">${r.age_used}</span>` : '—'}</td>
            <td>${r.removed_from||'—'}</td>
            <td><span class="badge badge-green">${r.oh_type}</span></td>
            <td>
                <button class="btn-secondary btn-sm" onclick="document.getElementById('i_tsc_no').value='${r.tsc_no}'">Select</button>
            </td>
        </tr>`).join('');
    } catch (err) {
        console.error('Available TSC error:', err);
    }
}

async function loadWaitingDispatch() {
    try {
        const data = await api('/waiting_dispatch');
        const rows = data.data || [];
        const tbody = document.getElementById('wait-disp-tbody');

        if (rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No TSCs waiting for dispatch</td></tr>';
            return;
        }

        tbody.innerHTML = rows.map(r => `<tr>
            <td><strong>${r['Turbo No.'] || r['TSC No.']}</strong></td>
            <td>${r['Removed from loco no.'] || r['Loco No.'] || '—'}</td>
            <td>${r['Removed date'] || r['Removal Date'] || '—'}</td>
            <td>${r['Fitment date'] || '—'}</td>
            <td>${r['commissioning date'] || '—'}</td>
            <td>${r['Reason to remove'] || r['Cause'] || '—'}</td>
            <td>
                <button class="btn-secondary btn-sm" onclick="document.getElementById('sb_tsc_no').value='${r['Turbo No.'] || r['TSC No.']}'; showView('tsc-send-blw')">Dispatch</button>
            </td>
        </tr>`).join('');
    } catch (err) {
        console.error('Waiting dispatch error:', err);
    }
}

function openRemoval(tscNo) {
    document.getElementById('rm_tsc_no').value = tscNo;
    showView('tsc-remove');
}

function showView(targetId) {
    document.querySelectorAll('.nav-links a').forEach(l => {
        l.classList.remove('active');
        if (l.dataset.target === targetId) l.classList.add('active');
    });
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active-view'));
    const el = document.getElementById(targetId);
    if (el) el.classList.add('active-view');
}

// ─── Form Handlers ───
function showMsg(id, msg, isSuccess) {
    const el = document.getElementById(id);
    el.textContent = msg;
    el.className = `form-msg ${isSuccess ? 'success' : 'error'}`;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 8000);
}

async function handleReceive(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd);
    try {
        const res = await api('/receive', 'POST', body);
        const msg = res.message || '';
        showMsg('receive-msg', msg, msg.includes('✅'));
        if (msg.includes('✅')) e.target.reset();
    } catch (err) { showMsg('receive-msg', 'Error: ' + err.message, false); }
}

async function handleIssue(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd);
    try {
        const res = await api('/issue', 'POST', body);
        const msg = res.message || '';
        showMsg('issue-msg', msg, msg.includes('✅'));
        if (msg.includes('✅')) e.target.reset();
    } catch (err) { showMsg('issue-msg', 'Error: ' + err.message, false); }
}

async function handleRemove(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd);
    try {
        const res = await api('/remove', 'POST', body);
        const msg = res.message || '';
        showMsg('remove-msg', msg, msg.includes('✅'));
        if (msg.includes('✅')) e.target.reset();
    } catch (err) { showMsg('remove-msg', 'Error: ' + err.message, false); }
}

async function handleSendBLW(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd);
    try {
        const res = await api('/send_blw', 'POST', body);
        const msg = res.message || '';
        showMsg('send-blw-msg', msg, msg.includes('✅'));
        if (msg.includes('✅')) e.target.reset();
    } catch (err) { showMsg('send-blw-msg', 'Error: ' + err.message, false); }
}

// ─── Registers ───
const REG_HEADERS = {
    receive: ['Sr. No.', 'T.S.C. No.', 'Received From', 'Date of Received', 'PL NO.', 'AGAINST WARRANTY /OVER HAULING', 'Received Against Letter No.', 'Date of given on Loco', 'Loco No.', 'Cause of Change of T.S.C.', 'Session'],
    issue: ['Sr_No','TSC_No','Issue_Date','Loco_No','Loco_Type','DOC','Is_New_DOC','Cause_of_Change','Remarks','FY_Session'],
    removal: ['Sr_No','TSC_No','Removal_Date','From_Loco','Cause','Condition','Next_Action','Is_Warranty','Remarks','FY_Session'],
    blw_dispatch: ['Sr. No.', 'T.S.C. No.', 'Loco No.', 'DATE OF REMOVAL', 'DATE OF FITMENT', 'D.O.C.', 'CAUSE OF FAILURE', 'LETTER NO. /WARRANTY NO.', 'LETTER NO FOR SEND TO BLW', 'DATE OF SEND TO BLW', 'Session', 'Status'],
    waiting: ['Sr. No.', 'Turbo No.', 'Removed from loco no.', 'Removed date', 'Fitment date', 'commissioning date', 'Reason to remove', 'Action'],
};

async function loadRegister() {
    const activeTab = document.querySelector('#reg-tabs .tab-btn.active');
    const regName = activeTab?.dataset.reg || 'receive';
    
    // Get FY from active button
    const activeFYBtn = document.querySelector('.fy-btn.active');
    const fy = activeFYBtn ? activeFYBtn.dataset.fy : '';

    try {
        const fyParam = fy ? `?fy=${fy}` : '';
        const data = await api(`/register/${regName}${fyParam}`);
        const rows = data.data || [];
        const summary = data.summary || [];
        const headers = REG_HEADERS[regName] || [];

        const thead = document.getElementById('reg-thead');
        thead.innerHTML = '<tr>' + headers.map(h => `<th>${h.replace(/_/g,' ')}</th>`).join('') + '</tr>';

        const tbody = document.getElementById('reg-tbody');
        if (rows.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${headers.length}"><div class="empty-state"><i class="fa-solid fa-folder-open"></i><p>No records found</p></div></td></tr>`;
        } else {
            tbody.innerHTML = rows.map(r => {
                let html = '<tr>' + headers.filter(h => h!=='Action').map(h => `<td>${r[h] ?? ''}</td>`).join('');
                if (headers.includes('Action')) {
                    if (regName === 'waiting') {
                        html += `<td><button class="btn-secondary btn-sm" onclick="document.getElementById('sb_tsc_no').value='${r['Turbo No.'] || r['TSC No.']}'; showView('tsc-send-blw')">Dispatch</button></td>`;
                    } else {
                        html += '<td></td>';
                    }
                }
                html += '</tr>';
                return html;
            }).join('');
        }
        
        const sumCont = document.getElementById('register-summary-container');
        const sumBody = document.getElementById('register-summary-tbody');
        
        let filteredSummary = summary;
        if (fy && fy !== 'ALL') {
            filteredSummary = summary.filter(s => s.fy === fy);
        }

        if (filteredSummary.length > 0) {
            sumCont.style.display = 'block';
            sumBody.innerHTML = filteredSummary.map(s => `<tr><td>${s.fy}</td><td>${s.warranty}</td><td>${s.overhaul}</td></tr>`).join('');
        } else {
            sumCont.style.display = 'none';
        }
    } catch (err) {
        console.error('Register load error:', err);
    }
}

function initFYButtons() {
    const container = document.getElementById('fy-filter-buttons');
    if (!container) return;

    const currentFY = getCurrentFY();
    const currentYear = parseInt(currentFY.split('-')[0]);
    
    // Create a list of years from 2021-22 up to current+1
    const years = [];
    for (let y = 2021; y <= currentYear; y++) {
        years.push(`${y}-${(y + 1).toString().slice(-2)}`);
    }
    
    container.innerHTML = years.map(fy => 
        `<button class="fy-btn ${fy === currentFY ? 'active' : ''}" data-fy="${fy}">${fy}</button>`
    ).join('') + `<button class="fy-btn" data-fy="">ALL</button>`;

    // Add events
    container.querySelectorAll('.fy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.fy-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadRegister(); // Refresh data on selection
        });
    });
}

function getCurrentFY() {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1; // 1-12
    if (month >= 4) {
        return `${year}-${(year + 1).toString().slice(-2)}`;
    } else {
        return `${year - 1}-${year.toString().slice(-2)}`;
    }
}
