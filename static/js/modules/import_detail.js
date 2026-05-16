'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch, showFlash, getCsrfToken } from '../main.js';

const SPRINT_ID = window.SPRINT_ID;
const IMPORT_ID = window.IMPORT_ID;

let _currentRows = [];
let _memberCapacities = {};
let _financeTypes = [];
let _labels = [];

// ── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    _loadFinanceTypes().then(_loadAll);

    document.getElementById('review-btn').addEventListener('click', _runReview);
    document.getElementById('confirm-btn').addEventListener('click', _confirmImport);
    document.getElementById('add-row-btn').addEventListener('click', _addRow);
});

async function _loadFinanceTypes() {
    try {
        _financeTypes = await apiFetch(API_URLS.finance_types.options.href) || [];
    } catch (_) { /* non-critical */ }
}

async function _loadAll() {
    try {
        const [fi, rowsResp, labelsData] = await Promise.all([
            apiFetch(API_URLS.sprint_forecast.detail(IMPORT_ID).href),
            apiFetch(API_URLS.sprint_forecast.rows(IMPORT_ID).href),
            apiFetch(API_URLS.sprint_forecast.labels_options.href).catch(() => []),
        ]);
        _currentRows = rowsResp.rows || [];
        _memberCapacities = rowsResp.member_capacities || {};
        _labels = labelsData || [];
        _renderHeader(fi);
        _renderRows(_currentRows);
        _renderCapacityPivot(_currentRows);
    } catch (e) {
        document.getElementById('rows-loading').innerHTML =
            '<span class="text-danger">Failed to load import data.</span>';
    }
}

// ── Header ───────────────────────────────────────────────────────────────────

function _renderHeader(fi) {
    const statusMap = {
        active: 'rp-badge--primary',
        confirmed: 'rp-badge--success',
        superseded: 'rp-badge--muted',
    };
    const badge = document.getElementById('import-status-badge');
    badge.textContent = fi.status.charAt(0).toUpperCase() + fi.status.slice(1);
    badge.className = `rp-badge ${statusMap[fi.status] || ''}`;

    const confirmed = fi.status === 'confirmed';
    document.getElementById('confirm-btn').disabled = confirmed;

    const by = fi.imported_by_name || 'Unknown';
    const at = _fmtDate(fi.imported_at);
    document.getElementById('import-meta').textContent =
        `Imported by ${by} on ${at} · ${fi.row_count} rows`;

    const summaryEl = document.getElementById('review-summary');
    if (fi.latest_review) {
        const r = fi.latest_review;
        const cls = r.error_count > 0 ? 'alert-danger' : 'alert-success';
        const icon = r.error_count > 0 ? 'bi-exclamation-triangle' : 'bi-check-circle';
        summaryEl.innerHTML = `<i class="bi ${icon} me-2"></i>Last review: ${r.error_count} error(s), ${r.pass_count} pass(es)`;
        summaryEl.className = `alert ${cls} py-2 mb-4`;
        summaryEl.classList.remove('d-none');
    } else {
        summaryEl.classList.add('d-none');
    }
}

// ── Rows tab ─────────────────────────────────────────────────────────────────

