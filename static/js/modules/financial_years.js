'use strict';

import {
    apiFetch, showFlash, formatDate, formatDateTime, setPageTitle,
    escHtml, escAttr, getPkFromUrl, isSubPathUrl,
    clearErrors, setSubmitting, applyErrors, showBanner, hasPerm,
} from './../main.js';
import { URLS, API_URLS } from './../urls.js';
import { initFetch } from './../list/fetch.js';
import { initSorting } from './../list/sort.js';
import { initRenderer } from './../list/render.js';
import { exportToCsv, exportToPdf } from './../export.js';

let fetcher = null;

const fyPk   = getPkFromUrl('fy');
const isEdit = isSubPathUrl('fy', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const fyTable = document.getElementById('fy-table');
    if (fyTable) {
        initListView();
        return;
    }

    const detailRoot = document.getElementById('detail-root');
    if (detailRoot) {
        initDetailView();
        return;
    }

    const formEl = document.getElementById('fy-form');
    if (formEl) {
        formEl.addEventListener('submit', handleCreateEditSubmit);
        if (isEdit) {
            initEditView();
        } else {
            initCreateView();
        }
    }
});

// ─────────────────────────────────────────────
// List View
// ─────────────────────────────────────────────
function initListView() {
    setPageTitle('Financial Years');
    loadWarningThreshold().then(threshold => {
        // Store on table so renderFyRow can read it synchronously
        const tbl = document.getElementById('fy-table');
        if (tbl) tbl.dataset.warningDays = threshold;
    });
    renderStatistics();
    renderStatusFilterOptions();

    const renderer = initRenderer({
        tbodyId:   'fy-tbody',
        colspan:   7,
        itemLabel: 'financial years',
        rowTemplate: renderFyRow,
        emptyState: {
            message: 'No financial years yet.',
            link: { href: URLS.financial_years.new, label: 'Create the first one' },
        },
        filterEmptyState: {
            message: 'No financial years match your filters.',
            link: { href: URLS.financial_years.new, label: 'Create a new financial year' },
        },
        paginationBarId:      'pagination-bar',
        paginationInfoId:     'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl:        API_URLS.financial_years.list.href,
        pageSize:      20,
        searchInputId: 'fy-search',
        filters: [
            { id: 'status-filter', param: 'is_active' },
        ],
        onLoadStart: () => renderer.renderLoading('Loading financial years…'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load financial years. Please refresh the page.'),
    });

    initSorting({ tableId: 'fy-table', fetcher });

    fetcher.refresh();

    document.getElementById('export-csv')?.addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf')?.addEventListener('click', () => runListExport('pdf'));
}

async function renderStatistics() {
    try {
        const { method, href } = API_URLS.financial_years.stats;
        const stats = await apiFetch(href, { method });
        document.getElementById('stat-total-fys').textContent  = stats.total_fys  ?? '—';
        document.getElementById('stat-active-fy').textContent  = stats.active_fy  ?? '—';
        document.getElementById('stat-past-fys').textContent   = stats.past_fys   ?? '—';
        document.getElementById('stat-future-fys').textContent = stats.future_fys ?? '—';
    } catch (err) {
        console.error('[renderStatistics] Failed to load statistics:', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.financial_years.options;
        const options = await apiFetch(href, { method });
        const statuses = options?.is_active ?? [];
        const select = document.getElementById('status-filter');
        statuses.forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value       = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions] Failed to load options:', err);
    }
}

function getFyStatusBadge(fy) {
    const today = new Date();

    const start = new Date(fy.start_date);
    const end = new Date(fy.end_date);

    // Normalize time (avoid time-of-day issues)
    today.setHours(0, 0, 0, 0);
    start.setHours(0, 0, 0, 0);
    end.setHours(0, 0, 0, 0);

    if (today > end) {
        return '<span class="rp-badge rp-badge--muted">Completed</span>';
    }

    if (today >= start && today <= end) {
        return '<span class="rp-badge rp-badge--success">Active</span>';
    }

    return '<span class="rp-badge rp-badge--info">Future</span>';
}

function isCompletedFy(fy) {
    const today = new Date();

    const end = new Date(fy.end_date + 'T00:00:00');

    today.setHours(0, 0, 0, 0);

    return today > end;
}

function renderFyRow(fy) {
    const tbl = document.getElementById('fy-table');
    const warningDays = tbl ? parseInt(tbl.dataset.warningDays || '0', 10) : 0;
    const isWarning = fy.is_active && warningDays > 0 && fy.remaining_days > 0 && fy.remaining_days <= warningDays;
    const isExpired = fy.remaining_days === 0;

    let remainingCell;
    if (isExpired) {
        remainingCell = `<span class="text-secondary">0</span>`;
    } else if (isWarning) {
        remainingCell = `<span class="rp-badge rp-badge--warning" title="Active FY ending soon">
                            <i class="bi bi-exclamation-triangle me-1"></i>${escHtml(fy.remaining_days)}
                         </span>`;
    } else {
        remainingCell = `<span class="fw-500">${escHtml(fy.remaining_days)}</span>`;
    }

    const fyStatusBadge = getFyStatusBadge(fy);
    const statusBadge = fy.is_active
        ? `<span class="rp-badge rp-badge--success">Active</span>`
        : `<span class="rp-badge rp-badge--muted">Inactive</span>`;

    const setActivBtn = (fy.is_active || isCompletedFy(fy) || !hasPerm('financial_years.change_financialyear'))
        ? ''
        : `<button class="btn btn-ghost-icon"
                   title="Set as active"
                   onclick="confirmSetActive(${fy.id}, '${escAttr(fy.long_fy)}')">
               <i class="bi bi-check-circle"></i>
           </button>`;

    return `
        <tr data-fy-id="${fy.id}">
            <td>
                <a href="${URLS.financial_years.detail(fy.id)}" class="rp-link fw-500">
                    <span class="rp-code">${escHtml(fy.long_fy)}</span>
                </a>
                ${fyStatusBadge}
            </td>
            <td>${escHtml(fy.start_date ?? '—')}</td>
            <td>${escHtml(fy.end_date   ?? '—')}</td>
            <td class="text-center"><span class="fw-500">${escHtml(fy.span_days ?? '—')}</span></td>
            <td class="text-center">${remainingCell}</td>
            <td class="text-center">${statusBadge}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.financial_years.detail(fy.id)}"
                       class="btn btn-ghost-icon" title="View">
                        <i class="bi bi-eye"></i>
                    </a>
                    ${setActivBtn}
                    ${hasPerm('financial_years.change_financialyear') ? `
                    <a href="${URLS.financial_years.edit(fy.id)}"
                       class="btn btn-ghost-icon" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </a>` : ''}
                    ${hasPerm('financial_years.delete_financialyear') ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete"
                            onclick="confirmDelete(${fy.id}, '${escAttr(fy.long_fy)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, label) {
    showFlash(`Financial year "${label}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-fy-id="${id}"]`)?.remove();
    fetcher?.refresh();
    renderStatistics();
    // Refresh navbar dropdown so deleted FY disappears
    refreshNavbarDropdown();
}

// ─────────────────────────────────────────────
// Create View
// ─────────────────────────────────────────────
function initCreateView() {
    setPageTitle('New Financial Year');
    document.getElementById('page-title').textContent    = 'New Financial Year';
    document.getElementById('page-subtitle').textContent = 'Add a new financial year to the planner.';
    document.getElementById('submit-label').textContent  = 'Create financial year';

    _initDatePreview();
}

// ─────────────────────────────────────────────
// Edit View
// ─────────────────────────────────────────────
async function initEditView() {
    if (!fyPk) return;
    setPageTitle('Edit Financial Year');

    // Copy actuals is a create-only option
    document.getElementById('copy-actuals-field')?.classList.add('d-none');

    try {
        const { method, href } = API_URLS.financial_years.detail(fyPk);
        const data = await apiFetch(href, { method });
        populateForm(data);
        _initDatePreview();
    } catch (err) {
        if (err?.status === 404) {
            showFlash('This financial year no longer exists. Redirecting…', 'warning');
            setTimeout(() => { window.location.href = URLS.financial_years.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load financial year. Please refresh.', 'danger');
    }
}

function populateForm(fy) {
    document.getElementById('fy-form').dataset.fyId         = fy.id;
    document.getElementById('id_start_date').value          = fy.start_date  ?? '';
    document.getElementById('id_end_date').value            = fy.end_date    ?? '';
    document.getElementById('id_is_active').checked         = fy.is_active   ?? false;
    document.getElementById('id_notes').value               = fy.notes       ?? '';

    document.getElementById('page-title').textContent       = 'Edit Financial Year';
    document.getElementById('page-subtitle').innerHTML      = `Updating <strong>${escHtml(fy.long_fy)}</strong>`;
    document.getElementById('submit-label').textContent     = 'Save changes';

    document.getElementById('meta-created').textContent     = formatDateTime(fy.created_at);
    document.getElementById('meta-updated').textContent     = formatDateTime(fy.updated_at);
    document.getElementById('metadata-card').classList.remove('d-none');

    document.getElementById('delete-btn-slot').innerHTML = `
        <button type="button" class="btn btn-outline-danger" id="delete-fy-btn">
            <i class="bi bi-trash me-1"></i>Delete
        </button>`;
    document.getElementById('delete-fy-btn')
        .addEventListener('click', () => confirmDelete(fy.id, fy.long_fy, onDeleteFromEdit));

    // Trigger preview with existing dates
    _updatePreview();
}

function onDeleteFromEdit() {
    window.location.href = URLS.financial_years.list;
}

// ─────────────────────────────────────────────
// Form submit — Create & Edit
// ─────────────────────────────────────────────
async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['start_date', 'end_date', 'notes']);
    showBanner('form-error-banner', '', false);

    const startDate = document.getElementById('id_start_date').value;
    const endDate   = document.getElementById('id_end_date').value;

    if (!startDate || !endDate) {
        showBanner('form-error-banner', 'Start date and end date are required.', true);
        return;
    }

    const payload = {
        start_date: startDate,
        end_date:   endDate,
        is_active:  document.getElementById('id_is_active').checked,
        notes:      document.getElementById('id_notes').value.trim(),
    };

    const method = isEdit
        ? API_URLS.financial_years.partial_edit(fyPk).method
        : API_URLS.financial_years.new.method;
    const url = isEdit
        ? API_URLS.financial_years.partial_edit(fyPk).href
        : API_URLS.financial_years.new.href;

    setSubmitting(true);

    try {
        const fy = await apiFetch(url, { method, body: JSON.stringify(payload) });
        // Saved — refresh the navbar so the new/updated FY appears immediately.
        await refreshNavbarDropdown();

        // On create: optionally copy project actuals from the preceding FY
        if (!isEdit && document.getElementById('id_copy_actuals')?.checked && fy?.id) {
            try {
                await apiFetch(API_URLS.project_actuals.copy_from_previous_fy.href, {
                    method: 'POST',
                    body: JSON.stringify({ fy_id: fy.id }),
                });
            } catch (_) { /* non-critical — proceed regardless */ }
        }

        window.location.href = URLS.financial_years.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['start_date', 'end_date', 'notes']);
            const nonField = err.data?.non_field_errors ?? err.data?.detail;
            if (nonField) showBanner('form-error-banner', nonField, true);
            return;
        }
        if (err?.status === 404) {
            showFlash('This financial year no longer exists. Redirecting…', 'warning');
            setTimeout(() => { window.location.href = URLS.financial_years.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || `Unexpected error (${err?.status}). Please try again.`, 'danger');
    } finally {
        setSubmitting(false);
    }
}

// ─────────────────────────────────────────────
// Form date preview (live FY label calculation)
// ─────────────────────────────────────────────
function _initDatePreview() {
    const startInput = document.getElementById('id_start_date');
    const endInput   = document.getElementById('id_end_date');
    if (!startInput || !endInput) return;
    startInput.addEventListener('change', _updatePreview);
    endInput.addEventListener('change', _updatePreview);
    _updatePreview();
}

function _updatePreview() {
    const startVal = document.getElementById('id_start_date')?.value;
    const endVal   = document.getElementById('id_end_date')?.value;
    const previewRow = document.getElementById('fy-preview-row');
    if (!previewRow) return;

    if (!startVal || !endVal) {
        previewRow.style.display = 'none';
        return;
    }

    const start = new Date(startVal);
    const end   = new Date(endVal);

    if (isNaN(start) || isNaN(end) || end <= start) {
        previewRow.style.display = 'none';
        return;
    }

    const startYear = start.getFullYear();
    const endYear   = end.getFullYear();
    const longFy    = `FY${startYear}-${String(endYear)}`;
    const shortFy   = `FY${String(startYear).slice(2)}-${String(endYear).slice(2)}`;
    const spanDays  = Math.round((end - start) / 86400000) + 1;

    document.getElementById('preview-long-fy').textContent  = longFy;
    document.getElementById('preview-short-fy').textContent = shortFy;
    document.getElementById('preview-span-days').textContent = `${spanDays} days`;
    previewRow.style.display = '';
}

// ─────────────────────────────────────────────
// Detail View
// ─────────────────────────────────────────────
async function initDetailView() {
    if (!fyPk) return;
    setPageTitle('Financial Year');

    try {
        const { method, href } = API_URLS.financial_years.detail(fyPk);
        const data = await apiFetch(href, { method });
        renderDetailHeader(data);
        renderDetailBody(data);
    } catch (err) {
        if (err?.status === 404) {
            showFlash('This financial year no longer exists. Redirecting…', 'warning');
            setTimeout(() => { window.location.href = URLS.financial_years.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load financial year details. Please refresh.', 'danger');
    }
}

function renderDetailHeader(fy) {
    document.getElementById('fy-label').textContent     = fy.long_fy;
    document.getElementById('fy-date-range').textContent =
        `${escHtml(fy.start_date)} → ${escHtml(fy.end_date)}`;

    const statusEl = document.getElementById('fy-status');
    statusEl.textContent = fy.is_active ? 'Active' : 'Inactive';
    statusEl.classList.add(fy.is_active ? 'rp-badge--success' : 'rp-badge--muted');

    document.getElementById('edit-fy-btn').href = URLS.financial_years.edit(fyPk);

    const setActiveBtn = document.getElementById('set-active-btn');
    const modalLabel   = document.getElementById('set-active-fy-label');
    const confirmBtn   = document.getElementById('confirm-set-active-btn');
    if (!fy.is_active && setActiveBtn) {
        setActiveBtn.classList.remove('d-none');
        if (modalLabel) modalLabel.textContent = fy.long_fy;
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => handleSetActive(fy.id, fy.long_fy));
        }
    }
}

function renderDetailBody(fy) {
    document.getElementById('detail-long-fy').textContent      = fy.long_fy       ?? '—';
    document.getElementById('detail-short-fy').textContent     = fy.short_fy      ?? '—';
    document.getElementById('detail-start-date').textContent   = fy.start_date    ?? '—';
    document.getElementById('detail-end-date').textContent     = fy.end_date      ?? '—';
    document.getElementById('detail-span-days').textContent    = fy.span_days     ?? '—';
    document.getElementById('detail-remaining-days').textContent = fy.remaining_days ?? '—';
    document.getElementById('detail-notes').textContent        = fy.notes || '—';
    document.getElementById('meta-created').textContent        = formatDateTime(fy.created_at);
    document.getElementById('meta-updated').textContent        = formatDateTime(fy.updated_at);
}

async function handleSetActive(id, label) {
    const confirmBtn = document.getElementById('confirm-set-active-btn');
    if (!confirmBtn) return;

    confirmBtn.disabled    = true;
    confirmBtn.innerHTML   = '<span class="spinner-border spinner-border-sm me-1"></span>Setting…';

    try {
        const { method, href } = API_URLS.financial_years.set_active(id);
        await apiFetch(href, { method });
//        await apiFetch(API_URLS.financial_years.set_active.href, {
//            method: API_URLS.financial_years.set_active.method,
//            body: JSON.stringify({ id }),
//        });
        bootstrap.Modal.getInstance(document.getElementById('setActiveModal'))?.hide();
        showFlash(`${label} is now the active financial year.`, 'success');
        await refreshNavbarDropdown();
        // Reload page to reflect updated status badges
        window.location.reload();
    } catch (err) {
        bootstrap.Modal.getInstance(document.getElementById('setActiveModal'))?.hide();
        showFlash(err?.data?.error || 'Failed to set active financial year.', 'danger');
    } finally {
        confirmBtn.disabled  = false;
        confirmBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Set as Active';
    }
}

// ─────────────────────────────────────────────
// Set Active from list
// ─────────────────────────────────────────────
function confirmSetActive(id, label) {
    const modal    = document.getElementById('setActiveModal');
    const labelEl  = document.getElementById('set-active-fy-label');
    const btn      = document.getElementById('confirm-set-active-btn');
    if (!modal || !btn) return;

    labelEl.textContent = label;

    // Clone to strip any prior listener
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);

    newBtn.addEventListener('click', async () => {
        newBtn.disabled    = true;
        newBtn.innerHTML   = '<span class="spinner-border spinner-border-sm me-1"></span>Setting…';
        try {
            const { method, href } = API_URLS.financial_years.set_active(id);
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            showFlash(`${label} is now the active financial year.`, 'success');
            await refreshNavbarDropdown();
            // On the list page: refresh rows + stats so status badges update
            fetcher?.refresh();
            renderStatistics();
            // Also refresh the global warning banner if present
            _refreshWarningBanner();
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            showFlash(err?.data?.error || 'Failed to set active financial year.', 'danger');
        } finally {
            newBtn.disabled    = false;
            newBtn.innerHTML   = '<i class="bi bi-check-circle me-1"></i>Set as Active';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

// ─────────────────────────────────────────────
// Delete Modal — Shared
// ─────────────────────────────────────────────
function confirmDelete(id, label, onSuccess) {
    const modal  = document.getElementById('deleteModal');
    const labelEl = document.getElementById('delete-fy-label');
    const btn    = document.getElementById('confirm-delete-btn');
    if (!modal || !btn) return;

    labelEl.textContent = label;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.financial_years.delete(id);

    newBtn.addEventListener('click', async () => {
        newBtn.disabled    = true;
        newBtn.textContent = 'Deleting…';
        try {
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            onSuccess(id, label);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            if (err?.status === 404) {
                showFlash(`"${label}" was not found — it may have already been deleted.`, 'warning');
                document.querySelector(`tr[data-fy-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(err?.data?.detail || `Failed to delete "${label}". Please try again.`, 'danger');
        } finally {
            newBtn.disabled    = false;
            newBtn.textContent = 'Delete';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

// ─────────────────────────────────────────────
// Export
// ─────────────────────────────────────────────
const LIST_EXPORT_COLUMNS = [
    { key: 'id',        label: 'ID' },
    { key: 'long_fy',   label: 'Financial Year' },
    { key: 'short_fy',  label: 'Short Label' },
    { key: 'start_date', label: 'Start Date' },
    { key: 'end_date',   label: 'End Date' },
    { key: 'span_days',  label: 'Span (days)' },
    { key: 'remaining_days', label: 'Remaining (days)' },
    { key: 'is_active',  label: 'Active' },
    { key: 'notes',      label: 'Notes' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();
    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }
    try {
        const { method, href } = API_URLS.financial_years.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, `financial_years-${date}`);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Financial Years', `financial_years-${date}`);
        }
    } catch {
        showFlash('Export failed. Please try again.', 'danger');
    } finally {
        if (btn) {
            btn.disabled  = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i>Export';
        }
    }
}

async function loadWarningThreshold() {
    try {
        const { method, href } = API_URLS.configurations.by_code("FY_EXPIRY_WARNING_DAYS");
        const res = await apiFetch(href, { method });
        const val = parseInt(res?.value ?? '30', 10);
        return isNaN(val) ? 30 : val;
    } catch {
        return 30;  // safe fallback
    }
}

function _refreshWarningBanner() {
    window.dispatchEvent(new CustomEvent('rp:fy-changed'));
}

// ─────────────────────────────────────────────
// Navbar dropdown refresh
// ─────────────────────────────────────────────
/**
 * Fetches the fresh FY summary and re-renders the navbar dropdown in-place.
 * Called after create / edit / delete / set-active so the navbar stays in sync
 * without a full page reload.
 */
async function refreshNavbarDropdown() {
    try {
        const { method, href } = API_URLS.financial_years.summary;
        const fys = await apiFetch(href, { method });
        renderNavbarDropdown(fys);
        // Also write the active FY into the cookie so any page can read it cheaply.
        _persistActiveFyToCookie(fys);
    } catch (err) {
        console.warn('[refreshNavbarDropdown] Could not refresh:', err);
    }
}

function renderNavbarDropdown(fys) {
    const container = document.getElementById('fy-dropdown-menu');
    if (!container) return;

    const active = fys.find(f => f.is_active) || null;

    let html = '';

    // Active indicator
    if (active) {
        html += `
            <li>
                <div class="px-3 py-2 d-flex align-items-center gap-2">
                    <span class="rp-badge rp-badge--success" style="font-size:10.5px">Active</span>
                    <span class="fw-500" style="font-size:13px">${escHtml(active.long_fy)}</span>
                </div>
            </li>
            <li><hr class="dropdown-divider my-1"></li>`;
    }

    // All FYs
    if (fys.length === 0) {
        html += `<li><span class="dropdown-item text-secondary" style="font-size:13px">No financial years yet</span></li>`;
    } else {
        fys.forEach(fy => {
            html += `
                <li>
                    <a class="dropdown-item d-flex align-items-center justify-content-between${fy.is_active ? ' fw-500' : ''}"
                       href="${URLS.financial_years.detail(fy.id)}">
                        <span>${escHtml(fy.long_fy)}</span>
                        <span class="text-secondary" style="font-size:11.5px">${escHtml(fy.short_fy)}</span>
                    </a>
                </li>`;
        });
    }

    // Footer links
    html += `
        <li><hr class="dropdown-divider my-1"></li>
        <li>
            <a class="dropdown-item" href="${URLS.financial_years.list}">
                <i class="bi bi-list-ul me-2"></i>All financial years
            </a>
        </li>
        <li>
            <a class="dropdown-item" href="${URLS.financial_years.new}">
                <i class="bi bi-plus me-2"></i>New financial year
            </a>
        </li>`;

    container.innerHTML = html;

    // Update the toggle button label
    const toggleLabel = document.getElementById('fy-nav-toggle-label');
    if (toggleLabel) {
        toggleLabel.textContent = active ? active.short_fy : 'Financial Years';
    }
}

function _persistActiveFyToCookie(fys) {
    const active = fys.find(f => f.is_active) || null;
    const val = active
        ? JSON.stringify({ id: active.id, long_fy: active.long_fy, short_fy: active.short_fy })
        : '';
    // Session cookie — no expiry, cleared when browser closes.
    // SameSite=Strict: internal tool, no cross-site usage.
    document.cookie = `rp_active_fy=${encodeURIComponent(val)}; path=/; SameSite=Strict`;
}

// ─────────────────────────────────────────────
// Window exports
// ─────────────────────────────────────────────
window.confirmDelete        = confirmDelete;
window.confirmSetActive     = confirmSetActive;
window.onDeleteFromList     = onDeleteFromList;
window.onDeleteFromEdit     = onDeleteFromEdit;
window.refreshNavbarDropdown  = refreshNavbarDropdown;
window.renderNavbarDropdown   = renderNavbarDropdown;
window.loadWarningThreshold   = loadWarningThreshold;