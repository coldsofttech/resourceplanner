'use strict';

import { apiFetch, escHtml, showFlash } from './../main.js';
import { API_URLS } from './../urls.js';

// ── Constants ─────────────────────────────────────────────────────────────────

const AGGRS = ['count', 'count_distinct', 'sum', 'average', 'minimum', 'maximum'];
const AGGR_LABELS = { count: 'COUNT', count_distinct: 'DISTINCT', sum: 'SUM', average: 'AVG', minimum: 'MIN', maximum: 'MAX' };

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

const TYPE_LABELS = { text: 'Abc', number: '123', date: 'Date', datetime: 'DT', boolean: 'T/F', choice: 'Opt' };
const TYPE_ICONS  = { text: 'bi-type', number: 'bi-123', date: 'bi-calendar-date', datetime: 'bi-clock', boolean: 'bi-toggle-on', choice: 'bi-list-check' };

const VIZ_CONFIG = {
    table:          { slots: ['fields', 'values'] },
    pivot:          { slots: ['rows', 'columns', 'values'] },
    bar:            { slots: ['axis', 'legend', 'values'] },
    stacked_bar:    { slots: ['axis', 'legend', 'values'] },
    column:         { slots: ['axis', 'legend', 'values'] },
    stacked_column: { slots: ['axis', 'legend', 'values'] },
    pie:            { slots: ['axis', 'values'] },
    line:           { slots: ['axis', 'legend', 'values'] },
    heatmap:        { slots: ['rows', 'columns', 'values'] },
    combo:          { slots: ['axis', 'legend', 'values'] },
    card:           { slots: ['values'] },
};

const SLOT_LABELS = {
    fields:  'Columns',
    rows:    'Rows',
    columns: 'Columns',
    axis:    'X-Axis',
    legend:  'Legend / Color',
    values:  'Values',
};

const CHART_COLORS = ['#3b82f6','#f59e0b','#10b981','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1','#84cc16'];

// ── State ─────────────────────────────────────────────────────────────────────

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
        format:  {},
    },
    dataSources:  [],
    fieldDefs:    [],
    chartInst:    null,
    dirty:        false,
    running:      false,
    dragField:    null,
};

// ── Init ──────────────────────────────────────────────────────────────────────

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
            opt.value       = ds.key;
            opt.textContent = ds.label;
            sel.appendChild(opt);
        });
    } catch {
        showFlash('Failed to load data sources.', 'danger');
    }
}

async function loadExistingReport() {
    try {
        const { href } = API_URLS.custom_reports.detail(_s.reportPk);
        const report   = await apiFetch(href, { method: 'GET' });
        _s.name          = report.name;
        _s.dataSource    = report.data_source;
        _s.visualization = report.visualization;
        _s.config = Object.assign(
            { fields: [], filters: [], axis: '', legend: '', rows: '', columns: '', values: [{ field: 'id', aggregation: 'count' }], format: {} },
            report.config,
        );

        document.getElementById('cr-name').value = _s.name;
        applyFormatToUI();

        if (_s.dataSource) {
            document.getElementById('cr-ds-select').value = _s.dataSource;
            await selectDataSource(_s.dataSource, true);   // preserveConfig = true (bug fix #1)
        }

        setVizActive(_s.visualization);
        renderConfigSlots();
        renderFilterList();
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
        _s.name = e.target.value; _s.dirty = true;
    });
    document.getElementById('btn-cr-save').addEventListener('click', saveReport);
    document.getElementById('btn-cr-run').addEventListener('click', executeReport);
    document.getElementById('cr-export-csv').addEventListener('click',  (e) => { e.preventDefault(); exportReport('csv'); });
    document.getElementById('cr-export-xlsx').addEventListener('click', (e) => { e.preventDefault(); exportReport('xlsx'); });
    document.getElementById('cr-export-img').addEventListener('click',  (e) => { e.preventDefault(); exportImage(); });
    document.getElementById('btn-share-add').addEventListener('click', addShare);

    // Format inputs
    ['cr-fmt-title', 'cr-fmt-subtitle', 'cr-fmt-xlabel', 'cr-fmt-ylabel'].forEach(id =>
        document.getElementById(id)?.addEventListener('input', syncFormat)
    );
    document.getElementById('cr-fmt-fontsize')?.addEventListener('change', syncFormat);
    document.getElementById('cr-fmt-border')?.addEventListener('change', syncFormat);

    // Drag-and-drop delegation on visual tab
    const visualTab = document.getElementById('cr-tab-visual');
    visualTab.addEventListener('dragover', (e) => {
        const slotEl = e.target.closest('[data-slot]');
        if (slotEl) { e.preventDefault(); slotEl.classList.add('drag-over'); }
    });
    visualTab.addEventListener('dragleave', (e) => {
        const slotEl = e.target.closest('[data-slot]');
        if (slotEl && !slotEl.contains(e.relatedTarget)) slotEl.classList.remove('drag-over');
    });
    visualTab.addEventListener('drop', (e) => {
        const slotEl = e.target.closest('[data-slot]');
        if (!slotEl || !_s.dragField) return;
        e.preventDefault();
        slotEl.classList.remove('drag-over');
        dropFieldToSlot(_s.dragField, slotEl.dataset.slot);
        _s.dragField = null;
    });

    loadUserList();
}