function _renderRows(rows) {
    const loading = document.getElementById('rows-loading');
    const wrap = document.getElementById('rows-table-wrap');
    const empty = document.getElementById('rows-empty');
    const badge = document.getElementById('rows-count-badge');

    loading.style.display = 'none';
    badge.textContent = rows.length;

    if (!rows.length) {
        wrap.style.display = 'none';
        empty.classList.remove('d-none');
        return;
    }
    empty.classList.add('d-none');
    wrap.style.display = '';

    document.getElementById('rows-tbody').innerHTML = rows.map((row, idx) => {
        const checks = _renderCheckBadges(row.latest_review_results || []);
        const hasOverride = row.has_overrides ? ' style="background:var(--color-warning-soft,#fff8e1)"' : '';
        return `<tr${hasOverride}>
            <td class="text-secondary">${idx + 1}</td>
            <td>${_esc(row.effective_story_type || '—')}</td>
            <td><code>${_esc(row.effective_jira_id || '—')}</code></td>
            <td style="max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
                title="${_esc(row.effective_title)}">${_esc(row.effective_title || '—')}</td>
            <td>${_esc(row.effective_assignee_name || row.effective_assignee_raw || '—')}</td>
            <td class="text-end font-mono">${((row.effective_efforts_ms || 0) / 1000).toLocaleString()}</td>
            <td class="text-end font-mono">${row.days}</td>
            <td>${_esc(row.effective_sprint_name || '—')}</td>
            <td>${_esc(row.effective_label_name || '—')}</td>
            <td>${_esc(row.effective_mapping_code || '—')}</td>
            <td>${checks}</td>
            <td>
                <button class="btn btn-ghost-icon btn-sm edit-row-btn" data-row-id="${row.id}" title="Edit">
                    <i class="bi bi-pencil"></i>
                </button>
            </td>
        </tr>`;
    }).join('');

    document.getElementById('rows-tbody').querySelectorAll('.edit-row-btn').forEach(btn => {
        btn.addEventListener('click', () => _editRow(btn.dataset.rowId));
    });
}

function _renderCheckBadges(results) {
    const relevant = results.filter(r => r.check_type !== 'capacity_check');
    if (!relevant.length) return '<span class="text-secondary">—</span>';
    const byType = {};
    relevant.forEach(r => { byType[r.check_type] = r; });
    const icons = { label_check: 'bi-tag', mapping_check: 'bi-diagram-2' };
    return Object.entries(byType).map(([type, r]) => {
        const cls = r.status === 'pass' ? 'text-success' : 'text-danger';
        const title = r.status === 'pass' ? `${type}: pass` : `${type}: ${r.message}`;
        return `<i class="bi ${icons[type] || 'bi-check'} ${cls}" title="${_esc(title)}"></i>`;
    }).join(' ');
}

// ── Capacity Pivot tab ───────────────────────────────────────────────────────

function _renderCapacityPivot(rows) {
    const memberMap = {};
    rows.forEach(row => {
        const name = row.effective_assignee_name || row.effective_assignee_raw;
        if (!name) return;
        if (!memberMap[name]) memberMap[name] = { days: 0, results: [] };
        memberMap[name].days += parseFloat(row.days || 0);
        const cap = (row.latest_review_results || []).find(r => r.check_type === 'capacity_check');
        if (cap) memberMap[name].results.push(cap);
    });

    document.getElementById('capacity-tbody').innerHTML =
        Object.entries(memberMap).map(([name, info]) => {
            const netCap = _memberCapacities[name];
            const netCapStr = netCap !== undefined ? parseFloat(netCap).toFixed(2) : '—';
            const lastCap = info.results[info.results.length - 1];
            const match = lastCap
                ? (lastCap.status === 'pass'
                    ? '<i class="bi bi-check-circle text-success"></i>'
                    : `<i class="bi bi-x-circle text-danger" title="${_esc(lastCap.message)}"></i>`)
                : '<span class="text-secondary">—</span>';
            return `<tr>
                <td>${_esc(name)}</td>
                <td class="text-end font-mono">${info.days.toFixed(2)}</td>
                <td class="text-end font-mono">${netCapStr}</td>
                <td class="text-center">${match}</td>
            </tr>`;
        }).join('') ||
        '<tr><td colspan="4" class="text-secondary text-center py-3">No assignee data.</td></tr>';
}

// ── Inline Row Edit ──────────────────────────────────────────────────────────

