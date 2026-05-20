'use strict';

import { apiFetch, escHtml, showFlash } from './../main.js';
import { API_URLS } from './../urls.js';

// ── Constants ─────────────────────────────────────────────────────────────────

const AGGRS = ['count', 'count_distinct', 'sum', 'average', 'minimum', 'maximum'];
const AGGR_LABELS = { count: 'COUNT', count_distinct: 'DISTINCT', sum: 'SUM', average: 'AVG', minimum: 'MIN', maximum: 'MAX' };

const OPS = [
    { value: 'eq',          label: 'equals',       types: ['text','number','date','datetime','boolean','choice'] },
    { value: 'neq',         label: 'not equal',    types: ['text','number','date','datetime','boolean','choice'] },
    { value: 'gt',          label: '>',             types: ['number','date','datetime'] },
    { value: 'gte',         label: '≥',             types: ['number','date','datetime'] },
    { value: 'lt',          label: '<',             types: ['number','date','datetime'] },
    { value: 'lte',         label: '≤',             types: ['number','date','datetime'] },
    { value: 'contains',    label: 'contains',      types: ['text'] },
    { value: 'starts_with', label: 'starts with',   types: ['text'] },
    { value: 'ends_with',   label: 'ends with',     types: ['text'] },
    { value: 'in',          label: 'in (any of)',   types: ['text','number','choice'] },
    { value: 'not_in',      label: 'not in',        types: ['text','number','choice'] },
    { value: 'range',       label: 'between',       types: ['number','date','datetime'] },
    { value: 'is_null',     label: 'is empty',      types: ['text','number','date','datetime','boolean','choice'] },
    { value: 'is_not_null', label: 'is not empty',  types: ['text','number','date','datetime','boolean','choice'] },
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
    fields:  'Columns', rows: 'Rows', columns: 'Columns',
    axis: 'X-Axis', legend: 'Legend / Color', values: 'Values',
};

const CHART_COLORS = ['#3b82f6','#f59e0b','#10b981','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1','#84cc16'];

// ── State ─────────────────────────────────────────────────────────────────────

const _s = {
    reportPk:      window.REPORT_PK || null,
    name:          'Untitled Report',
    dataSource:    '',
    visualization: 'table',
    config: {
        fields: [], filters: [], axis: '', legend: '', rows: '', columns: '',
        values: [{ field: 'id', aggregation: 'count' }],
        format: {}, joined_sources: [], sort_by: [],
    },
    allDataSources: [],   // full list from API (with related_sources)
    fieldDefs:     [],    // merged: primary + joined source fields
    joins:         [],    // [{key, label, fkPrefix, fields}]
    chartInst:     null,
    dirty:         false,
    running:       false,
    dragField:     null,
};

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    await loadDataSources();
    if (_s.reportPk && _s.reportPk !== 'null') {
        await loadExistingReport();
        executeReport();   // auto-execute (enhancement #1)
    }
    wireUI();
});

async function loadDataSources() {
    try {
        const sources   = await apiFetch(API_URLS.custom_reports.dataSources.href, { method: 'GET' });
        _s.allDataSources = sources;
        const sel = document.getElementById('cr-ds-select');
        sources.forEach(ds => {
            const opt = document.createElement('option');
            opt.value = ds.key; opt.textContent = ds.label;
            sel.appendChild(opt);
        });
    } catch { showFlash('Failed to load data sources.', 'danger'); }
}

async function loadExistingReport() {
    try {
        const { href } = API_URLS.custom_reports.detail(_s.reportPk);
        const report   = await apiFetch(href, { method: 'GET' });
        _s.name          = report.name;
        _s.dataSource    = report.data_source;
        _s.visualization = report.visualization;
        _s.config = Object.assign(
            { fields: [], filters: [], axis: '', legend: '', rows: '', columns: '',
              values: [{ field: 'id', aggregation: 'count' }], format: {}, joined_sources: [], sort_by: [] },
            report.config,
        );
        document.getElementById('cr-name').value = _s.name;

        if (_s.dataSource) {
            document.getElementById('cr-ds-select').value = _s.dataSource;
            await selectDataSource(_s.dataSource, true, false);

            // Restore joins
            for (const j of (_s.config.joined_sources || [])) {
                addJoinSource(j.source_key, j.fk_prefix, true);
            }
        }

        setVizActive(_s.visualization);
        renderConfigSlots();
        renderFilterList();
        renderFormatTab();
        loadShareList(report.shares);
    } catch { showFlash('Failed to load report.', 'danger'); }
}

