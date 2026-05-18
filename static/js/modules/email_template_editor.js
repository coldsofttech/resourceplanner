'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';
import {
    TOOLBAR_CONTAINER, initToolbarTooltips, injectCustomButtonIcons,
    addCustomHandlers, setupClipboardMatchers, setupTablePicker, setupIconPicker, setupContextMenu, SourceModeManager,
} from './quill_editor_utils.js';

// ── Sample data for client-side preview ───────────────────────────────────────
const SAMPLE_DATA = {
    user_created: {
        '{{ first_name }}': 'Jane', '{{ last_name }}': 'Smith',
        '{{ email }}': 'jane.smith@example.com', '{{ created_at }}': '18 May 2026 09:30',
        '{{ temp_password }}': 'Temp@1234', '{{ login_url }}': 'https://app.example.com/login/',
        '{{ app_name }}': 'ResourcePlanner',
    },
    password_reset: {
        '{{ first_name }}': 'Jane', '{{ last_name }}': 'Smith',
        '{{ email }}': 'jane.smith@example.com',
        '{{ reset_link }}': '<a href="#">https://app.example.com/reset/?token=abc123</a>',
        '{{ expires_at }}': '18 May 2026 11:30', '{{ app_name }}': 'ResourcePlanner',
    },
    recharge_forecast: {
        '{{ sprint_name }}': 'Sprint 12', '{{ fy }}': 'FY25/26',
        '{{ project_name }}': 'Data Platform Rebuild', '{{ project_code }}': 'DPR-001',
        '{{ total_days }}': '14.50', '{{ total_cost }}': '£10,875.00',
        '{{ recharge_table }}': '<table class="table table-sm table-bordered mt-2"><thead><tr><th>Jira ID</th><th>Title</th><th>Assignee</th><th>Days</th><th>Cost (£)</th></tr></thead><tbody><tr><td>DATA-101</td><td>Setup pipeline</td><td>Alex T.</td><td>5.00</td><td>3,750.00</td></tr><tr><td>DATA-102</td><td>ETL jobs</td><td>Sam K.</td><td>9.50</td><td>7,125.00</td></tr></tbody><tfoot><tr><th colspan="3">Total</th><th>14.50</th><th>£10,875.00</th></tr></tfoot></table>',
    },
    recharge_actuals: {
        '{{ sprint_name }}': 'Sprint 12', '{{ fy }}': 'FY25/26',
        '{{ project_name }}': 'Data Platform Rebuild', '{{ project_code }}': 'DPR-001',
        '{{ total_days }}': '13.00', '{{ total_cost }}': '£9,750.00',
        '{{ recharge_table }}': '<table class="table table-sm table-bordered mt-2"><thead><tr><th>Jira ID</th><th>Title</th><th>Assignee</th><th>Days</th><th>Cost (£)</th></tr></thead><tbody><tr><td>DATA-101</td><td>Setup pipeline</td><td>Alex T.</td><td>4.00</td><td>3,000.00</td></tr><tr><td>DATA-102</td><td>ETL jobs</td><td>Sam K.</td><td>9.00</td><td>6,750.00</td></tr></tbody><tfoot><tr><th colspan="3">Total</th><th>13.00</th><th>£9,750.00</th></tr></tfoot></table>',
    },
};

const NUMERIC_COLS = new Set(['days', 'cost']);

const scenario        = window.SCENARIO;
const isTableScenario = window.IS_TABLE_SCENARIO;

let quill        = null;
let sourceMgr    = null;
let tableColumns = [];

document.addEventListener('DOMContentLoaded', async () => {
    // ── Init Quill ──────────────────────────────────────────────────────────
    quill = new Quill('#quill-editor', {
        theme: 'snow',
        modules: { toolbar: TOOLBAR_CONTAINER },
        placeholder: 'Compose your email body here…',
    });

    initToolbarTooltips(quill);
    injectCustomButtonIcons(quill);
    addCustomHandlers(quill);
    setupClipboardMatchers(quill);
    setupTablePicker(quill);
    setupIconPicker(quill);
    setupContextMenu(quill);

    sourceMgr = new SourceModeManager({
        quill,
        richEl: document.getElementById('quill-editor'),
        htmlEl: document.getElementById('html-source'),
        mdEl:   document.getElementById('markdown-source'),
        tabsEl: document.getElementById('editor-mode-tabs'),
    });

    _setupDragDrop();

    // ── Load template + variables ───────────────────────────────────────────
    const [tmpl, varData] = await Promise.all([
        _loadTemplate(),
        _loadVariables(),
    ]);

    if (tmpl)    _applyTemplate(tmpl);
    if (varData) _renderVars(varData);

    await _loadSelectOptions();

    if (tmpl?.header_id) document.getElementById('header-select').value = tmpl.header_id;
    if (tmpl?.footer_id) document.getElementById('footer-select').value = tmpl.footer_id;

    if (isTableScenario && varData?.table_columns) {
        tableColumns = varData.table_columns;
        _buildTableConfig(tmpl?.table_config || {});
    }

    document.getElementById('editor-loading').classList.add('d-none');
    document.getElementById('editor-wrap').classList.remove('d-none');

    document.getElementById('save-btn').addEventListener('click', saveTemplate);
    document.getElementById('preview-btn').addEventListener('click', showPreview);
});