function _editRow(rowId) {
    const row = _currentRows.find(r => String(r.id) === String(rowId));
    if (!row) return;

    const existing = document.querySelector(`.rp-inline-edit[data-row-id="${rowId}"]`);
    if (existing) { existing.remove(); return; }

    const mappingOptions = _financeTypes.map(ft =>
        `<option value="${ft.id}" ${row.effective_mapping_id == ft.id ? 'selected' : ''}>${_esc(ft.code)} — ${_esc(ft.name)}</option>`
    ).join('');

    const datalistId = `label-datalist-${row.id}`;
    const labelDatalistOptions = _labels.map(lbl =>
        `<option value="${_esc(lbl.label)}">${_esc(lbl.label)}${lbl.project_name ? ' (' + _esc(lbl.project_name) + ')' : ''}</option>`
    ).join('');

    const assigneeNames = Object.keys(_memberCapacities).sort();
    const currentAssignee = row.effective_assignee_name || row.effective_assignee_raw || '';
    const assigneeOptions = assigneeNames.map(name =>
        `<option value="${_esc(name)}" ${currentAssignee === name ? 'selected' : ''}>${_esc(name)}</option>`
    ).join('');

    const html = `
    <div class="rp-inline-edit p-3 border rounded mb-2 bg-body" data-row-id="${row.id}" style="font-size:13px">
        <div class="row g-2">
            <div class="col-md-2">
                <label class="form-label mb-1">Story Type</label>
                <input type="text" class="form-control form-control-sm" data-field="story_type_override"
                    value="${_esc(row.effective_story_type || '')}">
            </div>
            <div class="col-md-2">
                <label class="form-label mb-1">Jira ID</label>
                <input type="text" class="form-control form-control-sm" data-field="jira_id_override"
                    value="${_esc(row.effective_jira_id || '')}">
            </div>
            <div class="col-md-3">
                <label class="form-label mb-1">Title / Description</label>
                <input type="text" class="form-control form-control-sm" data-field="title_override"
                    value="${_esc(row.effective_title || '')}">
            </div>
            <div class="col-md-2">
                <label class="form-label mb-1">Assignee</label>
                <select class="form-select form-select-sm" data-field="assignee_raw_override">
                    <option value="">— None —</option>
                    ${assigneeOptions}
                </select>
            </div>
            <div class="col-md-1">
                <label class="form-label mb-1">Efforts (s)</label>
                <input type="number" class="form-control form-control-sm" data-field="efforts_ms_override"
                    value="${((row.effective_efforts_ms || 0) / 1000)}">
            </div>
            <div class="col-md-1">
                <label class="form-label mb-1">Sprint</label>
                <input type="text" class="form-control form-control-sm" data-field="sprint_name_override"
                    value="${_esc(row.effective_sprint_name || '')}">
            </div>
            <div class="col-md-1">
                <label class="form-label mb-1">Label</label>
                <datalist id="${datalistId}">${labelDatalistOptions}</datalist>
                <input type="text" class="form-control form-control-sm" data-field="label_override_raw"
                    list="${datalistId}" value="${_esc(row.effective_label_name || '')}"
                    autocomplete="off" placeholder="Type to search…">
            </div>
        </div>
        <div class="row g-2 mt-1">
            <div class="col-md-3">
                <label class="form-label mb-1">Mapping</label>
                <select class="form-select form-select-sm" data-field="mapping_override">
                    <option value="">— None —</option>
                    ${mappingOptions}
                </select>
            </div>
            <div class="col-md-9 d-flex align-items-end gap-2 justify-content-end">
                <button class="btn btn-sm btn-outline-secondary cancel-edit-btn">Cancel</button>
                <button class="btn btn-sm btn-primary save-edit-btn">Save</button>
            </div>
        </div>
    </div>`;

    const tr = document.querySelector(`#rows-tbody .edit-row-btn[data-row-id="${rowId}"]`)?.closest('tr');
    if (!tr) return;
    const editEl = document.createElement('tr');
    editEl.innerHTML = `<td colspan="12" class="p-0">${html}</td>`;
    tr.after(editEl);

    editEl.querySelector('.cancel-edit-btn').addEventListener('click', () => editEl.remove());
    editEl.querySelector('.save-edit-btn').addEventListener('click', () => _saveRowEdit(row.id, editEl));
}