// ── Data source ───────────────────────────────────────────────────────────────

async function selectDataSource(key, preserveConfig = false) {
    _s.dataSource = key;
    const ds = _s.dataSources.find(d => d.key === key);
    _s.fieldDefs = ds ? (ds.fields || []) : [];
    renderFieldList();
    if (!preserveConfig) {
        _s.config.fields  = [];
        _s.config.axis    = '';
        _s.config.legend  = '';
        _s.config.rows    = '';
        _s.config.columns = '';
        _s.config.values  = [{ field: _s.fieldDefs[0]?.key || 'id', aggregation: 'count' }];
        _s.dirty = true;
    }
    renderConfigSlots();
}

// ── Field list (left panel) ───────────────────────────────────────────────────

function renderFieldList() {
    const el = document.getElementById('cr-fields-list');
    if (!_s.fieldDefs.length) {
        el.innerHTML = '<p class="text-secondary" style="font-size:12px;padding:4px 8px">Select a data source to see fields.</p>';
        return;
    }
    el.innerHTML = _s.fieldDefs.map(f => {
        const icon  = TYPE_ICONS[f.type]  || 'bi-question-circle';
        const badge = TYPE_LABELS[f.type] || f.type.substring(0, 3).toUpperCase();
        return `<div class="cr-field-item" draggable="true" data-field-key="${escAttr(f.key)}"
                    onclick="crAddField('${escAttr(f.key)}')"
                    title="${badge} · Click or drag to add ${escHtml(f.label)}">
            <i class="bi ${icon} cr-ft cr-ft-${escAttr(f.type)}"></i>
            <span>${escHtml(f.label)}</span>
        </div>`;
    }).join('');

    el.querySelectorAll('.cr-field-item').forEach(item => {
        item.addEventListener('dragstart', (e) => {
            _s.dragField = item.dataset.fieldKey;
            e.dataTransfer.effectAllowed = 'copy';
        });
        item.addEventListener('dragend', () => { _s.dragField = null; });
    });
}

window.crAddField = function(key) {
    const viz   = _s.visualization;
    const slots = VIZ_CONFIG[viz]?.slots || ['fields'];
    const fd    = _s.fieldDefs.find(f => f.key === key);
    const aggr  = fd?.aggregatable ? 'sum' : 'count';

    if (slots.includes('fields') && !_s.config.fields.includes(key)) {
        _s.config.fields.push(key); renderConfigSlots(); _s.dirty = true; return;
    }
    if (slots.includes('axis') && !_s.config.axis) {
        _s.config.axis = key; renderConfigSlots(); _s.dirty = true; return;
    }
    if (slots.includes('rows') && !_s.config.rows) {
        _s.config.rows = key; renderConfigSlots(); _s.dirty = true; return;
    }
    if (slots.includes('columns') && !_s.config.columns) {
        _s.config.columns = key; renderConfigSlots(); _s.dirty = true; return;
    }
    if (slots.includes('legend') && !_s.config.legend) {
        _s.config.legend = key; renderConfigSlots(); _s.dirty = true; return;
    }
    if (slots.includes('values')) {
        _s.config.values.push({ field: key, aggregation: aggr });
        renderConfigSlots(); _s.dirty = true;
    }
};

