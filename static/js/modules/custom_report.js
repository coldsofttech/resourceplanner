'use strict';

import { apiFetch, escHtml, showFlash } from './../main.js';
import { API_URLS } from './../urls.js';

// ── State ──────────────────────────────────────────────────────────────────

const _s = {
    reportPk:      window.REPORT_PK || null,
    name:          'Untitled Report',
    dataSource:    '',
    visualization: 'table',
    config: {
        fields:  [],
        filters: [],
        axis:    '',
        legend:  '',
        rows:    '',
        columns: '',
        values:  [{ field: 'id', aggregation: 'count' }],
    },
    dataSources:  [],   // [{key, label, app_label, fields}]
    fieldDefs:    [],   // current table's field defs
    chartInst:    null, // Chart.js instance
    dirty:        false,
    running:      false,
};

const AGGRS = ['count', 'count_distinct', 'sum', 'average', 'minimum', 'maximum'];
const AGGR_LABELS = { count: 'COUNT', count_distinct: 'COUNT DISTINCT', sum: 'SUM', average: 'AVG', minimum: 'MIN', maximum: 'MAX' };
const OPS = [
    { value: 'eq',          label: '=' },
    { value: 'neq',         label: '≠' },
    { value: 'gt',          label: '>' },
    { value: 'gte',         label: '≥' },
    { value: 'lt',          label: '<' },
    { value: 'lte',         label: '≤' },
    { value: 'contains',    label: 'contains' },
    { value: 'starts_with', label: 'starts with' },
    { value: 'is_null',     label: 'is empty' },
];
const VIZ_CONFIG = {
    table:       { slots: ['fields'] },
    pivot:       { slots: ['rows', 'columns', 'values'] },
    bar:         { slots: ['axis', 'legend', 'values'] },
    stacked_bar: { slots: ['axis', 'legend', 'values'] },
    pie:         { slots: ['axis', 'values'] },
    line:        { slots: ['axis', 'legend', 'values'] },
    heatmap:     { slots: ['rows', 'columns', 'values'] },
};

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    await loadDataSources();
    if (_s.reportPk && _s.reportPk !== 'null') {
        await loadExistingReport();
    }
    wireUI();
});

async function loadDataSources() {
    try {
        const sources = await apiFetch(API_URLS.custom_reports.dataSources.href, { method: 'GET' });
        _s.dataSources = sources;
        const sel = document.getElementById('cr-ds-select');
        sources.forEach(ds => {
            const opt = document.createElement('option');
            opt.value = ds.key;
            opt.textContent = ds.label;
            sel.appendChild(opt);
        });
    } catch (e) {
        showFlash('Failed to load data sources.', 'danger');
    }
}

async function loadExistingReport() {
    try {
        const { href } = API_URLS.custom_reports.detail(_s.reportPk);
        const report = await apiFetch(href, { method: 'GET' });
        _s.name          = report.name;
        _s.dataSource    = report.data_source;
        _s.visualization = report.visualization;
        _s.config        = Object.assign({ fields: [], filters: [], axis: '', legend: '', rows: '', columns: '', values: [{ field: 'id', aggregation: 'count' }] }, report.config);

        document.getElementById('cr-name').value = _s.name;

        if (_s.dataSource) {
            const sel = document.getElementById('cr-ds-select');
            sel.value = _s.dataSource;
            await selectDataSource(_s.dataSource);
        }

        setVizActive(_s.visualization);
        renderConfigSlots();
        loadShareList(report.shares);
    } catch {
        showFlash('Failed to load report.', 'danger');
    }
}

function wireUI() {
    document.getElementById('cr-ds-select').addEventListener('change', async (e) => {
        await selectDataSource(e.target.value);
    });
    document.getElementById('cr-name').addEventListener('input', (e) => {
        _s.name = e.target.value;
        _s.dirty = true;
    });
    document.getElementById('btn-cr-save').addEventListener('click', saveReport);
    document.getElementById('btn-cr-run').addEventListener('click', executeReport);
    document.getElementById('cr-export-csv').addEventListener('click', (e) => { e.preventDefault(); exportReport('csv'); });
    document.getElementById('cr-export-xlsx').addEventListener('click', (e) => { e.preventDefault(); exportReport('xlsx'); });
    document.getElementById('cr-export-img').addEventListener('click', (e) => { e.preventDefault(); exportImage(); });
    document.getElementById('btn-share-add').addEventListener('click', addShare);
    loadUserList();
}

