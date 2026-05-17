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
import { exportToCsv, exportToPdf } from './../export.js';

let fetcher = null;

const sprintPk = getPkFromUrl('sprints');
const isEdit   = isSubPathUrl('sprints', 'edit');

// Month names for display
const MONTHS = [
    '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

document.addEventListener('DOMContentLoaded', () => {
    const sprintsTable = document.getElementById('sprints-table');
    if (sprintsTable) { initListView(); return; }

    const detailRoot = document.getElementById('detail-root');
    if (detailRoot) { initDetailView(); return; }

    const formEl = document.getElementById('sprint-form');
    if (formEl) {
        formEl.addEventListener('submit', handleCreateEditSubmit);
        if (isEdit) {
            initEditView();
        } else {
            initCreateView();
        }
    }
});

// ═══════════════════════════════════════════════════════════════════════════
// List View
// ═══════════════════════════════════════════════════════════════════════════

function initListView() {
    setPageTitle('Sprints');
    renderStatistics();
    populateFyFilter();
    populateMonthFilter();

    const renderer = initRenderer({
        tbodyId: 'sprints-tbody',
        colspan: 6,
        itemLabel: 'sprints',
        rowTemplate: renderSprintRow,
        emptyState: {
            message: 'No sprints yet.',
            link: { href: URLS.sprints.new, label: 'Create the first one' },
        },
        filterEmptyState: {
            message: 'No sprints match your filters.',
            link: { href: URLS.sprints.new, label: 'Create a new sprint' },
        },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: API_URLS.sprints.list.href,
        pageSize: 20,
        searchInputId: 'sprint-search',
        filters: [
            { id: 'fy-filter',     param: 'fy_id' },
            { id: 'status-filter', param: 'is_active' },
            { id: 'month-filter',  param: 'month' },
        ],
        onLoadStart: () => renderer.renderLoading('Loading sprints…'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load sprints. Please refresh the page.'),
    });

    initSorting({ tableId: 'sprints-table', fetcher });
    fetcher.refresh();

    document.getElementById('export-csv').addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf').addEventListener('click', () => runListExport('pdf'));
    document.getElementById('run-engine-btn').addEventListener('click', openEngineModal);
}

async function renderStatistics(fyId = null) {
    try {
        const url = fyId
            ? `${API_URLS.sprints.stats.href}?fy_id=${fyId}`
            : API_URLS.sprints.stats.href;
        const stats = await apiFetch(url, { method: 'GET' });
        document.getElementById('stat-active-sprint').textContent = stats.active_sprint ?? '-';
        document.getElementById('stat-active-sprint-start-date').textContent = stats.active_sprint_start_date ?? '-';
        document.getElementById('stat-active-sprint-end-date').textContent = stats.active_sprint_end_date ?? '-';
        document.getElementById('stat-active-sprint-remaining-days').textContent = stats.active_sprint_remaining_days ?? '-';
    } catch (err) {
        console.error('[renderStatistics]', err);
    }
}

async function populateFyFilter() {
    try {
        const opts = await apiFetch(API_URLS.sprints.options.href, { method: 'GET' });
        const sel  = document.getElementById('fy-filter');
        if (!sel) return;
        (opts.financial_years ?? []).forEach(({ value, label, is_active }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label + (is_active ? ' ★' : '');
            sel.appendChild(opt);
        });
    } catch (err) {
        console.error('[populateFyFilter]', err);
    }
}

async function populateMonthFilter() {
    const sel = document.getElementById('month-filter');
    if (!sel) return;
    MONTHS.slice(1).forEach((name, idx) => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        sel.appendChild(opt);
    });
}

function getSprintStatusBadge(sprint) {
    const today     = new Date().toISOString().slice(0, 10);
    if (sprint.end_date < today) {
        return '<span class="rp-badge rp-badge--muted">Completed</span>';
    }
    if (sprint.start_date <= today && sprint.end_date >= today) {
        return '<span class="rp-badge rp-badge--success">In Progress</span>';
    }
    return '<span class="rp-badge rp-badge--info">Future</span>';
}

function isCompletedSprint(sprint) {
    const today = new Date();
    const end = new Date(sprint.end_date + 'T00:00:00');
    today.setHours(0, 0, 0, 0);
    return today > end;
}

function renderSprintRow(sprint) {
    const today     = new Date().toISOString().slice(0, 10);
    const isPast    = sprint.end_date < today;
    const isCurrent = sprint.start_date <= today && sprint.end_date >= today;

    const statusBadge = sprint.is_active
        ? '<span class="rp-badge rp-badge--success">Active</span>'
        : '<span class="rp-badge rp-badge--muted">Inactive</span';

    const sprintStatusBadge = getSprintStatusBadge(sprint);
    const overriddenTag = sprint.is_overridden
        ? ' <span class="rp-badge rp-badge--warning" title="Manually overridden">Overridden</span>'
        : '';
    const setActivBtn = (sprint.is_active || isCompletedSprint(sprint) || !hasPerm('sprints.change_sprint'))
        ? ''
        : `<button class="btn btn-ghost-icon"
                   title="Set as active"
                   onclick="confirmSetActive(${sprint.id}, '${escAttr(sprint.sprint_name)}')">
               <i class="bi bi-check-circle"></i>
           </button>`;

    return `
        <tr data-sprint-id="${sprint.id}">
            <td>
                <a href="${URLS.sprints.detail(sprint.id)}" class="rp-link fw-500 rp-code">${escHtml(sprint.sprint_name)}</a>
                ${sprintStatusBadge}
                ${overriddenTag}
            </td>
            <td class="text-secondary" style="font-size:13px;">
                ${escHtml(sprint.fy_label ?? sprint.fy_short ?? '—')}
            </td>
            <td class="text-secondary">${escHtml(sprint.start_date ?? '—')}</td>
            <td class="text-secondary">${escHtml(sprint.end_date ?? '—')}</td>
            <td class="text-center">${statusBadge}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.sprints.detail(sprint.id)}"
                       class="btn btn-ghost-icon" title="View sprint">
                        <i class="bi bi-eye"></i>
                    </a>
                    ${setActivBtn}
                    ${hasPerm('sprints.change_sprint') ? `
                    <a href="${URLS.sprints.edit(sprint.id)}"
                       class="btn btn-ghost-icon" title="Edit sprint">
                        <i class="bi bi-pencil"></i>
                    </a>` : ''}
                    ${hasPerm('sprints.delete_sprint') ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete sprint"
                            onclick="confirmDelete(${sprint.id}, '${escAttr(sprint.sprint_name)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, name) {
    showFlash(`Sprint "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-sprint-id="${id}"]`)?.remove();
    fetcher?.refresh();
    renderStatistics();
}

function confirmSetActive(id, name) {
    const modal   = document.getElementById('setActiveModal');
    const labelEl = document.getElementById('set-active-sprint-label');
    const btn     = document.getElementById('confirm-set-active-btn');
    if (!modal || !btn) return;

    labelEl.textContent = name;

    // Clone to strip any previously attached listener (same pattern as FY)
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);

    newBtn.addEventListener('click', async () => {
        newBtn.disabled  = true;
        newBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Setting…';
        try {
            const { method, href } = API_URLS.sprints.set_active(id);
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            showFlash(`${name} is now the active sprint.`, 'success');
            // Refresh rows + stat cards so badges update in place
            fetcher?.refresh();
            renderStatistics();
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            showFlash(err?.data?.error || 'Failed to set active sprint.', 'danger');
        } finally {
            newBtn.disabled  = false;
            newBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Set as Active';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

// ── Run Engine Modal ───────────────────────────────────────────────────────

async function openEngineModal() {
    // Populate FY select in the modal
    try {
        const opts = await apiFetch(API_URLS.sprints.options.href, { method: 'GET' });
        const sel  = document.getElementById('engine-fy-select');
        if (sel) {
            sel.innerHTML = '<option value="">Select a financial year…</option>';
            (opts.financial_years ?? []).forEach(({ value, label, is_active }) => {
                const opt = document.createElement('option');
                opt.value = value;
                opt.textContent = label + (is_active ? ' ★' : '');
                if (is_active) opt.selected = true;
                sel.appendChild(opt);
            });
        }
    } catch (err) {
        console.error('[openEngineModal] Failed to load options:', err);
    }

    // Reset results panel
    const resultsPanel = document.getElementById('engine-results');
    if (resultsPanel) resultsPanel.classList.add('d-none');

    bootstrap.Modal.getOrCreateInstance(document.getElementById('engineModal')).show();
    document.getElementById('engine-run-btn').onclick = runEngine;
}

async function runEngine() {
    const fyId   = document.getElementById('engine-fy-select').value;
    const dryRun = document.getElementById('engine-dry-run').checked;
    const btn    = document.getElementById('engine-run-btn');
    const panel  = document.getElementById('engine-results');
    const body   = document.getElementById('engine-results-body');

    if (!fyId) {
        showFlash('Please select a financial year.', 'warning');
        return;
    }

    btn.disabled  = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Running…';

    try {
        const result = await apiFetch(API_URLS.sprints.run_engine.href, {
            method: 'POST',
            body: JSON.stringify({ fy_id: parseInt(fyId, 10), dry_run: dryRun }),
        });

        panel.classList.remove('d-none');

        const modeLabel = dryRun
            ? '<span class="rp-badge rp-badge--warning">Dry Run — nothing saved</span>'
            : '<span class="rp-badge rp-badge--success">Saved</span>';

        let html = `
            <div class="d-flex align-items-center gap-2 mb-3">
                <strong>${escHtml(result.fy)}</strong> ${modeLabel}
            </div>
            <p class="text-secondary mb-2">
                <strong>${result.total_created}</strong> sprint(s) generated.
                ${result.skipped_overridden?.length ? `<strong>${result.skipped_overridden.length}</strong> overridden sprint(s) skipped.` : ''}
            </p>`;

        if (result.generated?.length) {
            html += '<div class="rp-table-wrap"><table class="table rp-table mb-0"><thead><tr><th>Sprint</th><th>Start</th><th>End</th></tr></thead><tbody>';
            result.generated.forEach(s => {
                html += `<tr><td class="rp-code fw-500">${escHtml(s.sprint_name)}</td><td>${escHtml(s.start_date)}</td><td>${escHtml(s.end_date)}</td></tr>`;
            });
            html += '</tbody></table></div>';
        }

        body.innerHTML = html;

        if (!dryRun) {
            fetcher?.refresh();
            renderStatistics();
            showFlash(`${result.total_created} sprint(s) generated for ${result.fy}.`, 'success');
            bootstrap.Modal.getInstance(document.getElementById('engineModal'))?.hide();
        }
    } catch (err) {
        showFlash(err?.data?.error || 'Engine run failed. Please try again.', 'danger');
    } finally {
        btn.disabled  = false;
        btn.innerHTML = '<i class="bi bi-lightning-charge me-1"></i>Generate Sprints';
    }
}

// ── Export ─────────────────────────────────────────────────────────────────

const LIST_EXPORT_COLUMNS = [
    { key: 'id',            label: 'ID' },
    { key: 'fy_long',      label: 'Financial Year' },
    { key: 'sprint_name',   label: 'Name' },
    { key: 'start_date',    label: 'Start Date' },
    { key: 'end_date',      label: 'End Date' },
    { key: 'month',         label: 'Month' },
    { key: 'is_active',     label: 'Active' },
    { key: 'is_overridden', label: 'Overridden' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();
    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Exporting…';
    }
    try {
        const res  = await apiFetch(API_URLS.sprints.export.href, { method: 'GET' });
        const date = new Date().toISOString().slice(0, 10);
        const fn   = `sprints-${date}`;
        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, fn);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Sprints', fn);
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

// ═══════════════════════════════════════════════════════════════════════════
// Create / Edit Form View
// ═══════════════════════════════════════════════════════════════════════════

let autoGeneratedSprintName = true;

async function getSprintNamePrefix() {
    const { method, href } = API_URLS.configurations.by_code("SPRINT_NAME_PREFIX")
    const res = await apiFetch(href, { method });
    return res.value;
}

async function getSprintDurationDays() {
    const { method, href } = API_URLS.configurations.by_code("SPRINT_DURATION_DAYS");
    const res = await apiFetch(href, { method });
    return res.value;
}

async function initCreateView() {
    setPageTitle('New Sprint');
    document.getElementById('page-title').textContent    = 'New Sprint';
    document.getElementById('page-subtitle').textContent = 'Create a sprint manually.';
    document.getElementById('submit-label').textContent  = 'Create sprint';
    await populateFySelect();
    wireEndDateMonthHint();

    const sprintNamePrefix = await getSprintNamePrefix();
    const sprintEl = document.getElementById('id_sprint_number');
    const sprintNameEl = document.getElementById('id_sprint_name');
    sprintEl.addEventListener('input', () => {
        if(autoGeneratedSprintName) {
            sprintNameEl.value = `${sprintNamePrefix} ${sprintEl.value}`;
        }
    });
    sprintNameEl.addEventListener('input', () => {
        autoGeneratedSprintName = false;
    });

    const sprintDurationDays = await getSprintDurationDays();
    console.log(sprintDurationDays);
    const startDateEl = document.getElementById('id_start_date');
    const endDateEl = document.getElementById('id_end_date');
    startDateEl.addEventListener('input', () => {
        const startValue = startDateEl.value;
        if (!startValue) return;
        const startDate = new Date(startValue);
        const endDate = new Date(startDate);
        endDate.setDate(endDate.getDate() + parseInt(sprintDurationDays, 10) - 1);
        const formatted = endDate.toISOString().split('T')[0];
        endDateEl.value = formatted;
    });
}

async function initEditView() {
    setPageTitle('Edit Sprint');
    await populateFySelect();
    wireEndDateMonthHint();
    if (!sprintPk) return;
    try {
        const sprint = await apiFetch(API_URLS.sprints.detail(sprintPk).href, { method: 'GET' });
        populateForm(sprint);
    } catch (err) {
        showFlash('Could not load sprint data. Please refresh.', 'danger');
    }
}

async function populateFySelect(selectedId = null) {
    try {
        const opts = await apiFetch(API_URLS.sprints.options.href, { method: 'GET' });
        const sel  = document.getElementById('id_financial_year');
        if (!sel) return;
        (opts.financial_years ?? []).forEach(({ value, label, is_active }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            if (is_active && !selectedId) opt.selected = true;
            if (selectedId && value === selectedId) opt.selected = true;
            sel.appendChild(opt);
        });
    } catch (err) {
        console.error('[populateFySelect]', err);
    }
}

function wireEndDateMonthHint() {
    const endDateEl = document.getElementById('id_end_date');
    const hintEl    = document.getElementById('month-hint');
    if (!endDateEl || !hintEl) return;
    endDateEl.addEventListener('change', () => {
        const val = endDateEl.value;
        if (!val) { hintEl.textContent = ''; return; }
        const month = new Date(val + 'T00:00:00').getMonth() + 1;
        hintEl.textContent = `Sprint month will be set to ${MONTHS[month]}.`;
    });
}

function populateForm(sprint) {
    document.getElementById('page-title').textContent    = 'Edit Sprint';
    document.getElementById('page-subtitle').innerHTML  = `Updating <strong>${escHtml(sprint.sprint_name)}</strong>`;
    document.getElementById('submit-label').textContent  = 'Save changes';

    // Populate FY select selection
    const fySelect = document.getElementById('id_financial_year');
    if (fySelect) fySelect.value = sprint.financial_year;

    document.getElementById('id_sprint_number').value = sprint.sprint_number ?? '';
    document.getElementById('id_sprint_name').value   = sprint.sprint_name   ?? '';
    document.getElementById('id_start_date').value    = sprint.start_date    ?? '';
    document.getElementById('id_end_date').value      = sprint.end_date      ?? '';
    document.getElementById('id_notes').value         = sprint.notes         ?? '';
    document.getElementById('id_is_active').checked   = sprint.is_active     ?? false;

    // Show month hint
    const hintEl = document.getElementById('month-hint');
    if (hintEl && sprint.month) {
        hintEl.textContent = `Sprint month: ${MONTHS[sprint.month] ?? sprint.month}.`;
    }

    // Metadata card
    const metaCard = document.getElementById('metadata-card');
    if (metaCard) {
        metaCard.classList.remove('d-none');
        document.getElementById('meta-month').textContent      = sprint.month ?? '—';
        document.getElementById('meta-overridden').textContent = sprint.is_overridden ? 'Yes' : 'No';
        document.getElementById('meta-created').textContent    = formatDateTime(sprint.created_at);
        document.getElementById('meta-updated').textContent    = formatDateTime(sprint.updated_at);
    }

    // Delete button
    const slot = document.getElementById('delete-btn-slot');
    if (slot) {
        slot.innerHTML = `
            <button type="button" class="btn btn-outline-danger" id="delete-sprint-btn">
                <i class="bi bi-trash me-1"></i>Delete
            </button>`;
        document.getElementById('delete-sprint-btn').addEventListener('click', () => {
            confirmDelete(sprint.id, sprint.sprint_name, onDeleteFromEdit);
        });
    }
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['financial_year', 'sprint_number', 'sprint_name', 'start_date', 'end_date']);

    const payload = {
        financial_year: parseInt(document.getElementById('id_financial_year').value, 10) || null,
        sprint_number:  parseInt(document.getElementById('id_sprint_number').value, 10)  || null,
        sprint_name:    document.getElementById('id_sprint_name').value.trim()           || null,
        start_date:     document.getElementById('id_start_date').value                  || null,
        end_date:       document.getElementById('id_end_date').value                    || null,
        notes:          document.getElementById('id_notes').value.trim(),
        is_active:      document.getElementById('id_is_active').checked,
    };

    const method = isEdit ? 'PATCH' : API_URLS.sprints.new.method;
    const url    = isEdit
        ? API_URLS.sprints.partial_edit(sprintPk).href
        : API_URLS.sprints.new.href;

    setSubmitting(true);
    try {
        await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.sprints.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['financial_year', 'sprint_number', 'sprint_name', 'start_date', 'end_date']);
            const banner = document.getElementById('form-error-banner');
            if (banner) {
                console.log(err);
                const msg = err.data?.details || err.data?.error || 'Please correct the errors above.';
                banner.textContent = msg;
                banner.classList.remove('d-none');
            }
            return;
        }
        if (err?.status === 404) {
            showFlash('This sprint no longer exists. Redirecting…', 'warning');
            setTimeout(() => { window.location.href = URLS.sprints.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || `Unexpected error (${err?.status}). Please try again.`, 'danger');
    } finally {
        setSubmitting(false);
    }
}

function onDeleteFromEdit() {
    window.location.href = URLS.sprints.list;
}

// ═══════════════════════════════════════════════════════════════════════════
// Detail View
// ═══════════════════════════════════════════════════════════════════════════

async function initDetailView() {
    if (!sprintPk) return;
    setPageTitle('Sprint');

    try {
        const sprint = await apiFetch(API_URLS.sprints.detail(sprintPk).href, { method: 'GET' });
        renderDetailHeader(sprint);
        renderDetailBody(sprint);
        renderSprintTimer(sprint);
    } catch (err) {
        if (err?.status === 404) {
            showFlash('This sprint no longer exists. Redirecting…', 'warning');
            setTimeout(() => { window.location.href = URLS.sprints.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load sprint details. Please refresh.', 'danger');
    }

    checkCompareReady();

    // Rebuild capacity button
    const rebuildBtn = document.getElementById('rebuild-capacity-btn');
    if (rebuildBtn) {
        rebuildBtn.addEventListener('click', () => {
            bootstrap.Modal.getOrCreateInstance(
                document.getElementById('rebuildConfirmModal')
            ).show();
        });
    }

    const confirmRebuildBtn = document.getElementById('confirm-rebuild-btn');
    if (confirmRebuildBtn) {
        confirmRebuildBtn.addEventListener('click', async () => {
            confirmRebuildBtn.disabled  = true;
            confirmRebuildBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Recalculating…';
            bootstrap.Modal.getInstance(document.getElementById('rebuildConfirmModal'))?.hide();
            try {
                await apiFetch(API_URLS.sprint_capacity.rebuild.href, {
                    method: 'POST',
                    body: JSON.stringify({ sprint_id: sprintPk }),
                });
                showFlash('Capacity recalculated.', 'success');
                loadCapacityTable(1);
            } catch (err) {
                showFlash('Recalculation failed. Please try again.', 'danger');
            } finally {
                confirmRebuildBtn.disabled  = false;
                confirmRebuildBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Recalculate';
            }
        });
    }

    // Team filter for capacity table
    const teamFilter = document.getElementById('team-filter');
    if (teamFilter) {
        await populateTeamFilter(teamFilter);
        teamFilter.addEventListener('change', () => loadCapacityTable(1));
    }

    loadCapacityTable(1);
}

async function checkCompareReady() {
    try {
        const [fcStatus, acStatus] = await Promise.all([
            apiFetch(API_URLS.sprint_forecast.sprint_status(sprintPk).href, { method: 'GET' }),
            apiFetch(API_URLS.sprint_actuals.sprint_status(sprintPk).href, { method: 'GET' }),
        ]);
        if (fcStatus.review_complete && acStatus.review_complete) {
            document.getElementById('compare-btn')?.classList.remove('d-none');
        }
    } catch (_err) {
        // silently ignore — Compare button remains hidden
    }
}

function renderDetailHeader(sprint) {
    document.getElementById('sprint-name').textContent    = sprint.sprint_name;
    document.getElementById('edit-sprint-btn').href       = URLS.sprints.edit(sprintPk);

    const statusEl = document.getElementById('sprint-status');
    if (sprint.is_active) {
        statusEl.textContent = 'Active';
        statusEl.classList.add('rp-badge--success');
    } else {
        const today = new Date().toISOString().slice(0, 10);
        if (sprint.end_date < today) {
            statusEl.textContent = 'Completed';
            statusEl.classList.add('rp-badge--muted');
        } else {
            statusEl.textContent = 'Future';
            statusEl.classList.add('rp-badge--info');
            // Show "Set Active" button only for non-active sprints
//            const setActiveBtn = document.getElementById('set-active-btn');
//            if (setActiveBtn) setActiveBtn.classList.remove('d-none');
        }
    }

    const ovrEl = document.getElementById('sprint-overridden');
    if (sprint.is_overridden && ovrEl) ovrEl.classList.remove('d-none');

    // Set Active button — mirror FY detail pattern exactly:
    // show only when not already active; wire the modal rather than firing directly
    const setActiveBtn  = document.getElementById('set-active-btn');
    const modalLabel    = document.getElementById('set-active-sprint-label');
    const confirmBtn    = document.getElementById('confirm-set-active-btn');

    if (!sprint.is_active && setActiveBtn) {
        setActiveBtn.classList.remove('d-none');
        if (modalLabel) modalLabel.textContent = sprint.sprint_name;
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () =>
                handleSetActive(sprint.id, sprint.sprint_name)
            );
        }
    }
}

function renderDetailBody(sprint) {
    const sub = document.getElementById('sprint-subtitle');
    if (sub) sub.textContent = sprint.fy_long ?? sprint.fy_short ?? '';

    document.getElementById('sprint-fy').textContent       = sprint.fy_long ?? '—';
    document.getElementById('sprint-number').textContent   = sprint.sprint_number ?? '—';
    document.getElementById('sprint-start').textContent    = sprint.start_date    ?? '—';
    document.getElementById('sprint-end').textContent      = sprint.end_date      ?? '—';
    document.getElementById('sprint-month').textContent    = sprint.month ?? '—';
    document.getElementById('sprint-notes').textContent    = sprint.notes         || '—';
    document.getElementById('meta-created').textContent    = formatDateTime(sprint.created_at);
    document.getElementById('meta-updated').textContent    = formatDateTime(sprint.updated_at);

    // Duration in working days (Mon–Fri between start and end)
    const start  = new Date(sprint.start_date + 'T00:00:00');
    const end    = new Date(sprint.end_date   + 'T00:00:00');
    const calDays = Math.round((end - start) / 86400000) + 1;
    document.getElementById('sprint-duration').textContent = `${calDays} calendar day${calDays !== 1 ? 's' : ''}`;
}

async function handleSetActive(id, name) {
    const confirmBtn = document.getElementById('confirm-set-active-btn');
    if (!confirmBtn) return;

    confirmBtn.disabled  = true;
    confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Setting…';

    try {
        const { method, href } = API_URLS.sprints.set_active(id);
        await apiFetch(href, { method });
        bootstrap.Modal.getInstance(document.getElementById('setActiveModal'))?.hide();
        showFlash(`${name} is now the active sprint.`, 'success');
        // Reload to reflect updated status badge + hide the Set Active button
        window.location.reload();
    } catch (err) {
        bootstrap.Modal.getInstance(document.getElementById('setActiveModal'))?.hide();
        showFlash(err?.data?.error || 'Failed to set active sprint.', 'danger');
    } finally {
        confirmBtn.disabled  = false;
        confirmBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Set as Active';
    }
}

// ── Sprint Countdown Timer ─────────────────────────────────────────────────

function renderSprintTimer(sprint) {
    console.log(sprint);
    const card    = document.getElementById('sprint-timer-card');
    const display = document.getElementById('timer-display');
    const label   = document.getElementById('timer-label');
    const progress = document.getElementById('timer-progress');
    const datesEl  = document.getElementById('timer-dates');
    if (!card || !display) return;

    const start = new Date(sprint.start_date + 'T00:00:00');
    const end   = new Date(sprint.end_date   + 'T00:00:00');

    function tick() {
        const now   = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

        const totalMs    = end - start;
        const elapsedMs  = today - start;
        const remainDays = sprint.remaining_days;
//        const remainMs   = end - today;
//        const remainDays = Math.ceil(remainMs / 86400000);

        if (today < start) {
            const startsIn = Math.ceil((start - today) / 86400000);
            display.textContent = startsIn;
            label.textContent   = `day${startsIn !== 1 ? 's' : ''} until sprint starts`;
            progress.style.width = '0%';
            progress.style.background = 'var(--color-text-2)';
        } else if (today > end) {
            display.textContent = 'Done';
            label.textContent   = 'This sprint has ended.';
            progress.style.width = '100%';
            progress.style.background = 'var(--color-text-2)';
        } else {
            const pct = Math.min(100, Math.round((elapsedMs / totalMs) * 100));
            display.textContent = Math.max(remainDays, 0);
            label.textContent   = `day${remainDays !== 1 ? 's' : ''} remaining`;
            progress.style.width = pct + '%';
            // Colour: green→amber→red as sprint runs out
            progress.style.background = pct < 50
                ? '#22c55e'
                : pct < 80
                    ? '#f59e0b'
                    : '#ef4444';
            display.style.color = pct < 50
                ? '#22c55e'
                : pct < 80
                    ? '#f59e0b'
                    : '#ef4444';
        }

        if (datesEl) {
            datesEl.textContent = `${sprint.start_date} – ${sprint.end_date}`;
        }
    }

    tick();
    // Refresh once per minute (no need for seconds)
    setInterval(tick, 60_000);
}

// ── Capacity Table ─────────────────────────────────────────────────────────

let capacityPage = 1;

async function loadCapacityTable(page = 1) {
    capacityPage = page;
    const teamId = document.getElementById('team-filter')?.value;
    let url = `${API_URLS.sprints.capacity(sprintPk).href}?page=${page}&page_size=50`;
    if (teamId) url += `&team_id=${teamId}`;

    const tbody = document.getElementById('capacity-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-secondary py-3">Loading…</td></tr>';

    try {
        const res = await apiFetch(url, { method: 'GET' });
        if (!res.results?.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-secondary py-3">No capacity data. Try recalculating.</td></tr>';
        } else {
            tbody.innerHTML = res.results.map(row => `
                <tr>
                    <td class="fw-500">${escHtml(row.member_name)}</td>
                    <td class="text-secondary">${escHtml(row.team_name ?? '—')}</td>
                    <td class="text-secondary">${escHtml(row.location_name ?? '—')}</td>
                    <td class="text-center">${row.working_days}</td>
                    <td class="text-center text-secondary">${row.holiday_days}</td>
                    <td class="text-center text-secondary">${row.leave_days}</td>
                    <td class="text-center">
                        <span class="fw-600 ${_netCapacityClass(row.net_capacity)}">
                            ${row.net_capacity}
                        </span>
                    </td>
                </tr>
            `).join('');
        }

        renderCapacityPagination(res.pagination);
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-3">Failed to load capacity data.</td></tr>';
    }
}

function _netCapacityClass(val) {
//    const n = parseFloat(val);
//    if (n <= 0) return 'text-danger';
//    if (n <= 3) return 'text-warning';
//    return 'text-success';
    return '';
}

function renderCapacityPagination(pagination) {
    const bar     = document.getElementById('capacity-pagination-bar');
    const infoEl  = document.getElementById('capacity-pagination-info');
    const ctrlEl  = document.getElementById('capacity-pagination-controls');
    if (!bar || !infoEl || !ctrlEl) return;

    if (!pagination || pagination.total_pages <= 1) {
        bar.style.display = 'none';
        return;
    }

    bar.style.display = '';
    infoEl.textContent = `${pagination.total_count} members`;
    ctrlEl.innerHTML   = '';

    for (let p = 1; p <= pagination.total_pages; p++) {
        const li = document.createElement('li');
        li.className = `page-item${p === pagination.current_page ? ' active' : ''}`;
        const btn = document.createElement('button');
        btn.className = 'page-link';
        btn.textContent = p;
        btn.addEventListener('click', () => loadCapacityTable(p));
        li.appendChild(btn);
        ctrlEl.appendChild(li);
    }
}

async function populateTeamFilter(select) {
    try {
        // Use delivery-teams options endpoint
        const res = await apiFetch('/api/v1/delivery-teams/?page_size=200', { method: 'GET' });
        (res.results ?? []).forEach(team => {
            const opt = document.createElement('option');
            opt.value = team.id;
            opt.textContent = team.name;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[populateTeamFilter]', err);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Delete Modal — shared across list & form views
// ═══════════════════════════════════════════════════════════════════════════

function confirmDelete(id, name, onSuccess) {
    const modal  = document.getElementById('deleteModal');
    const nameEl = document.getElementById('delete-sprint-name');
    const btn    = document.getElementById('confirm-delete-btn');
    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);

    newBtn.addEventListener('click', async () => {
        newBtn.disabled    = true;
        newBtn.textContent = 'Deleting…';
        try {
            await apiFetch(API_URLS.sprints.delete(id).href, { method: 'DELETE' });
            bootstrap.Modal.getInstance(modal)?.hide();
            onSuccess(id, name);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            if (err?.status === 404) {
                showFlash(`Sprint "${name}" was not found — it may already have been deleted.`, 'warning');
                document.querySelector(`tr[data-sprint-id="${id}"]`)?.remove();
                fetcher?.refresh();
                return;
            }
            showFlash(err?.data?.detail || `Failed to delete sprint "${name}". Please try again.`, 'danger');
        } finally {
            newBtn.disabled    = false;
            newBtn.textContent = 'Delete';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

// ═══════════════════════════════════════════════════════════════════════════
// Window Exports
// ═══════════════════════════════════════════════════════════════════════════

window.confirmDelete    = confirmDelete;
window.confirmSetActive = confirmSetActive;
window.onDeleteFromList = onDeleteFromList;
window.onDeleteFromEdit = onDeleteFromEdit;