function dropFieldToSlot(key, slot) {
    const fd   = _s.fieldDefs.find(f => f.key === key);
    const aggr = fd?.aggregatable ? 'sum' : 'count';
    if (slot === 'fields') {
        if (!_s.config.fields.includes(key)) _s.config.fields.push(key);
    } else if (slot === 'values') {
        _s.config.values.push({ field: key, aggregation: aggr });
    } else if (['axis', 'legend', 'rows', 'columns'].includes(slot)) {
        _s.config[slot] = key;
    }
    renderConfigSlots();
    _s.dirty = true;
}

// ── Visualization ─────────────────────────────────────────────────────────────

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

// ── Tabs ──────────────────────────────────────────────────────────────────────

window.crSwitchTab = function(tab) {
    ['visual', 'filters', 'format'].forEach(t => {
        document.querySelector(`.cr-tab[data-tab="${t}"]`)?.classList.toggle('active', t === tab);
        document.getElementById(`cr-tab-${t}`)?.classList.toggle('d-none', t !== tab);
    });
};

// ── Config slots (center panel) ───────────────────────────────────────────────

function renderConfigSlots() {
    const el    = document.getElementById('cr-config-slots');
    const viz   = _s.visualization;
    const slots = VIZ_CONFIG[viz]?.slots || ['fields'];
    const fm    = Object.fromEntries(_s.fieldDefs.map(f => [f.key, f.label]));

    let html = '';
    slots.forEach(slot => {
        const label = SLOT_LABELS[slot] || slot;
        if (slot === 'fields') {
            const chips = _s.config.fields.map(k => chipHtml(k, fm[k] || k, `crRemoveField('${escAttr(k)}')`)).join('');
            html += slotHtml(label, chips, slot);
        } else if (slot === 'values') {
            html += renderValuesSlot(fm);
        } else {
            const val  = _s.config[slot];
            const chip = val ? chipHtml(val, fm[val] || val, `crClearSlot('${slot}')`) : '';
            html += slotHtml(label, chip, slot);
        }
    });

    el.innerHTML = html || '<p class="text-secondary small">Pick a data source and visualization.</p>';
}

function slotHtml(label, content, slotKey) {
    return `<div class="cr-slot">
        <div class="cr-slot-label">${label}</div>
        <div class="cr-slot-drop" data-slot="${escAttr(slotKey)}">
            ${content || '<span class="cr-slot-hint">Drop or click a field to add…</span>'}
        </div>
    </div>`;
}

function chipHtml(key, label, removeExpr) {
    return `<span class="cr-slot-chip">${escHtml(label)}<span class="cr-chip-remove" onclick="${removeExpr};event.stopPropagation()">×</span></span>`;
}

function renderValuesSlot(fm) {
    const addBtn = `<span class="cr-val-add" onclick="crAddValue()" title="Add value"><i class="bi bi-plus-circle"></i></span>`;
    const inner  = _s.config.values.map((v, i) => valueChipHtml(v, i, fm)).join('');
    return `<div class="cr-slot">
        <div class="cr-slot-label d-flex justify-content-between align-items-center">
            <span>${SLOT_LABELS.values}</span>${addBtn}
        </div>
        <div class="cr-slot-drop" data-slot="values">
            ${inner || '<span class="cr-slot-hint">Drop or click a field to add…</span>'}
        </div>
    </div>`;
}

function valueChipHtml(v, i, fm) {
    const label = fm[v.field] || v.field || 'field';
    const aggr  = v.aggregation || 'count';
    const aggrL = AGGR_LABELS[aggr] || aggr;
    return `<span class="cr-val-chip">
        <span class="cr-val-aggr" onclick="crCycleAggr(${i})" title="Click to cycle aggregation">${aggrL} <i class="bi bi-chevron-down" style="font-size:9px"></i></span>
        <span class="cr-val-field">${escHtml(label)}</span>
        <span class="cr-chip-remove" onclick="crRemoveValue(${i});event.stopPropagation()">×</span>
    </span>`;
}

