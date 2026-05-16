'use strict';

import { apiFetch, showFlash, setPageTitle, escHtml } from './../main.js';

let _allCategories = [];
let _allPermissions = [];  // grouped by module
let _editingId = null;
let _categoryModal = null;
let _deleteModal = null;

document.addEventListener('DOMContentLoaded', () => {
    setPageTitle('Permission Categories');
    _categoryModal = new bootstrap.Modal(document.getElementById('categoryModal'));
    _deleteModal   = new bootstrap.Modal(document.getElementById('deleteCategoryModal'));

    loadCategories();
    loadPermissions();

    document.getElementById('new-category-btn').addEventListener('click', () => openModal(null));
    document.getElementById('category-save-btn').addEventListener('click', saveCategory);
    document.getElementById('category-search').addEventListener('input', () => {
        const q = document.getElementById('category-search').value.trim().toLowerCase();
        renderRows(_allCategories.filter(c =>
            c.name.toLowerCase().includes(q) ||
            (c.description || '').toLowerCase().includes(q)
        ));
    });
    document.getElementById('confirm-delete-cat-btn').addEventListener('click', confirmDelete);
});

async function loadCategories() {
    const tbody = document.getElementById('categories-tbody');
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary py-4">Loading…</td></tr>';
    try {
        _allCategories = await apiFetch('/api/v1/permission-categories/');
        renderRows(_allCategories);
    } catch (_) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger py-4">Failed to load. Please refresh.</td></tr>';
    }
}

async function loadPermissions() {
    try {
        _allPermissions = await apiFetch('/api/v1/permissions/');
    } catch (_) {
        document.getElementById('cat-perm-loading').textContent = 'Could not load permissions.';
        return;
    }
    renderPermAccordion([]);
}

const SCOPE_BADGE = {
    all:  { cls: 'rp-badge--muted',   icon: 'bi-globe',      label: 'All'  },
    team: { cls: 'rp-badge--info',    icon: 'bi-people',     label: 'Team' },
    self: { cls: 'rp-badge--warning', icon: 'bi-person',     label: 'Self' },
};

