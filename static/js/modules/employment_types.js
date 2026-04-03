'use strict';

import {
    apiFetch, showFlash, formatDateTime, setPageTitle, escHtml, escAttr,
    getPkFromUrl, isSubPathUrl, clearErrors, setSubmitting,
    showBanner, applyErrors
} from './../main.js';
import { URLS, API_URLS } from './../urls.js';
import { initFetch } from './../list/fetch.js';
import { initSorting } from './../list/sort.js';
import { initRenderer } from './../list/render.js';
import { exportToCsv, exportToPdf } from './../export.js';

let fetcher = null;

const typePk = getPkFromUrl('employment-types');
const isEdit = isSubPathUrl('employment-types', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const typesTable = document.getElementById('employment-types-table');
    if (typesTable) {
        initListView();
        return;
    }

    const detailRoot = document.getElementById('detail-root');
    if (detailRoot) {
        initDetailView();
        return;
    }

    const formEl = document.getElementById('employment-type-form');
    if (formEl) {
        formEl.addEventListener('submit', handleCreateEditSubmit);
        if (isEdit) {
            initEditView();
        } else {
            initCreateView();
        }
    }
});

/*
 * List View
 */
function initListView() {
    setPageTitle("Employment Types");
    renderStatistics();
    renderStatusFilterOptions();

    const renderer = initRenderer({
        tbodyId: 'employment-types-tbody',
        colspan: 3,
        itemLabel: 'employment types',
        rowTemplate: renderTypeRow,
        emptyState: {
            message: 'No employment types yet.',
            link: { href: URLS.employment_types.new, label: 'Create the first one' },
        },
        filterEmptyState: {
            message: 'No employment types match your filters.',
            link: { href: URLS.employment_types.new, label: 'Create a new type' },
        },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: API_URLS.employment_types.list.href,
        pageSize: 20,
        searchInputId: 'type-search',
        filters: [
            { id: 'status-filter', param: 'is_active' },
        ],
        onLoadStart: () => renderer.renderLoading('Loading employment types...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load employment types. Please refresh the page.'),
    });

    initSorting({ tableId: 'employment-types-table', fetcher });
    fetcher.refresh();

    document.getElementById('export-csv').addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf').addEventListener('click', () => runListExport('pdf'));
}

async function renderStatistics() {
    try {
        const { method, href } = API_URLS.employment_types.stats;
        const stats = await apiFetch(href, { method });
        document.getElementById('stat-total-types').textContent    = stats.total_types    ?? '-';
        document.getElementById('stat-active-types').textContent   = stats.active_types   ?? '-';
        document.getElementById('stat-inactive-types').textContent = stats.inactive_types ?? '-';
    } catch (err) {
        console.error('[renderStatistics] Failed to load statistics: ', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.employment_types.options;
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
        console.error('[renderStatusFilterOptions] Failed to load status filter options: ', err);
    }
}

function renderTypeRow(type) {
    return `
        <tr data-type-id="${type.id}">
            <td>
                <a href="${URLS.employment_types.detail(type.id)}" class="rp-link">
                    ${escHtml(type.name)}
                </a>
                ${type.is_default
                    ? '<span class="rp-badge rp-badge--info ms-1">Default</span>'
                    : ''
                }
            </td>
            <td class="text-center">
                ${type.is_active
                    ? '<span class="rp-badge rp-badge--success">Active</span>'
                    : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.employment_types.detail(type.id)}"
                       class="btn btn-ghost-icon"
                       title="View type">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.employment_types.edit(type.id)}"
                       class="btn btn-ghost-icon"
                       title="Edit type">
                        <i class="bi bi-pencil"></i>
                    </a>
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete type"
                            onclick="confirmDelete(${type.id}, '${escAttr(type.name)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, name) {
    showFlash(`Employment type "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-type-id="${id}"]`)?.remove();
    fetcher?.refresh();
    renderStatistics();
}

/*
 * Create & Edit View
 */
function initCreateView() {
    setPageTitle("New Employment Type");
    document.getElementById('page-title').textContent    = 'New Employment Type';
    document.getElementById('page-subtitle').textContent = 'Add a new employment type to the configuration';
    document.getElementById('submit-label').textContent  = 'Create type';
    document.getElementById('submit-btn').dataset.originalLabel = 'Create type';
}

async function initEditView() {
    setPageTitle("Edit Employment Type");
    const submitBtn = document.getElementById('submit-btn');
    document.getElementById('page-title').textContent    = 'Edit Employment Type';
    document.getElementById('page-subtitle').textContent = 'Loading…';
    document.getElementById('submit-label').textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    try {
        const { method, href } = API_URLS.employment_types.get(typePk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        document.getElementById('page-subtitle').textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash('This employment type no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.employment_types.list; }, 3000);
            return;
        }
        showFlash(err.data?.error || 'Could not load employment type data. Please try again.', 'danger');
    }

    submitBtn.disabled = false;
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['name']);

    const nameInput = document.getElementById('id_name');
    if (!nameInput.value.trim()) {
        nameInput.classList.add('is-invalid');
        document.getElementById('name-error').textContent = 'Name is required.';
        nameInput.focus();
        return;
    }

    const payload = {
        name:       nameInput.value.trim(),
        is_active:  document.getElementById('id_is_active').checked,
        is_default: document.getElementById('id_is_default').checked,
    };

    const method = isEdit
        ? API_URLS.employment_types.partial_edit(typePk).method
        : API_URLS.employment_types.new.method;
    const url = isEdit
        ? API_URLS.employment_types.partial_edit(typePk).href
        : API_URLS.employment_types.new.href;

    setSubmitting(true);

    try {
        await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.employment_types.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['name']);
            return;
        }
        if (err?.status === 404) {
            showFlash('This employment type no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.employment_types.list; }, 3000);
            return;
        }
        if (err?.status === 503 || err?.status === 500) {
            showFlash(err.data?.error || `Unexpected error (${err.status}). Please try again.`, 'danger');
            return;
        }
        showFlash('Could not reach the server. Check your connection and try again.', 'danger');
    } finally {
        setSubmitting(false);
    }
}