// ── Load helpers ──────────────────────────────────────────────────────────────

async function _loadTemplate() {
    try {
        return await apiFetch(API_URLS.email_templates.detail(scenario).href, { method: 'GET' });
    } catch { return null; }
}

async function _loadVariables() {
    try {
        return await apiFetch(API_URLS.email_templates.variables(scenario).href, { method: 'GET' });
    } catch { return null; }
}

async function _loadSelectOptions() {
    const [headers, footers] = await Promise.all([
        apiFetch(API_URLS.email_template_headers.options.href, { method: 'GET' }).catch(() => []),
        apiFetch(API_URLS.email_template_footers.options.href, { method: 'GET' }).catch(() => []),
    ]);
    _populateSelect('header-select', headers);
    _populateSelect('footer-select', footers);
}

function _populateSelect(id, items) {
    const sel = document.getElementById(id);
    if (!sel) return;
    items.forEach(({ id, name }) => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = name;
        sel.appendChild(opt);
    });
}

function _applyTemplate(tmpl) {
    document.getElementById('subject-input').value = tmpl.subject || '';
    document.getElementById('is-active-toggle').checked = !!tmpl.is_active;
    if (tmpl.body) sourceMgr.setContent(tmpl.body);
}

// ── Variables panel ───────────────────────────────────────────────────────────

function _renderVars(data) {
    const list    = document.getElementById('vars-list');
    const loading = document.getElementById('vars-loading');
    loading.classList.add('d-none');
    list.classList.remove('d-none');

    const vars = data.variables || [];
    const groups = {};
    vars.forEach(v => {
        const g = v.group || 'General';
        if (!groups[g]) groups[g] = [];
        groups[g].push(v);
    });

    list.innerHTML = Object.entries(groups).map(([groupName, items]) => `
        <div class="et-vars-section">
            <div class="et-vars-group">${_esc(groupName)}</div>
            ${items.map(v => _varChip(v)).join('')}
        </div>
    `).join('');

    list.querySelectorAll('.et-var-chip').forEach(chip => {
        const key = chip.dataset.key;
        chip.addEventListener('click', () => insertVariable(key));
        chip.setAttribute('draggable', 'true');
        chip.addEventListener('dragstart', e => {
            e.dataTransfer.setData('text/plain', key);
            e.dataTransfer.effectAllowed = 'copy';
        });
    });
}

function _varChip(v) {
    const isTable = v.type === 'table';
    const tip     = v.description ? ` title="${_esc(v.description)}"` : '';
    return `<span class="et-var-chip${isTable ? ' et-var-chip--table' : ''}"
                  data-key="${_esc(v.key)}"${tip}>
        ${isTable ? '<i class="bi bi-table et-var-icon"></i>' : ''}
        ${_esc(v.key)}
    </span>`;
}

function insertVariable(key) {
    if (sourceMgr?.mode === 'html') {
        const ta    = document.getElementById('html-source');
        const start = ta.selectionStart;
        ta.value    = ta.value.slice(0, start) + key + ta.value.slice(ta.selectionEnd);
        ta.selectionStart = ta.selectionEnd = start + key.length;
        ta.focus();
        return;
    }
    if (sourceMgr?.mode === 'markdown') {
        const ta    = document.getElementById('markdown-source');
        const start = ta.selectionStart;
        ta.value    = ta.value.slice(0, start) + key + ta.value.slice(ta.selectionEnd);
        ta.selectionStart = ta.selectionEnd = start + key.length;
        ta.focus();
        return;
    }
    quill.focus();
    const range = quill.getSelection(true);
    const idx   = range ? range.index : quill.getLength();
    quill.insertText(idx, key, 'user');
    quill.setSelection(idx + key.length);
}

// ── Drag & drop into Quill ────────────────────────────────────────────────────

function _setupDragDrop() {
    const editorEl = document.querySelector('#quill-editor .ql-editor');
    if (!editorEl) return;
    editorEl.addEventListener('dragover', e => {
        if (e.dataTransfer.types.includes('text/plain')) e.preventDefault();
    });
    editorEl.addEventListener('drop', e => {
        const text = e.dataTransfer.getData('text/plain');
        if (!text?.startsWith('{{')) return;
        e.preventDefault();
        e.stopPropagation();
        const range = quill.getSelection(true);
        const idx   = range ? range.index : quill.getLength();
        quill.insertText(idx, text, 'user');
        quill.setSelection(idx + text.length);
    });
}

