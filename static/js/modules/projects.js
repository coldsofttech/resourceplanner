'use strict';

import { initFetch } from './../list/fetch.js';
import { initFetchMulti } from './../list/fetch_multi.js';
import { initRenderer } from './../list/render.js';
import { initSorting } from './../list/sort.js';
import { apiFetch, escAttr, escHtml, formatDate, setPageTitle, showFlash } from './../main.js';
import { API_URLS, URLS } from './../urls.js';
import { exportToCsv, exportToPdf } from '../export.js';

let _allSubStatuses = [];
let _deliveryTeams = [];

const _MULTI_FILTER_IDS = [
    'prog-filter',
    'status-filter',
    'substatus-filter',
    'team-filter',
    'priority-filter',
    'confidence-filter',
    'ptype-filter',
    'active-filter',
];

const LIST_EXPORT_COLUMNS = [
    { key: 'name', label: 'Name' },
    { key: 'project_type_name', label: 'Type' },
    { key: 'programme_name', label: 'Programme' },
    { key: 'code', label: 'Code' },
    { key: 'status_display', label: 'Status' },
    { key: 'assigned_team_name', label: 'Assigned Team' },
    { key: 'confidence_display', label: 'Confidence' },
    { key: 'priority_display', label: 'Priority' },
    { key: 'is_active', label: 'Active' },
];

document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('proj-tbody')) return;
    initListView();
});

async function initListView() {
    setPageTitle('Projects');
    await loadStats();
    await populateFilterOptions();
    bindToolbarEvents();
    bindModalEvents();
    bindFilterEvents();
    initTable();
}

async function loadStats() {
    try {
        const { method, href } = API_URLS.projects.stats;
        const data = await apiFetch(href, { method });
        document.getElementById('stat-total').textContent = data.total_projects ?? '-';
        document.getElementById('stat-active').textContent = data.active_projects ?? '-';
        document.getElementById('stat-in-progress').textContent = data.in_progress_projects ?? '-';
        document.getElementById('stat-new').textContent = data.new_projects ?? '-';
    } catch (err) {
        console.error('[loadStats] Failed.', err);
    }
}

async function populateFilterOptions() {
    try {
        const { method, href } = API_URLS.projects.options;
        const opts = await apiFetch(href, { method });

        _deliveryTeams = opts.delivery_teams ?? [];
        _allSubStatuses = opts.sub_statuses ?? [];

        _populateMultiSelect('prog-filter', opts.programmes ?? []);
        _populateMultiSelect('status-filter', opts.status ?? []);
        _populateMultiSelect('team-filter', opts.delivery_teams ?? [], { useIdAsValue: true });
        _populateMultiSelect('priority-filter', opts.priority ?? []);
        _populateMultiSelect('confidence-filter', opts.confidence ?? []);
        _populateMultiSelect('ptype-filter', opts.project_types ?? [], { useIdAsValue: true });
        _populateMultiSelect('substatus-filter', _allSubStatuses, { useIdAsValue: true });
        _populateMultiSelect('active-filter', opts.is_active ?? []);

        // Add modal selects
        _populateSelect('proj-modal-type', opts.project_types ?? [], '', 'Select type…', {
            useIdAsValue: true,
        });
        _populateSelect('proj-modal-status', opts.status ?? [], 'NEW');
        _populateSelect('proj-modal-confidence', opts.confidence ?? [], '', 'Not set');
        _populateSelect('proj-modal-priority', opts.priority ?? [], '', 'Not set');
        _cascadeModalSubStatus();

        // Assign team modal selects
        _populateSelect('assign-team-select', _deliveryTeams, '', 'None (unassign)', {
            useIdAsValue: true,
        });

        window._progOptions = opts.programmes ?? [];

        document
            .getElementById('proj-modal-status')
            ?.addEventListener('change', _cascadeModalSubStatus);
    } catch (err) {
        console.error('[populateFilterOptions] Failed.', err);
    }
}

function _populateMultiSelect(id, items, opts = {}) {
    const el = document.getElementById(id);
    if (!el) return;
    while (el.options.length) el.remove(0);
    items.forEach((item) => {
        const opt = document.createElement('option');
        opt.value = opts.useIdAsValue ? (item.id ?? item.value) : (item.value ?? item.id);
        opt.textContent = item.label ?? item.name;
        el.appendChild(opt);
    });
}