async function selectDataSource(key) {
    _s.dataSource = key;
    const ds = _s.dataSources.find(d => d.key === key);
    _s.fieldDefs = ds ? (ds.fields || []) : [];
    renderFieldList();
    // Reset config fields
    _s.config.fields  = [];
    _s.config.axis    = '';
    _s.config.legend  = '';
    _s.config.rows    = '';
    _s.config.columns = '';
    _s.config.values  = [{ field: 'id', aggregation: 'count' }];
    renderConfigSlots();
    _s.dirty = true;
}

// ── Field list (left panel) ────────────────────────────────────────────────

function renderFieldList() {
    const el = document.getElementById('cr-fields-list');
    if (!_s.fieldDefs.length) {
        el.innerHTML = '<p class="text-secondary" style="font-size:12px;padding:4px 8px">Select a data source to see fields.</p>';
        return;
    }
    el.innerHTML = _s.fieldDefs.map(f => `
        <div class="cr-field-item" onclick="crAddField('${escAttr(f.key)}', '${escAttr(f.label)}')" title="Click to add ${escHtml(f.label)}">
            <span class="cr-ft cr-ft-${f.type}">${f.type.substring(0,3).toUpperCase()}</span>
            <span>${escHtml(f.label)}</span>
        </div>`).join('');
}

window.crAddField = function(key, label) {
    const viz  = _s.visualization;
    const slots = VIZ_CONFIG[viz]?.slots || ['fields'];

    if (slots.includes('fields')) {
        if (!_s.config.fields.includes(key)) {
            _s.config.fields.push(key);
            renderConfigSlots();
        }
        return;
    }
    // For axis/rows slots, prompt which slot to put it in
    if (slots.includes('axis') && !_s.config.axis) { _s.config.axis = key; renderConfigSlots(); return; }
    if (slots.includes('legend') && !_s.config.legend) { _s.config.legend = key; renderConfigSlots(); return; }
    if (slots.includes('rows') && !_s.config.rows) { _s.config.rows = key; renderConfigSlots(); return; }
    if (slots.includes('columns') && !_s.config.columns) { _s.config.columns = key; renderConfigSlots(); return; }
    if (slots.includes('values')) {
        const fieldDef = _s.fieldDefs.find(f => f.key === key);
        const aggr = fieldDef?.aggregatable ? 'sum' : 'count';
        _s.config.values.push({ field: key, aggregation: aggr });
        renderConfigSlots();
    }
    _s.dirty = true;
};

// ── Visualization ──────────────────────────────────────────────────────────

window.crSetViz = function(viz) {
    _s.visualization = viz;
    setVizActive(viz);
    renderConfigSlots();
    _s.dirty = true;
};

function setVizActive(viz) {
    document.querySelectorAll('.cr-viz-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.viz === viz);
    });
}

// ── Config slots (center panel) ────────────────────────────────────────────

