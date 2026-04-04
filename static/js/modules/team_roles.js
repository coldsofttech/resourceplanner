'use strict';

import {
    apiFetch, showFlash, formatDateTime, setPageTitle, escHtml, escAttr,
    getPkFromUrl, isSubPathUrl, clearErrors, setSubmitting, extractFieldMessage,
    showBanner, applyErrors
} from './../main.js';
import { URLS, API_URLS } from './../urls.js';
import { initFetch } from './../list/fetch.js';
import { initSorting } from './../list/sort.js';
import { initRenderer } from './../list/render.js';
import { loadSpecs, initImportDropZone } from './../import.js';
import { exportToCsv, exportToPdf } from './../export.js';
import { initMembersPanel } from './../member_panel.js';

let fetcher = null;

const rolePk = getPkFromUrl('roles');
const isEdit = isSubPathUrl('roles', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const rolesTable = document.getElementById('roles-table');
    if (rolesTable) {
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

    const formEl = document.getElementById('role-form');
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
    setPageTitle("Roles");
    renderStatistics();
    renderStatusFilterOptions();
    renderAssignableFilterOptions();

    const renderer = initRenderer({
        tbodyId: 'roles-tbody',
        colspan: 4,
        itemLabel: 'roles',
        rowTemplate: renderRoleRow,
        emptyState: {
            message: 'No roles yet.',
            link: {
                href: URLS.roles.new,
                label: 'Create the first one',
            },
        },
        filterEmptyState: {
            message: 'No roles match your filters.',
            link: {
                href: URLS.roles.new,
                label: 'Create a new role',
            },
        },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: API_URLS.roles.list.href,
        pageSize: 20,
        searchInputId: 'role-search',
        filters: [
            {
                id: 'status-filter',
                param: 'is_active',
            },
            {
                id: 'assignable-filter',
                param: 'is_assignable'
            },
        ],
        onLoadStart: () => renderer.renderLoading('Loading roles...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load roles. Please refresh the page.'),
    });

    initSorting({
        tableId: 'roles-table',
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
        const { method, href } = API_URLS.roles.stats;
        const stats = await apiFetch(href, { method });

        document.getElementById('stat-total-roles').textContent = stats.total_roles ?? '-';
        document.getElementById('stat-active-roles').textContent = stats.active_roles ?? '-';
        document.getElementById('stat-inactive-roles').textContent = stats.inactive_roles ?? '-';
        document.getElementById('stat-unassigned-roles').textContent = stats.unassigned_roles ?? '-';
    } catch (err) {
        console.error('[renderStatistics] Failed to load statistics: ', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.roles.options;
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

async function renderAssignableFilterOptions() {
    try {
        const { method, href } = API_URLS.roles.options;
        const options = await apiFetch(href, { method });
        const statuses = options?.is_assignable ?? [];

        const select = document.getElementById('assignable-filter');
        statuses.forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderAssignableFilterOptions] Failed to load assignable filter options: ', err);
    }
}

function renderRoleRow(role) {
    return `
        <tr data-role-id="${role.id}">
            <td>
                <a href="${URLS.roles.detail(role.id)}"
                   class="rp-link">
                   ${escHtml(role.role)}
                </a>
                ${role.is_default
                    ? '<span class="rp-badge rp-badge--info">Default</span>'
                    : ''
                }
            </td>
            <td class="text-center">
                ${role.is_active
                    ? '<span class="rp-badge rp-badge--success">Active</span>'
                    : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                ${role.is_assignable
                    ? '<span class="rp-badge rp-badge--info">Assignable</span>'
                    : ''
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.roles.detail(role.id)}"
                       class="btn btn-ghost-icon"
                       title="View role">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.roles.edit(role.id)}"
                       class="btn btn-ghost-icon"
                       title="Edit role">
                        <i class="bi bi-pencil"></i>
                    </a>
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete role"
                            onclick="confirmDelete(${role.id}, '${escAttr(role.role)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, name) {
    showFlash(`Role "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-role-id="${id}"]`)?.remove();
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

    loadSpecs(API_URLS.roles.import_spec.href);
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
    setPageTitle("New Role");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'New Role';
    pageSubtitle.textContent = 'Add a new role to the configuration';
    submitLabel.textContent  = 'Create role';
    submitBtn.dataset.originalLabel = 'Create role';
}

async function initEditView() {
    setPageTitle("Edit Role");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'Edit Role';
    pageSubtitle.textContent = 'Loading…';
    submitLabel.textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    try {
        const { method, href } = API_URLS.roles.get(rolePk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        pageSubtitle.textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash(
                'This role no longer exists. It may have been deleted. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.roles.list; }, 3000);
            return;
        }

        showFlash(
            err.data?.error || 'Could not load role data. Please try again.',
            'danger'
        );
    }

    submitBtn.disabled = false;
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['role']);

    const roleInput = document.getElementById('id_role');
    if (!roleInput.value.trim()) {
        roleInput.classList.add('is-invalid');
        document.getElementById('role-error').textContent = 'Role name is required.';
        roleInput.focus();
        return;
    }

    const payload = {
        role:      roleInput.value.trim(),
        is_active: document.getElementById('id_is_active').checked,
        is_default:    document.getElementById('id_is_default').checked,
        is_assignable: document.getElementById('id_is_assignable').checked,
    };

    const method = isEdit
        ? API_URLS.roles.partial_edit(rolePk).method
        : API_URLS.roles.new.method;
    const url = isEdit
        ? API_URLS.roles.partial_edit(rolePk).href
        : API_URLS.roles.new.href;

    setSubmitting(true);

    try {
        const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.roles.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['role']);
            return;
        }
        if (err?.status === 404) {
            showFlash(
                'This role no longer exists and cannot be saved. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.roles.list; }, 3000);
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

function populateForm(role) {
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const metadataCard  = document.getElementById('metadata-card');
    const deleteBtnSlot = document.getElementById('delete-btn-slot');

    document.getElementById('id_role').value       = role.role      ?? '';
    document.getElementById('id_is_active').checked = role.is_active ?? true;
    document.getElementById('id_is_default').checked   = role.is_default   ?? false;
    document.getElementById('id_is_assignable').checked = role.is_assignable ?? false;

    pageTitle.textContent    = 'Edit Role';
    pageSubtitle.innerHTML   = `Updating <strong>${escHtml(role.role)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(role.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(role.updated_at);
    metadataCard.classList.remove('d-none');

    deleteBtnSlot.innerHTML = `
        <button type="button"
                class="btn btn-outline-danger"
                id="delete-role-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document.getElementById('delete-role-btn')
        .addEventListener('click', () =>
            confirmDelete(role.id, role.role, onDeleteFromEdit)
        );
}

function onDeleteFromEdit(id, name) {
    window.location.href = URLS.roles.list;
}

/*
 * Detail View
 */
async function initDetailView() {
    if (!rolePk) return;
    setPageTitle("Role");

    try {
        const { method, href } = API_URLS.roles.detail(rolePk);
        const data = await apiFetch(href, { method });
        renderDetailTitle(data);
        renderRoleDetails(data);
    } catch (err) {
        if (err?.status === 404) {
            showFlash(
                'This role no longer exists. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.roles.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load role details. Please refresh.', 'danger');
    }

    initMembersPanel({
        containerSelector:      '#members-panel',
        tbodyId:                'members-tbody',
        paginationBarId:        'members-pagination-bar',
        paginationInfoId:       'members-pagination-info',
        paginationControlsId:   'members-pagination-controls',
        includeInactiveToggleId: 'include-inactive-toggle',
        filterParam:            'role_id',
        filterValue:            rolePk,
        columns:                'other',
        newMemberHref:          URLS.team_members.new,
    });
}

function renderDetailTitle(role) {
    document.getElementById('role-name').textContent = role.role;
    document.getElementById('role-status').textContent = role.is_active ? "Active" : "Inactive";
    document.getElementById('role-status').classList.add(
        role.is_active ? "rp-badge--success" : "rp-badge--muted"
    );
    document.getElementById('edit-role-btn').href = URLS.roles.edit(rolePk);
}

function renderRoleDetails(role) {
    document.getElementById('role-name-detail').textContent = role.role ?? '-';
    document.getElementById('role-is-default').textContent   = role.is_default   ? 'Yes' : 'No';
    document.getElementById('role-is-assignable').textContent = role.is_assignable ? 'Yes' : 'No';
    document.getElementById('total_members').textContent = role.total_members ?? 0;
    document.getElementById('active_members').textContent = role.active_members ?? 0;
    document.getElementById('inactive_members').textContent = role.inactive_members ?? 0;
    document.getElementById('meta-created').textContent = formatDateTime(role.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(role.updated_at);
}

/*
 * Delete Modal - Shared
 */
function confirmDelete(id, name, onSuccess) {
    const modal  = document.getElementById('deleteModal');
    const nameEl = document.getElementById('delete-role-name');
    const btn    = document.getElementById('confirm-delete-btn');

    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.roles.delete(id);

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
                    `Role "${name}" was not found — it may have already been deleted.`,
                    'warning',
                );
                document.querySelector(`tr[data-role-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete role "${name}". Please try again.`,
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
    { key: 'role', label: 'Role' },
    { key: 'is_active', label: 'Active' },
    { key: 'is_default', label: 'Default' },
    { key: 'is_assignable', label: 'Assignable' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.roles.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `roles-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Roles', filename);
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
