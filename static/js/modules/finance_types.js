'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch, showFlash } from '../main.js';

let _financeTypes = [];
let _mappings = [];
let _editingId = null;

document.addEventListener('DOMContentLoaded', () => {
    _load();
    document.getElementById('add-finance-type-btn').addEventListener('click', _openAddModal);
    document.getElementById('ft-save-btn').addEventListener('click', _saveFinanceType);
    document.getElementById('add-mapping-btn').addEventListener('click', _openMappingModal);
    document.getElementById('map-save-btn').addEventListener('click', _saveMapping);
});

async function _load() {
    try {
        const [types, mappings] = await Promise.all([
            apiFetch(API_URLS.finance_types.list.href),
            apiFetch(API_URLS.finance_type_mappings.list.href),
        ]);
        _financeTypes = types || [];
        _mappings = mappings || [];
        _renderTypes();
        _renderMappings();
    } catch (e) {
        showFlash('Failed to load finance types.', 'danger');
    }
}

function _renderTypes() {
    const wrap = document.getElementById('ft-table-wrap');
    const empty = document.getElementById('ft-empty');
    document.getElementById('ft-loading').classList.add('d-none');
    if (!_financeTypes.length) {
        wrap.classList.add('d-none');
        empty.classList.remove('d-none');
        return;
    }
    empty.classList.add('d-none');
    wrap.classList.remove('d-none');
    document.getElementById('ft-tbody').innerHTML = _financeTypes.map(ft => `<tr>
        <td><code>${_esc(ft.code)}</code></td>
        <td>${_esc(ft.name)}</td>
        <td class="text-center">
            ${ft.is_active
                ? '<i class="bi bi-check-circle text-success"></i>'
                : '<i class="bi bi-x-circle text-secondary"></i>'}
        </td>
        <td>
            <button class="btn btn-ghost-icon btn-sm edit-ft-btn" data-id="${ft.id}" title="Edit">
                <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-ghost-icon btn-sm delete-ft-btn" data-id="${ft.id}" title="Delete">
                <i class="bi bi-trash text-danger"></i>
            </button>
        </td>
    </tr>`).join('');

    document.querySelectorAll('.edit-ft-btn').forEach(btn =>
        btn.addEventListener('click', () => _openEditModal(parseInt(btn.dataset.id))));
    document.querySelectorAll('.delete-ft-btn').forEach(btn =>
        btn.addEventListener('click', () => _deleteType(parseInt(btn.dataset.id))));
}

function _renderMappings() {
    const wrap = document.getElementById('map-table-wrap');
    const empty = document.getElementById('map-empty');
    document.getElementById('map-loading').classList.add('d-none');
    if (!_mappings.length) {
        wrap.classList.add('d-none');
        empty.classList.remove('d-none');
        return;
    }
    empty.classList.add('d-none');
    wrap.classList.remove('d-none');
    document.getElementById('map-tbody').innerHTML = _mappings.map(m => `<tr>
        <td>${_esc(m.project_type_name)}</td>
        <td><code>${_esc(m.finance_type_code)}</code> — ${_esc(m.finance_type_name)}</td>
        <td>
            <button class="btn btn-ghost-icon btn-sm delete-map-btn" data-id="${m.id}" title="Remove">
                <i class="bi bi-trash text-danger"></i>
            </button>
        </td>
    </tr>`).join('');
    document.querySelectorAll('.delete-map-btn').forEach(btn =>
        btn.addEventListener('click', () => _deleteMapping(parseInt(btn.dataset.id))));
}

function _openAddModal() {
    _editingId = null;
    document.getElementById('ft-modal-title').textContent = 'Add Finance Type';
    document.getElementById('ft-code').value = '';
    document.getElementById('ft-name').value = '';
    document.getElementById('ft-description').value = '';
    document.getElementById('ft-active').checked = true;
    document.getElementById('ft-error').classList.add('d-none');
    new bootstrap.Modal(document.getElementById('ftModal')).show();
}

