// ═══════════════════════════════════════════════════════
//  TAMAKUN Dashboard JS
// ═══════════════════════════════════════════════════════

let currentTables = null;
let currentMode = 'db'; // 'db' or 'file'

// ── Source Switching ────────────────────────────────────
function switchSource(mode) {
    currentMode = mode;
    document.getElementById('dbSection').style.display = mode === 'db' ? 'block' : 'none';
    document.getElementById('fileSection').style.display = mode === 'file' ? 'block' : 'none';
    document.getElementById('tabDb').classList.toggle('active', mode === 'db');
    document.getElementById('tabFile').classList.toggle('active', mode === 'file');
}

// ── File Upload Setup ──────────────────────────────────
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const dropZone = document.getElementById('dropZone');
const uploadForm = document.getElementById('uploadForm');

if (fileInput) {
    fileInput.addEventListener('change', function () {
        if (this.files.length > 0) {
            fileName.textContent = this.files[0].name;
        }
    });
}

if (dropZone) {
    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        this.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', function () {
        this.classList.remove('dragover');
    });
    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        this.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            fileName.textContent = e.dataTransfer.files[0].name;
        }
    });
}

// ── Status Filter (Checkbox Multi-Select) ──────────────
function toggleAllStatuses(allCheckbox) {
    const container = document.getElementById('statusFilter');
    const checkboxes = container.querySelectorAll('input[name="status"]');
    checkboxes.forEach(cb => {
        cb.checked = allCheckbox.checked;
    });
}

// When individual status checkboxes change, update "الكل" state
document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('statusFilter');
    if (container) {
        const allCheckbox = container.querySelector('input[value="__all__"]');
        const statusCheckboxes = container.querySelectorAll('input[name="status"]');
        statusCheckboxes.forEach(cb => {
            cb.addEventListener('change', function () {
                if (allCheckbox) {
                    const allChecked = Array.from(statusCheckboxes).every(c => c.checked);
                    allCheckbox.checked = allChecked;
                }
            });
        });
    }
});

function getSelectedStatuses() {
    const container = document.getElementById('statusFilter');
    const allCheckbox = container.querySelector('input[value="__all__"]');
    if (allCheckbox && allCheckbox.checked) {
        return []; // empty = all statuses
    }
    const checked = container.querySelectorAll('input[name="status"]:checked');
    return Array.from(checked).map(cb => cb.value);
}

// ── Date Presets ────────────────────────────────────────
function setDatePreset(days, btnElement) {
    const dateTo = document.getElementById('dateTo');
    const dateFrom = document.getElementById('dateFrom');
    const customDiv = document.getElementById('customDays');

    // Highlight active preset button
    document.querySelectorAll('.date-preset-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    if (btnElement) {
        btnElement.classList.add('active');
    }

    if (days === 0) {
        customDiv.style.display = 'flex';
        return;
    }

    customDiv.style.display = 'none';
    const now = new Date();
    dateTo.value = now.toISOString().split('T')[0];
    const from = new Date(now);
    from.setDate(from.getDate() - days);
    dateFrom.value = from.toISOString().split('T')[0];
}

function applyCustomDays() {
    const days = parseInt(document.getElementById('customDaysInput').value);
    if (days > 0) {
        setDatePreset(days, null);
        document.getElementById('customDays').style.display = 'none';
        // Highlight the "مخصص" button
        const customBtn = document.querySelector('.date-preset-btn:last-child');
        document.querySelectorAll('.date-preset-btn').forEach(btn => btn.classList.remove('active'));
        if (customBtn) customBtn.classList.add('active');
    }
}

// ── Fetch from DB ──────────────────────────────────────
async function fetchFromDb() {
    const selectedStatuses = getSelectedStatuses();

    const formData = new FormData();
    formData.append('brand_key', window.BRAND_KEY);
    formData.append('status_values', selectedStatuses.join(','));
    formData.append('date_from', document.getElementById('dateFrom').value || '');
    formData.append('date_to', document.getElementById('dateTo').value || '');

    showLoading(true);

    try {
        const resp = await fetch('/api/fetch-db', {
            method: 'POST',
            body: formData,
        });
        const data = await resp.json();

        if (data.error) {
            alert(data.error);
            showLoading(false);
            return;
        }

        currentTables = data.tables;
        renderResults(data);
        showLoading(false);
    } catch (err) {
        alert('خطأ في الاتصال: ' + err.message);
        showLoading(false);
    }
}