function _getBodyHtml() {
    return sourceMgr ? sourceMgr.getContent() : quill.root.innerHTML;
}

// ── Table config ──────────────────────────────────────────────────────────────

function _buildTableConfig(saved) {
    const grid    = document.getElementById('table-columns-grid');
    const totGrid = document.getElementById('totals-for-grid');
    if (!grid) return;

    const savedCols     = saved.columns     ?? tableColumns.filter(c => c.default).map(c => c.key);
    const savedView     = saved.view        ?? 'table';
    const savedTotal    = saved.show_total  !== false;
    const savedTotalsFor = saved.totals_for ?? ['days', 'cost'];

    const viewEl = document.querySelector(`input[name="table-view"][value="${savedView}"]`);
    if (viewEl) viewEl.checked = true;

    grid.innerHTML = tableColumns.map(col => `
        <div class="form-check">
            <input class="form-check-input" type="checkbox" id="col-${col.key}"
                   value="${col.key}" ${savedCols.includes(col.key) ? 'checked' : ''}>
            <label class="form-check-label small" for="col-${col.key}">${_esc(col.label)}</label>
        </div>
    `).join('');

    const showTotalEl = document.getElementById('show-total');
    if (showTotalEl) {
        showTotalEl.checked = savedTotal;
        _toggleTotalsFor(savedTotal);
        showTotalEl.addEventListener('change', () => _toggleTotalsFor(showTotalEl.checked));
    }

    if (totGrid) {
        const numericCols = tableColumns.filter(c => NUMERIC_COLS.has(c.key));
        totGrid.innerHTML = numericCols.map(col => `
            <div class="form-check">
                <input class="form-check-input" type="checkbox" id="totfor-${col.key}"
                       value="${col.key}" ${savedTotalsFor.includes(col.key) ? 'checked' : ''}>
                <label class="form-check-label small" for="totfor-${col.key}">${_esc(col.label)}</label>
            </div>
        `).join('');
    }
}

function _toggleTotalsFor(show) {
    document.getElementById('totals-for-wrap')?.classList.toggle('d-none', !show);
}

function _readTableConfig() {
    if (!isTableScenario) return {};
    return {
        view:      document.querySelector('input[name="table-view"]:checked')?.value ?? 'table',
        columns:   [...document.querySelectorAll('#table-columns-grid input:checked')].map(i => i.value),
        show_total: document.getElementById('show-total')?.checked ?? true,
        totals_for: [...document.querySelectorAll('#totals-for-grid input:checked')].map(i => i.value),
    };
}

// ── Save ──────────────────────────────────────────────────────────────────────

async function saveTemplate() {
    const saveBtn = document.getElementById('save-btn');
    const orig    = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…';

    const payload = {
        subject:      document.getElementById('subject-input').value.trim(),
        body:         _getBodyHtml(),
        header_id:    document.getElementById('header-select').value || null,
        footer_id:    document.getElementById('footer-select').value || null,
        is_active:    document.getElementById('is-active-toggle').checked,
        table_config: _readTableConfig(),
    };

    try {
        await apiFetch(API_URLS.email_templates.save(scenario).href, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });
        showFlash('Template saved successfully.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Save failed. Please try again.', 'danger');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = orig;
    }
}

// ── Preview ───────────────────────────────────────────────────────────────────

function showPreview() {
    const body    = _getBodyHtml();
    const subject = document.getElementById('subject-input').value;
    const sample  = SAMPLE_DATA[scenario] || {};

    const headerSel = document.getElementById('header-select');
    const footerSel = document.getElementById('footer-select');
    const headerName = headerSel?.value ? headerSel.selectedOptions[0]?.text : null;
    const footerName = footerSel?.value ? footerSel.selectedOptions[0]?.text : null;

    document.getElementById('preview-subject').innerHTML =
        `<strong>Subject:</strong> ${_esc(_substituteSample(subject, sample))}`;
    document.getElementById('preview-content').innerHTML = _substituteSample(body, sample);

    const hBlock = document.getElementById('preview-header-block');
    const fBlock = document.getElementById('preview-footer-block');
    hBlock.classList.toggle('d-none', !headerName);
    fBlock.classList.toggle('d-none', !footerName);
    if (headerName) document.getElementById('preview-header-name').textContent = headerName;
    if (footerName) document.getElementById('preview-footer-name').textContent = footerName;

    new bootstrap.Modal(document.getElementById('previewModal')).show();
}

function _substituteSample(html, sample) {
    let out = html;
    Object.entries(sample).forEach(([key, val]) => { out = out.split(key).join(val); });
    return out;
}

// ── Utility ───────────────────────────────────────────────────────────────────

function _esc(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