async function _saveRowEdit(rowId, editEl) {
    const patch = {};
    editEl.querySelectorAll('[data-field]').forEach(el => {
        const field = el.dataset.field;
        if (field === 'label_override_raw') return;
        let value = el.value === '' ? null : el.value;
        if (field === 'efforts_ms_override' && value !== null) {
            value = String(Math.round(parseFloat(value) * 1000));
        }
        patch[field] = value;
    });
    const labelEl = editEl.querySelector('[data-field="label_override_raw"]');
    if (labelEl !== null) patch['label_override_raw'] = labelEl.value || null;

    try {
        const updated = await apiFetch(
            API_URLS.sprint_forecast.update_row(IMPORT_ID, rowId).href,
            { method: 'PATCH', body: JSON.stringify(patch) },
        );
        const idx = _currentRows.findIndex(r => r.id === rowId);
        if (idx >= 0) _currentRows[idx] = updated;
        editEl.remove();

        const fi = await apiFetch(API_URLS.sprint_forecast.detail(IMPORT_ID).href);
        _renderHeader(fi);
        _renderRows(_currentRows);
        _renderCapacityPivot(_currentRows);

        showFlash(fi.status === 'active' ? 'Row saved. Re-run review and confirm.' : 'Row saved.', 'success');
    } catch (e) {
        showFlash(e.data?.error || 'Save failed.', 'danger');
    }
}

async function _addRow() {
    const payload = {
        story_type: '', jira_id: '', title: '', assignee_raw: '',
        efforts_ms: 0, sprint_name: '', label_raw: '', mapping_raw: '',
        is_manually_added: true,
    };
    try {
        const row = await apiFetch(
            API_URLS.sprint_forecast.add_row(IMPORT_ID).href,
            { method: 'POST', body: JSON.stringify(payload) },
        );
        _currentRows.push(row);
        _renderRows(_currentRows);
        _renderCapacityPivot(_currentRows);
        showFlash('Row added.', 'success');
    } catch (e) {
        showFlash(e.data?.error || 'Failed to add row.', 'danger');
    }
}

// ── Review & Confirm ─────────────────────────────────────────────────────────

async function _runReview() {
    const btn = document.getElementById('review-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner-border spinner-border-sm me-1"></div>Reviewing…';
    try {
        const review = await apiFetch(
            API_URLS.sprint_forecast.review(IMPORT_ID).href,
            { method: 'POST', body: '{}' },
        );
        const errorCount = review.results.filter(r => r.status === 'error').length;
        showFlash(
            `Review complete: ${errorCount} error(s).`,
            errorCount > 0 ? 'warning' : 'success',
        );
        const [fi, rowsResp] = await Promise.all([
            apiFetch(API_URLS.sprint_forecast.detail(IMPORT_ID).href),
            apiFetch(API_URLS.sprint_forecast.rows(IMPORT_ID).href),
        ]);
        _currentRows = rowsResp.rows || [];
        _memberCapacities = rowsResp.member_capacities || {};
        _renderHeader(fi);
        _renderRows(_currentRows);
        _renderCapacityPivot(_currentRows);
    } catch (e) {
        showFlash(e.data?.error || 'Review failed.', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-cpu me-1"></i>Review';
    }
}

async function _confirmImport() {
    const btn = document.getElementById('confirm-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner-border spinner-border-sm me-1"></div>Confirming…';
    try {
        await apiFetch(
            API_URLS.sprint_forecast.confirm(IMPORT_ID).href,
            { method: 'POST', body: '{}' },
        );
        showFlash('Version confirmed.', 'success');
        const fi = await apiFetch(API_URLS.sprint_forecast.detail(IMPORT_ID).href);
        btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Confirm';
        _renderHeader(fi);
    } catch (e) {
        showFlash(e.data?.error || 'Confirm failed.', 'danger');
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Confirm';
    }
}

// ── Utilities ────────────────────────────────────────────────────────────────

function _esc(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
