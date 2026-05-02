document.addEventListener('DOMContentLoaded', () => {

    // --- Navigation ---
    const navLinks = document.querySelectorAll('.nav-links a');
    const views = document.querySelectorAll('.view');
    const pageHeader = document.getElementById('main-content');

    navLinks.forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const targetId = link.getAttribute('data-target');
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            views.forEach(v => v.classList.remove('active-view'));
            document.getElementById(targetId).classList.add('active-view');
        });
    });

    // --- API Helper ---
    async function api(endpoint, method = 'GET', body = null) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) opts.body = JSON.stringify(body);
        const r = await fetch(endpoint, opts);
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || data.error || 'API error');
        return data;
    }

    function esc(s) { return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    function strUp(v) { return String(v ?? '').trim().toUpperCase(); }

    // --- DASHBOARD ---
    const btnLocoSearch = document.getElementById('btn-loco-search');
    const inputLocoSearch = document.getElementById('loco-search-input');
    const locoContainer = document.getElementById('loco-status-container');
    const locoInfoCard = document.getElementById('loco-info-card');
    const equipAccordion = document.getElementById('equipment-accordion');
    const msgsTbody = document.querySelector('#messages-table tbody');
    const locoError = document.getElementById('loco-error');

    async function searchLoco() {
        const locoNo = inputLocoSearch.value.trim();
        if (!locoNo) return;
        const orig = btnLocoSearch.innerHTML;
        btnLocoSearch.innerHTML = '<i class="fa-solid fa-circle-notch spin"></i>';
        btnLocoSearch.disabled = true;
        locoError.classList.remove('show');

        try {
            const res = await api(`/api/status/${locoNo}`);
            if (res.error) throw new Error(res.error);
            locoContainer.style.display = 'block';

            const info = res.loco_info;
            locoInfoCard.innerHTML = `
                <div class="loco-number">${esc(info.loco_no)}</div>
                <div class="loco-details">
                    <div class="detail-item"><span class="detail-label">Type</span><span class="detail-value">${esc(info.type)}</span></div>
                    <div class="detail-item"><span class="detail-label">DOC</span><span class="detail-value">${esc(info.doc)}</span></div>
                    <div class="detail-item"><span class="detail-label">Last Major</span><span class="detail-value">${esc(info.last_major)}</span></div>
                    <div class="detail-item"><span class="detail-label">Next Major</span><span class="detail-value">${esc(info.next_major)}</span></div>
                    <div class="detail-item"><span class="detail-label">Status</span><span class="detail-value"><span class="badge badge-fitted">${esc(info.status)}</span></span></div>
                </div>`;

            equipAccordion.innerHTML = '';
            if (res.equipment && res.equipment.length > 0) {
                res.equipment.forEach(eq => {
                    const item = document.createElement('div');
                    item.className = 'acc-item';
                    item.innerHTML = `
                        <button class="acc-trigger" type="button">
                            <span>${esc(eq.type)} &mdash; <span class="font-mono" style="font-size:11px;color:var(--text-2);">${esc(eq.serial_mfg)}</span></span>
                            <i class="fa-solid fa-chevron-down"></i>
                        </button>
                        <div class="acc-body">
                            <div class="acc-field"><span class="acc-field-label">Make</span><span class="acc-field-value">${esc(eq.make)}</span></div>
                            <div class="acc-field"><span class="acc-field-label">Mfg Date</span><span class="acc-field-value">${esc(eq.mfg_date)}</span></div>
                            <div class="acc-field"><span class="acc-field-label">Fitment Date</span><span class="acc-field-value">${esc(eq.fitment_date)}</span></div>
                            <div class="acc-field"><span class="acc-field-label">Last OH</span><span class="acc-field-value">${esc(eq.last_oh)}</span></div>
                            <div class="acc-field"><span class="acc-field-label">Next Due</span><span class="acc-field-value">${esc(eq.next_due)}</span></div>
                            <div class="acc-field"><span class="acc-field-label">Status</span><span class="acc-field-value">${esc(eq.status)}</span></div>
                            <div class="acc-field full"><span class="acc-field-label">Notes</span><span class="acc-field-value">${esc(eq.notes)}</span></div>
                        </div>`;
                    item.querySelector('.acc-trigger').addEventListener('click', () => {
                        item.classList.toggle('open');
                    });
                    equipAccordion.appendChild(item);
                });
            } else {
                equipAccordion.innerHTML = '<div class="empty-state"><i class="fa-solid fa-microchip"></i><p>No equipment fitted</p></div>';
            }

            msgsTbody.innerHTML = '';
            if (res.messages && res.messages.length > 0) {
                res.messages.forEach(m => {
                    msgsTbody.innerHTML += `<tr>
                        <td class="msg-date">${esc(m.date)}</td>
                        <td class="msg-text">${esc(m.text)}</td>
                        <td class="msg-user"><i class="fa-solid fa-user" style="font-size:10px;"></i> ${esc(m.user)}</td>
                    </tr>`;
                });
            } else {
                msgsTbody.innerHTML = '<tr><td colspan="3"><div class="empty-state" style="padding:20px;"><p>No messages found</p></div></td></tr>';
            }
        } catch (e) {
            locoContainer.style.display = 'none';
            locoError.textContent = e.message;
            locoError.classList.add('show');
        } finally {
            btnLocoSearch.innerHTML = orig;
            btnLocoSearch.disabled = false;
        }
    }

    btnLocoSearch.addEventListener('click', searchLoco);
    inputLocoSearch.addEventListener('keydown', e => { if (e.key === 'Enter') searchLoco(); });

    // --- EQUIPMENT MASTER ---
    let allEquipment = [];
    let currentTab = 'MPH';
    let currentFilter = 'ALL';

    const masterTbody = document.querySelector('#master-table tbody');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const statusFilter = document.getElementById('eq-status-filter');
    const btnRefresh = document.getElementById('btn-refresh-master');

    async function loadMaster() {
        const orig = btnRefresh.innerHTML;
        btnRefresh.innerHTML = '<i class="fa-solid fa-rotate spin"></i>';
        btnRefresh.disabled = true;
        try {
            const res = await api('/api/equipment_all');
            allEquipment = res.data || [];
            renderMaster();
        } catch (e) {
            masterTbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><i class="fa-solid fa-triangle-exclamation" style="color:var(--danger);"></i><p>${esc(e.message)}</p></div></td></tr>`;
        } finally {
            btnRefresh.innerHTML = orig;
            btnRefresh.disabled = false;
        }
    }

    function renderMaster() {
        let rows = allEquipment.filter(eq => strUp(eq.Equipment_Type) === currentTab);

        if (currentFilter !== 'ALL') {
            rows = rows.filter(eq => {
                const s = strUp(eq.Status);
                if (currentFilter === 'FITTED') return s.includes('FIT') || s.includes('SERVICE');
                if (currentFilter === 'STORAGE') return s.includes('STORAGE') || s === '';
                if (currentFilter === 'UNDER_REPAIR') return s.includes('REPAIR') || s.includes('OVERHAUL');
                return true;
            });
        }

        if (rows.length === 0) {
            masterTbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><i class="fa-solid fa-inbox"></i><p>No equipment found</p></div></td></tr>';
            return;
        }

        masterTbody.innerHTML = rows.map(eq => {
            const s = strUp(eq.Status);
            const isFitted = s.includes('FIT') || s.includes('SERVICE') || eq.Current_Loco;
            const isRepair = s.includes('REPAIR') || s.includes('OVERHAUL') || s.includes('UNDER');
            let rowClass, badgeClass;
            if (isFitted) { rowClass = 'row-fitted'; badgeClass = 'badge-fitted'; }
            else if (isRepair) { rowClass = 'row-repair'; badgeClass = 'badge-repair'; }
            else { rowClass = 'row-storage'; badgeClass = 'badge-storage'; }

            const loco = eq.Current_Loco || '-';
            const date = eq.Last_Overhaul_Date || '-';
            const status = eq.Status || 'STORAGE';
            const serial = eq.Serial_No_MFG || '-';
            const eqType = eq.Equipment_Type || currentTab;

            const actionBtn = isFitted
                ? `<button class="btn-danger btn-sm" onclick="openRemoveModal('${esc(eqType)}','${esc(serial)}','${esc(loco)}')"><i class="fa-solid fa-eject"></i> Remove</button>`
                : `<button class="btn-success btn-sm" onclick="openFitModal('${esc(eqType)}','${esc(serial)}')"><i class="fa-solid fa-wrench"></i> Fit</button>`;

            return `<tr class="${rowClass}">
                <td class="col-serial">${esc(serial)}</td>
                <td>${esc(eq.Make || '-')}</td>
                <td class="col-loco">${loco !== '-' ? esc(loco) : '<span style="color:var(--text-3);">—</span>'}</td>
                <td class="col-date">${esc(date)}</td>
                <td><span class="badge ${badgeClass}">${esc(status)}</span></td>
                <td>${actionBtn}</td>
            </tr>`;
        }).join('');
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTab = btn.getAttribute('data-type');
            if (allEquipment.length === 0) loadMaster();
            else renderMaster();
        });
    });

    statusFilter.addEventListener('change', e => { currentFilter = e.target.value; renderMaster(); });
    btnRefresh.addEventListener('click', loadMaster);

    document.querySelector('a[data-target="equip-master"]').addEventListener('click', () => {
        if (allEquipment.length === 0) loadMaster();
    });

    // --- MODAL ACTIONS ---
    let _rmType = '', _rmSerial = '', _rmLoco = '';
    let _fitType = '', _fitSerial = '';

    window.openRemoveModal = function(type, serial, loco) {
        _rmType = type; _rmSerial = serial; _rmLoco = loco;
        document.getElementById('rm-eq-display').textContent = `${type}  —  ${serial}`;
        document.getElementById('rm-loco-no').textContent = loco;
        document.getElementById('rm-date').value = todayDDMMYYYY();
        document.getElementById('rm-oh').value = '';
        document.getElementById('rm-remarks').value = '';
        document.getElementById('modal-remove').classList.add('open');
    };

    window.openFitModal = function(type, serial) {
        _fitType = type; _fitSerial = serial;
        document.getElementById('fit-eq-display').textContent = `${type}  —  ${serial}`;
        document.getElementById('fit-loco').value = '';
        document.getElementById('fit-date').value = todayDDMMYYYY();
        document.getElementById('fit-remarks').value = '';
        document.getElementById('modal-fit').classList.add('open');
    };

    window.closeModals = function() {
        document.querySelectorAll('.modal-backdrop').forEach(m => m.classList.remove('open'));
    };

    document.querySelectorAll('.modal-backdrop').forEach(m => {
        m.addEventListener('click', e => { if (e.target === m) closeModals(); });
    });

    document.getElementById('btn-submit-remove').addEventListener('click', async () => {
        const btn = document.getElementById('btn-submit-remove');
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch spin"></i>';
        btn.disabled = true;
        try {
            await api('/api/removal', 'POST', {
                loco_no: _rmLoco,
                serial_no: _rmSerial,
                date: document.getElementById('rm-date').value,
                overhaul_type: document.getElementById('rm-oh').value,
                remarks: document.getElementById('rm-remarks').value
            });
            closeModals();
            loadMaster();
        } catch (e) {
            alert('Error: ' + e.message);
        } finally {
            btn.innerHTML = orig;
            btn.disabled = false;
        }
    });

    document.getElementById('btn-submit-fit').addEventListener('click', async () => {
        const loco = document.getElementById('fit-loco').value.trim();
        if (!loco) { document.getElementById('fit-loco').focus(); return; }
        const btn = document.getElementById('btn-submit-fit');
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch spin"></i>';
        btn.disabled = true;
        try {
            await api('/api/fitment', 'POST', {
                loco_no: loco,
                equipment_type: _fitType,
                serial_no: _fitSerial,
                date: document.getElementById('fit-date').value,
                remarks: document.getElementById('fit-remarks').value
            });
            closeModals();
            loadMaster();
        } catch (e) {
            alert('Error: ' + e.message);
        } finally {
            btn.innerHTML = orig;
            btn.disabled = false;
        }
    });

    // --- HISTORY SEARCH ---
    const btnEquipSearch = document.getElementById('btn-equip-search');
    const equipSearchInput = document.getElementById('equip-search-input');
    const equipResult = document.getElementById('equip-status-result');

    async function searchEquip() {
        const serial = equipSearchInput.value.trim();
        if (!serial) return;
        const orig = btnEquipSearch.innerHTML;
        btnEquipSearch.innerHTML = '<i class="fa-solid fa-circle-notch spin"></i>';
        btnEquipSearch.disabled = true;
        try {
            const res = await api(`/api/equipment/${encodeURIComponent(serial)}`);
            equipResult.style.display = 'block';
            equipResult.textContent = typeof res.data === 'string' ? res.data : JSON.stringify(res.data, null, 2);
        } catch (e) {
            equipResult.style.display = 'block';
            equipResult.textContent = 'Error: ' + e.message;
        } finally {
            btnEquipSearch.innerHTML = orig;
            btnEquipSearch.disabled = false;
        }
    }

    btnEquipSearch.addEventListener('click', searchEquip);
    equipSearchInput.addEventListener('keydown', e => { if (e.key === 'Enter') searchEquip(); });

    // --- OVERHAULS DUE ---
    const btnLoadOverhauls = document.getElementById('btn-load-overhauls');
    const overhaulDays = document.getElementById('overhaul-days');
    const overhaulResult = document.getElementById('overhauls-result');

    async function loadOverhauls() {
        const days = overhaulDays.value;
        const orig = btnLoadOverhauls.innerHTML;
        btnLoadOverhauls.innerHTML = '<i class="fa-solid fa-circle-notch spin"></i>';
        btnLoadOverhauls.disabled = true;
        overhaulResult.innerHTML = '';
        try {
            const res = await api(`/api/reports/upcoming?days=${days}`);
            const items = res.data;
            if (!items || items.length === 0) {
                overhaulResult.innerHTML = '<div class="empty-state"><i class="fa-regular fa-bell"></i><p>No overhauls due in this period</p></div>';
                return;
            }
            const html = items.map(item => {
                const d = item.days ?? item.days_remaining ?? 0;
                const iconClass = d < 0 ? 'overdue' : d <= 14 ? 'soon' : 'ok';
                const icon = d < 0 ? 'fa-triangle-exclamation' : 'fa-clock';
                const daysText = d < 0 ? `${Math.abs(d)} days overdue` : `${d} days`;
                const daysColor = d < 0 ? 'var(--danger)' : d <= 14 ? 'var(--warning)' : 'var(--accent)';
                return `<div class="overhaul-item">
                    <div class="ov-icon ${iconClass}"><i class="fa-solid ${icon}"></i></div>
                    <div class="ov-info">
                        <div class="ov-title">${esc(item.type)} &mdash; ${esc(item.serial)}</div>
                        <div class="ov-meta">Due: ${esc(item.due)} &bull; Loco: ${esc(item.loco)}</div>
                    </div>
                    <div class="ov-days">
                        <div class="num" style="color:${daysColor};">${esc(daysText)}</div>
                        <div class="lbl">remaining</div>
                    </div>
                </div>`;
            }).join('');
            overhaulResult.innerHTML = `<div class="overhaul-list">${html}</div>`;
        } catch (e) {
            overhaulResult.innerHTML = `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation" style="color:var(--danger);"></i><p>${esc(e.message)}</p></div>`;
        } finally {
            btnLoadOverhauls.innerHTML = orig;
            btnLoadOverhauls.disabled = false;
        }
    }

    btnLoadOverhauls.addEventListener('click', loadOverhauls);

    document.querySelector('a[data-target="overhauls"]').addEventListener('click', () => {
        if (!overhaulResult.innerHTML) loadOverhauls();
    });

    // --- AI PARSING ---
    async function runAIParse(btnId, textId, errId, step2Id, isAdd) {
        const btn = document.getElementById(btnId);
        const text = document.getElementById(textId).value.trim();
        const err = document.getElementById(errId);
        const step2 = document.getElementById(step2Id);
        if (!text) { err.textContent = 'Please enter a message first'; err.classList.add('show'); return; }

        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch spin"></i> Parsing…';
        btn.disabled = true;
        err.classList.remove('show');

        try {
            const res = await api('/api/parse_message', 'POST', { message: text });
            const d = res.parsed.data;
            if (isAdd) {
                document.getElementById('a_equipment_type').value = d.equipment_type || 'MPH';
                document.getElementById('a_serial_no').value = d.serial_no || '';
                document.getElementById('a_mfg_date').value = d.mfg_date || '';
                document.getElementById('a_remarks').value = d.original_message || text;
                document.getElementById('a_status').value = (d.status || '').toUpperCase().includes('REPAIR') ? 'UNDER_REPAIR' : 'STORAGE';
            } else {
                document.getElementById('f_loco_no').value = d.loco_no || '';
                document.getElementById('f_equipment_type').value = d.equipment_type || 'MPH';
                document.getElementById('f_serial_no').value = d.serial_no || '';
                document.getElementById('f_date').value = d.fitment_date || d.date || todayDDMMYYYY();
                document.getElementById('f_make').value = d.make || '';
                document.getElementById('f_loc_serial').value = d.loc_serial || '';
                document.getElementById('f_remarks').value = d.original_message || text;
            }
            step2.style.display = 'block';
            step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (e) {
            err.textContent = 'AI parsing failed: ' + e.message;
            err.classList.add('show');
        } finally {
            btn.innerHTML = orig;
            btn.disabled = false;
        }
    }

    document.getElementById('btn-parse-fitment').addEventListener('click', () => {
        runAIParse('btn-parse-fitment', 'ai-fitment-text', 'ai-fitment-error', 'fitment-step2', false);
    });

    document.getElementById('btn-parse-add').addEventListener('click', () => {
        runAIParse('btn-parse-add', 'ai-add-text', 'ai-add-error', 'add-step2', true);
    });

    // --- FORM SUBMITS ---
    document.getElementById('form-fitment').addEventListener('submit', async e => {
        e.preventDefault();
        const btn = e.target.querySelector('button[type="submit"]');
        const msg = document.getElementById('fitment-msg');
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch spin"></i> Submitting…';
        btn.disabled = true;
        msg.className = 'form-msg';
        try {
            const fd = new FormData(e.target);
            const res = await api('/api/fitment', 'POST', Object.fromEntries(fd));
            msg.textContent = res.message || 'Success';
            msg.classList.add('success');
            e.target.reset();
            document.getElementById('fitment-step2').style.display = 'none';
        } catch (err) {
            msg.textContent = err.message;
            msg.classList.add('error');
        } finally {
            btn.innerHTML = orig;
            btn.disabled = false;
        }
    });

    document.getElementById('form-add').addEventListener('submit', async e => {
        e.preventDefault();
        const btn = e.target.querySelector('button[type="submit"]');
        const msg = document.getElementById('add-msg');
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch spin"></i> Submitting…';
        btn.disabled = true;
        msg.className = 'form-msg';
        try {
            const fd = new FormData(e.target);
            const res = await api('/api/add_equipment', 'POST', Object.fromEntries(fd));
            msg.textContent = res.message || 'Equipment added';
            msg.classList.add('success');
            e.target.reset();
            document.getElementById('add-step2').style.display = 'none';
        } catch (err) {
            msg.textContent = err.message;
            msg.classList.add('error');
        } finally {
            btn.innerHTML = orig;
            btn.disabled = false;
        }
    });

    // --- UTIL ---
    function todayDDMMYYYY() {
        const d = new Date();
        const dd = String(d.getDate()).padStart(2, '0');
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        return `${dd}-${mm}-${d.getFullYear()}`;
    }

});