function wireUI() {
    document.getElementById('cr-ds-select').addEventListener('change', async (e) => {
        await selectDataSource(e.target.value);
    });
    document.getElementById('cr-name').addEventListener('input', (e) => {
        _s.name = e.target.value; _s.dirty = true;
    });
    document.getElementById('cr-field-search').addEventListener('input', () => renderFieldList());
    document.getElementById('btn-cr-save').addEventListener('click', saveReport);
    document.getElementById('btn-cr-run').addEventListener('click', executeReport);
    document.getElementById('cr-export-csv').addEventListener('click',  (e) => { e.preventDefault(); exportReport('csv'); });
    document.getElementById('cr-export-xlsx').addEventListener('click', (e) => { e.preventDefault(); exportReport('xlsx'); });
    document.getElementById('cr-export-img').addEventListener('click',  (e) => { e.preventDefault(); exportImage(); });
    document.getElementById('btn-share-add').addEventListener('click', addShare);

    // Drag-and-drop: visual config slots
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
        e.preventDefault(); slotEl.classList.remove('drag-over');
        dropFieldToSlot(_s.dragField, slotEl.dataset.slot);
        _s.dragField = null;
    });

    // Drag-and-drop: filters
    const filterDropzone = document.getElementById('cr-filter-dropzone');
    filterDropzone.addEventListener('dragover', (e) => {
        if (_s.dragField) { e.preventDefault(); filterDropzone.classList.add('drag-over'); }
    });
    filterDropzone.addEventListener('dragleave', () => filterDropzone.classList.remove('drag-over'));
    filterDropzone.addEventListener('drop', (e) => {
        if (!_s.dragField) return;
        e.preventDefault(); filterDropzone.classList.remove('drag-over');
        _s.config.filters.push({ field: _s.dragField, operator: 'eq', value: '' });
        renderFilterList(); _s.dirty = true; _s.dragField = null;
    });

    loadUserList();
}

// ── Data source & joins ───────────────────────────────────────────────────────

async function selectDataSource(key, preserveConfig = false, clearJoins = true) {
    _s.dataSource = key;
    const ds = _s.allDataSources.find(d => d.key === key);
    if (clearJoins) {
        _s.joins = [];
        if (!preserveConfig) _s.config.joined_sources = [];
    }
    mergeFieldDefs();
    renderFieldList();
    renderJoinList();

    if (!preserveConfig) {
        _s.config.fields   = [];
        _s.config.axis     = '';
        _s.config.legend   = '';
        _s.config.rows     = '';
        _s.config.columns  = '';
        _s.config.values   = [{ field: _s.fieldDefs[0]?.key || 'id', aggregation: 'count' }];
        _s.config.sort_by  = [];
        _s.dirty = true;
    }
    renderConfigSlots();

    // Show/hide join button based on available related sources
    const hasRelated = ds && Object.keys(ds.related_sources || {}).length > 0;
    document.getElementById('btn-add-join').classList.toggle('d-none', !hasRelated);
}

window.addJoinSource = function addJoinSource(sourceKey, fkPrefix, skipDirty = false) {
    if (_s.joins.find(j => j.key === sourceKey)) return;
    const joinDs = _s.allDataSources.find(d => d.key === sourceKey);
    if (!joinDs) return;

    const prefixedFields = (joinDs.fields || []).map(f => ({
        ...f,
        key:         `${fkPrefix}__${f.key}`,
        label:       f.label,
        sourceKey:   sourceKey,
        sourceLabel: joinDs.label,
    }));

    _s.joins.push({ key: sourceKey, label: joinDs.label, fkPrefix, fields: prefixedFields });
    if (!skipDirty) {
        _s.config.joined_sources = _s.config.joined_sources || [];
        _s.config.joined_sources.push({ source_key: sourceKey, fk_prefix: fkPrefix });
        _s.dirty = true;
    }
    mergeFieldDefs();
    renderFieldList();
    renderJoinList();
    document.getElementById('cr-join-menu').classList.add('d-none');
};

window.crRemoveJoin = function(key) {
    _s.joins = _s.joins.filter(j => j.key !== key);
    _s.config.joined_sources = (_s.config.joined_sources || []).filter(j => j.source_key !== key);
    mergeFieldDefs();
    renderFieldList();
    renderJoinList();
    _s.dirty = true;
};