function _populateSelect(id, items, defaultValue = '', emptyLabel = null, opts = {}) {
    const el = document.getElementById(id);
    if (!el) return;

    while (el.options.length) el.remove(0);

    if (emptyLabel !== null) {
        const ph = document.createElement('option');
        ph.value = '';
        ph.textContent = emptyLabel;
        el.appendChild(ph);
    }

    items.forEach((item) => {
        const opt = document.createElement('option');
        opt.value = opts.useIdAsValue ? (item.id ?? item.value) : (item.value ?? item.id);
        opt.textContent = item.label ?? item.name;
        if (String(opt.value) === String(defaultValue)) opt.selected = true;
        el.appendChild(opt);
    });
}

function _getActiveFilterCount() {
    return _MULTI_FILTER_IDS.filter((id) => {
        const el = document.getElementById(id);
        return el && Array.from(el.selectedOptions).length > 0;
    }).length;
}

function _updateClearBtn() {
    const count = _getActiveFilterCount();
    const btn = document.getElementById('clear-filters-btn');
    const badge = document.getElementById('filter-count-badge');
    if (btn) btn.classList.toggle('d-none', count === 0);
    if (badge) {
        badge.textContent = count > 0 ? `${count} active` : '';
        badge.classList.toggle('d-none', count === 0);
    }
}

function bindFilterEvents() {
    document.getElementById('status-filter')?.addEventListener('change', () => {
        _cascadeFilterSubStatus();
        _updateClearBtn();
    });

    [
        'prog-filter',
        'substatus-filter',
        'team-filter',
        'priority-filter',
        'confidence-filter',
        'ptype-filter',
        'active-filter',
    ].forEach((id) => {
        document.getElementById(id)?.addEventListener('change', _updateClearBtn);
    });

    document.getElementById('clear-filters-btn')?.addEventListener('click', () => {
        window._clearProjectFilters?.();
    });

    _updateClearBtn();
}

function _cascadeFilterSubStatus() {
    const statusEl = document.getElementById('status-filter');
    const selectedStatuses = statusEl
        ? Array.from(statusEl.selectedOptions).map((o) => o.value)
        : [];

    const matching =
        selectedStatuses.length === 0
            ? _allSubStatuses
            : _allSubStatuses.filter((s) => selectedStatuses.includes(s.main_status));

    const subEl = document.getElementById('substatus-filter');
    const prevSel = subEl
        ? new Set(Array.from(subEl.selectedOptions).map((o) => o.value))
        : new Set();

    _populateMultiSelect('substatus-filter', matching, { useIdAsValue: true });

    if (subEl) {
        Array.from(subEl.options).forEach((o) => {
            o.selected = prevSel.has(o.value);
        });
    }
    _syncProxy('substatus-filter', 'proxy-substatus');
}

function _cascadeModalSubStatus() {
    const statusVal = document.getElementById('proj-modal-status')?.value ?? '';
    const matching = statusVal ? _allSubStatuses.filter((s) => s.main_status === statusVal) : [];

    const subEl = document.getElementById('proj-modal-substatus');
    const currentVal = subEl?.value ?? '';

    while (subEl?.options.length) subEl.remove(0);

    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = 'Select sub-status…';
    subEl?.appendChild(ph);

    matching.forEach((s) => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name;
        if (String(s.id) === currentVal) opt.selected = true;
        subEl?.appendChild(opt);
    });
}

function bindToolbarEvents() {
    document.getElementById('add-project-btn')?.addEventListener('click', () => openAddModal());
    document.getElementById('export-csv')?.addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf')?.addEventListener('click', () => runListExport('pdf'));
}