window.crSwitchTab = function(tab) {
    document.querySelectorAll('.cr-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    document.getElementById('cr-tab-visual').classList.toggle('d-none', tab !== 'visual');
    document.getElementById('cr-tab-filters').classList.toggle('d-none', tab !== 'filters');
};

function renderConfigSlots() {
    const el    = document.getElementById('cr-config-slots');
    const viz   = _s.visualization;
    const slots = VIZ_CONFIG[viz]?.slots || ['fields'];
    const fm    = Object.fromEntries(_s.fieldDefs.map(f => [f.key, f.label]));

    let html = '';

    if (slots.includes('fields')) {
        html += slotHtml('Fields', _s.config.fields.map(k => chipHtml(k, fm[k] || k, `crRemoveField('${k}')`)), 'crSlotClick("fields")');
    }
    if (slots.includes('axis')) {
        const chip = _s.config.axis ? chipHtml(_s.config.axis, fm[_s.config.axis] || _s.config.axis, `crClearSlot('axis')`) : '';
        html += slotHtml('X-Axis', chip, 'crSlotClick("axis")');
    }
    if (slots.includes('legend')) {
        const chip = _s.config.legend ? chipHtml(_s.config.legend, fm[_s.config.legend] || _s.config.legend, `crClearSlot('legend')`) : '';
        html += slotHtml('Legend / Color', chip, 'crSlotClick("legend")');
    }
    if (slots.includes('rows')) {
        const chip = _s.config.rows ? chipHtml(_s.config.rows, fm[_s.config.rows] || _s.config.rows, `crClearSlot('rows')`) : '';
        html += slotHtml('Rows', chip, 'crSlotClick("rows")');
    }
    if (slots.includes('columns')) {
        const chip = _s.config.columns ? chipHtml(_s.config.columns, fm[_s.config.columns] || _s.config.columns, `crClearSlot('columns')`) : '';
        html += slotHtml('Columns', chip, 'crSlotClick("columns")');
    }
    if (slots.includes('values')) {
        html += `<div class="cr-slot">
            <div class="cr-slot-label d-flex justify-content-between align-items-center">
                <span>Values</span>
                <span class="btn btn-ghost-icon btn-sm p-0" onclick="crAddValue()" title="Add value"><i class="bi bi-plus-circle" style="font-size:14px"></i></span>
            </div>`;
        (_s.config.values.length ? _s.config.values : []).forEach((v, i) => {
            const flabel = fm[v.field] || v.field || 'field';
            html += `<div class="cr-value-row">
                <select onchange="crUpdateValue(${i},'field',this.value)" title="Field">
                    ${_s.fieldDefs.map(f => `<option value="${escAttr(f.key)}" ${f.key === v.field ? 'selected' : ''}>${escHtml(f.label)}</option>`).join('')}
                </select>
                <select onchange="crUpdateValue(${i},'aggregation',this.value)" title="Aggregation">
                    ${AGGRS.map(a => `<option value="${a}" ${a === v.aggregation ? 'selected' : ''}>${AGGR_LABELS[a]}</option>`).join('')}
                </select>
                <span class="ms-auto cr-chip-remove" onclick="crRemoveValue(${i})" title="Remove">×</span>
            </div>`;
        });
        html += '</div>';
    }

    el.innerHTML = html || '<p class="text-secondary small">Pick a data source and visualization.</p>';
}

function slotHtml(label, content, onclick) {
    return `<div class="cr-slot">
        <div class="cr-slot-label">${label}</div>
        <div class="cr-slot-drop" ${onclick ? `onclick="${onclick}"` : ''}>${content || '<span class="text-secondary" style="font-size:11px">Click a field to add…</span>'}</div>
    </div>`;
}

function chipHtml(key, label, removeExpr) {
    return `<span class="cr-slot-chip">${escHtml(label)}<span class="cr-chip-remove" onclick="${removeExpr};event.stopPropagation()">×</span></span>`;
}

window.crRemoveField  = (k)    => { _s.config.fields = _s.config.fields.filter(f => f !== k); renderConfigSlots(); _s.dirty = true; };
window.crClearSlot    = (slot) => { _s.config[slot] = ''; renderConfigSlots(); _s.dirty = true; };
window.crAddValue     = ()     => { _s.config.values.push({ field: _s.fieldDefs[0]?.key || 'id', aggregation: 'count' }); renderConfigSlots(); _s.dirty = true; };
window.crRemoveValue  = (i)    => { _s.config.values.splice(i, 1); renderConfigSlots(); _s.dirty = true; };
window.crUpdateValue  = (i, k, v) => { _s.config.values[i][k] = v; _s.dirty = true; };

window.crSlotClick = function(slot) {
    // Clicking the slot itself when empty — show field picker dropdown
    // For simplicity, just hint to use the left panel
};

// ── Filters ────────────────────────────────────────────────────────────────

window.crAddFilter = function() {
    const field = _s.fieldDefs[0]?.key || '';
    _s.config.filters.push({ field, operator: 'eq', value: '' });
    renderFilterList();
    _s.dirty = true;
};

function renderFilterList() {
    const el    = document.getElementById('cr-filters-list');
    const empty = document.getElementById('cr-filters-empty');
    empty.classList.toggle('d-none', _s.config.filters.length > 0);

    el.innerHTML = _s.config.filters.map((f, i) => `
        <div class="cr-filter-row">
            <select onchange="crUpdateFilter(${i},'field',this.value)">
                ${_s.fieldDefs.map(fd => `<option value="${escAttr(fd.key)}" ${fd.key === f.field ? 'selected' : ''}>${escHtml(fd.label)}</option>`).join('')}
            </select>
            <select onchange="crUpdateFilter(${i},'operator',this.value)">
                ${OPS.map(op => `<option value="${op.value}" ${op.value === f.operator ? 'selected' : ''}>${op.label}</option>`).join('')}
            </select>
            <input type="text" value="${escAttr(String(f.value || ''))}" onchange="crUpdateFilter(${i},'value',this.value)" placeholder="value">
            <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm p-0" onclick="crRemoveFilter(${i})"><i class="bi bi-x"></i></button>
        </div>`).join('');
}

window.crUpdateFilter = function(i, key, val) { _s.config.filters[i][key] = val; _s.dirty = true; };
window.crRemoveFilter = function(i) { _s.config.filters.splice(i, 1); renderFilterList(); _s.dirty = true; };

// ── Execute ────────────────────────────────────────────────────────────────

async function executeReport() {
    if (!_s.dataSource) { showFlash('Select a data source first.', 'warning'); return; }
    if (_s.running) return;
    _s.running = true;
    document.getElementById('cr-running-spinner').classList.remove('d-none');
    document.getElementById('btn-cr-run').disabled = true;
    document.getElementById('cr-canvas-info').textContent = 'Running…';

    const body = {
        data_source:   _s.dataSource,
        visualization: _s.visualization,
        config:        Object.assign({}, _s.config, { visualization: _s.visualization }),
    };

    try {
        const pk = _s.reportPk && _s.reportPk !== 'null' ? _s.reportPk : null;
        let result;
        if (pk) {
            const { href } = API_URLS.custom_reports.execute(pk);
            result = await apiFetch(href, { method: 'POST', body: JSON.stringify(body) });
        } else {
            // Unsaved report: use the preview endpoint (no pk required)
            const { method, href } = API_URLS.custom_reports.preview;
            result = await apiFetch(href, { method, body: JSON.stringify(body) });
        }
        renderCanvas(result);
        document.getElementById('cr-canvas-info').textContent = `${result.type} · ${result.total ?? (result.rows?.length ?? result.labels?.length ?? '—')} rows`;
    } catch (err) {
        const d = err?.data || err;
        showFlash(String(d?.error || d?.detail || 'Failed to execute report.'), 'danger');
        document.getElementById('cr-canvas-info').textContent = 'Error.';
    } finally {
        _s.running = false;
        document.getElementById('cr-running-spinner').classList.add('d-none');
        document.getElementById('btn-cr-run').disabled = false;
    }
}

// ── Canvas rendering ───────────────────────────────────────────────────────

function renderCanvas(result) {
    const placeholder = document.getElementById('cr-placeholder');
    const chartWrap   = document.getElementById('cr-chart-wrap');
    const tableWrap   = document.getElementById('cr-table-wrap');

    placeholder.classList.add('d-none');

    if (result.type === 'table') {
        chartWrap.classList.add('d-none');
        tableWrap.classList.remove('d-none');
        tableWrap.innerHTML = buildTableHtml(result);
        destroyChart();
        return;
    }

    if (result.type === 'pivot' || result.type === 'heatmap') {
        chartWrap.classList.add('d-none');
        tableWrap.classList.remove('d-none');
        tableWrap.innerHTML = buildPivotHtml(result);
        destroyChart();
        return;
    }

    // Chart (bar, stacked_bar, line, pie)
    tableWrap.classList.add('d-none');
    chartWrap.classList.remove('d-none');
    renderChartJs(result);
}

function buildTableHtml(result) {
    const cols = result.columns || [];
    const rows = result.rows    || [];
    return `<table class="cr-table">
        <thead><tr>${cols.map(c => `<th>${escHtml(c.label)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(row => `<tr>${cols.map(c => `<td>${escHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
    </table>`;
}

function buildPivotHtml(result) {
    const cols     = result.columns   || [];
    const rows     = result.rows      || [];
    const matrix   = result.matrix    || {};
    const rowTots  = result.row_totals || {};
    const colTots  = result.col_totals || [];
    const grand    = result.grand_total ?? '';
    const isHeat   = result.type === 'heatmap';
    const maxVal   = isHeat ? Math.max(...Object.values(rowTots), 1) : 0;

    function heatStyle(val) {
        if (!isHeat) return '';
        const intensity = Math.min(Math.round((val / maxVal) * 100), 100);
        return `style="background:rgba(30,58,95,${intensity / 100}); color: ${intensity > 50 ? '#fff' : 'inherit'}"`;
    }

    return `<table class="cr-table">
        <thead><tr>
            <th>${escHtml(result.rows_label || 'Row')} \\ ${escHtml(result.columns_label || 'Col')}</th>
            ${cols.map(c => `<th>${escHtml(String(c))}</th>`).join('')}
            <th class="cr-pivot-total">Total</th>
        </tr></thead>
        <tbody>
            ${rows.map(rv => {
                const rowVals = matrix[rv] || [];
                return `<tr>
                    <td><strong>${escHtml(String(rv))}</strong></td>
                    ${rowVals.map((v, ci) => `<td class="text-end cr-heatmap-cell" ${heatStyle(v)}>${v ?? ''}</td>`).join('')}
                    <td class="text-end cr-pivot-total">${rowTots[rv] ?? ''}</td>
                </tr>`;
            }).join('')}
            <tr class="cr-pivot-total">
                <td><strong>Total</strong></td>
                ${colTots.map(v => `<td class="text-end">${v}</td>`).join('')}
                <td class="text-end"><strong>${grand}</strong></td>
            </tr>
        </tbody>
    </table>`;
}

const CHART_COLORS = ['#3b82f6','#f59e0b','#10b981','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1','#84cc16'];

function renderChartJs(result) {
    destroyChart();
    const ctx  = document.getElementById('cr-chart').getContext('2d');
    const type = result.type === 'stacked_bar' ? 'bar' : result.type === 'pie' ? 'pie' : result.type;
    const stacked = result.type === 'stacked_bar';

    const datasets = (result.datasets || []).map((ds, i) => ({
        label:           ds.label,
        data:            ds.data,
        backgroundColor: type === 'pie'
            ? ds.data.map((_, j) => CHART_COLORS[j % CHART_COLORS.length])
            : CHART_COLORS[i % CHART_COLORS.length],
        borderColor:     type === 'line' ? CHART_COLORS[i % CHART_COLORS.length] : undefined,
        borderWidth:     type === 'line' ? 2 : 0,
        fill:            false,
    }));

    _s.chartInst = new Chart(ctx, {
        type,
        data: { labels: result.labels || [], datasets },
        options: {
            responsive:          true,
            maintainAspectRatio: true,
            plugins: {
                legend: { position: 'top' },
                title:  { display: false },
            },
            scales: type === 'pie' ? {} : {
                x: { stacked, title: { display: !!result.axis_label, text: result.axis_label || '' } },
                y: { stacked, beginAtZero: true },
            },
        },
    });
}

function destroyChart() {
    if (_s.chartInst) { _s.chartInst.destroy(); _s.chartInst = null; }
}

// ── Save ───────────────────────────────────────────────────────────────────

async function saveReport() {
    const name = document.getElementById('cr-name').value.trim() || 'Untitled Report';
    _s.name = name;

    const payload = {
        name,
        description:   '',
        data_source:   _s.dataSource,
        visualization: _s.visualization,
        config:        _s.config,
        is_shared:     _s.reportPk ? undefined : false,
    };

    const btn = document.getElementById('btn-cr-save');
    btn.disabled = true;
    setStatus('Saving…');

    try {
        let report;
        if (_s.reportPk && _s.reportPk !== 'null') {
            const { method, href } = API_URLS.custom_reports.update(_s.reportPk);
            report = await apiFetch(href, { method, body: JSON.stringify(payload) });
        } else {
            const { method, href } = API_URLS.custom_reports.create;
            report = await apiFetch(href, { method, body: JSON.stringify(payload) });
            _s.reportPk = report.id;
            history.replaceState(null, '', `/reports/custom/${report.id}/`);
        }
        _s.dirty = false;
        setStatus('Saved');
        setTimeout(() => setStatus(''), 2000);
    } catch (err) {
        const d = err?.data || err;
        showFlash(String(d?.detail || d?.name?.[0] || 'Failed to save.'), 'danger');
        setStatus('');
    } finally {
        btn.disabled = false;
    }
}

function setStatus(msg) {
    document.getElementById('cr-status').textContent = msg;
}

// ── Export ─────────────────────────────────────────────────────────────────

function exportReport(fmt) {
    if (!_s.reportPk || _s.reportPk === 'null') { showFlash('Save the report first.', 'info'); return; }
    const { href } = API_URLS.custom_reports.export(_s.reportPk, fmt);
    window.open(href, '_blank');
}

function exportImage() {
    const canvas = document.getElementById('cr-chart');
    if (!canvas || _s.chartInst === null) { showFlash('Run a chart visualization first.', 'info'); return; }
    const link    = document.createElement('a');
    link.download = (document.getElementById('cr-name').value.trim() || 'report') + '.png';
    link.href     = canvas.toDataURL('image/png');
    link.click();
}

// ── Sharing ────────────────────────────────────────────────────────────────

async function loadUserList() {
    try {
        const data  = await apiFetch('/api/v1/users/?page_size=200', { method: 'GET' });
        const users = Array.isArray(data) ? data : (data.results || []);
        const sel   = document.getElementById('share-user-sel');
        users.forEach(u => {
            const opt = document.createElement('option');
            opt.value = u.id;
            opt.textContent = `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email;
            sel.appendChild(opt);
        });
    } catch { /* ignore */ }
}

function loadShareList(shares) {
    const el = document.getElementById('share-list');
    if (!shares || !shares.length) { el.textContent = 'Not shared with anyone yet.'; return; }
    el.innerHTML = shares.map(s => `
        <div class="d-flex justify-content-between align-items-center py-1 border-bottom">
            <div>
                <span>${escHtml(s.user_name)}</span>
                <span class="text-secondary ms-1">(${s.permission})</span>
            </div>
            <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm p-0" onclick="removeShare(${s.user})">
                <i class="bi bi-x"></i>
            </button>
        </div>`).join('');
}

async function addShare() {
    if (!_s.reportPk || _s.reportPk === 'null') { showFlash('Save the report first.', 'info'); return; }
    const userId = document.getElementById('share-user-sel').value;
    const perm   = document.getElementById('share-perm-sel').value;
    if (!userId) return;
    try {
        const { method, href } = API_URLS.custom_reports.share(_s.reportPk);
        const res = await apiFetch(href, { method, body: JSON.stringify({ user_id: parseInt(userId), permission: perm }) });
        // Reload share list
        const { href: dh } = API_URLS.custom_reports.detail(_s.reportPk);
        const report = await apiFetch(dh, { method: 'GET' });
        loadShareList(report.shares);
    } catch (err) {
        const d = err?.data || err;
        showFlash(String(d?.error || 'Failed to share.'), 'danger');
    }
}

window.removeShare = async function(userId) {
    if (!_s.reportPk || _s.reportPk === 'null') return;
    try {
        const { method, href } = API_URLS.custom_reports.unshare(_s.reportPk, userId);
        await apiFetch(href, { method });
        const { href: dh } = API_URLS.custom_reports.detail(_s.reportPk);
        const report = await apiFetch(dh, { method: 'GET' });
        loadShareList(report.shares);
    } catch {
        showFlash('Failed to remove share.', 'danger');
    }
};

// ── Utils ──────────────────────────────────────────────────────────────────

function escAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;');
}
