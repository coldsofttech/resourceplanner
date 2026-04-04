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

const leavePk = getPkFromUrl('leaves');
const isEdit  = isSubPathUrl('leaves', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const leavesTable = document.getElementById('leaves-table');
    if (leavesTable) {
        initListView();
        return;
    }

    const detailRoot = document.getElementById('detail-root');
    if (detailRoot) {
        initDetailView();
        return;
    }

    // leave_form.html uses id="leave-form"
    const formEl = document.getElementById('leave-form');
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
    setPageTitle('Leaves');
    renderStatistics();
    renderMemberFilterOptions();

    const renderer = initRenderer({
        tbodyId:    'leaves-tbody',
        colspan:    6,
        itemLabel:  'leaves',
        rowTemplate: renderLeaveRow,
        emptyState: {
            message: 'No leave records yet.',
            link:    { href: URLS.leaves.new, label: 'Add the first one' },
        },
        filterEmptyState: {
            message: 'No leaves match your filters.',
            link:    { href: URLS.leaves.new, label: 'Add a new leave' },
        },
        paginationBarId:      'pagination-bar',
        paginationInfoId:     'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl:        API_URLS.leaves.list.href,
        pageSize:      20,
        searchInputId: 'leave-search',
        filters: [
            { id: 'member-filter',       param: 'member_id' },
            { id: 'include-past-filter', param: 'include_past' },
        ],
        onLoadStart: () => renderer.renderLoading('Loading leaves…'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load leaves. Please refresh the page.'),
    });

    initSorting({ tableId: 'leaves-table', fetcher });
    fetcher.refresh();

    document.getElementById('export-csv').addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf').addEventListener('click', () => runListExport('pdf'));
}

async function renderStatistics() {
    try {
        const { method, href } = API_URLS.leaves.stats;
        const stats = await apiFetch(href, { method });
        document.getElementById('stat-total-leaves').textContent    = stats.total_leaves    ?? 0;
        document.getElementById('stat-active-leaves').textContent   = stats.active_leaves   ?? 0;
        document.getElementById('stat-upcoming-leaves').textContent = stats.upcoming_leaves ?? 0;
    } catch (err) {
        console.error('[renderStatistics]', err);
    }
}

async function renderMemberFilterOptions() {
    try {
        const { method, href } = API_URLS.leaves.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('member-filter');
        if (!select) return;
        (options?.members ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value       = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderMemberFilterOptions]', err);
    }
}

function renderLeaveRow(leave) {
    const memberName = leave.member_name ?? '-';
    const memberId   = leave.member?.id ?? '';

    const typeBadge = leave.is_half_day
        ? `<span class="rp-badge rp-badge--muted">Half-day${leave.half_day_period ? ` (${escHtml(leave.half_day_period)})` : ''}</span>`
        : `<span class="rp-badge">Full day</span>`;

    return `
        <tr data-leave-id="${leave.id}">
            <td>
                <a href="${URLS.leaves.detail(leave.id)}" class="rp-link fw-500">
                    ${escHtml(memberName)}
                </a>
            </td>
            <td>${escHtml(leave.start_date ?? '—')}</td>
            <td>${escHtml(leave.end_date ?? '—')}</td>
            <td>${leave.days != null ? leave.days : '—'}</td>
            <td>${typeBadge}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.leaves.detail(leave.id)}"
                       class="btn btn-ghost-icon" title="View leave">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.leaves.edit(leave.id)}"
                       class="btn btn-ghost-icon" title="Edit leave">
                        <i class="bi bi-pencil"></i>
                    </a>
                    <button type="button"
                            class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete leave"
                            onclick="confirmDelete(${leave.id}, '${escAttr(memberName)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, name) {
    showFlash(`Leave record for "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-leave-id="${id}"]`)?.remove();
    fetcher?.refresh();
    renderStatistics();
}

/* =========================================================
 * Create & Edit View
 * ========================================================= */
async function initCreateView() {
    setPageTitle('New Leave');
    document.getElementById('page-title').textContent    = 'New Leave';
    document.getElementById('page-subtitle').textContent = 'Record confirmed leave for a team member';
    document.getElementById('submit-label').textContent  = 'Create leave';
    document.getElementById('submit-btn').dataset.originalLabel = 'Create leave';
    await loadMemberOptions(null);
    initHalfDayToggle();
}

async function initEditView() {
    setPageTitle('Edit Leave');
    const submitBtn = document.getElementById('submit-btn');
    document.getElementById('page-title').textContent    = 'Edit Leave';
    document.getElementById('page-subtitle').textContent = 'Loading…';
    document.getElementById('submit-label').textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    await loadMemberOptions(null);
    initHalfDayToggle();

    try {
        const { method, href } = API_URLS.leaves.get(leavePk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        document.getElementById('page-subtitle').textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash('This leave record no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.leaves.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load leave data. Please try again.', 'danger');
    }
}

async function loadMemberOptions(selectedMemberId) {
    try {
        const { method, href } = API_URLS.leaves.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('id_member');
        if (!select) return;
        (options?.members ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value       = value;
            opt.textContent = label;
            if (selectedMemberId && parseInt(value) === parseInt(selectedMemberId)) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[loadMemberOptions]', err);
        showFlash('Could not load member options. Please refresh.', 'danger');
    }
}

function initHalfDayToggle() {
    const checkbox    = document.getElementById('id_is_half_day');
    const periodRow   = document.getElementById('half-day-period-row');
    const endDateInput = document.getElementById('id_end_date');

    if (!checkbox || !periodRow) return;

    function syncHalfDay() {
        if (checkbox.checked) {
            periodRow.classList.remove('d-none');
            // Snap end_date to start_date when switching to half-day
            const startDate = document.getElementById('id_start_date').value;
            if (startDate && endDateInput) {
                endDateInput.value = startDate;
                endDateInput.setAttribute('readonly', 'readonly');
            }
        } else {
            periodRow.classList.add('d-none');
            if (endDateInput) endDateInput.removeAttribute('readonly');
        }
    }

    checkbox.addEventListener('change', syncHalfDay);
    // Sync on load (e.g. edit view with is_half_day=true)
    syncHalfDay();
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    console.log("hello");
    clearErrors(['member', 'start_date', 'end_date', 'half_day_period', 'note']);

    const memberId     = document.getElementById('id_member').value;
    const startDate    = document.getElementById('id_start_date').value;
    const endDate      = document.getElementById('id_end_date').value;
    const isHalfDay    = document.getElementById('id_is_half_day').checked;
    const halfDayPeriod = document.getElementById('id_half_day_period').value;
    const note         = document.getElementById('id_note').value.trim();

    let valid = true;

    if (!memberId) {
        _fieldError('id_member', 'member-error', 'Please select a team member.');
        valid = false;
    }
    if (!startDate) {
        _fieldError('id_start_date', 'start-date-error', 'Start date is required.');
        valid = false;
    }
    if (!endDate) {
        _fieldError('id_end_date', 'end-date-error', 'End date is required.');
        valid = false;
    }
    if (startDate && endDate && endDate < startDate) {
        _fieldError('id_end_date', 'end-date-error', 'End date cannot be before start date.');
        valid = false;
    }
    if (isHalfDay && startDate && endDate && startDate !== endDate) {
        _fieldError('id_end_date', 'end-date-error', 'Half-day leaves must start and end on the same date.');
        valid = false;
    }
    if (isHalfDay && !halfDayPeriod) {
        _fieldError('id_half_day_period', 'half-day-period-error', 'Please select AM or PM for half-day leave.');
        valid = false;
    }
    if (!valid) return;

    const payload = {
        member:           parseInt(memberId),
        start_date:       startDate,
        end_date:         endDate,
        is_half_day:      isHalfDay,
        half_day_period:  isHalfDay ? halfDayPeriod : null,
        note:             note || null,
    };

    const { method, href } = isEdit
        ? API_URLS.leaves.partial_edit(leavePk)
        : API_URLS.leaves.new;

    setSubmitting(true);
    try {
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.leaves.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['member', 'start_date', 'end_date', 'half_day_period', 'note']);
            const banner = document.getElementById('form-error-banner');
            if (banner && err.data?.non_field_errors) {
                banner.textContent = err.data.non_field_errors.join(' ');
                banner.classList.remove('d-none');
            }
            return;
        }
        if (err?.status === 404) {
            showFlash('This leave record no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.leaves.list; }, 3000);
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

function _fieldError(inputId, errorId, message) {
    document.getElementById(inputId)?.classList.add('is-invalid');
    const el = document.getElementById(errorId);
    if (el) el.textContent = message;
}

function populateForm(leave) {
    // Member select — option may already exist from loadMemberOptions
    const memberSelect = document.getElementById('id_member');
    if (memberSelect && leave.member) {
        memberSelect.value = leave.member;
    }

    document.getElementById('id_start_date').value   = leave.start_date ?? '';
    document.getElementById('id_end_date').value     = leave.end_date   ?? '';
    document.getElementById('id_is_half_day').checked = leave.is_half_day ?? false;

    const periodSelect = document.getElementById('id_half_day_period');
    if (periodSelect) periodSelect.value = leave.half_day_period ?? '';

    const noteEl = document.getElementById('id_note');
    if (noteEl) noteEl.value = leave.note ?? '';

    // Sync the half-day toggle UI
    const periodRow = document.getElementById('half-day-period-row');
    if (periodRow) {
        periodRow.classList.toggle('d-none', !leave.is_half_day);
    }

    document.getElementById('page-title').textContent   = 'Edit Leave';
    document.getElementById('page-subtitle').innerHTML  = `Updating leave for <strong>${escHtml(leave.member_name)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(leave.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(leave.updated_at);
    document.getElementById('metadata-card').classList.remove('d-none');

    document.getElementById('delete-btn-slot').innerHTML = `
        <button type="button" class="btn btn-outline-danger" id="delete-leave-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document.getElementById('delete-leave-btn')
        .addEventListener('click', () => confirmDelete(leave.id, leave.member_name, onDeleteFromEdit));
}

function onDeleteFromEdit() {
    window.location.href = URLS.leaves.list;
}

/* =========================================================
 * Detail View
 * ========================================================= */
async function initDetailView() {
    if (!leavePk) return;
    setPageTitle('Leave');

    try {
        const { method, href } = API_URLS.leaves.get(leavePk);
        const data = await apiFetch(href, { method });
        renderDetailTitle(data);
        renderLeaveDetails(data);
    } catch (err) {
        if (err?.status === 404) {
            showFlash('This leave record no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.leaves.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load leave details. Please refresh.', 'danger');
    }
}

function renderDetailTitle(leave) {
    document.getElementById('leave-title').textContent = leave.member_name;
    document.getElementById('leave-subtitle').innerHTML = `<span>On leave for <strong>${escHtml(leave.days)}</strong> days</span>`;
    document.getElementById('view-member-btn').href = URLS.team_members.detail(leave.member);
    document.getElementById('edit-leave-btn').href = URLS.leaves.edit(leavePk);
}

function renderLeaveDetails(leave) {
    const location = leave.member_location
        ? `${leave.member_location.city}, ${leave.member_location.country}`
        : '-';

    document.getElementById('detail-location').textContent = location;
    document.getElementById('detail-start').textContent    = leave.start_date ?? '—';
    document.getElementById('detail-end').textContent      = leave.end_date   ?? '—';

    const typeText = leave.is_half_day
        ? `Half-day${leave.half_day_period ? ` — ${leave.half_day_period}` : ''}`
        : 'Full day';
    document.getElementById('detail-type').textContent = typeText;
    document.getElementById('detail-days').textContent = leave.days != null ? `${leave.days} day${leave.days !== 1 ? 's' : ''}` : '—';
    document.getElementById('detail-note').textContent = leave.note || '—';

    document.getElementById('meta-created').textContent = formatDateTime(leave.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(leave.updated_at);
}

function onDeleteFromDetail() {
    window.location.href = URLS.leaves.list;
}

/* =========================================================
 * Delete Modal — shared across all views
 * ========================================================= */
function confirmDelete(id, name, onSuccess) {
    const modal  = document.getElementById('deleteModal');
    const nameEl = document.getElementById('delete-leave-name');
    const btn    = document.getElementById('confirm-delete-btn');
    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);

    const { method, href } = API_URLS.leaves.delete(id);

    newBtn.addEventListener('click', async () => {
        try {
            newBtn.disabled    = true;
            newBtn.textContent = 'Deleting…';
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            onSuccess(id, name);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            if (err?.status === 404) {
                showFlash(`Leave for "${name}" was not found — it may have already been deleted.`, 'warning');
                document.querySelector(`tr[data-leave-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete leave for "${name}". Please try again.`,
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
    { key: 'id',               label: 'ID' },
    { key: 'member_name',           label: 'Member' },
    { key: 'start_date',       label: 'Start Date' },
    { key: 'end_date',         label: 'End Date' },
    { key: 'days',             label: 'Days' },
    { key: 'is_half_day',      label: 'Half Day' },
    { key: 'half_day_period',  label: 'Period' },
    { key: 'note',             label: 'Note' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();
    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }
    try {
        const { method, href } = API_URLS.leaves.export;
        const res  = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, `leaves-${date}`);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Member Leaves', `leaves-${date}`);
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
window.confirmDelete    = confirmDelete;
window.onDeleteFromList = onDeleteFromList;
window.onDeleteFromEdit = onDeleteFromEdit;