'use strict';

import {
    apiFetch, showFlash, formatDateTime, setPageTitle, escHtml, escAttr,
    getPkFromUrl, isSubPathUrl, clearErrors, setSubmitting, extractFieldMessage,
    showBanner, applyErrors, hasPerm
} from './../main.js';
import { URLS, API_URLS } from './../urls.js';
import { initFetch } from './../list/fetch.js';
import { initSorting } from './../list/sort.js';
import { initRenderer } from './../list/render.js';
import { loadSpecs, initImportDropZone } from './../import.js';
import { exportToCsv, exportToPdf } from './../export.js';
import { initMembersPanel } from './../member_panel.js';
import { initLeavesPanel } from './../leave_panel.js';

let fetcher = null;

const typePk = getPkFromUrl('project-types');
const isEdit = isSubPathUrl('project-types', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const typesTable = document.getElementById('types-table');
    if (typesTable) {
        initListView();
        return;
    }

    const dropZone = document.getElementById('drop-zone');
    if (dropZone) {
        initImportView();
        return;
    }

    const detailRoot = document.getElementById('detail-root');
    if (detailRoot) {
        initDetailView();
        return;
    }

    const formEl = document.getElementById('type-form');
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
    setPageTitle("Project Types");
    renderStatistics();
    renderStatusFilterOptions();

    const renderer = initRenderer({
        tbodyId: 'types-tbody',
        colspan: 5,
        itemLabel: 'project types',
        rowTemplate: renderTypeRow,
        emptyState: {
            message: 'No project types yet.',
            link: {
                href: URLS.project_types.new,
                label: 'Create the first one',
            },
        },
        filterEmptyState: {
            message: 'No project types match your filters.',
            link: {
                href: URLS.project_types.new,
                label: 'Create a new project type',
            },
        },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: API_URLS.project_types.list.href,
        pageSize: 20,
        searchInputId: 'type-search',
        filters: [
            {
                id: 'status-filter',
                param: 'is_active',
            },
        ],
        onLoadStart: () => renderer.renderLoading('Loading project types...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load project types. Please refresh the page.'),
    });

    initSorting({
        tableId: 'types-table',
        fetcher,
    });

    fetcher.refresh();

    document.getElementById('export-csv').addEventListener('click', () => {
        runListExport('csv');
    });
    document.getElementById('export-pdf').addEventListener('click', () => {
        runListExport('pdf');
    });
}

