'use strict';

import { initFetch } from './../list/fetch.js';
import { initRenderer } from './../list/render.js';
import { initSorting } from './../list/sort.js';
import { apiFetch, escAttr, escHtml, formatDateTime, setPageTitle, showFlash, hasPerm } from './../main.js';
import { API_URLS, URLS } from './../urls.js';
import { exportToCsv, exportToPdf } from '../export.js';

// ── Constants ────────────────────────────────────────────────────────────────

const LIST_EXPORT_COLUMNS = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'Email' },
    { key: 'is_active', label: 'Active' },
];

// ── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('contact-tbody')) return;
    initListView();
});

// ── Init ─────────────────────────────────────────────────────────────────────

async function initListView() {
    setPageTitle('Contacts');
    _mountViewModal();
    await loadStats();
    renderStatusFilterOptions();
    bindToolbarEvents();
    bindModalEvents();
    initTable();
}

function _mountViewModal() {
    const modal = document.getElementById('contactViewModal');
    const parent = document.querySelector('.rp-main');
    if (!modal || !parent) return;

    parent.appendChild(modal);
    _setViewModalOffset(modal);

    window.addEventListener('resize', () => _setViewModalOffset(modal), { passive: true });
}

function _setViewModalOffset(modal) {
    const header = document.querySelector('.rp-page-header');
    const offset = header ? (header.offsetTop + header.offsetHeight) : 0;
    modal.style.top = `${offset}px`;
    modal.style.height = `calc(100% - ${offset}px)`;
}

// ── Stats ─────────────────────────────────────────────────────────────────────

async function loadStats() {
    try {
        const { method, href } = API_URLS.contacts.stats;
        const data = await apiFetch(href, { method });
        document.getElementById('stat-total').textContent = data.total_contacts ?? '—';
        document.getElementById('stat-active').textContent = data.active_contacts ?? '—';
        document.getElementById('stat-inactive').textContent = data.inactive_contacts ?? '—';
    } catch (err) {
        console.error('[loadStats] Failed to load stats.', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.contacts.options;
        const options = await apiFetch(href, { method });
        const statuses = options?.is_active ?? [];

        const select = document.getElementById('status-filter');
        statuses.forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions] Failed to load status filter options.', err);
    }
}

// ── Toolbar ───────────────────────────────────────────────────────────────────

function bindToolbarEvents() {
    document.getElementById('add-contact-btn')?.addEventListener('click', () => openAddModal());
    document.getElementById('export-csv')?.addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf')?.addEventListener('click', () => runListExport('pdf'));
}

// ── Table / Fetcher ───────────────────────────────────────────────────────────