function mergeFieldDefs() {
    const primaryDs = _s.allDataSources.find(d => d.key === _s.dataSource);
    const primary   = (primaryDs?.fields || []).map(f => ({ ...f, sourceKey: _s.dataSource, sourceLabel: primaryDs?.label || '' }));
    const joined    = _s.joins.flatMap(j => j.fields);
    const seen      = new Set();
    _s.fieldDefs    = [...primary, ...joined].filter(f => {
        if (seen.has(f.key)) return false;
        seen.add(f.key); return true;
    });
}

function renderJoinList() {
    const el = document.getElementById('cr-join-list');
    if (!_s.joins.length) { el.innerHTML = ''; return; }
    el.innerHTML = _s.joins.map(j => `
        <div class="cr-join-chip">
            <i class="bi bi-link-45deg"></i>
            <span>${escHtml(j.label)}</span>
            <span class="cr-chip-remove" onclick="crRemoveJoin('${escAttr(j.key)}')">×</span>
        </div>`).join('');
}

window.crShowJoinMenu = function() {
    const menuEl = document.getElementById('cr-join-menu');
    menuEl.classList.toggle('d-none');
    if (menuEl.classList.contains('d-none')) return;

    const primaryDs    = _s.allDataSources.find(d => d.key === _s.dataSource);
    const relatedSrcs  = primaryDs?.related_sources || {};
    const activeKeys   = new Set(_s.joins.map(j => j.key));

    const items = Object.entries(relatedSrcs)
        .filter(([key]) => !activeKeys.has(key))
        .map(([key, fkPrefix]) => {
            const ds = _s.allDataSources.find(d => d.key === key);
            if (!ds) return '';
            return `<div class="cr-join-opt" onclick="addJoinSource('${escAttr(key)}','${escAttr(fkPrefix)}')">
                <i class="bi bi-table"></i> ${escHtml(ds.label)}
                <small class="text-secondary ms-1">via ${escHtml(fkPrefix)}</small>
            </div>`;
        }).join('');

    menuEl.innerHTML = items || '<div class="cr-join-opt text-secondary">No more related sources.</div>';
};

// ── Field list ────────────────────────────────────────────────────────────────

function renderFieldList() {
    const el     = document.getElementById('cr-fields-list');
    const query  = (document.getElementById('cr-field-search')?.value || '').toLowerCase();
    const fields = query ? _s.fieldDefs.filter(f => f.label.toLowerCase().includes(query) || f.key.toLowerCase().includes(query)) : _s.fieldDefs;

    if (!fields.length) {
        el.innerHTML = `<p class="text-secondary" style="font-size:12px;padding:4px 8px">${_s.fieldDefs.length ? 'No matching fields.' : 'Select a data source to see fields.'}</p>`;
        return;
    }

    // Group by source when multiple sources are active
    const multiSource = _s.joins.length > 0;
    let html = '';

    if (multiSource) {
        const groups = {};
        for (const f of fields) {
            const src = f.sourceLabel || f.sourceKey || _s.dataSource;
            if (!groups[src]) groups[src] = [];
            groups[src].push(f);
        }
        for (const [srcLabel, flds] of Object.entries(groups)) {
            html += `<div class="cr-field-group-head">${escHtml(srcLabel)}</div>`;
            html += flds.map(f => fieldItemHtml(f)).join('');
        }
    } else {
        html = fields.map(f => fieldItemHtml(f)).join('');
    }

    el.innerHTML = html;
    el.querySelectorAll('.cr-field-item').forEach(item => {
        item.addEventListener('dragstart', (e) => {
            _s.dragField = item.dataset.fieldKey;
            e.dataTransfer.effectAllowed = 'copy';
        });
        item.addEventListener('dragend', () => { _s.dragField = null; });
    });
}

function fieldItemHtml(f) {
    const icon  = TYPE_ICONS[f.type]  || 'bi-question-circle';
    const badge = TYPE_LABELS[f.type] || f.type.substring(0, 3).toUpperCase();
    return `<div class="cr-field-item" draggable="true" data-field-key="${escAttr(f.key)}"
                onclick="crAddField('${escAttr(f.key)}')"
                title="${badge} · ${escHtml(f.label)}">
        <i class="bi ${icon} cr-ft cr-ft-${escAttr(f.type)}"></i>
        <span>${escHtml(f.label)}</span>
    </div>`;
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
    renderConfigSlots(); _s.dirty = true;
}

// ── Visualization ─────────────────────────────────────────────────────────────

window.crSetViz = function(viz) {
    _s.visualization = viz;
    setVizActive(viz);
    renderConfigSlots();
    renderFormatTab();
    _s.dirty = true;
};

