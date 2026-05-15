'use strict';

import {
    apiFetch, showFlash, formatDateTime, setPageTitle, escHtml,
    getPkFromUrl, isSubPathUrl, clearErrors, setSubmitting,
    showBanner, applyErrors, hasPerm
} from './../main.js';
import { URLS, API_URLS } from './../urls.js';
import { initFetch } from './../list/fetch.js';
import { initSorting } from './../list/sort.js';
import { initRenderer } from './../list/render.js';
import { loadSpecs, initImportDropZone } from './../import.js';
import { exportToCsv, exportToPdf } from './../export.js';

let fetcher = null;

const holidayPk = getPkFromUrl('holidays');
const isEdit    = isSubPathUrl('holidays', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const tableEl = document.getElementById('holidays-table');
    if (tableEl) {
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

    const formEl = document.getElementById('holiday-form');
    if (formEl) {
        formEl.addEventListener('submit', handleCreateEditSubmit);
        if (isEdit) {
            initEditView();
        } else {
            initCreateView();
        }
    }
});

/* =========================================================
 * List View
 * ========================================================= */
function initListView() {
    setPageTitle('Holidays');
    renderStatistics();
    renderLocationFilterOptions();
    renderYearFilterOptions();

    const renderer = initRenderer({
        tbodyId:     'holidays-tbody',
        colspan:     5,
        itemLabel:   'holidays',
        rowTemplate: renderHolidayRow,
        emptyState: {
            message: 'No holidays yet.',
            link:    { href: URLS.holidays.new, label: 'Add the first one' },
        },
        filterEmptyState: {
            message: 'No holidays match your filters.',
            link:    { href: URLS.holidays.new, label: 'Add a new holiday' },
        },
        paginationBarId:      'pagination-bar',
        paginationInfoId:     'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl:        API_URLS.holidays.list.href,
        pageSize:      20,
        searchInputId: 'holiday-search',
        filters: [
            { id: 'location-filter', param: 'location_id' },
            { id: 'year-filter', param: 'year' },
        ],
        onLoadStart: () => renderer.renderLoading('Loading holidays...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load holidays. Please refresh the page.'),
    });

    initSorting({ tableId: 'holidays-table', fetcher });
    fetcher.refresh();

    document.getElementById('export-csv').addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf').addEventListener('click', () => runListExport('pdf'));
}

async function renderStatistics() {
    try {
        const { method, href } = API_URLS.holidays.stats;
        const stats = await apiFetch(href, { method });
        document.getElementById('stat-total-holidays').textContent    = stats.total_holidays    ?? '—';
        document.getElementById('stat-upcoming-holidays').textContent = stats.upcoming_holidays ?? '—';
        document.getElementById('stat-total-locations').textContent   = stats.total_locations   ?? '—';
    } catch (err) {
        console.error('[renderStatistics]', err);
    }
}

async function renderLocationFilterOptions() {
    try {
        const { method, href } = API_URLS.holidays.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('location-filter');
        (options?.locations ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderLocationFilterOptions]', err);
    }
}

async function renderYearFilterOptions() {
    try {
        const { method, href } = API_URLS.holidays.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('year-filter');
        (options?.years ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderYearFilterOptions]', err);
    }
}

