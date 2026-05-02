document.addEventListener('DOMContentLoaded', () => {
    // --- Navigation Logic ---
    const navLinks = document.querySelectorAll('.nav-links a');
    const views = document.querySelectorAll('.view');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('data-target');
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            views.forEach(v => v.classList.remove('active-view'));
            document.getElementById(targetId).classList.add('active-view');
        });
    });

    // --- API Helper ---
    async function fetchApi(endpoint, method = 'GET', body = null) {
        const options = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) options.body = JSON.stringify(body);
        try {
            const response = await fetch(endpoint, options);
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || data.error || 'API Error');
            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // --- Loco Dashboard Logic ---
    const btnLocoSearch = document.getElementById('btn-loco-search');
    const inputLocoSearch = document.getElementById('loco-search-input');
    const locoStatusContainer = document.getElementById('loco-status-container');
    const locoInfoCard = document.getElementById('loco-info-card');
    const equipmentAccordion = document.getElementById('equipment-accordion');
    const messagesTableBody = document.querySelector('#messages-table tbody');
    const locoErrorBox = document.getElementById('loco-error');

    btnLocoSearch.addEventListener('click', async () => {
        const locoNo = inputLocoSearch.value.trim();
        if (!locoNo) return;
        
        const originalText = btnLocoSearch.innerHTML;
        btnLocoSearch.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
        btnLocoSearch.disabled = true;
        locoErrorBox.style.display = 'none';
        
        try {
            const res = await fetchApi(`/api/status/${locoNo}`);
            if (res.error) throw new Error(res.error);
            locoStatusContainer.style.display = 'block';
            
            // Top Card
            const info = res.loco_info;
            locoInfoCard.innerHTML = `
                <div class="info-grid">
                    <div class="info-item"><span class="info-label">Locomotive</span><span class="info-val" style="font-size:1.5rem;font-weight:700;color:var(--accent-color);">${info.loco_no}</span></div>
                    <div class="info-item"><span class="info-label">Type</span><span class="info-val">${info.type}</span></div>
                    <div class="info-item"><span class="info-label">DOC</span><span class="info-val">${info.doc}</span></div>
                    <div class="info-item"><span class="info-label">Last Major</span><span class="info-val">${info.last_major}</span></div>
                    <div class="info-item"><span class="info-label">Next Major</span><span class="info-val">${info.next_major}</span></div>
                    <div class="info-item"><span class="info-label">Status</span><span class="status-badge">${info.status}</span></div>
                </div>
            `;
            
            // Accordion
            equipmentAccordion.innerHTML = '';
            if (res.equipment && res.equipment.length > 0) {
                res.equipment.forEach(eq => {
                    equipmentAccordion.innerHTML += `
                        <div class="acc-item">
                            <div class="acc-header" onclick="toggleAccordion(this)">
                                <span>${eq.type} (${eq.serial_mfg})</span><i class="fa-solid fa-chevron-down"></i>
                            </div>
                            <div class="acc-content">
                                <div class="acc-body">
                                    <div><span class="info-label">Make:</span> ${eq.make}</div>
                                    <div><span class="info-label">Mfg Date:</span> ${eq.mfg_date}</div>
                                    <div><span class="info-label">Fitment Date:</span> ${eq.fitment_date}</div>
                                    <div><span class="info-label">Last OH:</span> ${eq.last_oh}</div>
                                    <div><span class="info-label">Status:</span> ${eq.status}</div>
                                    <div style="grid-column: 1 / -1;"><span class="info-label">Notes:</span> ${eq.notes}</div>
                                </div>
                            </div>
                        </div>`;
                });
            } else {
                equipmentAccordion.innerHTML = '<p>No equipment fitted.</p>';
            }
            
            // Messages
            messagesTableBody.innerHTML = '';
            if (res.messages && res.messages.length > 0) {
                res.messages.forEach(msg => {
                    messagesTableBody.innerHTML += `<tr><td style="white-space:nowrap;">${msg.date}</td><td>${msg.text}</td><td><i class="fa-solid fa-user-astronaut"></i> ${msg.user}</td></tr>`;
                });
            } else {
                messagesTableBody.innerHTML = '<tr><td colspan="3" style="text-align:center;">No recent messages</td></tr>';
            }
        } catch (e) {
            locoStatusContainer.style.display = 'none';
            locoErrorBox.textContent = '❌ ' + e.message;
            locoErrorBox.style.display = 'block';
        } finally {
            btnLocoSearch.innerHTML = originalText;
            btnLocoSearch.disabled = false;
        }
    });

    window.toggleAccordion = function(headerElement) {
        const item = headerElement.parentElement;
        document.querySelectorAll('.acc-item').forEach(el => { if (el !== item) el.classList.remove('active'); });
        item.classList.toggle('active');
    };

    // --- EQUIPMENT MASTER INVENTORY LOGIC ---
    let allEquipment = [];
    let currentTab = 'MPH';
    let currentFilter = 'ALL';
    
    const masterTableBody = document.querySelector('#master-table tbody');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const statusFilter = document.getElementById('eq-status-filter');
    const btnRefreshMaster = document.getElementById('btn-refresh-master');

    async function loadMasterData() {
        btnRefreshMaster.innerHTML = '<i class="fa-solid fa-rotate fa-spin"></i>';
        try {
            const res = await fetchApi('/api/equipment_all');
            allEquipment = res.data || [];
            renderMasterTable();
        } catch (e) {
            console.error(e);
            masterTableBody.innerHTML = `<tr><td colspan="6" class="error">Failed to load data: ${e.message}</td></tr>`;
        } finally {
            btnRefreshMaster.innerHTML = '<i class="fa-solid fa-rotate"></i> Refresh';
        }
    }

    function renderMasterTable() {
        masterTableBody.innerHTML = '';
        let filtered = allEquipment.filter(eq => strEq(eq.Equipment_Type) === currentTab);
        
        if (currentFilter !== 'ALL') {
            filtered = filtered.filter(eq => {
                const s = strEq(eq.Status);
                if (currentFilter === 'FITTED') return s.includes('FIT') || s.includes('SERVICE');
                if (currentFilter === 'STORAGE') return s.includes('STORAGE') || s === '';
                if (currentFilter === 'UNDER_REPAIR') return s.includes('REPAIR') || s.includes('OVERHAUL');
                return true;
            });
        }

        if (filtered.length === 0) {
            masterTableBody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);">No equipment found.</td></tr>';
            return;
        }

        filtered.forEach(eq => {
            const statusRaw = strEq(eq.Status).toUpperCase();
            let rowClass = 'row-unknown';
            let badgeClass = 'badge-storage';
            let isFitted = false;
            
            if (statusRaw.includes('FIT') || statusRaw.includes('SERVICE') || eq.Current_Loco) {
                rowClass = 'row-fitted'; badgeClass = 'badge-fitted'; isFitted = true;
            } else if (statusRaw.includes('REPAIR') || statusRaw.includes('OVERHAUL') || statusRaw.includes('UNDER')) {
                rowClass = 'row-repair'; badgeClass = 'badge-repair';
            } else {
                rowClass = 'row-storage'; badgeClass = 'badge-storage';
            }

            const statusText = eq.Status || 'STORAGE';
            const loco = eq.Current_Loco || '-';
            const date = eq.Last_Overhaul_Date || '-';
            
            let actionBtn = '';
            if (isFitted) {
                actionBtn = `<button class="btn-danger btn-sm" onclick="openRemoveModal('${eq.Equipment_Type}', '${eq.Serial_No_MFG}', '${loco}')"><i class="fa-solid fa-eject"></i> Remove</button>`;
            } else {
                actionBtn = `<button class="btn-success btn-sm" onclick="openFitModal('${eq.Equipment_Type}', '${eq.Serial_No_MFG}')"><i class="fa-solid fa-wrench"></i> Fit</button>`;
            }

            masterTableBody.innerHTML += `
                <tr class="${rowClass}">
                    <td style="font-weight:600;">${eq.Serial_No_MFG}</td>
                    <td>${eq.Make || '-'}</td>
                    <td>${loco}</td>
                    <td>${date}</td>
                    <td><span class="status-badge ${badgeClass}">${statusText}</span></td>
                    <td>${actionBtn}</td>
                </tr>
            `;
        });
    }

    function strEq(val) { return String(val || '').trim().toUpperCase(); }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTab = btn.getAttribute('data-type');
            renderMasterTable();
        });
    });

    statusFilter.addEventListener('change', (e) => {
        currentFilter = e.target.value;
        renderMasterTable();
    });

    btnRefreshMaster.addEventListener('click', loadMasterData);

    // Initial Load when navigating to Equipment Master
    document.querySelector('a[data-target="equip-master"]').addEventListener('click', () => {
        if (allEquipment.length === 0) loadMasterData();
    });

    // --- MODAL ACTIONS LOGIC ---
    let currentActionEqType = '';
    let currentActionSerial = '';
    let currentActionLoco = '';

    window.openRemoveModal = function(type, serial, loco) {
        currentActionEqType = type; currentActionSerial = serial; currentActionLoco = loco;
        document.getElementById('rm-eq-type').textContent = type;
        document.getElementById('rm-eq-serial').textContent = serial;
        document.getElementById('rm-loco-no').textContent = loco;
        document.getElementById('modal-remove').classList.add('active');
        document.getElementById('rm-date').value = new Date().toLocaleDateString('en-GB').replace(/\//g, '-');
    };

    window.openFitModal = function(type, serial) {
        currentActionEqType = type; currentActionSerial = serial;
        document.getElementById('fit-eq-type').textContent = type;
        document.getElementById('fit-eq-serial').textContent = serial;
        document.getElementById('modal-fit').classList.add('active');
        document.getElementById('fit-date').value = new Date().toLocaleDateString('en-GB').replace(/\//g, '-');
    };

    window.closeModals = function() {
        document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
    };

    document.getElementById('btn-submit-remove').addEventListener('click', async () => {
        const btn = document.getElementById('btn-submit-remove');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        btn.disabled = true;
        try {
            await fetchApi('/api/removal', 'POST', {
                loco_no: currentActionLoco, serial_no: currentActionSerial,
                date: document.getElementById('rm-date').value,
                overhaul_type: document.getElementById('rm-oh').value,
                remarks: document.getElementById('rm-remarks').value
            });
            closeModals();
            loadMasterData(); // refresh table
            alert('Successfully removed!');
        } catch (e) {
            alert('Error: ' + e.message);
        } finally {
            btn.innerHTML = 'Confirm Removal'; btn.disabled = false;
        }
    });

    document.getElementById('btn-submit-fit').addEventListener('click', async () => {
        const btn = document.getElementById('btn-submit-fit');
        const loco = document.getElementById('fit-loco').value.trim();
        if (!loco) return alert('Target Loco No is required');
        
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        btn.disabled = true;
        try {
            await fetchApi('/api/fitment', 'POST', {
                loco_no: loco, equipment_type: currentActionEqType, serial_no: currentActionSerial,
                date: document.getElementById('fit-date').value,
                remarks: document.getElementById('fit-remarks').value
            });
            closeModals();
            loadMasterData(); // refresh table
            alert('Successfully fitted!');
        } catch (e) {
            alert('Error: ' + e.message);
        } finally {
            btn.innerHTML = 'Confirm Fitment'; btn.disabled = false;
        }
    });

    // --- AI PARSING FORMS ---
    async function handleAIParsing(btnId, textId, errorId, step2Id, isAddForm) {
        const btn = document.getElementById(btnId);
        const textElem = document.getElementById(textId);
        const errorBox = document.getElementById(errorId);
        const step2 = document.getElementById(step2Id);
        const originalText = btn.innerHTML;

        const text = textElem.value.trim();
        if (!text) {
            errorBox.textContent = 'Please enter a message'; errorBox.style.display = 'block'; return;
        }
        
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Parsing with Groq AI...';
        btn.disabled = true; errorBox.style.display = 'none';

        try {
            const res = await fetchApi('/api/parse_message', 'POST', { message: text });
            const data = res.parsed.data;
            
            // Map parsed data to inputs depending on which form
            if (isAddForm) {
                document.getElementById('a_equipment_type').value = data.equipment_type || 'MPH';
                document.getElementById('a_serial_no').value = data.serial_no || '';
                document.getElementById('a_mfg_date').value = data.mfg_date || '';
                document.getElementById('a_remarks').value = data.original_message || '';
                if (data.status && data.status.toUpperCase().includes('REPAIR')) {
                    document.getElementById('a_status').value = 'UNDER_REPAIR';
                } else {
                    document.getElementById('a_status').value = 'STORAGE';
                }
            } else {
                document.getElementById('f_loco_no').value = data.loco_no || '';
                document.getElementById('f_equipment_type').value = data.equipment_type || 'MPH';
                document.getElementById('f_serial_no').value = data.serial_no || '';
                document.getElementById('f_date').value = data.fitment_date || new Date().toLocaleDateString('en-GB').replace(/\//g, '-');
                document.getElementById('f_make').value = data.make || '';
                document.getElementById('f_loc_serial').value = data.loc_serial || '';
                document.getElementById('f_remarks').value = data.original_message || '';
            }
            
            step2.style.display = 'block';
            step2.scrollIntoView({ behavior: 'smooth' });

        } catch (e) {
            errorBox.textContent = '❌ AI Parsing Failed: ' + e.message;
            errorBox.style.display = 'block';
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }

    document.getElementById('btn-parse-fitment').addEventListener('click', () => {
        handleAIParsing('btn-parse-fitment', 'ai-fitment-text', 'ai-fitment-error', 'fitment-step2', false);
    });

    document.getElementById('btn-parse-add').addEventListener('click', () => {
        handleAIParsing('btn-parse-add', 'ai-add-text', 'ai-add-error', 'add-step2', true);
    });

    // Final Form Submits
    document.getElementById('form-fitment').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button'); btn.disabled = true; btn.innerHTML = 'Processing...';
        try {
            const fd = new FormData(e.target);
            const res = await fetchApi('/api/fitment', 'POST', Object.fromEntries(fd));
            document.getElementById('fitment-msg').textContent = '✅ Success: ' + res.message;
            document.getElementById('fitment-msg').className = 'form-msg success';
            e.target.reset(); document.getElementById('fitment-step2').style.display = 'none';
        } catch (err) {
            document.getElementById('fitment-msg').textContent = '❌ ' + err.message;
            document.getElementById('fitment-msg').className = 'form-msg error';
        } finally { btn.disabled = false; btn.innerHTML = 'Final Submit'; }
    });

    document.getElementById('form-add').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button'); btn.disabled = true; btn.innerHTML = 'Processing...';
        try {
            const fd = new FormData(e.target);
            const res = await fetchApi('/api/add_equipment', 'POST', Object.fromEntries(fd));
            document.getElementById('add-msg').textContent = '✅ Success: ' + res.message;
            document.getElementById('add-msg').className = 'form-msg success';
            e.target.reset(); document.getElementById('add-step2').style.display = 'none';
        } catch (err) {
            document.getElementById('add-msg').textContent = '❌ ' + err.message;
            document.getElementById('add-msg').className = 'form-msg error';
        } finally { btn.disabled = false; btn.innerHTML = 'Final Submit'; }
    });
});