function setVizActive(viz) {
    document.querySelectorAll('.cr-viz-btn').forEach(btn =>
        btn.classList.toggle('active', btn.dataset.viz === viz)
    );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

window.crSwitchTab = function(tab) {
    ['visual', 'filters', 'format'].forEach(t => {
        document.querySelector(`.cr-tab[data-tab="${t}"]`)?.classList.toggle('active', t === tab);
        document.getElementById(`cr-tab-${t}`)?.classList.toggle('d-none', t !== tab);
    });
    if (tab === 'format') renderFormatTab();
};

window.crToggleSection = function(sectionId) {
    const el = document.getElementById(sectionId);
    if (!el) return;
    el.classList.toggle('cr-collapsed');
    const chevId = sectionId + '-chev';
    document.getElementById(chevId)?.classList.toggle('cr-chev-up', el.classList.contains('cr-collapsed'));
};

window.crTogglePanel = function(side) {
    const panel  = document.getElementById(`cr-${side}-panel`);
    const iconEl = document.getElementById(`cr-${side}-toggle-icon`);
    if (!panel) return;
    const collapsed = panel.classList.toggle('cr-panel-collapsed');
    if (iconEl) iconEl.className = collapsed ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
};

// ── Config slots ──────────────────────────────────────────────────────────────

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
    const opts  = AGGRS.map(a => `<option value="${a}" ${a === aggr ? 'selected' : ''}>${AGGR_LABELS[a]}</option>`).join('');
    return `<span class="cr-val-chip">
        <select class="cr-val-aggr-sel" onchange="crUpdateValue(${i},'aggregation',this.value)" title="Aggregation function">
            ${opts}
        </select>
        <span class="cr-val-field">${escHtml(label)}</span>
        <span class="cr-chip-remove" onclick="crRemoveValue(${i});event.stopPropagation()">×</span>
    </span>`;
}

window.crRemoveField = (k)    => { _s.config.fields = _s.config.fields.filter(f => f !== k); renderConfigSlots(); _s.dirty = true; };
window.crClearSlot   = (slot) => { _s.config[slot]  = ''; renderConfigSlots(); _s.dirty = true; };
window.crAddValue    = ()     => { _s.config.values.push({ field: _s.fieldDefs[0]?.key || 'id', aggregation: 'count' }); renderConfigSlots(); _s.dirty = true; };
window.crRemoveValue = (i)    => { _s.config.values.splice(i, 1); renderConfigSlots(); _s.dirty = true; };
window.crUpdateValue = (i, k, v) => {
    _s.config.values[i][k] = v;
    _s.dirty = true;
    if (k === 'field') renderConfigSlots();
};

// ── Filters ───────────────────────────────────────────────────────────────────

window.crAddFilter = function() {
    _s.config.filters.push({ field: _s.fieldDefs[0]?.key || '', operator: 'eq', value: '' });
    renderFilterList(); _s.dirty = true;
};

function renderFilterList() {
    const el    = document.getElementById('cr-filters-list');
    const empty = document.getElementById('cr-filters-empty');
    if (!el) return;
    empty?.classList.toggle('d-none', _s.config.filters.length > 0);
    el.innerHTML = _s.config.filters.map((f, i) => renderFilterRow(f, i)).join('');
}

