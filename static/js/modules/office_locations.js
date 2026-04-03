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

let fetcher = null;

const locationPk = getPkFromUrl('locations');
const isEdit = isSubPathUrl('locations', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const locationsTable = document.getElementById('locations-table');
    if (locationsTable) {
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

    const formEl = document.getElementById('location-form');
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
    setPageTitle("Locations");
    renderStatistics();
    renderStatusFilterOptions();

    const renderer = initRenderer({
        tbodyId: 'locations-tbody',
        colspan: 5,
        itemLabel: 'locations',
        rowTemplate: renderLocationRow,
        emptyState: {
            message: 'No locations yet.',
            link: {
                href: URLS.locations.new,
                label: 'Create the first one',
            },
        },
        filterEmptyState: {
            message: 'No locations match your filters.',
            link: {
                href: URLS.locations.new,
                label: 'Create a new location',
            },
        },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: API_URLS.locations.list.href,
        pageSize: 20,
        searchInputId: 'location-search',
        filters: [
            {
                id: 'status-filter',
                param: 'is_active',
            },
        ],
        onLoadStart: () => renderer.renderLoading('Loading locations...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load locations. Please refresh the page.'),
    });

    initSorting({
        tableId: 'locations-table',
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
        const { method, href } = API_URLS.locations.stats;
        const stats = await apiFetch(href, { method });

        document.getElementById('stat-total-locations').textContent = stats.total_locations ?? '-';
        document.getElementById('stat-active-locations').textContent = stats.active_locations ?? '-';
        document.getElementById('stat-inactive-locations').textContent = stats.inactive_locations ?? '-';
    } catch (err) {
        console.error('[renderStatistics] Failed to load statistics: ', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.locations.options;
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

function renderLocationRow(location) {
    return `
        <tr data-location-id="${location.id}">
            <td>
                <a href="${URLS.locations.detail(location.id)}"
                   class="rp-link fw-500">
                    ${escHtml(location.city)}
                </a>
                ${location.is_default
                    ? '<span class="rp-badge rp-badge--info">Default</span>'
                    : ''
                }
            </td>
            <td class="text-secondary">
                ${escHtml(location.country)}
            </td>
            <td class="text-center">
                ${location.is_active
                    ? '<span class="rp-badge rp-badge--success">Active</span>'
                    : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.locations.detail(location.id)}"
                       class="btn btn-ghost-icon"
                       title="View location">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.locations.edit(location.id)}"
                       class="btn btn-ghost-icon"
                       title="Edit location">
                        <i class="bi bi-pencil"></i>
                    </a>
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete location"
                            onclick="confirmDelete(${location.id}, '${escAttr(location.city)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, name) {
    showFlash(`Location "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-location-id="${id}"]`)?.remove();
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
    setPageTitle("New Location");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'New Location';
    pageSubtitle.textContent = 'Add a new location';
    submitLabel.textContent  = 'Create location';
    submitBtn.dataset.originalLabel = 'Create location';
}

async function initEditView() {
    setPageTitle("Edit Location");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'Edit Location';
    pageSubtitle.textContent = 'Loading…';
    submitLabel.textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    try {
        const { method, href } = API_URLS.locations.get(locationPk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        pageSubtitle.textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash(
                'This location no longer exists. It may have been deleted. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.locations.list; }, 3000);
            return;
        }

        showFlash(
            err?.data?.error || 'Could not load location data. Please try again.',
            'danger',
        );
    }

    submitBtn.disabled = false;
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['city', 'country']);

    const cityInput = document.getElementById('id_city');
    if (!cityInput.value.trim()) {
        cityInput.classList.add('is-invalid');
        document.getElementById('city-error').textContent = 'City is required.';
        cityInput.focus();
        return;
    }

    const countryInput = document.getElementById('id_country');
    if (!countryInput.value.trim()) {
        countryInput.classList.add('is-invalid');
        document.getElementById('country-error').textContent = 'Country is required.';
        countryInput.focus();
        return;
    }

    const payload = {
        city:       cityInput.value.trim(),
        country:    countryInput.value.trim(),
        is_active:   document.getElementById('id_is_active').checked,
        is_default:    document.getElementById('id_is_default').checked,
    };

    const method = isEdit
        ? API_URLS.locations.partial_edit(locationPk).method
        : API_URLS.locations.new.method;
    const url = isEdit
        ? API_URLS.locations.partial_edit(locationPk).href
        : API_URLS.locations.new.href;

    setSubmitting(true);

    try {
        const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.locations.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['city', 'country']);
            return;
        }
        if (err?.status === 404) {
            showFlash(
                'This location no longer exists and cannot be saved. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.locations.list; }, 3000);
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

function populateForm(location) {
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const metadataCard  = document.getElementById('metadata-card');
    const deleteBtnSlot = document.getElementById('delete-btn-slot');

    document.getElementById('id_city').value        = location.city        ?? '';
    document.getElementById('id_country').value = location.country ?? '';
    document.getElementById('id_is_active').checked = location.is_active   ?? true;
    document.getElementById('id_is_default').checked   = location.is_default   ?? false;

    pageTitle.textContent    = 'Edit Location';
    pageSubtitle.innerHTML   = `Updating <strong>${escHtml(location.city)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(location.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(location.updated_at);
    metadataCard.classList.remove('d-none');

    deleteBtnSlot.innerHTML = `
        <button type="button"
                class="btn btn-outline-danger"
                id="delete-location-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document.getElementById('delete-location-btn')
        .addEventListener('click', () =>
            confirmDelete(location.id, location.city, onDeleteFromEdit)
        );
}

function onDeleteFromEdit(id, name) {
    window.location.href = URLS.locations.list;
}

/*
 * Detail View
 */
async function initDetailView() {
    if (!locationPk) return;
    setPageTitle("Location");

    try {
        const { method, href } = API_URLS.locations.detail(locationPk);
        const data = await apiFetch(href, { method });
        renderDetailTitle(data);
        renderLocationDetails(data);
    } catch (err) {
        if (err?.status === 404) {
            showFlash(
                'This location no longer exists. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.locations.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load location details. Please refresh.', 'danger');
    }
}

function renderDetailTitle(location) {
    document.getElementById('location-city').textContent = location.city;
    document.getElementById('location-status').textContent = location.is_active ? "Active" : "Inactive";
    document.getElementById('location-status').classList.add(
        location.is_active ? "rp-badge--success" : "rp-badge--muted"
    );
    document.getElementById('edit-location-btn').href = URLS.locations.edit(locationPk);
}

function renderLocationDetails(location) {
    document.getElementById('location-country').textContent = location.country ?? "-";
    document.getElementById('location-is-default').textContent   = location.is_default   ? 'Yes' : 'No';
    document.getElementById('meta-created').textContent = formatDateTime(location.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(location.updated_at);
}

/*
 * Delete Modal - Shared
 */
function confirmDelete(id, name, onSuccess) {
    const modal     = document.getElementById('deleteModal');
    const nameEl    = document.getElementById('delete-location');
    const btn       = document.getElementById('confirm-delete-btn');

    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.locations.delete(id);

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
                    `Location "${name}" was not found — it may have already been deleted.`,
                    'warning',
                );
                document.querySelector(`tr[data-location-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete location "${name}". Please try again.`,
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
    { key: 'city', label: 'City' },
    { key: 'country', label: 'Country' },
    { key: 'is_active', label: 'Active' },
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
        const { method, href } = API_URLS.locations.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `locations-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Locations', filename);
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