function renderRows(cats) {
    const tbody = document.getElementById('categories-tbody');
    if (!cats.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-4">No categories yet.</td></tr>';
        return;
    }
    tbody.innerHTML = cats.map(c => {
        const sb = SCOPE_BADGE[c.scope] || SCOPE_BADGE.all;
        return `
        <tr>
            <td class="text-secondary small">${escHtml(c.module_label || '—')}</td>
            <td class="fw-500">${escHtml(c.name)}</td>
            <td class="text-secondary small">${escHtml(c.description || '—')}</td>
            <td class="text-center">
                <span class="rp-badge ${sb.cls}" title="${escHtml(c.scope_label || c.scope)}">
                    <i class="bi ${sb.icon} me-1"></i>${sb.label}
                </span>
            </td>
            <td class="text-center">
                <span class="rp-badge rp-badge--muted">${c.permission_count}</span>
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <button class="btn btn-ghost-icon" title="Edit" onclick="openEditModal(${c.id})">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-ghost-icon text-danger" title="Delete"
                            onclick="showDeleteModal(${c.id}, '${escHtml(c.name)}')">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function renderPermAccordion(selectedIds) {
    const loadingEl  = document.getElementById('cat-perm-loading');
    const accordionEl = document.getElementById('cat-perm-accordion');
    if (loadingEl) loadingEl.classList.add('d-none');

    if (!_allPermissions.length) {
        accordionEl.innerHTML = '<p class="text-secondary small">No permissions configured.</p>';
        return;
    }

    const idSet = new Set(selectedIds);
    accordionEl.innerHTML = _allPermissions.map((mod, i) => {
        const checked = mod.permissions.filter(p => idSet.has(p.id)).length;
        return `
        <div class="accordion-item border-0 border-bottom">
            <h2 class="accordion-header" id="cp-head-${i}">
                <button class="accordion-button collapsed py-2 px-0 bg-transparent shadow-none fw-500"
                        type="button" data-bs-toggle="collapse"
                        data-bs-target="#cp-body-${i}">
                    ${escHtml(mod.label)}
                    <span class="ms-2 text-secondary small" id="cp-count-${i}">
                        (${checked} / ${mod.permissions.length})
                    </span>
                </button>
            </h2>
            <div id="cp-body-${i}" class="accordion-collapse collapse">
                <div class="accordion-body px-0 pb-2 pt-1">
                    ${mod.permissions.map(p => `
                        <div class="form-check mb-1">
                            <input class="form-check-input cp-perm-check"
                                   type="checkbox" value="${p.id}"
                                   id="cp-${p.id}"
                                   data-mod-idx="${i}"
                                   ${idSet.has(p.id) ? 'checked' : ''}
                                   onchange="updateCpCount(${i})">
                            <label class="form-check-label small" for="cp-${p.id}">
                                ${escHtml(p.name)}
                            </label>
                        </div>`).join('')}
                </div>
            </div>
        </div>`;
    }).join('');
}

window.updateCpCount = (idx) => {
    const mod = _allPermissions[idx];
    if (!mod) return;
    const n = document.querySelectorAll(`.cp-perm-check[data-mod-idx="${idx}"]:checked`).length;
    const el = document.getElementById(`cp-count-${idx}`);
    if (el) el.textContent = `(${n} / ${mod.permissions.length})`;
};

function openModal(cat) {
    _editingId = cat ? cat.id : null;
    document.getElementById('category-modal-title').textContent = cat ? 'Edit Category' : 'New Category';
    document.getElementById('cat-module').value      = cat ? (cat.module || '') : '';
    document.getElementById('cat-scope').value       = cat ? (cat.scope  || 'all') : 'all';
    document.getElementById('cat-name').value        = cat ? cat.name        : '';
    document.getElementById('cat-description').value = cat ? cat.description : '';
    document.getElementById('category-modal-error').classList.add('d-none');
    document.getElementById('cat-module').classList.remove('is-invalid');
    document.getElementById('cat-name').classList.remove('is-invalid');
    document.getElementById('cat-name-error').textContent = '';
    renderPermAccordion(cat ? cat.permission_ids : []);
    _categoryModal.show();
}

window.openEditModal = (id) => {
    const cat = _allCategories.find(c => c.id === id);
    if (cat) openModal(cat);
};

window.showDeleteModal = (id, name) => {
    _editingId = id;
    document.getElementById('delete-cat-name').textContent = name;
    _deleteModal.show();
};

function _getSelectedPermIds() {
    return [...document.querySelectorAll('.cp-perm-check:checked')].map(cb => Number(cb.value));
}

async function saveCategory() {
    const nameEl   = document.getElementById('cat-name');
    const errorEl  = document.getElementById('category-modal-error');
    const saveBtn  = document.getElementById('category-save-btn');
    const saveLabel = document.getElementById('category-save-label');

    errorEl.classList.add('d-none');
    nameEl.classList.remove('is-invalid');
    document.getElementById('cat-name-error').textContent = '';

    const moduleEl = document.getElementById('cat-module');
    moduleEl.classList.remove('is-invalid');

    const module = moduleEl.value;
    if (!module) {
        moduleEl.classList.add('is-invalid');
        return;
    }

    const name = nameEl.value.trim();
    if (!name) {
        nameEl.classList.add('is-invalid');
        document.getElementById('cat-name-error').textContent = 'Name is required.';
        return;
    }

    const payload = {
        module,
        scope: document.getElementById('cat-scope').value || 'all',
        name,
        description: document.getElementById('cat-description').value.trim(),
        permission_ids: _getSelectedPermIds(),
    };

    saveBtn.disabled = true;
    saveLabel.textContent = 'Saving…';

    try {
        if (_editingId) {
            const updated = await apiFetch(`/api/v1/permission-categories/${_editingId}/`, {
                method: 'PATCH',
                body: JSON.stringify(payload),
            });
            _allCategories = _allCategories.map(c => c.id === _editingId ? updated : c);
        } else {
            const created = await apiFetch('/api/v1/permission-categories/', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            _allCategories = [created, ..._allCategories];
        }
        _categoryModal.hide();
        renderRows(_allCategories);
        showFlash(_editingId ? 'Category updated.' : 'Category created.', 'success');
    } catch (err) {
        const msg = err?.data?.error || 'Save failed.';
        errorEl.textContent = msg;
        errorEl.classList.remove('d-none');
    } finally {
        saveBtn.disabled = false;
        saveLabel.textContent = 'Save';
    }
}

async function confirmDelete() {
    _deleteModal.hide();
    try {
        await apiFetch(`/api/v1/permission-categories/${_editingId}/`, { method: 'DELETE' });
        _allCategories = _allCategories.filter(c => c.id !== _editingId);
        renderRows(_allCategories);
        showFlash('Category deleted.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Could not delete category.', 'error');
    }
}