function renderFilterRow(f, i) {
    const fieldDef = _s.fieldDefs.find(fd => fd.key === f.field);
    const ftype    = fieldDef?.type || 'text';
    const choices  = fieldDef?.choices || [];
    const op       = f.operator || 'eq';

    const validOps = OPS.filter(o => o.types.includes(ftype));
    const opSel    = `<select class="cr-filter-op" onchange="crUpdateFilter(${i},'operator',this.value)">
        ${validOps.map(o => `<option value="${o.value}" ${o.value === op ? 'selected' : ''}>${o.label}</option>`).join('')}
    </select>`;

    const fieldSel = `<select class="cr-filter-field" onchange="crUpdateFilter(${i},'field',this.value)">
        ${_s.fieldDefs.map(fd => `<option value="${escAttr(fd.key)}" ${fd.key === f.field ? 'selected' : ''}>${escHtml(fd.label)}</option>`).join('')}
    </select>`;

    let valueHtml = '';
    if (op === 'is_null' || op === 'is_not_null') {
        valueHtml = '<span class="text-secondary small px-1">—</span>';
    } else if (op === 'range') {
        const vals = Array.isArray(f.value) ? f.value : [f.value || '', ''];
        const itype = (ftype === 'date' || ftype === 'datetime') ? 'date' : 'number';
        valueHtml = `<input type="${itype}" class="cr-filter-val" value="${escAttr(String(vals[0] || ''))}" onchange="crFilterRangeFrom(${i},this.value)" placeholder="from">
                     <input type="${itype}" class="cr-filter-val" value="${escAttr(String(vals[1] || ''))}" onchange="crFilterRangeTo(${i},this.value)" placeholder="to">`;
    } else if ((op === 'in' || op === 'not_in') && choices.length) {
        const selected = Array.isArray(f.value) ? f.value : (f.value ? [String(f.value)] : []);
        valueHtml = `<select multiple class="cr-filter-multisel" onchange="crFilterMulti(${i},this)">
            ${choices.map(c => `<option value="${escAttr(c.value)}" ${selected.includes(c.value) ? 'selected' : ''}>${escHtml(c.label)}</option>`).join('')}
        </select>`;
    } else if (choices.length) {
        valueHtml = `<select class="cr-filter-val" onchange="crUpdateFilter(${i},'value',this.value)">
            <option value="">— any —</option>
            ${choices.map(c => `<option value="${escAttr(c.value)}" ${c.value === String(f.value || '') ? 'selected' : ''}>${escHtml(c.label)}</option>`).join('')}
        </select>`;
    } else {
        const itype = (ftype === 'date' || ftype === 'datetime') ? 'date' : (ftype === 'number' ? 'number' : 'text');
        valueHtml = `<input type="${itype}" class="cr-filter-val" value="${escAttr(String(f.value || ''))}" onchange="crUpdateFilter(${i},'value',this.value)" placeholder="value">`;
    }

    return `<div class="cr-filter-row">
        ${fieldSel}${opSel}
        <div class="cr-filter-val-wrap">${valueHtml}</div>
        <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm p-0" onclick="crRemoveFilter(${i})"><i class="bi bi-x"></i></button>
    </div>`;
}

window.crUpdateFilter = function(i, key, val) {
    _s.config.filters[i][key] = val;
    _s.dirty = true;
    if (key === 'operator' || key === 'field') renderFilterList();
};
window.crRemoveFilter    = (i)       => { _s.config.filters.splice(i, 1); renderFilterList(); _s.dirty = true; };
window.crFilterRangeFrom = (i, v)   => { if (!Array.isArray(_s.config.filters[i].value)) _s.config.filters[i].value = ['',''];  _s.config.filters[i].value[0] = v; _s.dirty = true; };
window.crFilterRangeTo   = (i, v)   => { if (!Array.isArray(_s.config.filters[i].value)) _s.config.filters[i].value = ['',''];  _s.config.filters[i].value[1] = v; _s.dirty = true; };
window.crFilterMulti     = (i, sel) => { _s.config.filters[i].value = Array.from(sel.selectedOptions).map(o => o.value); _s.dirty = true; };

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
    document.getElementById('cr-canvas-area')?.classList.toggle('cr-bordered', !!(_s.config.format?.showBorder));

    if (result.type === 'card') {
        const w = document.getElementById('cr-card-wrap');
        w.classList.remove('d-none'); w.innerHTML = buildCardHtml(result); destroyChart(); return;
    }
    if (result.type === 'heatmap') {
        const w = document.getElementById('cr-heatmap-wrap');
        w.classList.remove('d-none'); w.innerHTML = buildHeatmapHtml(result); destroyChart(); return;
    }
    if (result.type === 'table' || result.type === 'pivot') {
        const w = document.getElementById('cr-table-wrap');
        w.classList.remove('d-none');
        w.innerHTML = result.type === 'table' ? buildTableHtml(result) : buildPivotHtml(result);
        destroyChart(); return;
    }
    document.getElementById('cr-chart-wrap').classList.remove('d-none');
    renderChartJs(result);
}

function titleHtml() {
    const fmt = _s.config.format || {};
    if (!fmt.title && !fmt.subtitle) return '';
    return `<div class="cr-canvas-title">${fmt.title ? `<div class="cr-title">${escHtml(fmt.title)}</div>` : ''}${fmt.subtitle ? `<div class="cr-subtitle">${escHtml(fmt.subtitle)}</div>` : ''}</div>`;
}