async function renderStatistics() {
    try {
        const { method, href } = API_URLS.project_types.stats;
        const stats = await apiFetch(href, { method });

        document.getElementById('stat-total-types').textContent = stats.total_types ?? '-';
        document.getElementById('stat-assigned-types').textContent = stats.assigned_types ?? '-';
        document.getElementById('stat-unassigned-types').textContent = stats.unassigned_types ?? '-';
    } catch (err) {
        console.error('[renderStatistics] Failed to load statistics: ', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.project_types.options;
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
                <a href="${URLS.project_types.detail(type.id)}"
                   class="rp-link fw-500">
                    ${escHtml(type.name)}
                </a>
            </td>
            <td class="text-secondary"
                style="max-width: 260px;">
                <span class="rp-truncate">
                    ${escHtml(type.description ?? '')}
                </span>
            </td>
            <td class="text-center">
                ${type.is_active
                    ? '<span class="rp-badge rp-badge--success">Active</span>'
                    : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.project_types.detail(type.id)}"
                       class="btn btn-ghost-icon"
                       title="View project type">
                        <i class="bi bi-eye"></i>
                    </a>
                    ${hasPerm('project_types.change_projecttype') ? `
                    <a href="${URLS.project_types.edit(type.id)}"
                       class="btn btn-ghost-icon"
                       title="Edit project type">
                        <i class="bi bi-pencil"></i>
                    </a>` : ''}
                    ${hasPerm('project_types.delete_projecttype') ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete project type"
                            onclick="confirmDelete(${type.id}, '${escAttr(type.name)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, name) {
    showFlash(`Project type "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-type-id="${id}"]`)?.remove();
    fetcher?.refresh();
    renderStatistics();
}

/*
 * Import View
 */
function initImportView() {
    setPageTitle("Import");
    const importBtn        = document.getElementById('import-btn');
    const importResults    = document.getElementById('import-results');
    const importAnotherBtn = document.getElementById('import-another-btn');

    let importFile = null;

    loadSpecs(API_URLS.delivery_teams.import_spec.href);
    const dropZoneEl = document.getElementById('drop-zone');

    if (dropZoneEl) {
        const dropZoneApi = initImportDropZone(
            {
                dropZone:   dropZoneEl,
                fileInput:  document.getElementById('csv-file-input'),
                fileInfo:   document.getElementById('file-info'),
                fileNameEl: document.getElementById('file-name'),
                fileSizeEl: document.getElementById('file-size'),
                removeBtn:  document.getElementById('remove-file-btn'),
                submitBtn:  importBtn,
                errorEl:    document.getElementById('file-error'),
                errorMsgEl: document.getElementById('file-error-msg'),
            },
            {
                accept:  '.csv',
                onFile:  file => { importFile = file; },
                onReset: ()   => { importFile = null; },
            }
        );

        importBtn.addEventListener('click', () => {
            if (!importFile) return;

            submitImport(window.location.pathname, importFile, {
                submitBtn: importBtn,
                onSuccess: data => renderImportResults(data),
                onError:   msg  => dropZoneApi.showError(msg),
            });
        });
    }

    if (importAnotherBtn) {
        importAnotherBtn.addEventListener('click', () => {
            importResults.classList.add('d-none');
            document.getElementById('remove-file-btn')?.click();
        });
    }
}

/*
 * Create & Edit View
 */
function initCreateView() {
    setPageTitle("New Project Type");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'New Project Type';
    pageSubtitle.textContent = 'Add a new project type';
    submitLabel.textContent  = 'Create project type';
    submitBtn.dataset.originalLabel = 'Create project type';
}

async function initEditView() {
    setPageTitle("Edit Project Type");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'Edit Project Type';
    pageSubtitle.textContent = 'Loading…';
    submitLabel.textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    try {
        const { method, href } = API_URLS.project_types.get(typePk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        pageSubtitle.textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash(
                'This project type no longer exists. It may have been deleted. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.project_types.list; }, 3000);
            return;
        }

        showFlash(
            err?.data?.error || 'Could not load project type data. Please try again.',
            'danger',
        );
    }

    submitBtn.disabled = false;
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['name', 'description']);

    const nameInput = document.getElementById('id_name');
    if (!nameInput.value.trim()) {
        nameInput.classList.add('is-invalid');
        document.getElementById('name-error').textContent = 'Project type is required.';
        nameInput.focus();
        return;
    }

    const payload = {
        name:        nameInput.value.trim(),
        description: document.getElementById('id_description').value.trim(),
        is_active:   document.getElementById('id_is_active').checked,
    };

    const method = isEdit
        ? API_URLS.project_types.partial_edit(typePk).method
        : API_URLS.project_types.new.method;
    const url = isEdit
        ? API_URLS.project_types.partial_edit(typePk).href
        : API_URLS.project_types.new.href;

    setSubmitting(true);

    try {
        const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.project_types.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['name', 'description']);
            return;
        }
        if (err?.status === 404) {
            showFlash(
                'This project type no longer exists and cannot be saved. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.project_types.list; }, 3000);
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
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const metadataCard  = document.getElementById('metadata-card');
    const deleteBtnSlot = document.getElementById('delete-btn-slot');

    document.getElementById('id_name').value        = type.name        ?? '';
    document.getElementById('id_description').value = type.description ?? '';
    document.getElementById('id_is_active').checked = type.is_active   ?? true;

    pageTitle.textContent    = 'Edit Project Type';
    pageSubtitle.innerHTML   = `Updating <strong>${escHtml(type.name)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(type.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(type.updated_at);
    metadataCard.classList.remove('d-none');

    deleteBtnSlot.innerHTML = `
        <button type="button"
                class="btn btn-outline-danger"
                id="delete-type-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document.getElementById('delete-type-btn')
        .addEventListener('click', () =>
            confirmDelete(type.id, type.name, onDeleteFromEdit)
        );
}

function onDeleteFromEdit(id, name) {
    window.location.href = URLS.project_types.list;
}

/*
 * Detail View
 */
async function initDetailView() {
    if (!typePk) return;
    setPageTitle("Project Type");

    try {
        const { method, href } = API_URLS.project_types.detail(typePk);
        const data = await apiFetch(href, { method });
        renderDetailTitle(data);
        renderTypeDetails(data);
    } catch (err) {
        if (err?.status === 404) {
            showFlash(
                'This project type no longer exists. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.project_types.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load project type details. Please refresh.', 'danger');
    }
}

function renderDetailTitle(type) {
    document.getElementById('type-name').textContent = type.name;
    document.getElementById('type-status').textContent = type.is_active ? "Active" : "Inactive";
    document.getElementById('type-status').classList.add(
        type.is_active ? "rp-badge--success" : "rp-badge--muted"
    );
    document.getElementById('edit-type-btn').href = URLS.project_types.edit(typePk);
}

function renderTypeDetails(type) {
    document.getElementById('type-description').textContent = type.description ?? "-";
    document.getElementById('meta-created').textContent = formatDateTime(type.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(type.updated_at);
}

/*
 * Delete Modal - Shared
 */
function confirmDelete(id, name, onSuccess) {
    const modal     = document.getElementById('deleteModal');
    const nameEl    = document.getElementById('delete-type-name');
    const btn       = document.getElementById('confirm-delete-btn');

    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.project_types.delete(id);

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
                showFlash(
                    `Project type "${name}" was not found — it may have already been deleted.`,
                    'warning',
                );
                document.querySelector(`tr[data-type-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete project type "${name}". Please try again.`,
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
 * Export View
 */
const LIST_EXPORT_COLUMNS = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'description', label: 'Description' },
    { key: 'is_active', label: 'Active' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.project_types.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `project_types-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Project Types', filename);
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
window.confirmDelete = confirmDelete;
window.onDeleteFromList = onDeleteFromList;
window.onDeleteFromEdit = onDeleteFromEdit;