function populateForm(type) {
    document.getElementById('id_name').value         = type.name       ?? '';
    document.getElementById('id_is_active').checked  = type.is_active  ?? true;
    document.getElementById('id_is_default').checked = type.is_default ?? false;

    document.getElementById('page-title').textContent   = 'Edit Employment Type';
    document.getElementById('page-subtitle').innerHTML  = `Updating <strong>${escHtml(type.name)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(type.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(type.updated_at);
    document.getElementById('metadata-card').classList.remove('d-none');

    document.getElementById('delete-btn-slot').innerHTML = `
        <button type="button" class="btn btn-outline-danger" id="delete-type-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document.getElementById('delete-type-btn')
        .addEventListener('click', () => confirmDelete(type.id, type.name, onDeleteFromEdit));
}

function onDeleteFromEdit() {
    window.location.href = URLS.employment_types.list;
}

/*
 * Detail View
 */
async function initDetailView() {
    if (!typePk) return;
    setPageTitle("Employment Type");

    try {
        const { method, href } = API_URLS.employment_types.detail(typePk);
        const data = await apiFetch(href, { method });
        renderDetailTitle(data);
        renderTypeDetails(data);
    } catch (err) {
        if (err?.status === 404) {
            showFlash('This employment type no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.employment_types.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load employment type details. Please refresh.', 'danger');
    }
}

function renderDetailTitle(type) {
    document.getElementById('type-name').textContent = type.name;
    document.getElementById('type-status').textContent = type.is_active ? 'Active' : 'Inactive';
    document.getElementById('type-status').classList.add(
        type.is_active ? 'rp-badge--success' : 'rp-badge--muted'
    );
    if (type.is_default) {
        document.getElementById('type-default-badge').classList.remove('d-none');
    }
    document.getElementById('edit-type-btn').href = URLS.employment_types.edit(typePk);
}

function renderTypeDetails(type) {
    document.getElementById('type-name-detail').textContent = type.name       ?? '-';
    document.getElementById('type-is-default').textContent  = type.is_default ? 'Yes' : 'No';
    document.getElementById('meta-created').textContent     = formatDateTime(type.created_at);
    document.getElementById('meta-updated').textContent     = formatDateTime(type.updated_at);
}

/*
 * Delete Modal - Shared
 */
function confirmDelete(id, name, onSuccess) {
    const modal  = document.getElementById('deleteModal');
    const nameEl = document.getElementById('delete-type-name');
    const btn    = document.getElementById('confirm-delete-btn');

    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.employment_types.delete(id);

    newBtn.addEventListener('click', async () => {
        try {
            newBtn.disabled    = true;
            newBtn.textContent = 'Deleting...';
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            onSuccess(id, name);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            if (err?.status === 404) {
                showFlash(`Employment type "${name}" was not found — it may have already been deleted.`, 'warning');
                document.querySelector(`tr[data-type-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete employment type "${name}". Please try again.`,
                'error'
            );
        } finally {
            newBtn.disabled    = false;
            newBtn.textContent = 'Delete';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

/*
 * Export
 */
const LIST_EXPORT_COLUMNS = [
    { key: 'id',         label: 'ID' },
    { key: 'name',       label: 'Name' },
    { key: 'is_active',  label: 'Active' },
    { key: 'is_default', label: 'Default' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.employment_types.export;
        const res  = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `employment-types-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Employment Types', filename);
        }
    } catch (_err) {
        showFlash('Export failed. Please try again.', 'error');
    } finally {
        if (btn) {
            btn.disabled  = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i>Export';
        }
    }
}

/*
 * Window Exports
 */
window.confirmDelete    = confirmDelete;
window.onDeleteFromList = onDeleteFromList;
window.onDeleteFromEdit = onDeleteFromEdit;