function initTable() {
    const { method, href } = API_URLS.contacts.list;

    const renderer = initRenderer({
        tbodyId: 'contact-tbody',
        colspan: 4,
        itemLabel: 'contacts',
        rowTemplate: renderContactRow,
        emptyState: {
            message: 'No contacts yet.',
            link: { href: '#', label: 'Add the first one', onClick: 'openAddModal()' },
        },
        filterEmptyState: {
            message: 'No contacts match your filters.',
            link: { href: '#', label: 'Create a new one', onClick: 'openAddModal()' },
        },
        paginationBarId: 'contact-pagination-bar',
        paginationInfoId: 'contact-pagination-info',
        paginationControlsId: 'contact-pagination-controls',
        onPageChange: (page) => fetcher.goToPage(page),
    });

    const fetcher = initFetch({
        apiUrl: href,
        pageSize: 20,
        searchInputId: 'contact-search',
        filters: [{ id: 'status-filter', param: 'is_active' }],
        onLoadStart: () => renderer.renderLoading('Loading contacts…'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.values(state.filters).some((v) => v !== '');
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load contacts. Please refresh the page.'),
    });

    initSorting({ tableId: 'contact-table', fetcher });
    fetcher.refresh();

    window._contactFetcher = fetcher;
}

// ── Row template ──────────────────────────────────────────────────────────────

function renderContactRow(contact) {
    const activeBtnTitle = contact.is_active ? 'Deactivate contact' : 'Activate contact';
    const activeBtnClass = contact.is_active ? 'btn-ghost-icon--danger' : 'btn-ghost-icon--success';

    return `
        <tr data-contact-id="${contact.id}">
            <td class="fw-medium">
                <a href="#" class="rp-link fw-500" onclick="openViewModal(${contact.id}); return false;">
                    ${escHtml(contact.name)}
                </a>
            </td>
            <td>
                <a href="mailto:${escAttr(contact.email)}" class="rp-link">
                    ${escHtml(contact.email)}
                </a>
            </td>
            <td class="text-center">
                ${
                    contact.is_active
                        ? '<span class="rp-badge rp-badge--success">Active</span>'
                        : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <button class="btn btn-ghost-icon" title="View contact"
                            onclick="openViewModal(${contact.id})">
                        <i class="bi bi-eye"></i>
                    </button>
                    ${hasPerm('contacts.change_contact') ? `
                    <button class="btn btn-ghost-icon" title="Edit contact"
                            onclick="openEditModal(${contact.id}, '${escAttr(contact.name)}', '${escAttr(contact.email)}')">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-ghost-icon ${activeBtnClass}" title="${activeBtnTitle}"
                            onclick="openActiveModal(${contact.id}, '${escAttr(contact.name)}', ${contact.is_active})">
                        <i class="bi bi-check-circle"></i>
                    </button>` : ''}
                    ${hasPerm('contacts.delete_contact') ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger" title="Delete contact"
                            onclick="openDeleteModal(${contact.id}, '${escAttr(contact.name)}')">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

// ── Modals — Add / Edit ────────────────────────────────────────────────────────

function bindModalEvents() {
    document.getElementById('contactModal')?.addEventListener('hidden.bs.modal', resetAddEditModal);
    document.getElementById('contact-modal-save')?.addEventListener('click', handleModalSave);
    document.getElementById('confirm-active-btn')?.addEventListener('click', handleConfirmActive);
    document.getElementById('confirm-delete-btn')?.addEventListener('click', handleConfirmDelete);
}

async function openViewModal(id) {
    const modal = document.getElementById('contactViewModal');
    if (modal) {
        _setViewModalOffset(modal);

        modal.style.setProperty('padding', '3px', 'important');
        const content = modal.querySelector('.modal-content');
        if (content) content.style.borderRadius = '15px';

        const top = modal.offsetTop;
        window.scrollTo({ top, behavior: 'smooth' });
    }

    _renderViewLoading();
    _showModal('contactViewModal');

    try {
        const { method, href } = API_URLS.contacts.detail(id);
        const contact = await apiFetch(href, { method });
        _renderViewContent(contact);
    } catch (err) {
        _renderViewError('Failed to load contact details. Please try again.');
        console.error('[openViewModal] Failed to fetch contact.', err);
    }
}

function _renderViewLoading() {
    document.getElementById('contact-view-body').innerHTML = `
        <div class="d-flex align-items-center justify-content-center py-5 text-secondary">
            <div class="spinner-border spinner-border-sm me-2" role="status"></div>
            Loading…
        </div>`;
    document.getElementById('contact-view-title').textContent = 'Contact';
    document.getElementById('contact-view-edit-btn').classList.add('d-none');
    document.getElementById('contact-view-delete-btn').classList.add('d-none');
}

function _renderViewError(message) {
    document.getElementById('contact-view-body').innerHTML = `
        <div class="d-flex align-items-center justify-content-center py-5 text-danger">
            <i class="bi bi-exclamation-circle me-2"></i>${escHtml(message)}
        </div>`;
}

function _renderViewContent(contact) {
    const editBtn = document.getElementById('contact-view-edit-btn');
    if (hasPerm('contacts.change_contact')) {
        editBtn.classList.remove('d-none');
    } else {
        editBtn.classList.add('d-none');
    }
    editBtn.onclick = () => {
        _hideModal('contactViewModal');
        openEditModal(contact.id, contact.name, contact.email);
    };

    const deleteBtn = document.getElementById('contact-view-delete-btn');
    if (hasPerm('contacts.delete_contact')) {
        deleteBtn.classList.remove('d-none');
    } else {
        deleteBtn.classList.add('d-none');
    }
    deleteBtn.onclick = () => {
        _hideModal('contactViewModal');
        openDeleteModal(contact.id, contact.name);
    };

    const createdAt = contact.created_at ? formatDateTime(contact.created_at) : '—';
    const updatedAt = contact.updated_at ? formatDateTime(contact.updated_at) : '—';

    const statusBadge = contact.is_active
        ? '<span class="rp-badge rp-badge--success">Active</span>'
        : '<span class="rp-badge rp-badge--muted">Inactive</span>';

    document.getElementById('contact-view-title').innerHTML = `
        <i class="bi bi-person-lines-fill me-2 opacity-50"></i>
        <span>${contact.name}</span>
    `;

    document.getElementById('contact-view-body').innerHTML = `
        <div class="row g-4 rp-view-layout">
            <div class="col-lg-8 rp-view-main">
                <div class="rp-view-section">
                    <h6 class="rp-view-section-title">Details</h6>

                    <div class="rp-view-field">
                        <span class="rp-view-label">Name</span>
                        <span class="rp-view-value">${escHtml(contact.name)}</span>
                    </div>

                    <div class="rp-view-field">
                        <span class="rp-view-label">Email</span>
                        <span class="rp-view-value">
                            <a href="mailto:${escAttr(contact.email)}" class="rp-link">
                                ${escHtml(contact.email)}
                            </a>
                        </span>
                    </div>

                    <div class="rp-view-field">
                        <span class="rp-view-label">Status</span>
                        <span class="rp-view-value">${statusBadge}</span>
                    </div>
                </div>
            </div>
            <aside class="col-lg-4 rp-view-meta">
                <div class="rp-view-section">
                    <h6 class="rp-view-section-title">
                        <i class="bi bi-clock-history me-2"></i>Metadata
                    </h6>

                    <div class="rp-view-field">
                        <span class="rp-view-label">Created</span>
                        <span class="rp-view-value">${createdAt}</span>
                    </div>

                    <div class="rp-view-field">
                        <span class="rp-view-label">Last updated</span>
                        <span class="rp-view-value">${updatedAt}</span>
                    </div>
                </div>
            </aside>
        </div>`;
}

function openAddModal() {
    resetAddEditModal();
    document.getElementById('contact-modal-title').textContent = 'Add Contact';
    document.getElementById('contact-modal-save').dataset.mode = 'add';
    delete document.getElementById('contact-modal-save').dataset.id;
    _showModal('contactModal');
    setTimeout(() => document.getElementById('contact-modal-name').focus(), 300);
}

function openEditModal(id, name, email) {
    resetAddEditModal();
    document.getElementById('contact-modal-title').textContent = 'Edit Contact';
    document.getElementById('contact-modal-name').value = name;
    document.getElementById('contact-modal-email').value = email;
    document.getElementById('contact-modal-save').dataset.mode = 'edit';
    document.getElementById('contact-modal-save').dataset.id = id;
    _showModal('contactModal');
    setTimeout(() => document.getElementById('contact-modal-name').focus(), 300);
}

function resetAddEditModal() {
    document.getElementById('contact-modal-name').value = '';
    document.getElementById('contact-modal-email').value = '';
    clearAddEditModalErrors();
}

function clearAddEditModalErrors() {
    document.getElementById('contact-modal-banner').classList.add('d-none');
    ['contact-modal-name', 'contact-modal-email'].forEach((id) => {
        document.getElementById(id)?.classList.remove('is-invalid');
        const errEl = document.getElementById(`${id}-error`);
        if (errEl) errEl.textContent = '';
    });
}

function setFieldError(fieldId, message) {
    document.getElementById(fieldId)?.classList.add('is-invalid');
    const errEl = document.getElementById(`${fieldId}-error`);
    if (errEl) errEl.textContent = message;
}

function showAddEditBanner(message) {
    const el = document.getElementById('contact-modal-banner');
    el.textContent = message;
    el.classList.remove('d-none');
}

function _isValidEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

async function handleModalSave() {
    const saveBtn = document.getElementById('contact-modal-save');
    const mode = saveBtn.dataset.mode;
    const id = saveBtn.dataset.id;
    const name = document.getElementById('contact-modal-name').value.trim();
    const email = document.getElementById('contact-modal-email').value.trim();

    clearAddEditModalErrors();

    let hasError = false;
    if (!name) {
        setFieldError('contact-modal-name', 'Name is required.');
        hasError = true;
    }
    if (!email) {
        setFieldError('contact-modal-email', 'Email is required.');
        hasError = true;
    } else if (!_isValidEmail(email)) {
        setFieldError('contact-modal-email', 'Please enter a valid email address.');
        hasError = true;
    }
    if (hasError) return;

    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        if (mode === 'add') {
            const { method, href } = API_URLS.contacts.new;
            await apiFetch(href, {
                method,
                body: JSON.stringify({ name, email }),
            });
            showFlash(`${name} added successfully.`, 'success');
        } else {
            const { method, href } = API_URLS.contacts.partial_edit(id);
            await apiFetch(href, {
                method,
                body: JSON.stringify({ name, email }),
            });
            showFlash(`${name} updated successfully.`, 'success');
        }

        _hideModal('contactModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to save contact. Please try again.');
        showAddEditBanner(msg);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

// ── Modals — Activate / Deactivate ────────────────────────────────────────────

function openActiveModal(id, name, isActive) {
    const titleEl = document.getElementById('contact-active-modal-title');
    const messageEl = document.getElementById('contact-active-message');
    const confirmBtn = document.getElementById('confirm-active-btn');

    const action = isActive ? 'deactivated' : 'activated';
    titleEl.textContent = isActive ? 'Deactivate Contact' : 'Activate Contact';
    confirmBtn.textContent = isActive ? 'Deactivate' : 'Activate';
    confirmBtn.className = isActive ? 'btn btn-sm btn-danger' : 'btn btn-sm btn-success';
    confirmBtn.dataset.id = id;
    confirmBtn.dataset.isActive = isActive;

    messageEl.innerHTML = `<strong>${escHtml(name)}</strong> will be ${action}. Do you want to proceed?`;

    document.getElementById('contact-active-modal-banner').classList.add('d-none');
    _showModal('contactActiveModal');
}

async function handleConfirmActive() {
    const btn = document.getElementById('confirm-active-btn');
    const id = btn.dataset.id;
    const isActive = btn.dataset.isActive === 'true';

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        const { method, href } = API_URLS.contacts.partial_edit(id);
        await apiFetch(href, {
            method,
            body: JSON.stringify({ is_active: !isActive }),
        });
        showFlash(`Contact ${isActive ? 'deactivated' : 'activated'}.`, 'success');
        _hideModal('contactActiveModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to update contact. Please try again.');
        document.getElementById('contact-active-modal-banner').textContent = msg;
        document.getElementById('contact-active-modal-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

// ── Modals — Delete ───────────────────────────────────────────────────────────

function openDeleteModal(id, name) {
    document.getElementById('contact-delete-name').textContent = name;
    document.getElementById('confirm-delete-btn').dataset.id = id;
    document.getElementById('confirm-delete-btn').dataset.name = name;
    document.getElementById('contact-delete-modal-banner').classList.add('d-none');
    _showModal('contactDeleteModal');
}

async function handleConfirmDelete() {
    const btn = document.getElementById('confirm-delete-btn');
    const id = btn.dataset.id;
    const name = btn.dataset.name;

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        const { method, href } = API_URLS.contacts.delete(id);
        await apiFetch(href, { method });
        showFlash(`"${name}" deleted.`, 'success');
        _hideModal('contactDeleteModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to delete contact. Please try again.');
        document.getElementById('contact-delete-modal-banner').textContent = msg;
        document.getElementById('contact-delete-modal-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

// ── Export ────────────────────────────────────────────────────────────────────

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled = true;
        btn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.contacts.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `contacts-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Contacts', filename);
        }
    } catch (err) {
        showFlash('Export failed. Please try again.', 'error');
        console.error('[runListExport] Export failed.', err);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i>Export';
        }
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _showModal(id) {
    bootstrap.Modal.getOrCreateInstance(
        document.getElementById(id),
        { focus: false }
    ).show();
}

function _hideModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).hide();
}

function _refreshTable() {
    window._contactFetcher?.refresh();
}

function _extractError(err, fallback) {
    if (err?.data?.details) {
        const details = err.data.details;
        if (typeof details === 'string') return details;
        if (Array.isArray(details)) return details.join(' ');
        if (typeof details === 'object') return Object.values(details).flat().join(' ');
    }
    if (err?.data?.error) return err.data.error;
    return fallback;
}

// ── Window exports (required for inline onclick= attributes) ──────────────────
window.openViewModal = openViewModal;
window.openAddModal = openAddModal;
window.openEditModal = openEditModal;
window.openActiveModal = openActiveModal;
window.openDeleteModal = openDeleteModal;