function _openEditModal(id) {
    const ft = _financeTypes.find(f => f.id === id);
    if (!ft) return;
    _editingId = id;
    document.getElementById('ft-modal-title').textContent = 'Edit Finance Type';
    document.getElementById('ft-code').value = ft.code;
    document.getElementById('ft-name').value = ft.name;
    document.getElementById('ft-description').value = ft.description || '';
    document.getElementById('ft-active').checked = ft.is_active;
    document.getElementById('ft-error').classList.add('d-none');
    new bootstrap.Modal(document.getElementById('ftModal')).show();
}

async function _saveFinanceType() {
    const payload = {
        code: document.getElementById('ft-code').value.trim().toUpperCase(),
        name: document.getElementById('ft-name').value.trim(),
        description: document.getElementById('ft-description').value.trim(),
        is_active: document.getElementById('ft-active').checked,
    };
    if (!payload.code || !payload.name) {
        document.getElementById('ft-error').textContent = 'Code and Name are required.';
        document.getElementById('ft-error').classList.remove('d-none');
        return;
    }
    try {
        if (_editingId) {
            await apiFetch(API_URLS.finance_types.update(_editingId).href, { method: 'PATCH', body: JSON.stringify(payload) });
        } else {
            await apiFetch(API_URLS.finance_types.create.href, { method: 'POST', body: JSON.stringify(payload) });
        }
        bootstrap.Modal.getInstance(document.getElementById('ftModal'))?.hide();
        showFlash('Finance type saved.', 'success');
        await _load();
    } catch (e) {
        const err = typeof e === 'object' ? JSON.stringify(e) : String(e);
        document.getElementById('ft-error').textContent = err;
        document.getElementById('ft-error').classList.remove('d-none');
    }
}

async function _deleteType(id) {
    if (!confirm('Delete this finance type?')) return;
    try {
        await apiFetch(API_URLS.finance_types.delete(id).href, { method: 'DELETE' });
        showFlash('Finance type deleted.', 'success');
        await _load();
    } catch (e) {
        showFlash('Delete failed.', 'danger');
    }
}

async function _openMappingModal() {
    const ptSel = document.getElementById('map-project-type');
    const ftSel = document.getElementById('map-finance-type');
    ptSel.innerHTML = '<option value="">Loading…</option>';
    ftSel.innerHTML = _financeTypes.map(ft =>
        `<option value="${ft.id}">${_esc(ft.code)} — ${_esc(ft.name)}</option>`
    ).join('');
    document.getElementById('map-error').classList.add('d-none');

    try {
        const pts = await apiFetch(API_URLS.project_types.list.href);
        ptSel.innerHTML = (pts.results || pts || []).map(pt =>
            `<option value="${pt.id}">${_esc(pt.name)}</option>`
        ).join('');
    } catch (_) { ptSel.innerHTML = '<option value="">Failed to load</option>'; }

    new bootstrap.Modal(document.getElementById('mapModal')).show();
}

async function _saveMapping() {
    const ptId = document.getElementById('map-project-type').value;
    const ftId = document.getElementById('map-finance-type').value;
    if (!ptId || !ftId) {
        document.getElementById('map-error').textContent = 'Both fields are required.';
        document.getElementById('map-error').classList.remove('d-none');
        return;
    }
    try {
        await apiFetch(API_URLS.finance_type_mappings.create.href, { method: 'POST', body: JSON.stringify({ project_type: ptId, finance_type: ftId }) });
        bootstrap.Modal.getInstance(document.getElementById('mapModal'))?.hide();
        showFlash('Mapping added.', 'success');
        await _load();
    } catch (e) {
        const err = typeof e === 'object' ? JSON.stringify(e) : String(e);
        document.getElementById('map-error').textContent = err;
        document.getElementById('map-error').classList.remove('d-none');
    }
}

async function _deleteMapping(id) {
    if (!confirm('Remove this mapping?')) return;
    try {
        await apiFetch(API_URLS.finance_type_mappings.delete(id).href, { method: 'DELETE' });
        showFlash('Mapping removed.', 'success');
        await _load();
    } catch (e) {
        showFlash('Delete failed.', 'danger');
    }
}

function _esc(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