// ── Upload Form Submit ─────────────────────────────────
if (uploadForm) {
    uploadForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (!fileInput.files || fileInput.files.length === 0) {
            alert('يرجى اختيار ملف');
            return;
        }

        const formData = new FormData();
        formData.append('brand_key', window.BRAND_KEY);
        formData.append('file', fileInput.files[0]);

        showLoading(true);

        try {
            const resp = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });
            const data = await resp.json();

            if (data.error) {
                alert(data.error);
                showLoading(false);
                return;
            }

            currentTables = data.tables;
            renderResults(data);
            showLoading(false);
        } catch (err) {
            alert('خطأ في الاتصال: ' + err.message);
            showLoading(false);
        }
    });
}

// ── Render Results ─────────────────────────────────────
function renderResults(data) {
    document.getElementById('totalRows').textContent = data.total_rows || 0;
    document.getElementById('filteredRows').textContent = data.filtered_rows || 0;

    const container = document.getElementById('tablesContainer');
    container.innerHTML = '';

    const tables = data.tables.tables || [];

    tables.forEach((table, tableIdx) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'dashboard-table-wrapper';

        const title = document.createElement('h3');
        title.textContent = table.title;
        wrapper.appendChild(title);

        const tbl = document.createElement('table');
        tbl.className = 'dashboard-table';

        // Header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        table.columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        tbl.appendChild(thead);

        // Body
        const tbody = document.createElement('tbody');
        table.rows.forEach((rowData, rowIdx) => {
            const tr = document.createElement('tr');
            table.columns.forEach((col, colIdx) => {
                const td = document.createElement('td');
                td.textContent = rowData[col] !== undefined ? rowData[col] : '';

                // Make numeric cells editable (skip first column = label)
                if (colIdx > 0) {
                    td.contentEditable = 'true';
                    td.dataset.tableIdx = tableIdx;
                    td.dataset.rowIdx = rowIdx;
                    td.dataset.colName = col;
                    td.addEventListener('blur', onCellEdit);
                }

                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        tbl.appendChild(tbody);
        wrapper.appendChild(tbl);
        container.appendChild(wrapper);
    });

    document.getElementById('resultsSection').style.display = 'block';
}

// ── Cell Edit Handler ──────────────────────────────────
function onCellEdit(e) {
    const td = e.target;
    const tableIdx = parseInt(td.dataset.tableIdx);
    const rowIdx = parseInt(td.dataset.rowIdx);
    const colName = td.dataset.colName;
    const newValue = td.textContent.trim();

    if (currentTables && currentTables.tables[tableIdx]) {
        const parsedValue = isNaN(newValue) ? newValue : parseFloat(newValue);
        currentTables.tables[tableIdx].rows[rowIdx][colName] = parsedValue;
    }
}

// ── Export Excel ───────────────────────────────────────
async function exportExcel() {
    if (!currentTables) {
        alert('لا توجد بيانات للتصدير');
        return;
    }

    readEditsFromDom();

    try {
        const resp = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                brand_key: window.BRAND_KEY,
                tables: currentTables,
            }),
        });
        const data = await resp.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        window.location.href = data.download_url;
    } catch (err) {
        alert('خطأ في التصدير: ' + err.message);
    }
}

// ── Read edits from DOM ────────────────────────────────
function readEditsFromDom() {
    const editableCells = document.querySelectorAll('.dashboard-table td[contenteditable="true"]');
    editableCells.forEach(td => {
        const tableIdx = parseInt(td.dataset.tableIdx);
        const rowIdx = parseInt(td.dataset.rowIdx);
        const colName = td.dataset.colName;
        const val = td.textContent.trim();
        if (currentTables && currentTables.tables[tableIdx]) {
            currentTables.tables[tableIdx].rows[rowIdx][colName] = isNaN(val) ? val : parseFloat(val);
        }
    });
}

// ── Utility ────────────────────────────────────────────
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
    if (show) {
        document.getElementById('resultsSection').style.display = 'none';
    }
}
