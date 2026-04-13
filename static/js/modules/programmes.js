'use strict';

import { initFetch } from './../list/fetch.js';
import { initRenderer } from './../list/render.js';
import { initSorting } from './../list/sort.js';
import { apiFetch, escAttr, escHtml, formatDateTime, setPageTitle, showFlash } from './../main.js';
import { API_URLS, URLS } from './../urls.js';
import { exportToCsv, exportToPdf } from '../export.js';

const LIST_EXPORT_COLUMNS = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'description', label: 'Description' },
    { key: 'is_active', label: 'Active' },
];

const RISK_BADGE = {
    GREEN: '<span class="rp-badge rp-badge--success">OB</span>',
    AMBER: '<span class="rp-badge rp-badge--warning">AR</span>',
    RED: '<span class="rp-badge rp-badge--danger">OVR</span>',
};

let _progId = null;
let _fyId = null;
let _projPage = 1;

document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('prog-tbody')) return;
    initListView();
});

async function initListView() {
    setPageTitle('Programmes');
    _mountViewModal();
    await loadStats();
    renderStatusFilterOptions();
    bindToolbarEvents();
    bindModalEvents();
    initTable();
}

function _mountViewModal() {
    const modal = document.getElementById('progViewModal');
    const parent = document.querySelector('.rp-main');
    if (!modal || !parent) return;

    parent.appendChild(modal);
    _setViewModalOffset(modal);

    window.addEventListener('resize', () => _setViewModalOffset(modal), { passive: true });
}

function _setViewModalOffset(modal) {
    const header = document.querySelector('.rp-page-header');
    const offset = header ? header.offsetTop + header.offsetHeight : 0;
    modal.style.top = `${offset}px`;
    modal.style.height = `calc(100% - ${offset}px)`;
}