function initTable() {
    const { method, href } = API_URLS.projects.list;

    const renderer = initRenderer({
        tbodyId: 'proj-tbody',
        colspan: 11,
        itemLabel: 'projects',
        rowTemplate: renderProjectRow,
        emptyState: {
            message: 'No projects yet.',
            link: { href: '#', label: 'Add the first one', onClick: 'openAddModal()' },
        },
        filterEmptyState: {
            message: 'No projects match your filters.',
            link: { href: '#', label: 'Create a new one', onClick: 'openAddModal()' },
        },
        paginationBarId: 'proj-pagination-bar',
        paginationInfoId: 'proj-pagination-info',
        paginationControlsId: 'proj-pagination-controls',
        onPageChange: (page) => fetcher.goToPage(page),
    });

    const fetcher = initFetchMulti({
        apiUrl: href,
        pageSize: 20,
        searchInputId: 'proj-search',
        filters: [],
        multiFilters: [
            { id: 'prog-filter', param: 'programme' },
            { id: 'status-filter', param: 'status' },
            { id: 'substatus-filter', param: 'sub_status' },
            { id: 'team-filter', param: 'team' },
            { id: 'priority-filter', param: 'priority' },
            { id: 'confidence-filter', param: 'confidence' },
            { id: 'ptype-filter', param: 'project_type' },
            { id: 'active-filter', param: 'is_active' },
        ],
        onLoadStart: () => renderer.renderLoading('Loading projects…'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters =
                !!state.search ||
                Object.keys(state.multiFilters).length > 0 ||
                Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load projects. Please refresh the page.'),
    });

    initSorting({ tableId: 'proj-table', fetcher });
    fetcher.refresh();

    window._projFetcher = fetcher;
    window._projRenderer = renderer;
    window._projBaseApiUrl = href;
}

function renderProjectRow(proj) {
    const detailUrl = URLS.projects.detail(proj.id);

    return `
        <tr data-project-id="${proj.id}">
            <td class="fw-medium">
                <a href="${detailUrl}" class="rp-link fw-500">${escHtml(proj.name)}</a>
            </td>
            <td>${escHtml(proj.project_type_name ?? '-')}</td>
            <td>${escHtml(proj.programme_name ?? '-')}</td>
            <td><span class="rp-code">${escHtml(proj.code || '-')}</span></td>
            <td>${_statusBadge(proj.status, proj.status_display)}</td>
            <td>${proj.sub_status_name ? `<span class="rp-badge rp-badge--muted">${escHtml(proj.sub_status_name)}</span>` : '-'}</td>
            <td>${escHtml(proj.assigned_team_name ?? '-')}</td>
            <td>${_levelBadge(proj.confidence, proj.confidence_display)}</td>
            <td>${_levelBadge(proj.priority, proj.priority_display)}</td>
            <td class="text-center">
                ${
                    proj.is_active
                        ? '<span class="rp-badge rp-badge--success">Active</span>'
                        : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${detailUrl}" class="btn btn-ghost-icon" title="View project">
                        <i class="bi bi-eye"></i>
                    </a>
                    <button class="btn btn-ghost-icon" title="Assign team"
                            onclick="openAssignTeamModal(${proj.id}, '${escAttr(proj.name)}', ${proj.assigned_team ?? 'null'})">
                        <i class="bi bi-people"></i>
                    </button>
                    <button class="btn btn-ghost-icon ${proj.is_active ? 'btn-ghost-icon--danger' : 'btn-ghost-icon--success'}"
                            title="${proj.is_active ? 'Deactivate' : 'Activate'} project"
                            onclick="openActiveModal(${proj.id}, '${escAttr(proj.name)}', ${proj.is_active})">
                        <i class="bi bi-check-circle"></i>
                    </button>
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger" title="Delete project"
                            onclick="openDeleteModal(${proj.id}, '${escAttr(proj.name)}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function _statusBadge(status, label) {
    if (!status) return '—';
    return `<span class="rp-badge rp-badge-status--${status.toLowerCase()}">${escHtml(label || status)}</span>`;
}

function _levelBadge(value, label) {
    if (!value) return '<span class="text-muted">-</span>';
    const key = value.toLowerCase().replace(/_/g, '-');
    return `<span class="rp-badge rp-badge-level--${key}">${escHtml(label || value)}</span>`;
}

function openAddModal() {
    resetAddModal();

    document.getElementById('proj-modal-status').value = 'NEW';
    _cascadeModalSubStatus();
    document.getElementById('proj-modal-banner').classList.add('d-none');

    const saveBtn = document.getElementById('proj-modal-save');
    saveBtn.dataset.mode = 'add';
    saveBtn.dataset.id = '';
    saveBtn.textContent = 'Create project';

    document.getElementById('proj-modal-title').textContent = 'New Project';
    _showModal('projModal');
    setTimeout(() => document.getElementById('proj-modal-name').focus(), 300);
}

function resetAddModal() {
    [
        'proj-modal-name',
        'proj-modal-type',
        'proj-modal-programme',
        'proj-modal-programme-id',
        'proj-modal-code',
        'proj-modal-status',
        'proj-modal-substatus',
        'proj-modal-confidence',
        'proj-modal-priority',
        'proj-modal-start',
        'proj-modal-end',
    ].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    clearAddModalErrors();
}

function clearAddModalErrors() {
    document.getElementById('proj-modal-banner')?.classList.add('d-none');
    ['proj-modal-name', 'proj-modal-type'].forEach((id) => {
        document.getElementById(id)?.classList.remove('is-invalid');
        const errEl = document.getElementById(`${id}-err`);
        if (errEl) errEl.textContent = '';
    });
}

function bindModalEvents() {
    document.getElementById('projModal')?.addEventListener('hidden.bs.modal', resetAddModal);
    document.getElementById('proj-modal-save')?.addEventListener('click', handleModalSave);
    document.getElementById('confirm-active-btn')?.addEventListener('click', handleConfirmActive);
    document.getElementById('confirm-delete-btn')?.addEventListener('click', handleConfirmDelete);
    document
        .getElementById('confirm-assign-team-btn')
        ?.addEventListener('click', handleConfirmAssignTeam);
    document.getElementById('projModal')?.addEventListener('shown.bs.modal', () => {
        const inputEl = document.getElementById('proj-modal-programme');
        const suggestionsEl = document.getElementById('proj-modal-programme-suggestions');
        if (inputEl & suggestionsEl) {
            suggestionsEl.style.width = inputEl.getBoundingClientRect().width + 'px';
        }
    });

    _bindProgrammeAutocomplete(
        'proj-modal-programme',
        'proj-modal-programme-id',
        'proj-modal-programme-suggestions',
    );
}

function _bindProgrammeAutocomplete(inputId, hiddenId, suggestionsId) {
    const input = document.getElementById(inputId);
    const hiddenInput = document.getElementById(hiddenId);
    const suggestions = document.getElementById(suggestionsId);
    if (!input || !suggestions) return;

    input.addEventListener('input', () => {
        const val = input.value.trim().toLowerCase();
        hiddenInput.value = '';

        const progs = window._progOptions ?? [];
        const matches =
            val.length < 1
                ? []
                : progs.filter((p) => p.name.toLowerCase().includes(val)).slice(0, 10);

        if (!matches.length) {
            suggestions.style.display = 'none';
            return;
        }

        suggestions.innerHTML = matches
            .map(
                (p) =>
                    `<button type="button" class="list-group-item list-group-item-action py-1 px-2 small"
                     data-id="${p.id}" data-name="${escAttr(p.name)}">
                ${escHtml(p.name)}
             </button>`,
            )
            .join('');
        suggestions.style.display = 'block';
    });

    suggestions.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-id]');
        if (!btn) return;
        input.value = btn.dataset.name;
        hiddenInput.value = btn.dataset.id;
        suggestions.style.display = 'none';
    });

    document.addEventListener('click', (e) => {
        if (!suggestions.contains(e.target) && e.target !== input) {
            suggestions.style.display = 'none';
        }
    });
}

async function handleModalSave() {
    clearAddModalErrors();

    const name = document.getElementById('proj-modal-name').value.trim();
    const project_type = document.getElementById('proj-modal-type').value;
    const progInput = document.getElementById('proj-modal-programme').value.trim();
    const progId = document.getElementById('proj-modal-programme-id').value;

    let hasErrors = false;
    if (!name) {
        _setFieldError('proj-modal-name', 'proj-modal-name-err', 'Name is required.');
        hasErrors = true;
    }
    if (!project_type) {
        _setFieldError('proj-modal-type', 'proj-modal-type-err', 'Project type is required.');
        hasErrors = true;
    }
    if (hasErrors) return;

    const saveBtn = document.getElementById('proj-modal-save');
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        let programme = progId || null;
        if (!programme && progInput) {
            programme = await _resolveOrCreateProgramme(progInput);
        }

        const payload = {
            name,
            project_type: parseInt(project_type),
            programme: programme ? parseInt(programme) : null,
            code: document.getElementById('proj-modal-code').value.trim(),
            status: document.getElementById('proj-modal-status').value || 'NEW',
            sub_status: document.getElementById('proj-modal-substatus').value || null,
            confidence: document.getElementById('proj-modal-confidence').value || '',
            priority: document.getElementById('proj-modal-priority').value || '',
            tentative_start_date: document.getElementById('proj-modal-start').value || null,
            tentative_end_date: document.getElementById('proj-modal-end').value || null,
        };

        const { method, href } = API_URLS.projects.new;
        const created = await apiFetch(href, {
            method,
            body: JSON.stringify(payload),
        });

        showFlash(`"${name}" created successfully.`, 'success');
        _hideModal('projModal');

        window.location.href = URLS.projects.detail(created.id);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save project. Please try again.');
        const banner = document.getElementById('proj-modal-banner');
        banner.textContent = msg;
        banner.classList.remove('d-none');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function _resolveOrCreateProgramme(name) {
    const existing = (window._progOptions ?? []).find(
        (p) => p.name.toLowerCase() === name.toLowerCase(),
    );
    if (existing) return existing.id;

    const { method, href } = API_URLS.programmes.new;
    const created = await apiFetch(href, {
        method,
        body: JSON.stringify({ name }),
    });

    if (!window._progOptions) window._progOptions = [];
    window._progOptions.push({ id: created.id, name: created.name });

    return created.id;
}

function openAssignTeamModal(projectId, projectName, currentTeamId) {
    document.getElementById('proj-assign-team-project-name').textContent =
        `Project: ${projectName}`;
    document.getElementById('assign-team-select').value = currentTeamId ?? '';
    document.getElementById('proj-assign-team-banner').classList.add('d-none');

    const confirmBtn = document.getElementById('confirm-assign-team-btn');
    confirmBtn.dataset.projectId = projectId;

    _showModal('projAssignTeamModal');
}

async function handleConfirmAssignTeam() {
    const btn = document.getElementById('confirm-assign-team-btn');
    const projectId = btn.dataset.projectId;
    const teamVal = document.getElementById('assign-team-select').value;
    const teamId = teamVal ? parseInt(teamVal) : null;

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        const { method, href } = API_URLS.projects.edit_teams(projectId);
        await apiFetch(href, { method, body: JSON.stringify({ assigned_team: teamId }) });
        showFlash('Team assigned successfully.', 'success');
        _hideModal('projAssignTeamModal');
        _refreshTable();
    } catch (err) {
        const msg = _extractError(err, 'Failed to assign team. Please try again.');
        const banner = document.getElementById('proj-assign-team-banner');
        banner.textContent = msg;
        banner.classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

function openActiveModal(id, name, isActive) {
    const titleEl = document.getElementById('proj-active-modal-title');
    const messageEl = document.getElementById('proj-active-message');
    const confirmBtn = document.getElementById('confirm-active-btn');

    const action = isActive ? 'deactivated' : 'activated';
    titleEl.textContent = isActive ? 'Deactivate Project' : 'Activate Project';
    confirmBtn.textContent = isActive ? 'Deactivate' : 'Activate';
    confirmBtn.className = `btn btn-sm ${isActive ? 'btn-danger' : 'btn-success'}`;
    confirmBtn.dataset.id = id;
    confirmBtn.dataset.isActive = isActive;

    messageEl.innerHTML = `<strong>${escHtml(name)}</strong> will be ${action}. Do you want to proceed?`;
    document.getElementById('proj-active-modal-banner').classList.add('d-none');
    _showModal('projActiveModal');
}

async function handleConfirmActive() {
    const btn = document.getElementById('confirm-active-btn');
    const id = btn.dataset.id;
    const isActive = btn.dataset.isActive === 'true';

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        const { method, href } = API_URLS.projects.partial_edit(id);
        await apiFetch(href, { method, body: JSON.stringify({ is_active: !isActive }) });
        showFlash(`Project ${isActive ? 'deactivated' : 'activated'}.`, 'success');
        _hideModal('projActiveModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to update project. Please try again.');
        const banner = document.getElementById('proj-active-modal-banner');
        banner.textContent = msg;
        banner.classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

function openDeleteModal(id, name) {
    document.getElementById('proj-delete-name').textContent = name;
    document.getElementById('confirm-delete-btn').dataset.id = id;
    document.getElementById('confirm-delete-btn').dataset.name = name;
    document.getElementById('proj-delete-modal-banner').classList.add('d-none');
    _showModal('projDeleteModal');
}

async function handleConfirmDelete() {
    const btn = document.getElementById('confirm-delete-btn');
    const id = btn.dataset.id;
    const name = btn.dataset.name;

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        const { method, href } = API_URLS.projects.delete(id);
        await apiFetch(href, { method });
        showFlash(`"${name}" deleted.`, 'success');
        _hideModal('projDeleteModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to delete project. Please try again.');
        const banner = document.getElementById('proj-delete-modal-banner');
        banner.textContent = msg;
        banner.classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled = true;
        btn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.projects.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `projects-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Projects', filename);
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

function _showModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id), { focus: false }).show();
}

function _hideModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).hide();
}

function _refreshTable() {
    window._projFetcher?.refresh();
}

function _setFieldError(inputId, errId, message) {
    document.getElementById(inputId)?.classList.add('is-invalid');
    const errEl = document.getElementById(errId);
    if (errEl) errEl.textContent = message;
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

window.openAddModal = openAddModal;
window.openAssignTeamModal = openAssignTeamModal;
window.openActiveModal = openActiveModal;
window.openDeleteModal = openDeleteModal;
window._clearProjectFilters = function () {
    _MULTI_FILTER_IDS.forEach((id) => {
        const el = document.getElementById(id);
        if (el) Array.from(el.options).forEach((o) => (o.selected = false));
    });
    _populateMultiSelect('substatus-filter', _allSubStatuses, { useIdAsValue: true });
    _updateClearBtn();
    window._projFetcher?.syncAndRefresh();
};