function renderHolidayRow(holiday) {
    const locDisplay = holiday.location
        ? escHtml(`${holiday.location.city}, ${holiday.location.country}`)
        : '—';

    return `
        <tr data-holiday-id="${holiday.id}">
            <td>
                <span class="rp-code">${escHtml(holiday.date)}</span>
            </td>
            <td>
                <a href="/holidays/${holiday.id}/" class="rp-link fw-500">
                    ${escHtml(holiday.name)}
                </a>
            </td>
            <td>${locDisplay}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.holidays.detail(holiday.id)}"
                       class="btn btn-ghost-icon"
                       title="View holiday">
                        <i class="bi bi-eye"></i>
                    </a>
                    ${hasPerm('public_holidays.change_publicholiday') ? `
                    <a href="${URLS.holidays.edit(holiday.id)}"
                       class="btn btn-ghost-icon"
                       title="Edit holiday">
                        <i class="bi bi-pencil"></i>
                    </a>` : ''}
                    ${hasPerm('public_holidays.delete_publicholiday') ? `
                    <button type="button"
                            class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete holiday"
                            onclick="confirmDelete(${holiday.id}, '${escHtml(holiday.name)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, name) {
    showFlash(`Holiday "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-holiday-id="${id}"]`)?.remove();
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

    loadSpecs(API_URLS.holidays.import_spec.href);
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

/* =========================================================
 * Detail View
 * ========================================================= */
async function initDetailView() {
    if (!holidayPk) return;
    setPageTitle("Holiday");

    try {
        const { method, href } = API_URLS.holidays.detail(holidayPk);
        const holiday = await apiFetch(href, { method });
        renderDetailTitle(holiday);
        renderHolidayDetails(holiday);
    } catch (err) {
        if (err?.status === 404) {
            showFlash(
                'This holiday no longer exists. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.holidays.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load holiday details. Please refresh.', 'danger');
    }
}

function renderDetailTitle(holiday) {
    document.getElementById('holiday-name').textContent = holiday.name;
        document.getElementById('holiday-location-date').textContent =
            `${holiday.location?.city ?? ''}, ${holiday.location?.country ?? ''} · ${holiday.date}`;
    document.getElementById('edit-holiday-btn').href = URLS.holidays.edit(holidayPk);
}

function renderHolidayDetails(holiday) {
    document.getElementById('detail-name').textContent     = holiday.name;
        document.getElementById('detail-date').textContent     = holiday.date;
        document.getElementById('detail-location').textContent =
            holiday.location
                ? `${holiday.location.city}, ${holiday.location.country}`
                : '—';
        document.getElementById('meta-created').textContent = formatDateTime(holiday.created_at);
        document.getElementById('meta-updated').textContent = formatDateTime(holiday.updated_at);
}

/* =========================================================
 * Create View
 * ========================================================= */
async function initCreateView() {
    setPageTitle("New Holiday");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'New Holiday';
    pageSubtitle.textContent = 'Add a public holiday for an office location';
    submitLabel.textContent  = 'Create holiday';
    submitBtn.dataset.originalLabel = 'Create holiday';
    await _populateLocationSelect();
}

/* =========================================================
 * Edit View
 * ========================================================= */
async function initEditView() {
    setPageTitle('Edit Holiday');
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'Edit Holiday';
    pageSubtitle.textContent = 'Loading…';
    submitLabel.textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    await _populateLocationSelect();

    try {
        const { method, href } = API_URLS.holidays.detail(holidayPk);
        const holiday = await apiFetch(href, { method });
        populateForm(holiday);
        submitBtn.disable = false;
    } catch (err) {
        pageSubtitle.textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash(
                'This holiday no longer exists. It may have been deleted. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.holidays.list; }, 3000);
            return;
        }

        showFlash(
            err?.data?.error || 'Could not load holiday data. Please try again.',
            'danger',
        );
    }

    submitBtn.disabled = false;
}

function populateForm(holiday) {
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const metadataCard  = document.getElementById('metadata-card');
    const deleteBtnSlot = document.getElementById('delete-btn-slot');

    document.getElementById('id_location').value = holiday.location?.id ?? '';
    document.getElementById('id_date').value     = holiday.date;
    document.getElementById('id_name').value     = holiday.name;

    pageTitle.textContent    = 'Edit Holiday';
    pageSubtitle.innerHTML   = `Updating <strong>${escHtml(holiday.name)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(holiday.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(holiday.updated_at);
    metadataCard.classList.remove('d-none');

    deleteBtnSlot.innerHTML = `
        <button type="button"
                class="btn btn-outline-danger"
                id="delete-team-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document.getElementById('delete-team-btn')
        .addEventListener('click', () =>
            confirmDelete(holiday.id, holiday.name, onDeleteFromEdit)
        );
}

/* =========================================================
 * Form Submit
 * ========================================================= */
async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['location', 'date', 'name']);

    const locationInput = document.getElementById('id_location');
    if (!locationInput.value.trim()) {
        locationInput.classList.add('is-invalid');
        document.getElementById('location-error').textContent = 'Location is required.';
        locationInput.focus();
        return;
    }

    const dateInput = document.getElementById('id_date');
    if (!dateInput.value.trim()) {
        dateInput.classList.add('is-invalid');
        document.getElementById('date-error').textContent = 'Date is required.';
        dateInput.focus();
        return;
    }

    const nameInput = document.getElementById('id_name');
    if (!nameInput.value.trim()) {
        nameInput.classList.add('is-invalid');
        document.getElementById('name-error').textContent = 'Team name is required.';
        nameInput.focus();
        return;
    }

    const payload = {
        location: document.getElementById('id_location').value,
        date:     document.getElementById('id_date').value,
        name:     document.getElementById('id_name').value.trim(),
    };

    const method = isEdit
        ? API_URLS.holidays.partial_edit(holidayPk).method
        : API_URLS.holidays.new.method;
    const url = isEdit
        ? API_URLS.holidays.partial_edit(holidayPk).href
        : API_URLS.holidays.new.href;

    setSubmitting(true);

    try {
        const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.holidays.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['location', 'date', 'name']);
            return;
        }
        if (err?.status === 404) {
            showFlash(
                'This holiday no longer exists and cannot be saved. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.holidays.list; }, 3000);
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

function onDeleteFromEdit(id, name) {
    window.location.href = URLS.holidays.list;
}

/* =========================================================
 * Helpers
 * ========================================================= */
async function _populateLocationSelect() {
    try {
        const { method, href } = API_URLS.holidays.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('id_location');
        if (!select) return;
        (options?.locations ?? []).forEach(({ value, label, is_default }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            if (is_default && !isEdit) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[_populateLocationSelect]', err);
    }
}

/* =========================================================
 * Delete Modal — shared across all views
 * ========================================================= */
function confirmDelete(id, name, onSuccess) {
    const modal  = document.getElementById('deleteModal');
    const nameEl = document.getElementById('delete-holiday-name');
    const btn    = document.getElementById('confirm-delete-btn');
    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);

    const { method, href } = API_URLS.holidays.delete(id);

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
                showFlash(`"${name}" was not found — it may have already been deleted.`, 'warning');
                if (fetcher) {
                    document.querySelector(`tr[data-holiday-id="${id}"]`)?.remove();
                    fetcher.refresh();
                    renderStatistics();
                }
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete "${name}". Please try again.`,
                'danger'
            );
        } finally {
            newBtn.disabled    = false;
            newBtn.textContent = 'Delete';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

/* =========================================================
 * Export
 * ========================================================= */
const LIST_EXPORT_COLUMNS = [
    { key: 'id',       label: 'ID' },
    { key: 'location', label: 'Location' },
    { key: 'date',     label: 'Date' },
    { key: 'name',     label: 'Holiday Name' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();
    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }
    try {
        const { method, href } = API_URLS.holidays.export;
        const res  = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, `holidays-${date}`);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Holidays', `holidays-${date}`);
        }
    } catch (_err) {
        showFlash('Export failed. Please try again.', 'danger');
    } finally {
        if (btn) {
            btn.disabled  = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i>Export';
        }
    }
}

/* =========================================================
 * Window Exports (called from inline onclick handlers)
 * ========================================================= */
window.confirmDelete     = confirmDelete;
window.onDeleteFromList = onDeleteFromList;
window.onDeleteFromEdit = onDeleteFromEdit;