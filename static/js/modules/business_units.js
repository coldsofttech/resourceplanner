'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch, showFlash, escHtml } from '../main.js';

const API = API_URLS.business_units;

let _state = { search: '', isActive: '', page: 1, pageSize: 20 };
let _editingId = null;
let _isStaff = false;

document.addEventListener('DOMContentLoaded', () => {
    _isStaff = !!document.getElementById('new-bu-btn');
    _loadStats();
    _loadList();

    document.getElementById('bu-search').addEventListener('input', _debounce(() => {
        _state.search = document.getElementById('bu-search').value.trim();
        _state.page = 1;
        _loadList();
    }, 300));

    document.getElementById('bu-status-filter').addEventListener('change', () => {
        _state.isActive = document.getElementById('bu-status-filter').value;
        _state.page = 1;
        _loadList();
    });

    document.getElementById('new-bu-btn')?.addEventListener('click', _openCreateModal);
    document.getElementById('bu-save-btn').addEventListener('click', _save);
    document.getElementById('bu-delete-btn').addEventListener('click', _openDeleteConfirm);
    document.getElementById('bu-confirm-delete-btn').addEventListener('click', _confirmDelete);
});

async function _loadStats() {
    try {
        const stats = await apiFetch(API.stats.href, { method: API.stats.method });
        document.getElementById('stat-total').textContent   = stats.total   ?? 0;
        document.getElementById('stat-active').textContent  = stats.active  ?? 0;
        document.getElementById('stat-inactive').textContent = stats.inactive ?? 0;
    } catch (_) {}
}

async function _loadList() {
    const tbody = document.getElementById('bu-tbody');
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-secondary py-4">
        <div class="spinner-border spinner-border-sm me-2"></div>Loading…</td></tr>`;

    const params = new URLSearchParams({ page: _state.page, page_size: _state.pageSize });
    if (_state.search) params.set('search', _state.search);
    if (_state.isActive !== '') params.set('is_active', _state.isActive);

    try {
        const data = await apiFetch(`${API.list.href}?${params}`, { method: API.list.method });
        _renderRows(data.results ?? []);
        _renderPagination(data.pagination ?? {});
    } catch (_) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger py-4">
            Failed to load business units. Please refresh.</td></tr>`;
    }
}

function _renderRows(items) {
    const tbody = document.getElementById('bu-tbody');
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-secondary py-4">
            No business units found.</td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(bu => `
        <tr>
            <td>${escHtml(bu.full_name)}</td>
            <td><code>${escHtml(bu.short_name)}</code></td>
            <td class="text-center">
                ${bu.is_active
                    ? '<span class="rp-badge rp-badge--success">Active</span>'
                    : '<span class="rp-badge rp-badge--muted">Inactive</span>'}
            </td>
            <td class="text-center">
                ${_isStaff ? `
                <button class="btn btn-ghost-icon" title="Edit" onclick="_buEdit(${bu.id})">
                    <i class="bi bi-pencil"></i>
                </button>` : ''}
            </td>
        </tr>`).join('');
}

function _renderPagination(pg) {
    const bar = document.getElementById('bu-pagination');
    if (!pg || pg.total_pages <= 1) {
        bar.style.display = 'none';
        return;
    }
    bar.style.display = '';
    const info = `<span class="text-secondary small">Page ${pg.current_page} of ${pg.total_pages} &mdash; ${pg.total_count} total</span>`;
    const prev = `<button class="btn btn-sm btn-outline-secondary" ${!pg.has_previous ? 'disabled' : ''} onclick="_buPage(${pg.current_page - 1})">
        <i class="bi bi-chevron-left"></i></button>`;
    const next = `<button class="btn btn-sm btn-outline-secondary" ${!pg.has_next ? 'disabled' : ''} onclick="_buPage(${pg.current_page + 1})">
        <i class="bi bi-chevron-right"></i></button>`;
    bar.innerHTML = `${info}<div class="d-flex gap-1">${prev}${next}</div>`;
}

window._buPage = (page) => { _state.page = page; _loadList(); };