window.crRemoveField = (k)    => { _s.config.fields = _s.config.fields.filter(f => f !== k); renderConfigSlots(); _s.dirty = true; };
window.crClearSlot   = (slot) => { _s.config[slot]  = ''; renderConfigSlots(); _s.dirty = true; };
window.crAddValue    = ()     => { _s.config.values.push({ field: _s.fieldDefs[0]?.key || 'id', aggregation: 'count' }); renderConfigSlots(); _s.dirty = true; };
window.crRemoveValue = (i)    => { _s.config.values.splice(i, 1); renderConfigSlots(); _s.dirty = true; };
window.crCycleAggr   = (i)    => {
    const cur = _s.config.values[i].aggregation || 'count';
    _s.config.values[i].aggregation = AGGRS[(AGGRS.indexOf(cur) + 1) % AGGRS.length];
    renderConfigSlots();
    _s.dirty = true;
};

// ── Filters ───────────────────────────────────────────────────────────────────

window.crAddFilter = function() {
    _s.config.filters.push({ field: _s.fieldDefs[0]?.key || '', operator: 'eq', value: '' });
    renderFilterList();
    _s.dirty = true;
};

function renderFilterList() {
    const el    = document.getElementById('cr-filters-list');
    const empty = document.getElementById('cr-filters-empty');
    if (!el) return;
    empty?.classList.toggle('d-none', _s.config.filters.length > 0);
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

// ── Execute ───────────────────────────────────────────────────────────────────

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
            const { method, href } = API_URLS.custom_reports.preview;
            result = await apiFetch(href, { method, body: JSON.stringify(body) });
        }
        renderCanvas(result);
        const count = result.total ?? result.rows?.length ?? result.labels?.length ?? result.cards?.length ?? '—';
        document.getElementById('cr-canvas-info').textContent = `${result.type} · ${count} items`;
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

// ── Canvas rendering ──────────────────────────────────────────────────────────

function renderCanvas(result) {
    ['cr-placeholder','cr-chart-wrap','cr-table-wrap','cr-card-wrap','cr-heatmap-wrap'].forEach(id =>
        document.getElementById(id)?.classList.add('d-none')
    );

    const fmt = _s.config.format || {};
    document.getElementById('cr-canvas-area')?.classList.toggle('cr-bordered', !!fmt.showBorder);

    if (result.type === 'card') {
        const w = document.getElementById('cr-card-wrap');
        w.classList.remove('d-none'); w.innerHTML = buildCardHtml(result);
        destroyChart(); return;
    }
    if (result.type === 'heatmap') {
        const w = document.getElementById('cr-heatmap-wrap');
        w.classList.remove('d-none'); w.innerHTML = buildHeatmapHtml(result);
        destroyChart(); return;
    }
    if (result.type === 'table' || result.type === 'pivot') {
        const w = document.getElementById('cr-table-wrap');
        w.classList.remove('d-none');
        w.innerHTML = result.type === 'table' ? buildTableHtml(result) : buildPivotHtml(result);
        destroyChart(); return;
    }
    // chart types: bar, stacked_bar, column, stacked_column, pie, line, combo
    document.getElementById('cr-chart-wrap').classList.remove('d-none');
    renderChartJs(result);
}