async function loadStats() {
    try {
        const { method, href } = API_URLS.programmes.stats;
        const data = await apiFetch(href, { method });
        document.getElementById('stat-total').textContent = data.total_programmes ?? '—';
        document.getElementById('stat-active').textContent = data.active_programmes ?? '—';
        document.getElementById('stat-inactive').textContent = data.inactive_programmes ?? '—';
    } catch (err) {
        console.error('[loadStats] Failed to load stats.', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.programmes.options;
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

function bindToolbarEvents() {
    document.getElementById('add-programme-btn')?.addEventListener('click', () => openAddModal());
    document.getElementById('export-csv')?.addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf')?.addEventListener('click', () => runListExport('pdf'));
}

function initTable() {
    const { method, href } = API_URLS.programmes.list;

    const renderer = initRenderer({
        tbodyId: 'prog-tbody',
        colspan: 4,
        itemLabel: 'programmes',
        rowTemplate: renderProgrammeRow,
        emptyState: {
            message: 'No programmes yet.',
            link: { href: '#', label: 'Add the first one', onClick: 'openAddModal()' },
        },
        filterEmptyState: {
            message: 'No programmes match your filters.',
            link: { href: '#', label: 'Create a new one', onClick: 'openAddModal()' },
        },
        paginationBarId: 'prog-pagination-bar',
        paginationInfoId: 'prog-pagination-info',
        paginationControlsId: 'prog-pagination-controls',
        onPageChange: (page) => fetcher.goToPage(page),
    });

    const fetcher = initFetch({
        apiUrl: href,
        pageSize: 20,
        searchInputId: 'prog-search',
        filters: [{ id: 'status-filter', param: 'is_active' }],
        onLoadStart: () => renderer.renderLoading('Loading programmes…'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.values(state.filters).some((v) => v !== '');
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load programmes. Please refresh the page.'),
    });

    initSorting({ tableId: 'prog-table', fetcher });
    fetcher.refresh();

    window._progFetcher = fetcher;
}

function renderProgrammeRow(prog) {
    const activeBtnTitle = prog.is_active ? 'Deactivate programme' : 'Activate programme';
    const activeBtnClass = prog.is_active ? 'btn-ghost-icon--danger' : 'btn-ghost-icon--success';

    if (prog.is_protected) {
        return `
            <tr data-programme-id="${prog.id}">
                <td class="fw-medium">
                    <a href="#" class="rp-link fw-500" onclick="openViewModal(${prog.id}); return false;">
                        ${escHtml(prog.name)}
                    </a>
                    <span class="rp-badge rp-badge--muted ms-1" title="Default programme — cannot be modified">Default</span>
                </td>
                <td>${escHtml(prog.description ?? '')}</td>
                <td class="text-center">
                    ${
                        prog.is_active
                            ? '<span class="rp-badge rp-badge--success">Active</span>'
                            : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                    }
                </td>
                <td class="text-center">
                    <div class="d-flex justify-content-center gap-1">
                        <button class="btn btn-ghost-icon" title="View programme"
                                onclick="openViewModal(${prog.id})">
                            <i class="bi bi-eye"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }

    return `
        <tr data-programme-id="${prog.id}">
            <td class="fw-medium">
                <a href="#" class="rp-link fw-500" onclick="openViewModal(${prog.id}); return false;">
                    ${escHtml(prog.name)}
                </a>
            </td>
            <td>${escHtml(prog.description ?? '')}</td>
            <td class="text-center">
                ${
                    prog.is_active
                        ? '<span class="rp-badge rp-badge--success">Active</span>'
                        : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <button class="btn btn-ghost-icon" title="View programme"
                            onclick="openViewModal(${prog.id})">
                        <i class="bi bi-eye"></i>
                    </button>
                    <button class="btn btn-ghost-icon" title="Edit programme"
                            onclick="openEditModal(${prog.id}, '${escAttr(prog.name)}', '${escAttr(prog.description)}')">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-ghost-icon ${activeBtnClass}" title="${activeBtnTitle}"
                            onclick="openActiveModal(${prog.id}, '${escAttr(prog.name)}', ${prog.is_active})">
                        <i class="bi bi-check-circle"></i>
                    </button>
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger" title="Delete programme"
                            onclick="openDeleteModal(${prog.id}, '${escAttr(prog.name)}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function bindModalEvents() {
    document.getElementById('progModal')?.addEventListener('hidden.bs.modal', resetAddEditModal);
    document.getElementById('prog-modal-save')?.addEventListener('click', handleModalSave);
    document.getElementById('confirm-active-btn')?.addEventListener('click', handleConfirmActive);
    document.getElementById('confirm-delete-btn')?.addEventListener('click', handleConfirmDelete);
}

async function openViewModal(id) {
    _progId = id;
    _fyId = null;
    _projPage = 1;

    const modal = document.getElementById('progViewModal');
    if (modal) {
        _setViewModalOffset(modal);

        modal.style.setProperty('padding', '3px', 'important');
        const content = modal.querySelector('.modal-content');
        if (content) content.style.borderRadius = '15px';

        const top = modal.offsetTop;
        window.scrollTo({ top, behavior: 'smooth' });
    }

    _renderViewLoading();
    _showModal('progViewModal');

    try {
        const { method, href } = API_URLS.programmes.detail(id);
        const prog = await apiFetch(href, { method });
        await _renderViewContent(prog);
    } catch (err) {
        _renderViewError('Failed to load programme details. Please try again.');
        console.error('[openViewModal] Failed to fetch programme.', err);
    }
}

function _renderViewLoading() {
    document.getElementById('prog-view-title').textContent = 'Programme';
    document.getElementById('prog-view-edit-btn').classList.add('d-none');
    document.getElementById('prog-view-delete-btn').classList.add('d-none');
    document.getElementById('prog-view-body').innerHTML = `
        <div class="d-flex align-items-center justify-content-center py-5 text-secondary">
            <div class="spinner-border spinner-border-sm me-2" role="status"></div>
            Loading…
        </div>`;
    document.getElementById('prog-view-title').textContent = 'Programme';
    document.getElementById('prog-view-edit-btn').classList.add('d-none');
}

function _renderViewError(message) {
    document.getElementById('prog-view-body').innerHTML = `
        <div class="d-flex align-items-center justify-content-center py-5 text-danger">
            <i class="bi bi-exclamation-circle me-2"></i>${escHtml(message)}
        </div>`;
}

async function _renderViewContent(prog) {
    const editBtn = document.getElementById('prog-view-edit-btn');
    if (prog.is_protected) {
        editBtn.classList.add('d-none');
    } else {
        editBtn.classList.remove('d-none');
        editBtn.onclick = () => {
            _hideModal('progViewModal');
            openEditModal(prog.id, prog.name, prog.description ?? '');
        };
    }

    const deleteBtn = document.getElementById('prog-view-delete-btn');
    if (prog.is_protected) {
        deleteBtn.classList.add('d-none');
    } else {
        deleteBtn.classList.remove('d-none');
        deleteBtn.onclick = () => {
            _hideModal('progViewModal');
            openDeleteModal(prog.id, prog.name);
        };
    }

    const createdAt = prog.created_at ? formatDateTime(prog.created_at) : '—';
    const updatedAt = prog.updated_at ? formatDateTime(prog.updated_at) : '—';

    const statusBadge = prog.is_active
        ? '<span class="rp-badge rp-badge--success">Active</span>'
        : '<span class="rp-badge rp-badge--muted">Inactive</span>';

    const protectedBadge = prog.is_protected
        ? '<span class="rp-badge rp-badge--muted ms-2" title="Default programme — cannot be modified">Default</span>'
        : '';

    const descriptionHtml = prog.description
        ? `<p class="mb-0" style="white-space: pre-wrap;">${escHtml(prog.description)}</p>`
        : `<p class="mb-0 text-secondary fst-italic">No description provided.</p>`;

    document.getElementById('prog-view-title').innerHTML = `
        <i class="bi bi-collection me-2 opacity-50"></i>
        <span class="me-1">${prog.name}</span><span class="me-1">${statusBadge}</span><span>${protectedBadge}</span>
    `;

    document.getElementById('prog-view-body').innerHTML = `
        <div class="row g-4 rp-view-layout">
            <div class="col-lg-8 rp-view-main">
                <div class="rp-view-section">
                    <h6 class="rp-view-section-title">Details</h6>
                    <div class="rp-view-field rp-view-field--block">
                        <span class="rp-view-label">Description</span>
                        <div class="rp-view-value rp-view-description">
                            ${descriptionHtml}
                        </div>
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
        </div>

        <div class="rp-card mt-3">
            <div id="prog-view-projects-panel">
                <div class="d-flex align-items-center justify-content-between mb-3 flex-wrap gap-2">
                    <h6 class="rp-view-section-title mb-0">
                        <i class="bi bi-folder2 me-2 opacity-50"></i>Projects
                    </h6>
                    <select id="prog-view-fy-select" class="form-select form-select-sm rp-select" style="width:auto;min-width:150px;">
                        <option value="">Loading…</option>
                    </select>
                </div>

                <div class="row g-2 mb-3" id="prog-view-summary-cards">
                    ${_summaryCardsSkeleton()}
                </div>

                <div class="rp-table-wrap">
                    <table class="table rp-table rp-table--sm mb-0">
                        <thead>
                            <tr>
                                <th>Project</th>
                                <th>Status</th>
                                <th>Team</th>
                                <th>Financial Year</th>
                                <th class="text-end">Actual Budget</th>
                                <th class="text-end">Estimate Cost</th>
                                <th class="text-end">Remaining</th>
                                <th class="text-end">Risk %</th>
                                <th class="text-center">Risk</th>
                            </tr>
                        </thead>
                        <tbody id="prog-view-proj-tbody">${_projLoadingRow()}</tbody>
                    </table>
                </div>

                <div class="rp-pagination-bar d-flex align-items-center justify-content-between px-1 pt-3 flex-wrap gap-2"
                    id="prog-view-proj-pagination-bar" style="display:none!important">
                    <span class="rp-pagination-info text-secondary small" id="prog-view-proj-pagination-info"></span>
                    <nav>
                        <ul class="rp-pagination-controls pagination pagination-sm mb-0"
                            id="prog-view-proj-pagination-controls"></ul>
                    </nav>
                </div>
            </div>
        </div>`;

    await _loadFyOptions(prog.id);
}

async function _loadFyOptions(progId) {
    const select = document.getElementById('prog-view-fy-select');
    if (!select) return;

    try {
        const { method, href } = API_URLS.financial_years.list;
        const data = await apiFetch(href, { method });
        const fys = data.results ?? [];

        select.innerHTML = '';
        const lifetimeOpt = document.createElement('option');
        lifetimeOpt.value = '';
        lifetimeOpt.textContent = 'Lifetime';
        select.appendChild(lifetimeOpt);

        let currentFyId = null;
        (fys ?? []).forEach((fy) => {
            const opt = document.createElement('option');
            opt.value = fy.id;
            opt.textContent = fy.label ?? fy.short_fy ?? fy.long_fy ?? String(fy.id);
            if (fy.is_active) {
                opt.selected = true;
                currentFyId = fy.id;
            }
            select.appendChild(opt);
        });

        _fyId = currentFyId;

        select.addEventListener('change', () => {
            _fyId = select.value ? parseInt(select.value, 10) : null;
            _projPage = 1;
            _loadSummary(progId);
        });
    } catch (err) {
        console.error('[_loadFyOptions]', err);
        select.innerHTML = '<option value="">Lifetime</option>';
        _fyId = null;
    }

    _loadSummary(progId);
}

async function _loadSummary(progId) {
    const tbody = document.getElementById('prog-view-proj-tbody');
    if (tbody) tbody.innerHTML = _projLoadingRow();
    _renderSummaryCards(null);

    try {
        const { method, href } = API_URLS.programmes.summary(progId);
        const params = new URLSearchParams({ page: _projPage, page_size: 20 });
        if (_fyId) params.set('fy', _fyId);

        const data = await apiFetch(`${href}?${params}`, { method });

        _renderSummaryCards(data.summary ?? null);
        _renderProjRows(data.results ?? []);
        _renderProjPagination(data);
    } catch (err) {
        if (tbody)
            tbody.innerHTML = `
            <tr><td colspan="9" class="text-center text-danger py-3">
                <i class="bi bi-exclamation-circle me-1"></i>Failed to load projects.
            </td></tr>`;
        console.error('[_loadSummary]', err);
    }
}

function _summaryCardsSkeleton() {
    return ['Actual Budget', 'Estimate Cost', 'Remaining', 'Risk']
        .map(
            (label) => `
        <div class="col-6 col-md-3">
            <div class="rp-stat-card">
                <span class="rp-stat-label">${label}</span>
                <span class="rp-stat-value text-secondary">—</span>
            </div>
        </div>`,
        )
        .join('');
}

function _renderSummaryCards(summary) {
    const el = document.getElementById('prog-view-summary-cards');
    if (!el) return;
    if (!summary) {
        el.innerHTML = _summaryCardsSkeleton();
        return;
    }

    const riskBadge = summary.risk ? (RISK_BADGE[summary.risk] ?? '—') : '—';
    const riskPct = summary.risk_pct != null ? `${Number(summary.risk_pct).toFixed(1)}%` : '—';
    const remNeg =
        summary.total_remaining_budget != null && Number(summary.total_remaining_budget) < 0;

    el.innerHTML = `
        <div class="col-6 col-md-3">
            <div class="rp-stat-card">
                <span class="rp-stat-label">Actual Budget</span>
                <span class="rp-stat-value">${_fmtAmt(summary.actual_budget)}</span>
            </div>
        </div>
        <div class="col-6 col-md-3">
            <div class="rp-stat-card">
                <span class="rp-stat-label">Estimate Cost</span>
                <span class="rp-stat-value">${_fmtAmt(summary.estimated_cost)}</span>
            </div>
        </div>
        <div class="col-6 col-md-3">
            <div class="rp-stat-card">
                <span class="rp-stat-label">Remaining</span>
                <span class="rp-stat-value ${remNeg ? 'text-danger' : ''}">${_fmtAmt(summary.remaining_budget)}</span>
            </div>
        </div>
        <div class="col-6 col-md-3">
            <div class="rp-stat-card">
                <span class="rp-stat-label">Risk (${riskPct})</span>
                <span class="rp-stat-value">${riskBadge}</span>
            </div>
        </div>`;
}

function _renderProjRows(results) {
    const tbody = document.getElementById('prog-view-proj-tbody');
    if (!tbody) return;

    if (!results.length) {
        tbody.innerHTML = `
            <tr><td colspan="9" class="text-center py-4 text-secondary">
                <i class="bi bi-folder2-open fs-4 d-block mb-2 opacity-50"></i>
                No projects found for this selection.
            </td></tr>`;
        return;
    }

    tbody.innerHTML = results
        .map((p) => {
            const remNeg = p.remaining_budget != null && Number(p.remaining_budget) < 0;
            const riskBadge = p.risk ? (RISK_BADGE[p.risk] ?? '—') : '—';
            const riskPct = p.risk_pct != null ? `${Number(p.risk_pct).toFixed(1)}%` : '—';

            return `
        <tr>
            <td><a href="${URLS.projects.detail(p.id)}" class="rp-link">${escHtml(p.name)}</a></td>
            <td><span class="rp-badge ${_statusBadgeCls(p.status)}">${escHtml(p.status)}</span></td>
            <td>${p.assigned_team ? escHtml(p.assigned_team) : '—'}</td>
            <td class="text-secondary small">${p.financial_year ? escHtml(p.financial_year) : '—'}</td>
            <td class="text-end"><span class="rp-basis-amount">${_fmtAmt(p.actual_budget)}</span></td>
            <td class="text-end"><span class="rp-basis-amount">${_fmtAmt(p.estimate_total_cost)}</span></td>
            <td class="text-end"><span class="rp-basis-amount ${remNeg ? ' text-danger fw-semibold' : ''}">
                ${_fmtAmt(p.remaining_budget)}
            </span></td>
            <td class="text-end"><span class="rp-code" style="font-size: 0.75rem;">${riskPct}</span></td>
            <td class="text-center">${riskBadge}</td>
        </tr>`;
        })
        .join('');
}

function _renderProjPagination(data) {
    const bar = document.getElementById('prog-view-proj-pagination-bar');
    const infoEl = document.getElementById('prog-view-proj-pagination-info');
    const controls = document.getElementById('prog-view-proj-pagination-controls');
    if (!bar) return;

    const { total_count, total_pages, current_page, has_next, has_previous } = data;
    if (!total_count || total_pages <= 1) {
        bar.style.setProperty('display', 'none', 'important');
        return;
    }
    bar.style.removeProperty('display');

    if (infoEl) {
        const start = (current_page - 1) * 20 + 1;
        const end = Math.min(current_page * 20, total_count);
        infoEl.textContent = `${start}–${end} of ${total_count}`;
    }

    if (controls) {
        let html = `<li class="page-item ${!has_previous ? 'disabled' : ''}">
            <button class="page-link" data-p="${current_page - 1}">&laquo;</button></li>`;
        for (let p = 1; p <= total_pages; p++) {
            html += `<li class="page-item ${p === current_page ? 'active' : ''}">
                <button class="page-link" data-p="${p}">${p}</button></li>`;
        }
        html += `<li class="page-item ${!has_next ? 'disabled' : ''}">
            <button class="page-link" data-p="${current_page + 1}">&raquo;</button></li>`;
        controls.innerHTML = html;
        controls.querySelectorAll('button[data-p]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const pg = parseInt(btn.dataset.p, 10);
                if (pg >= 1 && pg <= total_pages) {
                    _projPage = pg;
                    _loadSummary(_progId);
                }
            });
        });
    }
}

function _projLoadingRow() {
    return `<tr><td colspan="9" class="text-center py-3 text-secondary">
        <span class="spinner-border spinner-border-sm me-2" role="status"></span>Loading…
    </td></tr>`;
}

function _fmtMoney(val) {
    if (val == null) return '—';
    return `£${Number(val).toLocaleString('en-GB', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

const _fmtAmt = (v, fallback = '—') =>
    v == null
        ? fallback
        : `£${parseFloat(v).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function _statusBadgeCls(status) {
    const map = {
        New: 'rp-badge--muted',
        'In Progress': 'rp-badge--success',
        'On Hold': 'rp-badge--warning',
        Completed: 'rp-badge',
        Cancelled: 'rp-badge--danger',
    };
    return map[status] ?? 'rp-badge--muted';
}

function openAddModal() {
    resetAddEditModal();
    document.getElementById('prog-modal-title').textContent = 'Add Programme';
    document.getElementById('prog-modal-save').dataset.mode = 'add';
    delete document.getElementById('prog-modal-save').dataset.id;
    _showModal('progModal');
    setTimeout(() => document.getElementById('prog-modal-name').focus(), 300);
}

function openEditModal(id, name, description) {
    resetAddEditModal();
    document.getElementById('prog-modal-title').textContent = 'Edit Programme';
    document.getElementById('prog-modal-name').value = name;
    document.getElementById('prog-modal-description').value = description;
    document.getElementById('prog-modal-save').dataset.mode = 'edit';
    document.getElementById('prog-modal-save').dataset.id = id;
    _showModal('progModal');
    setTimeout(() => document.getElementById('prog-modal-name').focus(), 300);
}

function resetAddEditModal() {
    document.getElementById('prog-modal-name').value = '';
    document.getElementById('prog-modal-description').value = '';
    clearAddEditModalErrors();
}

function clearAddEditModalErrors() {
    document.getElementById('prog-modal-banner').classList.add('d-none');
    ['prog-modal-name', 'prog-modal-description'].forEach((id) => {
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
    const el = document.getElementById('prog-modal-banner');
    el.textContent = message;
    el.classList.remove('d-none');
}

async function handleModalSave() {
    const saveBtn = document.getElementById('prog-modal-save');
    const mode = saveBtn.dataset.mode;
    const id = saveBtn.dataset.id;
    const name = document.getElementById('prog-modal-name').value.trim();
    const description = document.getElementById('prog-modal-description').value.trim();

    clearAddEditModalErrors();

    if (!name) {
        setFieldError('prog-modal-name', 'Name is required.');
        return;
    }

    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        if (mode === 'add') {
            const { method, href } = API_URLS.programmes.create;
            await apiFetch(href, {
                method,
                body: JSON.stringify({ name, description }),
            });
            showFlash(`${name} programme added successfully.`, 'success');
        } else {
            const { method, href } = API_URLS.programmes.update(id);
            await apiFetch(href, {
                method,
                body: JSON.stringify({ name, description }),
            });
            showFlash(`${name} programme updated successfully.`, 'success');
        }

        _hideModal('progModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to save programme. Please try again.');
        showAddEditBanner(msg);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

// ── Modals — Activate / Deactivate ────────────────────────────────────────────

function openActiveModal(id, name, isActive) {
    const titleEl = document.getElementById('prog-active-modal-title');
    const messageEl = document.getElementById('prog-active-message');
    const confirmBtn = document.getElementById('confirm-active-btn');

    const action = isActive ? 'deactivated' : 'activated';
    titleEl.textContent = isActive ? 'Deactivate Programme' : 'Activate Programme';
    confirmBtn.textContent = isActive ? 'Deactivate' : 'Activate';
    confirmBtn.className = isActive ? 'btn btn-sm btn-danger' : 'btn btn-sm btn-success';
    confirmBtn.dataset.id = id;
    confirmBtn.dataset.isActive = isActive;

    messageEl.innerHTML = `<strong>${escHtml(name)}</strong> will be ${action}. Do you want to proceed?`;

    document.getElementById('prog-active-modal-banner').classList.add('d-none');
    _showModal('progActiveModal');
}

async function handleConfirmActive() {
    const btn = document.getElementById('confirm-active-btn');
    const id = btn.dataset.id;
    const isActive = btn.dataset.isActive === 'true';

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        const { method, href } = API_URLS.programmes.update(id);
        await apiFetch(href, {
            method,
            body: JSON.stringify({ is_active: !isActive }),
        });
        showFlash(`Programme ${isActive ? 'deactivated' : 'activated'}.`, 'success');
        _hideModal('progActiveModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to update programme. Please try again.');
        document.getElementById('prog-active-modal-banner').textContent = msg;
        document.getElementById('prog-active-modal-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

// ── Modals — Delete ───────────────────────────────────────────────────────────

function openDeleteModal(id, name) {
    document.getElementById('prog-delete-name').textContent = name;
    document.getElementById('confirm-delete-btn').dataset.id = id;
    document.getElementById('confirm-delete-btn').dataset.name = name;
    document.getElementById('prog-delete-modal-banner').classList.add('d-none');
    _showModal('progDeleteModal');
}

async function handleConfirmDelete() {
    const btn = document.getElementById('confirm-delete-btn');
    const id = btn.dataset.id;
    const name = btn.dataset.name;

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        const { method, href } = API_URLS.programmes.delete(id);
        await apiFetch(href, { method });
        showFlash(`"${name}" deleted.`, 'success');
        _hideModal('progDeleteModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to delete programme. Please try again.');
        document.getElementById('prog-delete-modal-banner').textContent = msg;
        document.getElementById('prog-delete-modal-banner').classList.remove('d-none');
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
        const { method, href } = API_URLS.programmes.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `programmes-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Programmes', filename);
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
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id), { focus: false }).show();
}

function _hideModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).hide();
}

function _refreshTable() {
    window._progFetcher?.refresh();
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