window._buEdit = async (id) => {
    try {
        const bu = await apiFetch(API.detail(id).href, { method: API.detail(id).method });
        _editingId = id;
        document.getElementById('bu-modal-title').textContent = 'Edit Business Unit';
        document.getElementById('bu-full-name').value   = bu.full_name  ?? '';
        document.getElementById('bu-short-name').value  = bu.short_name ?? '';
        document.getElementById('bu-is-active').checked = bu.is_active  ?? true;
        _clearFieldErrors();
        document.getElementById('bu-delete-btn').classList.remove('d-none');
        bootstrap.Modal.getOrCreateInstance(document.getElementById('buModal')).show();
    } catch (_) {
        showFlash('Could not load business unit. Please try again.', 'danger');
    }
};

function _openCreateModal() {
    _editingId = null;
    document.getElementById('bu-modal-title').textContent = 'New Business Unit';
    document.getElementById('bu-full-name').value   = '';
    document.getElementById('bu-short-name').value  = '';
    document.getElementById('bu-is-active').checked = true;
    _clearFieldErrors();
    document.getElementById('bu-delete-btn').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('buModal')).show();
}

async function _save() {
    _clearFieldErrors();
    const fullName  = document.getElementById('bu-full-name').value.trim();
    const shortName = document.getElementById('bu-short-name').value.trim();
    let valid = true;

    if (!fullName) {
        _showFieldError('bu-full-name', 'bu-full-name-error', 'Full name is required.');
        valid = false;
    }
    if (!shortName) {
        _showFieldError('bu-short-name', 'bu-short-name-error', 'Short name is required.');
        valid = false;
    }
    if (!valid) return;

    const payload = { full_name: fullName, short_name: shortName, is_active: document.getElementById('bu-is-active').checked };
    const saveBtn = document.getElementById('bu-save-btn');
    saveBtn.disabled = true;

    try {
        if (_editingId) {
            const { method, href } = API.update(_editingId);
            await apiFetch(href, { method, body: JSON.stringify(payload) });
            showFlash('Business unit updated.', 'success');
        } else {
            await apiFetch(API.create.href, { method: API.create.method, body: JSON.stringify(payload) });
            showFlash('Business unit created.', 'success');
        }
        bootstrap.Modal.getInstance(document.getElementById('buModal'))?.hide();
        _loadStats();
        _loadList();
    } catch (err) {
        if (err?.status === 400 && err?.data?.details) {
            const d = err.data.details;
            if (d.full_name)  _showFieldError('bu-full-name',  'bu-full-name-error',  d.full_name[0]);
            if (d.short_name) _showFieldError('bu-short-name', 'bu-short-name-error', d.short_name[0]);
        } else {
            showFlash(err?.data?.error || 'Could not save business unit. Please try again.', 'danger');
        }
    } finally {
        saveBtn.disabled = false;
    }
}

function _openDeleteConfirm() {
    const name = document.getElementById('bu-full-name').value.trim() || 'this business unit';
    document.getElementById('bu-delete-name').textContent = name;
    bootstrap.Modal.getInstance(document.getElementById('buModal'))?.hide();
    bootstrap.Modal.getOrCreateInstance(document.getElementById('buDeleteModal')).show();
}

async function _confirmDelete() {
    if (!_editingId) return;
    const btn = document.getElementById('bu-confirm-delete-btn');
    btn.disabled = true;
    try {
        const { method, href } = API.delete(_editingId);
        await apiFetch(href, { method });
        bootstrap.Modal.getInstance(document.getElementById('buDeleteModal'))?.hide();
        showFlash('Business unit deleted.', 'success');
        _editingId = null;
        _loadStats();
        _loadList();
    } catch (err) {
        bootstrap.Modal.getInstance(document.getElementById('buDeleteModal'))?.hide();
        if (err?.status === 404) {
            showFlash('Business unit not found — it may have already been deleted.', 'warning');
        } else {
            showFlash(err?.data?.error || 'Delete failed. Please try again.', 'danger');
        }
    } finally {
        btn.disabled = false;
    }
}

function _clearFieldErrors() {
    ['bu-full-name', 'bu-short-name'].forEach(id => {
        document.getElementById(id)?.classList.remove('is-invalid');
    });
    ['bu-full-name-error', 'bu-short-name-error'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.textContent = ''; el.classList.add('d-none'); }
    });
}

function _showFieldError(inputId, errorId, msg) {
    document.getElementById(inputId)?.classList.add('is-invalid');
    const err = document.getElementById(errorId);
    if (err) { err.textContent = msg; err.classList.remove('d-none'); }
}

function _debounce(fn, ms) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}