function buildTableHtml(result) {
    const cols = result.columns || [];
    const rows = result.rows    || [];
    const fmt  = _s.config.format || {};
    const fs   = { sm: '11px', md: '13px', lg: '15px' }[fmt.fontSize || 'md'];
    let html   = '';
    if (fmt.title || fmt.subtitle) {
        html += `<div class="cr-canvas-title">${fmt.title ? `<div class="cr-title">${escHtml(fmt.title || _s.name)}</div>` : ''}${fmt.subtitle ? `<div class="cr-subtitle">${escHtml(fmt.subtitle)}</div>` : ''}</div>`;
    }
    html += `<table class="cr-table" style="font-size:${fs}">
        <thead><tr>${cols.map(c => `<th>${escHtml(c.label)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(row => `<tr>${cols.map(c => `<td>${escHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
    </table>`;
    return html;
}

function buildPivotHtml(result) {
    const cols    = result.columns    || [];
    const rows    = result.rows       || [];
    const matrix  = result.matrix     || {};
    const rowTots = result.row_totals  || {};
    const colTots = result.col_totals  || [];
    const grand   = result.grand_total ?? '';
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
                    ${rowVals.map(v => `<td class="text-end">${v ?? ''}</td>`).join('')}
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

function buildHeatmapHtml(result) {
    const cols    = result.columns    || [];
    const rows    = result.rows       || [];
    const matrix  = result.matrix     || {};
    const rowTots = result.row_totals || {};
    const allVals = Object.values(rowTots).filter(v => v != null);
    const maxVal  = allVals.length ? Math.max(...allVals, 1) : 1;

    function cellStyle(val) {
        const pct = Math.min(Math.round(((val || 0) / maxVal) * 100), 100);
        return `background:rgba(30,58,95,${(pct / 100).toFixed(2)});color:${pct > 45 ? '#fff' : '#1e293b'}`;
    }

    return `<div class="cr-heatmap-grid">
        <div class="cr-hm-header">
            <div class="cr-hm-cell cr-hm-label">${escHtml(result.rows_label || '')} / ${escHtml(result.columns_label || '')}</div>
            ${cols.map(c => `<div class="cr-hm-cell cr-hm-col-head">${escHtml(String(c))}</div>`).join('')}
        </div>
        ${rows.map(rv => {
            const rowVals = matrix[rv] || [];
            return `<div class="cr-hm-row">
                <div class="cr-hm-cell cr-hm-row-head">${escHtml(String(rv))}</div>
                ${rowVals.map(v => `<div class="cr-hm-cell cr-hm-data" style="${cellStyle(v)}">${v ?? ''}</div>`).join('')}
            </div>`;
        }).join('')}
    </div>`;
}

function buildCardHtml(result) {
    const cards = result.cards || [];
    return `<div class="cr-cards">
        ${cards.map(c => {
            const val = c.value !== null && c.value !== undefined
                ? (Number.isInteger(c.value) ? c.value : Number(c.value).toFixed(2))
                : '—';
            return `<div class="cr-card">
                <div class="cr-card-value">${val}</div>
                <div class="cr-card-label">${escHtml(c.label)}</div>
            </div>`;
        }).join('')}
    </div>`;
}

function renderChartJs(result) {
    destroyChart();
    const fmt     = _s.config.format || {};
    const ctx     = document.getElementById('cr-chart').getContext('2d');
    const rtype   = result.type;
    const isHoriz = rtype === 'bar' || rtype === 'stacked_bar';
    const isStack = rtype === 'stacked_bar' || rtype === 'stacked_column';
    const isPie   = rtype === 'pie';
    const isLine  = rtype === 'line';
    const isCombo = rtype === 'combo';

    const datasets = (result.datasets || []).map((ds, i) => {
        const color      = CHART_COLORS[i % CHART_COLORS.length];
        const seriesType = ds.series_type || (isCombo && i > 0 ? 'line' : 'bar');
        const isLineSeries = isLine || seriesType === 'line';
        return {
            type:            isPie ? undefined : (isCombo ? seriesType : undefined),
            label:           ds.label,
            data:            ds.data,
            backgroundColor: isPie
                ? ds.data.map((_, j) => CHART_COLORS[j % CHART_COLORS.length])
                : (isLineSeries ? color + '33' : color),
            borderColor:     color,
            borderWidth:     isLineSeries ? 2 : 0,
            fill:            false,
            tension:         isLineSeries ? 0.3 : 0,
            pointRadius:     isLineSeries ? 3 : 0,
        };
    });

    const xLabel = fmt.xLabel || result.axis_label || '';
    const yLabel = fmt.yLabel || '';

    const scales = isPie ? {} : {
        x: { stacked: isStack, title: { display: !!xLabel, text: xLabel } },
        y: { stacked: isStack, beginAtZero: true, title: { display: !!yLabel, text: yLabel } },
    };

    _s.chartInst = new Chart(ctx, {
        type: isPie ? 'pie' : 'bar',
        data: { labels: result.labels || [], datasets },
        options: {
            indexAxis:           isHoriz ? 'y' : 'x',
            responsive:          true,
            maintainAspectRatio: true,
            plugins: {
                legend:  { position: 'top' },
                title: {
                    display: !!(fmt.title || fmt.subtitle),
                    text:    [fmt.title || _s.name, fmt.subtitle].filter(Boolean),
                },
                tooltip: { mode: 'index', intersect: false },
            },
            scales,
        },
    });
}

function destroyChart() {
    if (_s.chartInst) { _s.chartInst.destroy(); _s.chartInst = null; }
}

// ── Save ──────────────────────────────────────────────────────────────────────

async function saveReport() {
    const name = document.getElementById('cr-name').value.trim() || 'Untitled Report';
    _s.name = name;

    const payload = {
        name,
        description:   '',
        data_source:   _s.dataSource,
        visualization: _s.visualization,
        config:        _s.config,
        is_shared:     (_s.reportPk && _s.reportPk !== 'null') ? undefined : false,
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
    const el = document.getElementById('cr-status');
    if (el) el.textContent = msg;
}

// ── Export ────────────────────────────────────────────────────────────────────

function exportReport(fmt) {
    if (!_s.reportPk || _s.reportPk === 'null') { showFlash('Save the report first.', 'info'); return; }
    const { href } = API_URLS.custom_reports.export(_s.reportPk, fmt);
    const a = document.createElement('a');
    a.href = href;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function exportImage() {
    const canvas = document.getElementById('cr-chart');
    if (!canvas || !_s.chartInst) { showFlash('Run a chart visualization first.', 'info'); return; }
    const link    = document.createElement('a');
    link.download = (document.getElementById('cr-name').value.trim() || 'report') + '.png';
    link.href     = canvas.toDataURL('image/png');
    link.click();
}

// ── Format ────────────────────────────────────────────────────────────────────

function syncFormat() {
    _s.config.format = {
        title:      document.getElementById('cr-fmt-title')?.value     || '',
        subtitle:   document.getElementById('cr-fmt-subtitle')?.value  || '',
        xLabel:     document.getElementById('cr-fmt-xlabel')?.value    || '',
        yLabel:     document.getElementById('cr-fmt-ylabel')?.value    || '',
        fontSize:   document.getElementById('cr-fmt-fontsize')?.value  || 'md',
        showBorder: document.getElementById('cr-fmt-border')?.checked  || false,
    };
    _s.dirty = true;
}

function applyFormatToUI() {
    const fmt = _s.config.format || {};
    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
    setVal('cr-fmt-title',    fmt.title);
    setVal('cr-fmt-subtitle', fmt.subtitle);
    setVal('cr-fmt-xlabel',   fmt.xLabel);
    setVal('cr-fmt-ylabel',   fmt.yLabel);
    const fs = document.getElementById('cr-fmt-fontsize');
    if (fs) fs.value = fmt.fontSize || 'md';
    const cb = document.getElementById('cr-fmt-border');
    if (cb) cb.checked = !!fmt.showBorder;
}

// ── Sharing ───────────────────────────────────────────────────────────────────

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
            <span>${escHtml(s.user_name)} <span class="text-secondary">(${s.permission})</span></span>
            <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm p-0" onclick="removeShare(${s.user})"><i class="bi bi-x"></i></button>
        </div>`).join('');
}

async function addShare() {
    if (!_s.reportPk || _s.reportPk === 'null') { showFlash('Save the report first.', 'info'); return; }
    const userId = document.getElementById('share-user-sel').value;
    const perm   = document.getElementById('share-perm-sel').value;
    if (!userId) return;
    try {
        const { method, href } = API_URLS.custom_reports.share(_s.reportPk);
        await apiFetch(href, { method, body: JSON.stringify({ user_id: parseInt(userId), permission: perm }) });
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

// ── Utils ─────────────────────────────────────────────────────────────────────

function escAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;');
}