function buildTableHtml(result) {
    const cols = result.columns || [];
    const rows = result.rows    || [];
    const fs   = { sm: '11px', md: '13px', lg: '15px' }[_s.config.format?.fontSize || 'md'];
    return `${titleHtml()}<table class="cr-table" style="font-size:${fs}">
        <thead><tr>${cols.map(c => `<th>${escHtml(c.label)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(row => `<tr>${cols.map(c => `<td>${escHtml(String(row[c.key] ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
    </table>`;
}

function buildPivotHtml(result) {
    const cols = result.columns || []; const rows = result.rows || [];
    const matrix = result.matrix || {}; const rowTots = result.row_totals || {};
    const colTots = result.col_totals || []; const grand = result.grand_total ?? '';
    return `${titleHtml()}<table class="cr-table">
        <thead><tr>
            <th>${escHtml(result.rows_label || 'Row')} \\ ${escHtml(result.columns_label || 'Col')}</th>
            ${cols.map(c => `<th>${escHtml(String(c))}</th>`).join('')}
            <th class="cr-pivot-total">Total</th>
        </tr></thead>
        <tbody>
            ${rows.map(rv => `<tr>
                <td><strong>${escHtml(String(rv))}</strong></td>
                ${(matrix[rv] || []).map(v => `<td class="text-end">${v ?? ''}</td>`).join('')}
                <td class="text-end cr-pivot-total">${rowTots[rv] ?? ''}</td>
            </tr>`).join('')}
            <tr class="cr-pivot-total">
                <td><strong>Total</strong></td>
                ${colTots.map(v => `<td class="text-end">${v}</td>`).join('')}
                <td class="text-end"><strong>${grand}</strong></td>
            </tr>
        </tbody>
    </table>`;
}

function buildHeatmapHtml(result) {
    const cols = result.columns || []; const rows = result.rows || [];
    const matrix = result.matrix || {}; const rowTots = result.row_totals || {};
    const allVals = Object.values(rowTots).filter(v => v != null);
    const maxVal  = allVals.length ? Math.max(...allVals, 1) : 1;
    const cellStyle = (val) => {
        const pct = Math.min(Math.round(((val || 0) / maxVal) * 100), 100);
        return `background:rgba(30,58,95,${(pct/100).toFixed(2)});color:${pct > 45 ? '#fff' : '#1e293b'}`;
    };
    return `${titleHtml()}<div class="cr-heatmap-grid">
        <div class="cr-hm-header">
            <div class="cr-hm-cell cr-hm-label">${escHtml(result.rows_label||'')} / ${escHtml(result.columns_label||'')}</div>
            ${cols.map(c => `<div class="cr-hm-cell cr-hm-col-head">${escHtml(String(c))}</div>`).join('')}
        </div>
        ${rows.map(rv => `<div class="cr-hm-row">
            <div class="cr-hm-cell cr-hm-row-head">${escHtml(String(rv))}</div>
            ${(matrix[rv]||[]).map(v => `<div class="cr-hm-cell cr-hm-data" style="${cellStyle(v)}">${v??''}</div>`).join('')}
        </div>`).join('')}
    </div>`;
}

function buildCardHtml(result) {
    const cards = result.cards || [];
    return `${titleHtml()}<div class="cr-cards">
        ${cards.map(c => {
            const val = c.value !== null && c.value !== undefined
                ? (Number.isInteger(c.value) ? c.value : Number(c.value).toFixed(2)) : '—';
            return `<div class="cr-card"><div class="cr-card-value">${val}</div><div class="cr-card-label">${escHtml(c.label)}</div></div>`;
        }).join('')}
    </div>`;
}

function renderChartJs(result) {
    destroyChart();
    const fmt   = _s.config.format || {};
    const ctx   = document.getElementById('cr-chart').getContext('2d');
    const rtype = result.type;
    const isHoriz = rtype === 'bar' || rtype === 'stacked_bar';
    const isStack = rtype === 'stacked_bar' || rtype === 'stacked_column';
    const isPie   = rtype === 'pie';
    const isLine  = rtype === 'line';
    const isCombo = rtype === 'combo';

    const datasets = (result.datasets || []).map((ds, i) => {
        const color = CHART_COLORS[i % CHART_COLORS.length];
        const st    = ds.series_type || (isCombo && i > 0 ? 'line' : 'bar');
        const isLS  = isLine || st === 'line';
        return {
            type:            isPie ? undefined : (isCombo ? st : undefined),
            label:           ds.label, data: ds.data,
            backgroundColor: isPie ? ds.data.map((_, j) => CHART_COLORS[j % CHART_COLORS.length]) : (isLS ? color + '33' : color),
            borderColor: color, borderWidth: isLS ? 2 : 0,
            fill: false, tension: isLS ? 0.3 : 0, pointRadius: isLS ? 3 : 0,
        };
    });

    _s.chartInst = new Chart(ctx, {
        type: isPie ? 'pie' : 'bar',
        data: { labels: result.labels || [], datasets },
        options: {
            indexAxis: isHoriz ? 'y' : 'x',
            responsive: true, maintainAspectRatio: true,
            plugins: {
                legend:  { display: !fmt.hideLegend, position: 'top' },
                title:   { display: !!(fmt.title || fmt.subtitle), text: [fmt.title || _s.name, fmt.subtitle].filter(Boolean) },
                tooltip: { mode: 'index', intersect: false },
            },
            scales: isPie ? {} : {
                x: { stacked: isStack, title: { display: !!(fmt.xLabel || result.axis_label), text: fmt.xLabel || result.axis_label || '' } },
                y: { stacked: isStack, beginAtZero: true, title: { display: !!fmt.yLabel, text: fmt.yLabel || '' } },
            },
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
        name, description: '',
        data_source: _s.dataSource, visualization: _s.visualization,
        config: _s.config,
        is_shared: (_s.reportPk && _s.reportPk !== 'null') ? undefined : false,
    };
    const btn = document.getElementById('btn-cr-save');
    btn.disabled = true; setStatus('Saving…');
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
        _s.dirty = false; setStatus('Saved'); setTimeout(() => setStatus(''), 2000);
    } catch (err) {
        const d = err?.data || err;
        showFlash(String(d?.detail || d?.name?.[0] || 'Failed to save.'), 'danger'); setStatus('');
    } finally { btn.disabled = false; }
}

function setStatus(msg) { const el = document.getElementById('cr-status'); if (el) el.textContent = msg; }

// ── Export ────────────────────────────────────────────────────────────────────

function exportReport(fmt) {
    if (!_s.reportPk || _s.reportPk === 'null') { showFlash('Save the report first.', 'info'); return; }
    const { href } = API_URLS.custom_reports.export(_s.reportPk, fmt);
    const a = document.createElement('a');
    a.href = href; a.style.display = 'none';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}

function exportImage() {
    const canvas = document.getElementById('cr-chart');
    if (!canvas || !_s.chartInst) { showFlash('Run a chart visualization first.', 'info'); return; }
    const link    = document.createElement('a');
    link.download = (document.getElementById('cr-name').value.trim() || 'report') + '.png';
    link.href     = canvas.toDataURL('image/png'); link.click();
}

// ── Sort helpers ──────────────────────────────────────────────────────────────

function getSortColumns() {
    const viz = _s.visualization;
    const fm  = Object.fromEntries(_s.fieldDefs.map(f => [f.key, f.label]));
    const cols = [];
    if (viz === 'table') {
        (_s.config.fields || []).forEach(k => cols.push({ key: k, label: fm[k] || k }));
    } else if (['bar','stacked_bar','column','stacked_column','line','combo','pie'].includes(viz)) {
        if (_s.config.axis) cols.push({ key: _s.config.axis, label: fm[_s.config.axis] || _s.config.axis });
    } else if (['pivot','heatmap'].includes(viz)) {
        if (_s.config.rows)    cols.push({ key: _s.config.rows,    label: fm[_s.config.rows]    || _s.config.rows });
        if (_s.config.columns) cols.push({ key: _s.config.columns, label: fm[_s.config.columns] || _s.config.columns });
    }
    (_s.config.values || []).forEach((v, i) => {
        cols.push({ key: `_val${i}`, label: `${AGGR_LABELS[v.aggregation || 'count']}(${fm[v.field] || v.field || 'id'})` });
    });
    if (!cols.length) _s.fieldDefs.forEach(f => cols.push({ key: f.key, label: f.label }));
    return cols;
}

function sortSectionHtml() {
    const cols  = getSortColumns();
    const rules = _s.config.sort_by || [];

    const rulesHtml = rules.map((r, i) => {
        const fieldOpts = cols.map(c =>
            `<option value="${escAttr(c.key)}" ${r.field === c.key ? 'selected' : ''}>${escHtml(c.label)}</option>`
        ).join('');
        return `<div class="cr-filter-row">
            <select class="cr-filter-field" onchange="crUpdateSort(${i},'field',this.value)">${fieldOpts}</select>
            <select class="cr-filter-op" onchange="crUpdateSort(${i},'direction',this.value)">
                <option value="asc"  ${r.direction !== 'desc' ? 'selected' : ''}>ASC ↑</option>
                <option value="desc" ${r.direction === 'desc' ? 'selected' : ''}>DESC ↓</option>
            </select>
            <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm p-0" onclick="crRemoveSort(${i})">
                <i class="bi bi-x"></i></button>
        </div>`;
    }).join('');

    return `<div class="cr-slot-label mb-1 d-flex justify-content-between align-items-center">
        <span>Sort</span>
        <span class="cr-val-add" onclick="crAddSort()" title="Add sort rule"><i class="bi bi-plus-circle"></i></span>
    </div>
    <div id="cr-sort-rules" class="mb-3">
        ${rulesHtml || '<p class="text-secondary small mb-0">Default order. Add a rule to customise.</p>'}
    </div>`;
}

window.crAddSort = () => {
    const cols = getSortColumns();
    if (!_s.config.sort_by) _s.config.sort_by = [];
    _s.config.sort_by.push({ field: cols[0]?.key || '', direction: 'asc' });
    renderFormatTab();
    _s.dirty = true;
};
window.crRemoveSort  = (i)       => { _s.config.sort_by.splice(i, 1); renderFormatTab(); _s.dirty = true; };
window.crUpdateSort  = (i, k, v) => { _s.config.sort_by[i][k] = v; renderFormatTab(); _s.dirty = true; };

// ── Format tab (dynamic per viz type) ────────────────────────────────────────

function renderFormatTab() {
    const viz   = _s.visualization;
    const fmt   = _s.config.format || {};
    const panel = document.getElementById('cr-tab-format');
    if (!panel) return;

    const isChart = ['bar','stacked_bar','column','stacked_column','line','combo'].includes(viz);
    const isPie   = viz === 'pie';

    const v = (k, d = '') => escAttr(fmt[k] !== undefined ? fmt[k] : d);
    const c = (k)         => fmt[k] ? 'checked' : '';
    const sel = (k, opts) => opts.map(([val, lbl]) =>
        `<option value="${val}" ${(fmt[k] || opts[1][0]) === val ? 'selected' : ''}>${lbl}</option>`).join('');

    let html = sortSectionHtml();

    html += `
        <div class="cr-slot-label mb-1">Title</div>
        <input type="text" class="form-control form-control-sm mb-2" value="${v('title')}" placeholder="Leave blank to use report name" oninput="syncFmt('title',this.value)">
        <div class="cr-slot-label mb-1">Subtitle</div>
        <input type="text" class="form-control form-control-sm mb-2" value="${v('subtitle')}" placeholder="Optional" oninput="syncFmt('subtitle',this.value)">`;

    if (isChart || isPie) {
        html += `<div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" id="cr-fmt-legend" ${c('hideLegend') ? '' : 'checked'} onchange="syncFmt('hideLegend',!this.checked)">
            <label class="form-check-label small" for="cr-fmt-legend">Show legend</label>
        </div>`;
    }
    if (isChart) {
        html += `
        <div class="cr-slot-label mb-1">X-Axis Label</div>
        <input type="text" class="form-control form-control-sm mb-2" value="${v('xLabel')}" placeholder="X axis" oninput="syncFmt('xLabel',this.value)">
        <div class="cr-slot-label mb-1">Y-Axis Label</div>
        <input type="text" class="form-control form-control-sm mb-2" value="${v('yLabel')}" placeholder="Y axis" oninput="syncFmt('yLabel',this.value)">`;
    }

    html += `
        <div class="cr-slot-label mb-1">Font Size</div>
        <select class="form-select form-select-sm mb-2" onchange="syncFmt('fontSize',this.value)">
            ${sel('fontSize', [['sm','Small (11px)'],['md','Medium (13px)'],['lg','Large (15px)']])}
        </select>
        <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" id="cr-fmt-border" ${c('showBorder')} onchange="syncFmt('showBorder',this.checked)">
            <label class="form-check-label small" for="cr-fmt-border">Show border around canvas</label>
        </div>`;

    panel.innerHTML = html;
}

window.syncFmt = function(key, value) {
    if (!_s.config.format) _s.config.format = {};
    _s.config.format[key] = value;
    _s.dirty = true;
};

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
    } catch { showFlash('Failed to remove share.', 'danger'); }
};

// ── Utils ─────────────────────────────────────────────────────────────────────

function escAttr(s) {
    return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;');
}
