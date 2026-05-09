'use strict';

import { initFetch } from './../list/fetch.js';
import { initRenderer } from './../list/render.js';
import {
    apiFetch,
    escHtml,
    formatDateTime,
    getPkFromUrl,
    setPageTitle,
    showFlash,
} from './../main.js';
import { API_URLS } from './../urls.js';

const planPk = getPkFromUrl('resource-plans');
const versionPk = getPkFromUrl('versions');

let _versionData = null;
let _optionsData = { sprints: [] };
let _spp = 1150;
let _fyId = null;
let _isReadOnly = false;
let _unmappedProjects = [];
let _currentEditEntryId = null;
let _currentEditEntry = null;
let _modalIsView = false;
let _projectsFetcher = null;
let _currentPhaseId = null;
let _phaseTeamEntryId = null;
let _phaseEntryId = null;
let _segmentsChart = null;
let _parentModalHiddenForPhase = false;
let _assignOptions = { available: [], all: [], split_mode: 'AUTO', allow_multiple: false };
let _newlyAddedTeamEntryId = null;

document.addEventListener('DOMContentLoaded', () => {
    if (!planPk || !versionPk) return;
    initPage();
});

async function initPage() {
    try {
        const [versionData, optionsData, sppConfig] = await Promise.all([
            apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href),
            apiFetch(API_URLS.rp_versions.projects.options(planPk, versionPk).href).catch(() => ({ sprints: [] })),
            apiFetch(API_URLS.configurations.by_code('SPRINT_POINT_PRICE').href).catch(() => null),
        ]);
        _versionData = versionData;
        _optionsData = optionsData || { sprints: [] };
        _fyId = _optionsData.financial_year_id ?? null;
        if (sppConfig?.value != null) {
            _spp = parseFloat(sppConfig.value) || 1150;
        }

        _isReadOnly = _versionData.status !== 'DRAFT';

        renderHeader();
        renderSppDisplay();
        renderThreshold();
        if (_isReadOnly) {
            _showBanner(
                `This version is ${_versionData.status} and cannot be configured. Only DRAFT versions are editable.`,
                'warning',
            );
        }
        populateSprintOptions();
        populateProgrammeFilter();
        loadUnmappedProjects();
        initProjectsTable();
        bindEvents();
    } catch (err) {
        console.error('[initPage] Failed to initialize.', err);
        _showBanner('Failed to load version data. Please refresh the page.', 'danger');
    }
}

// ─── Header ───────────────────────────────────────────────────────────────────

function renderHeader() {
    if (!_versionData) return;
    const v = _versionData;
    document.getElementById('vc-plan-name').textContent = v.plan_name ?? 'Resource Plan';
    document.getElementById('vc-version-badge').innerHTML =
        `<span class="rp-badge rp-badge--muted">v${escHtml(String(v.version))}</span>`;
    document.getElementById('vc-status-badge').innerHTML = _versionStatusBadge(v.status);
    document.getElementById('vc-project-count').textContent = v.project_count ?? 0;
    setPageTitle(`v${v.version} – ${v.plan_name}`);
}

function _versionStatusBadge(status) {
    const map = {
        ACTIVE: 'rp-badge--success',
        DRAFT: 'rp-badge--muted',
        LOCKED: 'rp-badge--warning',
        SUPERSEDED: 'rp-badge--muted',
        EXPIRED: 'rp-badge--danger',
    };
    return `<span class="rp-badge ${map[status] || 'rp-badge--muted'}">${escHtml(status ?? '—')}</span>`;
}

// ─── Version Settings ─────────────────────────────────────────────────────────

function renderSppDisplay() {
    const el = document.getElementById('spp-display');
    if (el) el.textContent = `£${_spp.toLocaleString('en-GB', { minimumFractionDigits: 2 })}`;
}

function renderThreshold() {
    const el = document.getElementById('threshold-display');
    if (!el) return;
    const t = _versionData?.threshold_pct;
    el.textContent = t != null ? `${parseFloat(t).toFixed(1)}%` : '—';
}

// ─── Calculator ───────────────────────────────────────────────────────────────

function bindCalculator() {
    const daysEl = document.getElementById('calc-days');
    const costEl = document.getElementById('calc-cost');

    daysEl?.addEventListener('input', () => {
        const days = parseFloat(daysEl.value);
        costEl.value = (!isNaN(days) && _spp > 0) ? (days * _spp).toFixed(2) : '';
    });

    costEl?.addEventListener('input', () => {
        const cost = parseFloat(costEl.value);
        daysEl.value = (!isNaN(cost) && _spp > 0) ? (cost / _spp).toFixed(2) : '';
    });
}

// ─── Basis Hint / Estimate Versions ──────────────────────────────────────────

// context: 'add' | 'edit'; savedEstimateId pre-selects estimate dropdown
async function loadBasisContext(basis, projectId, context, savedEstimateId = null) {
    const prefix = context === 'add' ? 'add' : 'ep';
    const hintWrap = document.getElementById(`${prefix}-basis-hint-wrap`);
    const hintLabel = document.getElementById(`${prefix}-basis-hint-label`);
    const hintValue = document.getElementById(`${prefix}-basis-hint-value`);
    const hintSub = document.getElementById(`${prefix}-basis-hint-sub`);
    const estGroup = document.getElementById(`${prefix}-estimate-version-group`);
    const estSelect = document.getElementById(`${prefix}-estimate-version`);

    // Hide estimate dropdown by default
    estGroup?.classList.add('d-none');

    if (!projectId || basis === 'CUSTOM') {
        hintWrap?.classList.add('d-none');
        return;
    }

    if (hintWrap) {
        hintWrap.classList.remove('d-none');
        if (hintValue) hintValue.textContent = 'Loading…';
        if (hintSub) hintSub.textContent = '';
    }

    try {
        if (basis === 'BUDGET') {
            if (hintLabel) hintLabel.textContent = 'Available Budget';
            const data = await apiFetch(API_URLS.projects.budgets.list(projectId).href);
            const budgets = Array.isArray(data) ? data : (data.results ?? []);
            const relevant = _fyId
                ? (budgets.find(b => b.financial_year === _fyId) ?? budgets[0])
                : budgets[0];
            if (relevant) {
                const amt = relevant.actual_budget != null
                    ? `£${parseFloat(relevant.actual_budget).toLocaleString('en-GB', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
                    : '—';
                const fyLabel = relevant.financial_year_display ? ` (${relevant.financial_year_display})` : '';
                if (hintValue) hintValue.textContent = amt;
                if (hintSub) hintSub.textContent = `Actual budget${fyLabel}`;
            } else {
                if (hintValue) hintValue.textContent = '—';
                if (hintSub) hintSub.textContent = 'No budget record found.';
            }
        } else if (basis === 'ESTIMATE') {
            if (hintLabel) hintLabel.textContent = 'Estimate Value';
            const data = await apiFetch(API_URLS.projects.estimates.list(projectId).href);
            const estimates = Array.isArray(data) ? data : (data.results ?? []);

            if (estGroup && estSelect && estimates.length) {
                estGroup.classList.remove('d-none');
                estSelect.innerHTML = estimates.map(e => {
                    const lbl = e.version_label ?? `v${e.id}`;
                    const statusLbl = e.status_display ? ` [${e.status_display}]` : '';
                    const sel = savedEstimateId && String(e.id) === String(savedEstimateId) ? ' selected' : '';
                    return `<option value="${e.id}" data-cost="${e.total_cost ?? ''}"${sel}>${escHtml(lbl + statusLbl)}</option>`;
                }).join('');
                _updateEstimateHint(estSelect, hintValue, hintSub);
            } else if (estimates.length === 0) {
                if (hintValue) hintValue.textContent = '—';
                if (hintSub) hintSub.textContent = 'No estimate records found.';
            }
        }
    } catch {
        if (hintWrap) hintWrap.classList.add('d-none');
    }
}

function _updateEstimateHint(selectEl, valueEl, subEl) {
    const selected = selectEl.options[selectEl.selectedIndex];
    const cost = selected?.dataset.cost;
    if (valueEl) {
        valueEl.textContent = cost
            ? `£${parseFloat(cost).toLocaleString('en-GB', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
            : '—';
    }
    if (subEl) subEl.textContent = selected ? `Version: ${selected.text}` : '';
}

// ─── Unmapped Projects ────────────────────────────────────────────────────────

async function loadUnmappedProjects() {
    const container = document.getElementById('unmapped-projects-list');
    if (!container) return;
    container.innerHTML = '<p class="text-secondary small">Loading…</p>';

    try {
        const { method, href } = API_URLS.rp_versions.projects.unmapped(planPk, versionPk);
        const data = await apiFetch(href, { method });
        _unmappedProjects = Array.isArray(data) ? data : [];
        renderUnmappedProjects('');
    } catch {
        container.innerHTML = '<p class="text-danger small">Failed to load unmapped projects.</p>';
    }
}

function renderUnmappedProjects(filter) {
    const container = document.getElementById('unmapped-projects-list');
    if (!container) return;

    const lower = filter.toLowerCase();
    const filtered = _unmappedProjects
        .map(group => ({
            ...group,
            projects: group.projects.filter(p =>
                !lower ||
                p.name?.toLowerCase().includes(lower) ||
                group.programme?.toLowerCase().includes(lower)
            ),
        }))
        .filter(group => group.projects.length > 0);

    if (!filtered.length) {
        container.innerHTML = '<p class="text-secondary small mb-0">No unmapped projects.</p>';
        return;
    }

    const totalProjects = filtered.reduce((s, g) => s + g.projects.length, 0);

    container.innerHTML = `
        <div class="rp-hint mb-2">${totalProjects} project${totalProjects !== 1 ? 's' : ''} not yet in this version</div>
        <table class="table table-sm rp-table mb-0">
            <thead>
                <tr>
                    <th>Project</th>
                    <th>Programme</th>
                    ${_isReadOnly ? '' : '<th style="width:60px"></th>'}
                </tr>
            </thead>
            <tbody>
                ${filtered.map(group =>
                    group.projects.map(p => `
                        <tr>
                            <td style="font-size:.85rem">${escHtml(p.name)}</td>
                            <td style="font-size:.8rem" class="text-secondary">${escHtml(group.programme || '—')}</td>
                            ${_isReadOnly ? '' : `
                            <td>
                                <button type="button"
                                    class="btn btn-sm btn-outline-primary py-0 px-2 js-unmapped-add"
                                    style="font-size:.75rem"
                                    data-project-id="${p.id}"
                                    data-project-name="${escHtml(p.name)}">
                                    Add
                                </button>
                            </td>`}
                        </tr>
                    `).join('')
                ).join('')}
            </tbody>
        </table>`;

    if (!_isReadOnly) {
        container.querySelectorAll('.js-unmapped-add').forEach(btn => {
            btn.addEventListener('click', () =>
                openAddProjectModal(btn.dataset.projectId, btn.dataset.projectName)
            );
        });
    }
}

// ─── Projects Table ───────────────────────────────────────────────────────────

function initProjectsTable() {
    const renderer = initRenderer({
        tbodyId: 'vc-projects-tbody',
        colspan: 9,
        itemLabel: 'projects',
        rowTemplate: renderProjectRow,
        emptyState: { message: 'No projects configured for this version.' },
        filterEmptyState: { message: 'No projects match your search.' },
        paginationBarId: 'proj-pagination-bar',
        paginationInfoId: 'proj-pagination-info',
        paginationControlsId: 'proj-pagination-controls',
        onPageChange: page => _projectsFetcher?.goToPage(page),
    });

    _projectsFetcher = initFetch({
        apiUrl: API_URLS.rp_versions.projects.list(planPk, versionPk).href,
        pageSize: 20,
        searchInputId: 'projects-search',
        filters: [{ id: 'projects-programme-filter', param: 'programme' }],
        onLoadStart: () => renderer.renderLoading('Loading projects…'),
        onSuccess: ({ results, pagination }) => {
            renderer.renderRows(results, false);
            renderer.renderPagination(pagination);
            _bindProjectTableActions();
            document.getElementById('vc-project-count').textContent =
                pagination?.total_count ?? results.length;
        },
        onError: () => renderer.renderError('Failed to load projects. Please refresh the page.'),
    });

    _projectsFetcher.refresh();
}

function renderProjectRow(entry) {
    const amount = entry.basis_amount
        ? `£${parseFloat(entry.basis_amount).toLocaleString('en-GB', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
        : '—';
    const days = entry.days_required ? parseFloat(entry.days_required).toFixed(2) : '—';

    const viewBtn = `<button class="btn btn-ghost-icon js-proj-view" data-id="${entry.id}" title="View"><i class="bi bi-eye"></i></button>`;

    const actions = _isReadOnly
        ? viewBtn
        : `
            <button class="btn btn-ghost-icon js-proj-edit" data-id="${entry.id}" title="Configure">
                <i class="bi bi-gear"></i>
            </button>
            ${viewBtn}
            ${(entry.basis === 'BUDGET' || entry.basis === 'ESTIMATE') ? `
            <button class="btn btn-ghost-icon js-proj-resync"
                data-id="${entry.id}"
                data-basis="${escHtml(entry.basis)}"
                data-name="${escHtml(entry.project_name ?? '')}" title="Resync">
                <i class="bi bi-arrow-repeat"></i>
            </button>` : ''}
            <button class="btn btn-ghost-icon btn-ghost-icon--danger js-proj-delete"
                data-id="${entry.id}"
                data-name="${escHtml(entry.project_name ?? '')}" title="Remove">
                <i class="bi bi-trash"></i>
            </button>`;

    return `
        <tr data-entry-id="${entry.id}">
            <td>
                <div class="fw-semibold" style="font-size:.85rem">${escHtml(entry.project_name ?? '—')}</div>
            </td>
            <td style="font-size:.8rem">${escHtml(entry.programme_name ?? '—')}</td>
            <td><span class="rp-badge rp-badge--muted" style="font-size:.72rem">${escHtml(_basisLabel(entry.basis))}</span></td>
            <td class="text-end" style="font-size:.85rem">${amount}</td>
            <td class="text-end" style="font-size:.85rem">${days}</td>
            <td>${_levelBadge(entry.effective_priority, entry.priority_override, entry.priority_snapshot)}</td>
            <td>${_levelBadge(entry.effective_confidence, entry.confidence_override, entry.confidence_snapshot)}</td>
            <td>${_flagsHtml(entry)}</td>
            <td><div class="d-flex gap-1 align-items-center flex-wrap">${actions}</div></td>
        </tr>
    `;
}

function _levelBadge(effective, override, snapshot) {
    if (!effective) return '<span class="text-secondary" style="font-size:.8rem">—</span>';
    const cls = { VERY_HIGH: 'rp-badge--danger', HIGH: 'rp-badge--warning', MEDIUM: 'rp-badge--info', LOW: 'rp-badge--muted' }[effective] || 'rp-badge--muted';
    const label = { VERY_HIGH: 'Very High', HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low' }[effective] || effective;
    const dot = (override && override !== snapshot)
        ? `<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--color-primary,#6c5ce7);vertical-align:middle;margin-left:3px;" title="Override active"></span>`
        : '';
    return `<span class="rp-badge ${cls}" style="font-size:.72rem">${escHtml(label)}${dot}</span>`;
}

function _basisLabel(basis) {
    return basis === 'BUDGET' ? 'Budget' : basis === 'ESTIMATE' ? 'Estimate' : 'Custom';
}

function _flagsHtml(entry) {
    const flags = [];
    if (entry.is_over_threshold)
        flags.push('<span class="rp-badge rp-badge--danger" style="font-size:.7rem">Over</span>');
    if (entry.is_under_threshold)
        flags.push('<span class="rp-badge rp-badge--warning" style="font-size:.7rem">Under</span>');
    if (entry.is_team_budget_mismatch || entry.is_budget_mismatch)
        flags.push('<span class="rp-badge" style="font-size:.7rem;background:#fd7e14;color:#fff;">Mismatch</span>');
    if (entry.is_percent_incomplete)
        flags.push('<span class="rp-badge rp-badge--warning" style="font-size:.7rem">Teams %</span>');
    return flags.length
        ? `<div class="d-flex gap-1 flex-wrap">${flags.join('')}</div>`
        : '<span class="text-secondary" style="font-size:.8rem">—</span>';
}

function _bindProjectTableActions() {
    const tbody = document.getElementById('vc-projects-tbody');
    if (!tbody) return;
    tbody.onclick = e => {
        const btn = e.target.closest('button');
        if (!btn) return;
        const entryId = btn.dataset.id;
        if (btn.classList.contains('js-proj-view')) {
            openEditModal(entryId, true);
        } else if (btn.classList.contains('js-proj-edit')) {
            openEditModal(entryId, false);
        } else if (btn.classList.contains('js-proj-resync')) {
            openResyncModal(entryId, btn.dataset.name, btn.dataset.basis);
        } else if (btn.classList.contains('js-proj-delete')) {
            openDeleteModal(entryId, btn.dataset.name);
        }
    };
}

// ─── Programme Filter ─────────────────────────────────────────────────────────

function populateProgrammeFilter() {
    const sel = document.getElementById('projects-programme-filter');
    if (!sel) return;
    const programmes = _optionsData?.programmes ?? [];
    programmes.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        sel.appendChild(opt);
    });
}

// ─── Add Project Modal ────────────────────────────────────────────────────────

function openAddProjectModal(projectId, projectName) {
    document.getElementById('add-proj-id').value = projectId;
    document.getElementById('add-proj-name').textContent = projectName || '—';
    document.getElementById('add-proj-basis').value = 'BUDGET';
    document.getElementById('add-proj-amount-group').classList.add('d-none');
    document.getElementById('add-estimate-version-group').classList.add('d-none');
    document.getElementById('add-basis-hint-wrap').classList.add('d-none');
    document.getElementById('add-proj-amount').value = '';
    document.getElementById('add-proj-priority').value = '';
    document.getElementById('add-proj-confidence').value = '';
    document.getElementById('add-proj-banner').classList.add('d-none');
    loadBasisContext('BUDGET', projectId, 'add');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('addProjectModal')).show();
}

async function submitAddProject() {
    const projectId = document.getElementById('add-proj-id').value;
    const basis = document.getElementById('add-proj-basis').value;
    const amountEl = document.getElementById('add-proj-amount');
    const amountErrEl = document.getElementById('add-proj-amount-err');

    amountEl.classList.remove('is-invalid');
    amountErrEl.textContent = '';

    const payload = {
        project: projectId,
        basis,
        priority_override: document.getElementById('add-proj-priority').value || null,
        confidence_override: document.getElementById('add-proj-confidence').value || null,
    };

    if (basis === 'ESTIMATE') {
        const estId = document.getElementById('add-estimate-version')?.value;
        if (estId) payload.estimate_id = estId;
    }

    if (basis === 'CUSTOM') {
        const amount = parseFloat(amountEl.value);
        if (isNaN(amount) || amount < 0) {
            amountEl.classList.add('is-invalid');
            amountErrEl.textContent = 'Please enter a valid amount.';
            return;
        }
        payload.basis_amount = amount;
    }

    const spinner = document.getElementById('add-proj-spinner');
    const btn = document.getElementById('btn-confirm-add-proj');
    spinner.classList.remove('d-none');
    btn.disabled = true;

    try {
        const { method, href } = API_URLS.rp_versions.projects.create(planPk, versionPk);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('addProjectModal')).hide();
        showFlash('Project added to version.', 'success');
        _projectsFetcher?.refresh();
        loadUnmappedProjects();
    } catch (err) {
        const msg = _extractError(err, 'Failed to add project.');
        document.getElementById('add-proj-banner').textContent = msg;
        document.getElementById('add-proj-banner').classList.remove('d-none');
    } finally {
        spinner.classList.add('d-none');
        btn.disabled = false;
    }
}

// ─── Edit Project Modal ───────────────────────────────────────────────────────

function _applyViewMode(active) {
    const configInputs = ['ep-basis', 'ep-estimate-version', 'ep-amount', 'ep-priority',
        'ep-confidence', 'ep-start-sprint', 'ep-end-sprint', 'ep-dates-strict',
        'ep-budget-release-mode'];
    configInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = active;
    });
    const saveBtn = document.getElementById('btn-save-edit-proj');
    if (saveBtn) saveBtn.style.display = active ? 'none' : '';
}

async function openEditModal(entryId, viewOnly = false) {
    _modalIsView = viewOnly;
    _currentEditEntryId = entryId;
    _currentEditEntry = null;
    document.getElementById('edit-proj-entry-id').value = entryId;
    document.getElementById('edit-proj-banner').classList.add('d-none');
    document.getElementById('edit-proj-title').textContent = viewOnly ? 'View Project' : 'Configure Project';

    // Reset to Config tab immediately
    const configTab = document.getElementById('ep-tab-config');
    if (configTab) {
        bootstrap.Tab.getOrCreateInstance(configTab).show();
    }

    // Clear sub-tab content to avoid stale data
    document.getElementById('ep-teams-list').innerHTML = '<p class="text-secondary small">Loading…</p>';
    document.getElementById('ep-releases-list').innerHTML = '<p class="text-secondary small">Loading…</p>';
    document.getElementById('ep-basis-hint-wrap')?.classList.add('d-none');
    document.getElementById('ep-mode-change-warn')?.classList.add('d-none');

    // Show modal while loading
    bootstrap.Modal.getOrCreateInstance(document.getElementById('editProjectModal')).show();

    try {
        const { method, href } = API_URLS.rp_versions.projects.detail(planPk, versionPk, entryId);
        const entry = await apiFetch(href, { method });
        _currentEditEntry = entry;

        document.getElementById('edit-proj-title').textContent =
            `${_modalIsView ? 'View' : 'Configure'}: ${escHtml(entry.project_name ?? '')}`;
        loadEditConfigTab(entry);
        _applyViewMode(_modalIsView);
        document.getElementById('ep-team-count').textContent = entry.team_count ?? 0;
        document.getElementById('ep-release-count').textContent = entry.release_count ?? 0;
    } catch (err) {
        document.getElementById('edit-proj-banner').textContent =
            _extractError(err, 'Failed to load project data.');
        document.getElementById('edit-proj-banner').classList.remove('d-none');
    }
}

function loadEditConfigTab(entry) {
    document.getElementById('ep-basis').value = entry.basis ?? 'BUDGET';
    _toggleEpAmountGroup(entry.basis);
    document.getElementById('ep-amount').value = entry.basis_amount
        ? parseFloat(entry.basis_amount).toFixed(2) : '';
    document.getElementById('ep-synced-at').textContent = entry.basis_synced_at
        ? formatDateTime(entry.basis_synced_at) : '—';

    document.getElementById('ep-priority').value = entry.priority_override ?? '';
    document.getElementById('ep-priority-hint').textContent =
        `Snapshot: ${_levelFullLabel(entry.priority_snapshot)}`;

    document.getElementById('ep-confidence').value = entry.confidence_override ?? '';
    document.getElementById('ep-confidence-hint').textContent =
        `Snapshot: ${_levelFullLabel(entry.confidence_snapshot)}`;

    // Budget release mode is in the Releases pane
    document.getElementById('ep-budget-release-mode').value = entry.budget_release_mode ?? '';

    document.getElementById('ep-start-sprint').value = entry.start_sprint ?? '';
    document.getElementById('ep-end-sprint').value = entry.end_sprint ?? '';
    document.getElementById('ep-dates-strict').checked = !!entry.dates_strict;

    // Load basis context (hint + estimate dropdown); pass saved estimate to pre-select
    loadBasisContext(entry.basis, entry.project, 'edit', entry.snapshotted_estimate ?? entry.estimate_id ?? null);
}

function _toggleEpAmountGroup(basis) {
    document.getElementById('ep-amount-group').classList.toggle('d-none', basis !== 'CUSTOM');
}

function _levelFullLabel(level) {
    return { VERY_HIGH: 'Very High', HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low' }[level] ?? '—';
}

async function saveEditConfig() {
    const entryId = document.getElementById('edit-proj-entry-id').value;
    const basis = document.getElementById('ep-basis').value;
    const amountEl = document.getElementById('ep-amount');
    const amountErrEl = document.getElementById('ep-amount-err');

    amountEl.classList.remove('is-invalid');
    amountErrEl.textContent = '';

    const payload = {
        basis,
        priority_override: document.getElementById('ep-priority').value || null,
        confidence_override: document.getElementById('ep-confidence').value || null,
        budget_release_mode: document.getElementById('ep-budget-release-mode').value || null,
        start_sprint: document.getElementById('ep-start-sprint').value || null,
        end_sprint: document.getElementById('ep-end-sprint').value || null,
        dates_strict: document.getElementById('ep-dates-strict').checked,
    };

    if (basis === 'ESTIMATE') {
        const estId = document.getElementById('ep-estimate-version')?.value;
        if (estId) payload.estimate_id = estId;
    }

    if (basis === 'CUSTOM') {
        const amount = parseFloat(amountEl.value);
        if (isNaN(amount) || amount < 0) {
            amountEl.classList.add('is-invalid');
            amountErrEl.textContent = 'Please enter a valid amount.';
            return;
        }
        payload.basis_amount = amount;
    }

    const spinner = document.getElementById('edit-proj-spinner');
    const btn = document.getElementById('btn-save-edit-proj');
    spinner.classList.remove('d-none');
    btn.disabled = true;

    try {
        const { method, href } = API_URLS.rp_versions.projects.update(planPk, versionPk, entryId);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('editProjectModal')).hide();
        showFlash('Project configuration saved.', 'success');
        _projectsFetcher?.refresh();
    } catch (err) {
        const msg = _extractError(err, 'Failed to save configuration.');
        document.getElementById('edit-proj-banner').textContent = msg;
        document.getElementById('edit-proj-banner').classList.remove('d-none');
    } finally {
        spinner.classList.add('d-none');
        btn.disabled = false;
    }
}

// ─── Teams Sub-tab ────────────────────────────────────────────────────────────

async function loadTeamsTab() {
    if (!_currentEditEntryId) return;
    const listEl = document.getElementById('ep-teams-list');
    listEl.innerHTML = '<p class="text-secondary small">Loading…</p>';

    try {
        const [teams, teamOptions] = await Promise.all([
            apiFetch(API_URLS.rp_versions.teams.list(planPk, versionPk, _currentEditEntryId).href),
            apiFetch(API_URLS.rp_versions.teams.options(planPk, versionPk, _currentEditEntryId).href).catch(() => []),
        ]);

        const results = Array.isArray(teams) ? teams : (teams.results ?? []);
        const options = Array.isArray(teamOptions) ? teamOptions : (teamOptions.results ?? []);

        const addTeamBtn = document.getElementById('btn-show-add-team');
        if (addTeamBtn) addTeamBtn.style.display = _modalIsView ? 'none' : '';

        const teamSelect = document.getElementById('at-team');
        teamSelect.innerHTML = options.length
            ? options.map(t => `<option value="${t.id}">${escHtml(t.name)}</option>`).join('')
            : '<option value="">No available teams</option>';

        document.getElementById('ep-team-count').textContent = results.length;

        const totalDays = results.reduce((s, t) => s + parseFloat(t.allocated_days ?? 0), 0);
        document.getElementById('ep-teams-summary').textContent =
            `${results.length} team${results.length !== 1 ? 's' : ''} · ${totalDays.toFixed(2)} days allocated`;

        const pctTeams = results.filter(t => t.allocation_type === 'PERCENT');
        const pctSum = pctTeams.reduce((s, t) => s + parseFloat(t.allocation_pct ?? 0), 0);
        const warnEl = document.getElementById('ep-teams-warning');
        if (pctTeams.length > 0 && Math.abs(pctSum - 100) > 0.01) {
            warnEl.textContent = `PERCENT allocations sum to ${pctSum.toFixed(1)}% — should total 100%.`;
            warnEl.className = 'alert alert-warning mb-2 py-2';
            warnEl.classList.remove('d-none');
        } else {
            warnEl.classList.add('d-none');
        }

        if (!results.length) {
            listEl.innerHTML = '<p class="text-secondary small mb-0">No teams assigned yet.</p>';
            return;
        }

        // Fetch phases for all teams in parallel
        const phasesMap = {};
        await Promise.all(results.map(async t => {
            try {
                const phases = await apiFetch(
                    API_URLS.rp_versions.phases.list(planPk, versionPk, _currentEditEntryId, t.id).href
                );
                phasesMap[t.id] = Array.isArray(phases) ? phases : (phases.results ?? []);
            } catch {
                phasesMap[t.id] = [];
            }
        }));

        listEl.innerHTML = `
            <div class="d-flex flex-column gap-2">
                ${results.map(t => {
                    const phases = phasesMap[t.id] ?? [];
                    const allocVal = t.allocation_pct ?? t.allocation_days ?? t.allocation_budget ?? 0;
                    const collapseId = `team-body-${t.id}`;
                    return `
                <div class="border rounded" id="team-acc-${t.id}">
                    <div class="d-flex align-items-center gap-2 px-2 py-2">
                        <button class="btn btn-link p-0 text-body text-decoration-none flex-shrink-0 js-team-toggle"
                                type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}"
                                aria-expanded="false" style="font-size:.82rem;line-height:1">
                            <i class="bi bi-chevron-right" style="transition:transform .2s"></i>
                        </button>
                        <div class="flex-grow-1 d-flex align-items-center flex-wrap gap-1">
                            <span class="fw-semibold" style="font-size:.85rem">${escHtml(t.team_name ?? '—')}</span>
                            <span class="rp-badge rp-badge--muted" style="font-size:.7rem">${escHtml(_allocTypeLabel(t.allocation_type))}</span>
                            <span style="font-size:.8rem">${parseFloat(allocVal).toLocaleString('en-GB')}</span>
                            <span class="text-secondary" style="font-size:.78rem">· ${parseFloat(t.allocated_days ?? 0).toFixed(2)} days</span>
                            <span class="rp-badge rp-badge--muted" style="font-size:.7rem">${phases.length} phase${phases.length !== 1 ? 's' : ''}</span>
                        </div>
                        ${_modalIsView ? '' : `
                        <div class="d-flex gap-1 flex-shrink-0">
                            <button class="btn btn-ghost-icon js-edit-team"
                                data-team-id="${t.id}"
                                data-type="${escHtml(t.allocation_type)}"
                                data-value="${allocVal}"
                                data-seq="${t.sequence_order ?? 1}"
                                title="Edit Allocation">
                                <i class="bi bi-pencil" style="font-size:.75rem"></i>
                            </button>
                            <button class="btn btn-ghost-icon btn-ghost-icon--danger js-del-team"
                                data-team-id="${t.id}" title="Remove">
                                <i class="bi bi-trash" style="font-size:.75rem"></i>
                            </button>
                        </div>`}
                    </div>
                    <div class="collapse" id="${collapseId}">
                        <div class="border-top px-3 py-2">
                            <div class="d-flex align-items-center justify-content-between mb-1">
                                <div class="small text-secondary fw-semibold">
                                    <i class="bi bi-layers me-1"></i>Phases
                                    <span class="badge bg-secondary ms-1 fw-normal">${phases.length}</span>
                                </div>
                                ${_modalIsView ? '' : `
                                <button class="btn btn-sm py-0 btn-outline-primary js-add-phase"
                                    data-entry-id="${_currentEditEntryId}"
                                    data-team-entry-id="${t.id}"
                                    style="font-size:.75rem">
                                    <i class="bi bi-plus-lg me-1"></i>Add Phase
                                </button>`}
                            </div>
                            ${phases.length ? `
                            <div class="d-flex flex-column gap-1">
                                ${phases.map(ph => `
                                <div class="d-flex align-items-center gap-2 py-1 px-2 rounded" style="background:var(--bs-tertiary-bg,#f8f9fa);font-size:.8rem">
                                    <span class="fw-semibold">${ph.sequence_order}.</span>
                                    <span>${escHtml(ph.name)}</span>
                                    <span class="rp-badge rp-badge--muted" style="font-size:.7rem">${escHtml(ph.ramp_pattern ?? '')}</span>
                                    ${ph.segment_count > 0 ? `<span class="rp-badge rp-badge--info" style="font-size:.7rem">${ph.segment_count} seg</span>` : ''}
                                    ${ph.dependency_count > 0 ? `<span class="rp-badge rp-badge--muted" style="font-size:.7rem">${ph.dependency_count} dep</span>` : ''}
                                    ${ph.pause_count > 0 ? `<span class="rp-badge rp-badge--warning" style="font-size:.7rem">${ph.pause_count} pause</span>` : ''}
                                    ${ph.assignment_count > 0 ? `<span class="rp-badge rp-badge--success" style="font-size:.7rem">${ph.assignment_count} assigned</span>` : ''}
                                    ${ph.is_split_incomplete ? `<span class="rp-badge rp-badge--danger" style="font-size:.7rem" title="Split values incomplete">split!</span>` : ''}
                                    <div class="ms-auto d-flex gap-1">
                                        ${_modalIsView ? '' : `
                                        <button class="btn btn-ghost-icon js-phase-up"
                                            data-phase-id="${ph.id}"
                                            data-team-id="${t.id}"
                                            title="Move Up">
                                            <i class="bi bi-arrow-up" style="font-size:.75rem"></i>
                                        </button>
                                        <button class="btn btn-ghost-icon js-phase-down"
                                            data-phase-id="${ph.id}"
                                            data-team-id="${t.id}"
                                            title="Move Down">
                                            <i class="bi bi-arrow-down" style="font-size:.75rem"></i>
                                        </button>`}
                                        <button class="btn btn-ghost-icon js-configure-phase"
                                            data-phase-id="${ph.id}"
                                            data-entry-id="${_currentEditEntryId}"
                                            data-team-entry-id="${t.id}"
                                            title="${_modalIsView ? 'View' : 'Configure'} Phase">
                                            <i class="bi bi-${_modalIsView ? 'eye' : 'gear'}" style="font-size:.75rem"></i>
                                        </button>
                                        ${_modalIsView ? '' : `
                                        <button class="btn btn-ghost-icon btn-ghost-icon--danger js-delete-phase"
                                            data-phase-id="${ph.id}"
                                            data-phase-name="${escHtml(ph.name)}"
                                            title="Delete Phase">
                                            <i class="bi bi-trash" style="font-size:.75rem"></i>
                                        </button>`}
                                    </div>
                                </div>`).join('')}
                            </div>` : `<p class="text-secondary small mb-0">No phases defined.</p>`}
                        </div>
                    </div>
                </div>`;
                }).join('')}
            </div>`;

        // Rotate chevron + close siblings on collapse show/hide
        listEl.querySelectorAll('.collapse').forEach(colEl => {
            const cardId = colEl.id.replace('team-body-', '');
            const card = document.getElementById(`team-acc-${cardId}`);
            const chevron = card?.querySelector('.js-team-toggle .bi');
            if (chevron) {
                colEl.addEventListener('show.bs.collapse', () => {
                    chevron.style.transform = 'rotate(90deg)';
                    // Close all other open collapses
                    listEl.querySelectorAll('.collapse.show').forEach(other => {
                        if (other !== colEl) bootstrap.Collapse.getOrCreateInstance(other).hide();
                    });
                });
                colEl.addEventListener('hide.bs.collapse', () => { chevron.style.transform = ''; });
            }
        });

        // Auto-expand the newly added team
        if (_newlyAddedTeamEntryId) {
            const targetCollapse = document.getElementById(`team-body-${_newlyAddedTeamEntryId}`);
            if (targetCollapse) {
                bootstrap.Collapse.getOrCreateInstance(targetCollapse).show();
            }
            _newlyAddedTeamEntryId = null;
        }

        listEl.querySelectorAll('.js-del-team').forEach(btn => {
            btn.addEventListener('click', () => deleteTeam(btn.dataset.teamId));
        });
        listEl.querySelectorAll('.js-edit-team').forEach(btn => {
            btn.addEventListener('click', () => openEditTeamModal(
                btn.dataset.teamId, btn.dataset.type, btn.dataset.value, btn.dataset.seq
            ));
        });
        listEl.querySelectorAll('.js-add-phase').forEach(btn => {
            btn.addEventListener('click', () =>
                openPhaseModal(btn.dataset.entryId, btn.dataset.teamEntryId, null)
            );
        });
        listEl.querySelectorAll('.js-configure-phase').forEach(btn => {
            btn.addEventListener('click', () =>
                openPhaseModal(btn.dataset.entryId, btn.dataset.teamEntryId, btn.dataset.phaseId)
            );
        });
        listEl.querySelectorAll('.js-delete-phase').forEach(btn => {
            btn.addEventListener('click', () => deletePhase(btn.dataset.phaseId, btn.dataset.phaseName));
        });
        listEl.querySelectorAll('.js-phase-up').forEach(btn => {
            btn.addEventListener('click', () => reorderPhase(btn.dataset.phaseId, btn.dataset.teamId, -1));
        });
        listEl.querySelectorAll('.js-phase-down').forEach(btn => {
            btn.addEventListener('click', () => reorderPhase(btn.dataset.phaseId, btn.dataset.teamId, +1));
        });
    } catch {
        listEl.innerHTML = '<p class="text-danger small">Failed to load teams.</p>';
    }
}

function _allocTypeLabel(type) {
    return { PERCENT: '% of Basis Amount', DAYS: 'Days', BUDGET: 'Budget (£)' }[type] ?? type;
}

function _updateReleaseModeForm(mode) {
    const addBtn = document.getElementById('btn-show-add-release');
    const sprintGroup = document.getElementById('ar-sprint-group');
    const monthGroup = document.getElementById('ar-month-group');
    if (!addBtn) return;

    if (mode === 'SPRINT') {
        addBtn.disabled = false;
        addBtn.title = 'Add Release';
        sprintGroup?.classList.remove('d-none');
        monthGroup?.classList.add('d-none');
        // Populate sprint select if needed
        const sprintSel = document.getElementById('ar-sprint');
        if (sprintSel && !sprintSel.options.length) {
            const sprints = _optionsData?.sprints ?? [];
            sprintSel.innerHTML = sprints.length
                ? sprints.map(s => `<option value="${s.id}">${escHtml(s.sprint_name ?? s.name ?? '')}</option>`).join('')
                : '<option value="">No sprints available</option>';
        }
    } else if (mode === 'MONTH') {
        addBtn.disabled = false;
        addBtn.title = 'Add Release';
        sprintGroup?.classList.add('d-none');
        monthGroup?.classList.remove('d-none');
    } else {
        addBtn.disabled = true;
        addBtn.title = 'Set a Release Mode first.';
    }
}

async function addTeam() {
    const teamId = document.getElementById('at-team').value;
    const type = document.getElementById('at-type').value;
    const value = parseFloat(document.getElementById('at-value').value);
    const seq = parseInt(document.getElementById('at-seq').value, 10) || 1;
    const errEl = document.getElementById('at-err');

    errEl.classList.add('d-none');

    if (!teamId) {
        errEl.textContent = 'Please select a team.';
        errEl.classList.remove('d-none');
        return;
    }
    if (isNaN(value) || value < 0) {
        errEl.textContent = 'Please enter a valid value.';
        errEl.classList.remove('d-none');
        return;
    }

    const btn = document.getElementById('btn-confirm-add-team');
    btn.disabled = true;

    try {
        const { method, href } = API_URLS.rp_versions.teams.create(planPk, versionPk, _currentEditEntryId);
        const newTeam = await apiFetch(href, {
            method,
            body: JSON.stringify({
                team: teamId,
                allocation_type: type,
                value,
                sequence_order: seq,
            }),
        });
        _newlyAddedTeamEntryId = newTeam?.id ?? null;
        document.getElementById('add-team-form').classList.add('d-none');
        document.getElementById('at-value').value = '';
        loadTeamsTab();
        _projectsFetcher?.refresh();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to add team.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

async function deleteTeam(teamEntryId) {
    try {
        const { method, href } = API_URLS.rp_versions.teams.delete(
            planPk, versionPk, _currentEditEntryId, teamEntryId
        );
        await apiFetch(href, { method });
        loadTeamsTab();
        _projectsFetcher?.refresh();
    } catch (err) {
        showFlash(_extractError(err, 'Failed to remove team.'), 'error');
    }
}

function openEditTeamModal(teamId, type, value, seq) {
    document.getElementById('et-team-id').value = teamId;
    document.getElementById('et-type').value = type;
    document.getElementById('et-value').value = parseFloat(value).toLocaleString('en-GB', { maximumFractionDigits: 4 });
    document.getElementById('et-seq').value = seq;
    document.getElementById('et-err').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('editTeamModal')).show();
}

async function saveTeam() {
    const teamId = document.getElementById('et-team-id').value;
    const type = document.getElementById('et-type').value;
    const value = parseFloat(document.getElementById('et-value').value.replace(/,/g, ''));
    const seq = parseInt(document.getElementById('et-seq').value, 10) || 1;
    const errEl = document.getElementById('et-err');
    errEl.classList.add('d-none');

    if (isNaN(value) || value < 0) {
        errEl.textContent = 'Please enter a valid value.';
        errEl.classList.remove('d-none');
        return;
    }

    const btn = document.getElementById('btn-confirm-edit-team');
    btn.disabled = true;
    try {
        const { method, href } = API_URLS.rp_versions.teams.update(
            planPk, versionPk, _currentEditEntryId, teamId
        );
        await apiFetch(href, {
            method,
            body: JSON.stringify({ allocation_type: type, value, sequence_order: seq }),
        });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('editTeamModal')).hide();
        loadTeamsTab();
        _projectsFetcher?.refresh();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to update team.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

// ─── Budget Releases Sub-tab ──────────────────────────────────────────────────

async function loadReleasesTab() {
    if (!_currentEditEntryId) return;
    const listEl = document.getElementById('ep-releases-list');
    listEl.innerHTML = '<p class="text-secondary small">Loading…</p>';

    const addReleaseBtn = document.getElementById('btn-show-add-release');
    addReleaseBtn.style.display = _modalIsView ? 'none' : '';
    addReleaseBtn.disabled = false;
    addReleaseBtn.title = 'Add Release';

    try {
        const data = await apiFetch(API_URLS.rp_versions.releases.list(planPk, versionPk, _currentEditEntryId).href);
        const results = Array.isArray(data) ? data : (data.results ?? []);

        // Read mode from DOM (it's set by loadEditConfigTab)
        const mode = document.getElementById('ep-budget-release-mode')?.value || '';
        _updateReleaseModeForm(mode);

        const releaseSum = results.reduce((s, r) => s + parseFloat(r.amount ?? 0), 0);
        const basisAmount = parseFloat(_currentEditEntry?.basis_amount ?? 0);
        document.getElementById('ep-release-count').textContent = results.length;
        document.getElementById('ep-releases-summary').textContent =
            `${results.length} release${results.length !== 1 ? 's' : ''} · ` +
            `£${releaseSum.toLocaleString('en-GB', { minimumFractionDigits: 2 })} ` +
            `of £${basisAmount.toLocaleString('en-GB', { minimumFractionDigits: 2 })}`;

        const warnEl = document.getElementById('ep-releases-warning');
        if (basisAmount > 0 && Math.abs(releaseSum - basisAmount) > 0.01) {
            warnEl.textContent =
                `Release total £${releaseSum.toLocaleString('en-GB', { minimumFractionDigits: 2 })} ` +
                `does not match basis amount £${basisAmount.toLocaleString('en-GB', { minimumFractionDigits: 2 })}.`;
            warnEl.className = 'alert alert-warning mb-2 py-2';
            warnEl.classList.remove('d-none');
        } else {
            warnEl.classList.add('d-none');
        }

        if (!results.length) {
            listEl.innerHTML = '<p class="text-secondary small mb-0">No budget releases yet.</p>';
            return;
        }

        const isMonth = mode === 'MONTH';
        listEl.innerHTML = `
            <table class="table table-sm rp-table mb-0">
                <thead>
                    <tr>
                        <th>${isMonth ? 'Month' : 'Sprint'}</th>
                        <th class="text-end">Amount (£)</th>
                        <th>Notes</th>
                        ${_modalIsView ? '' : '<th style="width:36px"></th>'}
                    </tr>
                </thead>
                <tbody>
                    ${results.map(r => `
                    <tr>
                        <td style="font-size:.85rem">${escHtml(isMonth ? (r.month ?? '—') : (r.sprint_name ?? '—'))}</td>
                        <td class="text-end" style="font-size:.82rem">£${parseFloat(r.amount ?? 0).toLocaleString('en-GB', { minimumFractionDigits: 2 })}</td>
                        <td style="font-size:.82rem">${escHtml(r.notes ?? '')}</td>
                        ${_modalIsView ? '' : `<td>
                            <button class="btn btn-ghost-icon btn-ghost-icon--danger js-del-release"
                                data-release-id="${r.id}" title="Remove">
                                <i class="bi bi-trash" style="font-size:.75rem"></i>
                            </button>
                        </td>`}
                    </tr>`).join('')}
                </tbody>
            </table>`;

        listEl.querySelectorAll('.js-del-release').forEach(btn => {
            btn.addEventListener('click', () => deleteRelease(btn.dataset.releaseId));
        });
    } catch {
        listEl.innerHTML = '<p class="text-danger small">Failed to load budget releases.</p>';
    }
}

async function addRelease() {
    // Read mode from the DOM element (in releases pane)
    const mode = document.getElementById('ep-budget-release-mode')?.value || '';
    const errEl = document.getElementById('ar-err');
    errEl.classList.add('d-none');

    const amount = parseFloat(document.getElementById('ar-amount').value);
    if (isNaN(amount) || amount <= 0) {
        errEl.textContent = 'Please enter a valid positive amount.';
        errEl.classList.remove('d-none');
        return;
    }

    const payload = {
        amount,
        notes: document.getElementById('ar-notes').value.trim() || null,
        entry_type: mode,
    };

    if (mode === 'SPRINT') {
        const sprintId = document.getElementById('ar-sprint').value;
        if (!sprintId) {
            errEl.textContent = 'Please select a sprint.';
            errEl.classList.remove('d-none');
            return;
        }
        payload.sprint = sprintId;
    } else if (mode === 'MONTH') {
        payload.month = document.getElementById('ar-month').value;
    } else {
        errEl.textContent = 'Please set a Release Mode first.';
        errEl.classList.remove('d-none');
        return;
    }

    const btn = document.getElementById('btn-confirm-add-release');
    btn.disabled = true;

    try {
        const { method, href } = API_URLS.rp_versions.releases.create(planPk, versionPk, _currentEditEntryId);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        document.getElementById('add-release-form').classList.add('d-none');
        document.getElementById('ar-amount').value = '';
        document.getElementById('ar-notes').value = '';
        loadReleasesTab();
        _projectsFetcher?.refresh();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to add budget release.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

async function deleteRelease(releaseId) {
    try {
        const { method, href } = API_URLS.rp_versions.releases.delete(
            planPk, versionPk, _currentEditEntryId, releaseId
        );
        await apiFetch(href, { method });
        loadReleasesTab();
        _projectsFetcher?.refresh();
    } catch (err) {
        showFlash(_extractError(err, 'Failed to remove budget release.'), 'error');
    }
}

// ─── Delete Project Modal ─────────────────────────────────────────────────────

function openDeleteModal(entryId, projectName) {
    document.getElementById('del-proj-entry-id').value = entryId;
    document.getElementById('del-proj-name').textContent = projectName || 'this project';
    document.getElementById('del-proj-banner').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('deleteProjectModal')).show();
}

async function confirmDeleteProject() {
    const entryId = document.getElementById('del-proj-entry-id').value;
    const spinner = document.getElementById('del-proj-spinner');
    const btn = document.getElementById('btn-confirm-del-proj');

    spinner.classList.remove('d-none');
    btn.disabled = true;

    try {
        const { method, href } = API_URLS.rp_versions.projects.delete(planPk, versionPk, entryId);
        await apiFetch(href, { method });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('deleteProjectModal')).hide();
        showFlash('Project removed from version.', 'success');
        _projectsFetcher?.refresh();
        loadUnmappedProjects();
    } catch (err) {
        const msg = _extractError(err, 'Failed to remove project.');
        document.getElementById('del-proj-banner').textContent = msg;
        document.getElementById('del-proj-banner').classList.remove('d-none');
    } finally {
        spinner.classList.add('d-none');
        btn.disabled = false;
    }
}

// ─── Resync Modal ─────────────────────────────────────────────────────────────

function openResyncModal(entryId, projectName, basis) {
    document.getElementById('resync-entry-id').value = entryId;
    document.getElementById('resync-proj-name').textContent = projectName || 'this project';
    document.getElementById('resync-basis-label').textContent = _basisLabel(basis).toLowerCase();
    document.getElementById('resync-banner').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('resyncModal')).show();
}

async function confirmResync() {
    const entryId = document.getElementById('resync-entry-id').value;
    const spinner = document.getElementById('resync-spinner');
    const btn = document.getElementById('btn-confirm-resync');

    spinner.classList.remove('d-none');
    btn.disabled = true;

    try {
        const { method, href } = API_URLS.rp_versions.projects.resync(planPk, versionPk, entryId);
        await apiFetch(href, { method });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('resyncModal')).hide();
        showFlash('Project basis resynced successfully.', 'success');
        _projectsFetcher?.refresh();
    } catch (err) {
        const msg = _extractError(err, 'Failed to resync project.');
        document.getElementById('resync-banner').textContent = msg;
        document.getElementById('resync-banner').classList.remove('d-none');
    } finally {
        spinner.classList.add('d-none');
        btn.disabled = false;
    }
}

// ─── Sprint Options ───────────────────────────────────────────────────────────

function populateSprintOptions() {
    const sprints = _optionsData?.sprints ?? [];
    const sprintOptions = sprints.map(s =>
        `<option value="${s.id}">${escHtml(s.sprint_name ?? s.name ?? '')}</option>`
    ).join('');
    const none = '<option value="">— None —</option>';

    ['ep-start-sprint', 'ep-end-sprint'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = none + sprintOptions;
    });
}

// ─── Event Binding ────────────────────────────────────────────────────────────

function bindEvents() {
    bindCalculator();

    let _searchTimer;
    document.getElementById('unmapped-search')?.addEventListener('input', e => {
        clearTimeout(_searchTimer);
        _searchTimer = setTimeout(() => renderUnmappedProjects(e.target.value.trim()), 300);
    });

    // Add modal — basis change
    document.getElementById('add-proj-basis')?.addEventListener('change', e => {
        const basis = e.target.value;
        document.getElementById('add-proj-amount-group').classList.toggle('d-none', basis !== 'CUSTOM');
        const projectId = document.getElementById('add-proj-id').value;
        loadBasisContext(basis, projectId, 'add');
    });

    // Add modal — estimate version selection
    document.getElementById('add-estimate-version')?.addEventListener('change', e => {
        const valueEl = document.getElementById('add-basis-hint-value');
        const subEl = document.getElementById('add-basis-hint-sub');
        _updateEstimateHint(e.target, valueEl, subEl);
    });

    document.getElementById('btn-confirm-add-proj')?.addEventListener('click', submitAddProject);

    // Edit modal — basis change
    document.getElementById('ep-basis')?.addEventListener('change', e => {
        const basis = e.target.value;
        _toggleEpAmountGroup(basis);
        loadBasisContext(basis, _currentEditEntry?.project, 'edit');
    });

    // Edit modal — estimate version selection
    document.getElementById('ep-estimate-version')?.addEventListener('change', e => {
        const valueEl = document.getElementById('ep-basis-hint-value');
        const subEl = document.getElementById('ep-basis-hint-sub');
        _updateEstimateHint(e.target, valueEl, subEl);
    });

    document.getElementById('btn-save-edit-proj')?.addEventListener('click', saveEditConfig);

    document.getElementById('ep-tab-teams')?.addEventListener('shown.bs.tab', loadTeamsTab);
    document.getElementById('ep-tab-releases')?.addEventListener('shown.bs.tab', loadReleasesTab);

    // Budget release mode change: update warning + re-configure add-release form
    document.getElementById('ep-budget-release-mode')?.addEventListener('change', e => {
        const mode = e.target.value;
        const releaseCount = parseInt(document.getElementById('ep-release-count')?.textContent ?? '0', 10);
        const warnEl = document.getElementById('ep-mode-change-warn');
        if (releaseCount > 0 && warnEl) {
            warnEl.classList.remove('d-none');
        } else if (warnEl) {
            warnEl.classList.add('d-none');
        }
        _updateReleaseModeForm(mode);
    });

    document.getElementById('btn-show-add-team')?.addEventListener('click', () => {
        document.getElementById('add-team-form').classList.remove('d-none');
    });
    document.getElementById('btn-cancel-add-team')?.addEventListener('click', () => {
        document.getElementById('add-team-form').classList.add('d-none');
        document.getElementById('at-err').classList.add('d-none');
    });
    document.getElementById('btn-confirm-add-team')?.addEventListener('click', addTeam);

    document.getElementById('btn-show-add-release')?.addEventListener('click', () => {
        document.getElementById('add-release-form').classList.remove('d-none');
    });
    document.getElementById('btn-cancel-add-release')?.addEventListener('click', () => {
        document.getElementById('add-release-form').classList.add('d-none');
        document.getElementById('ar-err').classList.add('d-none');
    });
    document.getElementById('btn-confirm-add-release')?.addEventListener('click', addRelease);

    document.getElementById('btn-confirm-del-proj')?.addEventListener('click', confirmDeleteProject);
    document.getElementById('btn-confirm-resync')?.addEventListener('click', confirmResync);
    document.getElementById('btn-confirm-edit-team')?.addEventListener('click', saveTeam);

    document.getElementById('editProjectModal')?.addEventListener('show.bs.modal', () => {
        document.getElementById('add-team-form').classList.add('d-none');
        document.getElementById('add-release-form').classList.add('d-none');
        document.getElementById('ep-teams-warning').classList.add('d-none');
        document.getElementById('ep-releases-warning').classList.add('d-none');
        document.getElementById('at-err').classList.add('d-none');
        document.getElementById('ar-err').classList.add('d-none');
        document.getElementById('ep-mode-change-warn').classList.add('d-none');
    });
    document.getElementById('editProjectModal')?.addEventListener('hidden.bs.modal', () => {
        // Skip cleanup if modal was temporarily hidden to open phase modal
        if (_parentModalHiddenForPhase) return;
        _currentEditEntryId = null;
        _currentEditEntry = null;
        _modalIsView = false;
        _applyViewMode(false);
    });

    bindPhaseEvents();

    document.getElementById('tab-vc-jobs')?.addEventListener('shown.bs.tab', () => {
        _vcRenderJobs();
    });

    document.getElementById('vc-btn-run-engine')?.addEventListener('click', async () => {
        await _vcResetEngineModal();
        bootstrap.Modal.getOrCreateInstance(document.getElementById('vcEngineModal')).show();
    });

    document.getElementById('vc-btn-engine-submit')?.addEventListener('click', _vcSubmitEngineRun);

    document.getElementById('vcEngineModal')?.addEventListener('hidden.bs.modal', () => {
        _vcStopEnginePoller();
    });
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function _showBanner(message, type = 'danger') {
    const banner = document.getElementById('vc-banner');
    if (!banner) return;
    banner.textContent = message;
    banner.className = `alert alert-${type} mb-3`;
    banner.classList.remove('d-none');
}

function _extractError(err, fallback) {
    const d = err?.data;
    if (!d) return fallback;
    if (d.detail) return typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
    if (d.error) return d.error;
    if (d.details) {
        if (typeof d.details === 'string') return d.details;
        if (Array.isArray(d.details)) return d.details.join(' ');
        if (typeof d.details === 'object') return Object.values(d.details).flat().filter(v => typeof v === 'string').join(' ');
    }
    // DRF field-level errors: {"field_name": ["message"]}
    const fieldMsgs = Object.values(d).flat().filter(v => typeof v === 'string');
    if (fieldMsgs.length) return fieldMsgs.join(' ');
    return fallback;
}

// ─── Phase Modal ──────────────────────────────────────────────────────────────

function _phaseModalEl() { return document.getElementById('phaseModal'); }
function _phaseBanner(msg) {
    const el = document.getElementById('phase-banner');
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('d-none');
}
function _clearPhaseBanner() {
    document.getElementById('phase-banner')?.classList.add('d-none');
}

async function openPhaseModal(entryId, teamEntryId, phaseId) {
    _phaseEntryId = entryId;
    _phaseTeamEntryId = teamEntryId;
    _currentPhaseId = phaseId || null;

    // Hide parent modal to avoid backdrop/scroll issues with nested modals
    const parentModalEl = document.getElementById('editProjectModal');
    if (parentModalEl?.classList.contains('show')) {
        _parentModalHiddenForPhase = true;
        bootstrap.Modal.getInstance(parentModalEl)?.hide();
        // Wait for hide transition before opening phase modal
        await new Promise(resolve => {
            parentModalEl.addEventListener('hidden.bs.modal', resolve, { once: true });
        });
    }

    document.getElementById('phase-entry-id').value = entryId;
    document.getElementById('phase-team-entry-id').value = teamEntryId;
    _clearPhaseBanner();

    // Reset tabs
    const configTab = document.getElementById('ph-tab-config');
    if (configTab) bootstrap.Tab.getOrCreateInstance(configTab).show();

    // Reset badge counts
    ['ph-segment-count', 'ph-dep-count', 'ph-pause-count', 'ph-assign-count'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '0';
    });

    // Show save button
    const saveBtn = document.getElementById('btn-save-phase');
    if (saveBtn) saveBtn.style.display = _modalIsView ? 'none' : '';

    // Populate sprint dropdowns BEFORE filling values so selects are ready
    _populatePhaseSprintDropdowns();

    if (phaseId) {
        document.getElementById('phase-modal-title').textContent = 'Loading…';
        bootstrap.Modal.getOrCreateInstance(_phaseModalEl()).show();
        try {
            const phase = await apiFetch(API_URLS.rp_versions.phases.detail(planPk, versionPk, phaseId).href);
            document.getElementById('phase-modal-title').textContent =
                `${_modalIsView ? 'View' : 'Configure'} Phase: ${escHtml(phase.name)}`;
            _fillPhaseConfigTab(phase);
            document.getElementById('ph-segment-count').textContent = phase.segment_count ?? 0;
            document.getElementById('ph-dep-count').textContent = phase.dependency_count ?? 0;
            document.getElementById('ph-pause-count').textContent = phase.pause_count ?? 0;
            document.getElementById('ph-assign-count').textContent = phase.assignment_count ?? 0;
            _updateSplitModeHint(phase.split_mode ?? 'AUTO');
            _updateSuggestButton(phase.ramp_pattern ?? 'FLAT');
        } catch (err) {
            _phaseBanner(_extractError(err, 'Failed to load phase.'));
        }
    } else {
        document.getElementById('phase-modal-title').textContent = 'New Phase';
        _fillPhaseConfigTab(null);
        _updateSplitModeHint('AUTO');
        _updateSuggestButton('FLAT');
        bootstrap.Modal.getOrCreateInstance(_phaseModalEl()).show();
    }
}

function _fillPhaseConfigTab(phase) {
    document.getElementById('ph-name').value = phase?.name ?? '';
    document.getElementById('ph-sequence').value = phase?.sequence_order ?? 1;
    document.getElementById('ph-max-days').value = phase?.max_days_per_sprint
        ? parseFloat(phase.max_days_per_sprint) : '';
    document.getElementById('ph-start-sprint').value = phase?.start_sprint ?? '';
    document.getElementById('ph-end-sprint').value = phase?.end_sprint ?? '';
    document.getElementById('ph-ramp-pattern').value = phase?.ramp_pattern ?? 'FLAT';
    document.getElementById('ph-multi-eng').checked = !!phase?.allow_multiple_engineers;
    document.getElementById('ph-split-mode').value = phase?.split_mode ?? 'AUTO';
    document.getElementById('ph-notes').value = phase?.notes ?? '';
}

const _SPLIT_HINTS = {
    AUTO:    'Days are distributed automatically based on the ramp pattern and team capacity.',
    PERCENT: 'Each sprint receives a % of the total phase days. Configure via Segments.',
    DAYS:    'Each sprint receives a fixed number of days. Configure via Segments.',
    EQUAL:   'Total days are split equally across all sprints in the phase.',
};

function _updateSplitModeHint(mode) {
    const el = document.getElementById('ph-split-mode-hint');
    if (el) {
        el.textContent = _SPLIT_HINTS[mode] ?? '';
        el.className = 'form-text text-secondary mt-1' + (mode ? '' : ' d-none');
    }
}

function _updateSuggestButton(rampPattern) {
    const btn = document.getElementById('btn-suggest-segments');
    if (!btn) return;
    const isCustom = rampPattern === 'CUSTOM';
    btn.disabled = isCustom;
    btn.title = isCustom ? 'Suggest is not available for Custom ramp pattern.' : 'Auto-generate segments from ramp pattern';
}

function _populatePhaseSprintDropdowns() {
    const sprints = _optionsData?.sprints ?? [];
    const noneOpt = '<option value="">— None —</option>';
    const sprintOpts = sprints.map(s => `<option value="${s.id}">${escHtml(s.sprint_name ?? '')}</option>`).join('');
    ['ph-start-sprint', 'ph-end-sprint'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = noneOpt + sprintOpts;
    });
    // Pause sprint selects (no "None" option)
    ['ap-from', 'ap-until', 'ep2-until'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = sprintOpts || '<option value="">No sprints</option>';
    });
}

async function savePhase() {
    const name = document.getElementById('ph-name').value.trim();
    if (!name) {
        _phaseBanner('Phase name is required.');
        return;
    }

    const payload = {
        name,
        sequence_order: parseInt(document.getElementById('ph-sequence').value, 10) || 1,
        start_sprint: document.getElementById('ph-start-sprint').value || null,
        end_sprint: document.getElementById('ph-end-sprint').value || null,
        max_days_per_sprint: document.getElementById('ph-max-days').value
            ? parseFloat(document.getElementById('ph-max-days').value) : null,
        ramp_pattern: document.getElementById('ph-ramp-pattern').value,
        allow_multiple_engineers: document.getElementById('ph-multi-eng').checked,
        split_mode: document.getElementById('ph-split-mode').value,
        notes: document.getElementById('ph-notes').value.trim() || null,
    };

    const spinner = document.getElementById('save-phase-spinner');
    const btn = document.getElementById('btn-save-phase');
    spinner.classList.remove('d-none');
    btn.disabled = true;
    _clearPhaseBanner();

    try {
        if (_currentPhaseId) {
            const { method, href } = API_URLS.rp_versions.phases.update(planPk, versionPk, _currentPhaseId);
            const updated = await apiFetch(href, { method, body: JSON.stringify(payload) });
            document.getElementById('phase-modal-title').textContent =
                `Configure Phase: ${escHtml(updated.name)}`;
        } else {
            const { method, href } = API_URLS.rp_versions.phases.create(
                planPk, versionPk, _phaseEntryId, _phaseTeamEntryId
            );
            const created = await apiFetch(href, { method, body: JSON.stringify(payload) });
            _currentPhaseId = created.id;
            document.getElementById('phase-modal-title').textContent =
                `Configure Phase: ${escHtml(created.name)}`;
        }
        bootstrap.Modal.getOrCreateInstance(_phaseModalEl()).hide();
        showFlash('Phase saved.', 'success');
        loadTeamsTab();
    } catch (err) {
        _phaseBanner(_extractError(err, 'Failed to save phase.'));
    } finally {
        spinner.classList.add('d-none');
        btn.disabled = false;
    }
}

async function deletePhase(phaseId, phaseName) {
    if (!confirm(`Delete phase "${phaseName}"? This will also remove all its segments, dependencies, and pauses.`)) return;
    try {
        const { method, href } = API_URLS.rp_versions.phases.delete(planPk, versionPk, phaseId);
        await apiFetch(href, { method });
        showFlash('Phase deleted.', 'success');
        loadTeamsTab();
    } catch (err) {
        showFlash(_extractError(err, 'Cannot delete phase — another phase may depend on it.'), 'error');
    }
}

async function reorderPhase(phaseId, teamId, direction) {
    // Fetch current phases for this team, find target, swap sequence_order
    try {
        const phases = await apiFetch(
            API_URLS.rp_versions.phases.list(planPk, versionPk, _currentEditEntryId, teamId).href
        );
        const list = Array.isArray(phases) ? phases : (phases.results ?? []);
        const idx = list.findIndex(p => String(p.id) === String(phaseId));
        if (idx === -1) return;
        const swapIdx = idx + direction;
        if (swapIdx < 0 || swapIdx >= list.length) return;

        const current = list[idx];
        const target = list[swapIdx];
        // Swap sequence_order values
        await Promise.all([
            apiFetch(API_URLS.rp_versions.phases.update(planPk, versionPk, current.id).href, {
                method: API_URLS.rp_versions.phases.update(planPk, versionPk, current.id).method,
                body: JSON.stringify({ sequence_order: target.sequence_order }),
            }),
            apiFetch(API_URLS.rp_versions.phases.update(planPk, versionPk, target.id).href, {
                method: API_URLS.rp_versions.phases.update(planPk, versionPk, target.id).method,
                body: JSON.stringify({ sequence_order: current.sequence_order }),
            }),
        ]);
        loadTeamsTab();
    } catch (err) {
        showFlash(_extractError(err, 'Failed to reorder phases.'), 'error');
    }
}

// ─── Phase Segments Tab ───────────────────────────────────────────────────────

async function loadPhaseSegmentsTab() {
    if (!_currentPhaseId) {
        document.getElementById('ph-segments-list').innerHTML =
            '<p class="text-secondary small">Save the phase first to add segments.</p>';
        return;
    }
    const listEl = document.getElementById('ph-segments-list');
    listEl.innerHTML = '<p class="text-secondary small">Loading…</p>';

    try {
        const data = await apiFetch(API_URLS.rp_versions.phases.segments.list(planPk, versionPk, _currentPhaseId).href);
        const segments = Array.isArray(data) ? data : (data.results ?? []);

        document.getElementById('ph-segment-count').textContent = segments.length;
        document.getElementById('ph-segments-summary').textContent =
            `${segments.length} segment${segments.length !== 1 ? 's' : ''} · ` +
            `${segments.reduce((s, seg) => s + (seg.duration || 0), 0)} sprints total`;

        if (!segments.length) {
            listEl.innerHTML = '<p class="text-secondary small mb-0">No segments defined. Use "Suggest" to generate from ramp pattern.</p>';
            document.getElementById('ph-segments-chart-wrap')?.classList.add('d-none');
            return;
        }

        listEl.innerHTML = `
            <table class="table table-sm rp-table mb-0">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Type</th>
                        <th class="text-end">Start %</th>
                        <th class="text-end">End %</th>
                        <th>Progression</th>
                        <th class="text-end">Duration</th>
                        ${_modalIsView ? '' : '<th style="width:36px"></th>'}
                    </tr>
                </thead>
                <tbody>
                    ${segments.map(s => `
                    <tr>
                        <td style="font-size:.82rem">${s.segment_order}</td>
                        <td style="font-size:.82rem"><span class="rp-badge rp-badge--muted">${escHtml(s.segment_type)}</span></td>
                        <td class="text-end" style="font-size:.82rem">${parseFloat(s.start_pct).toFixed(0)}%</td>
                        <td class="text-end" style="font-size:.82rem">${parseFloat(s.end_pct).toFixed(0)}%</td>
                        <td style="font-size:.82rem">${escHtml(s.progression)}${s.step_count ? ` (${s.step_count})` : ''}</td>
                        <td class="text-end" style="font-size:.82rem">${s.duration}</td>
                        ${_modalIsView ? '' : `<td>
                            <button class="btn btn-ghost-icon btn-ghost-icon--danger js-del-segment"
                                data-seg-id="${s.id}" title="Remove">
                                <i class="bi bi-trash" style="font-size:.75rem"></i>
                            </button>
                        </td>`}
                    </tr>`).join('')}
                </tbody>
            </table>`;

        listEl.querySelectorAll('.js-del-segment').forEach(btn => {
            btn.addEventListener('click', () => deleteSegment(btn.dataset.segId));
        });

        // Draw chart
        renderSegmentsChart(segments);
    } catch {
        listEl.innerHTML = '<p class="text-danger small">Failed to load segments.</p>';
    }
}

function _computeSegmentPoints(seg) {
    const s = parseFloat(seg.start_pct);
    const e = parseFloat(seg.end_pct);
    const dur = parseInt(seg.duration, 10) || 1;
    const steps = parseInt(seg.step_count, 10) || 3;
    const points = [];
    for (let i = 0; i < dur; i++) {
        const t = dur > 1 ? i / (dur - 1) : 0;
        let pct;
        switch (seg.progression) {
            case 'FLAT': pct = e; break;
            case 'EXPONENTIAL': pct = s + Math.pow(t, 2) * (e - s); break;
            case 'LOGARITHMIC': {
                const lt = t > 0 ? Math.log(1 + t * (Math.E - 1)) : 0;
                pct = s + lt * (e - s);
                break;
            }
            case 'STEPPED': {
                const step = Math.min(Math.floor(t * steps), steps - 1);
                pct = s + (step / (steps - 1)) * (e - s);
                break;
            }
            default: pct = s + t * (e - s);
        }
        points.push(Math.round(pct * 10) / 10);
    }
    return points;
}

function renderSegmentsChart(segments) {
    const wrap = document.getElementById('ph-segments-chart-wrap');
    const canvas = document.getElementById('ph-segments-chart');
    if (!wrap || !canvas || typeof Chart === 'undefined') return;

    if (_segmentsChart) {
        _segmentsChart.destroy();
        _segmentsChart = null;
    }

    const allPoints = segments.flatMap(seg => _computeSegmentPoints(seg));
    // Use actual FY sprint names if start sprint is set
    const startSprintId = document.getElementById('ph-start-sprint')?.value;
    const allSprints = _optionsData?.sprints ?? [];
    const startIdx = startSprintId ? allSprints.findIndex(s => String(s.id) === String(startSprintId)) : -1;
    const labels = allPoints.map((_, i) => {
        const sprint = startIdx >= 0 ? allSprints[startIdx + i] : null;
        return sprint ? (sprint.sprint_name ?? sprint.name ?? `S${i + 1}`) : `S${i + 1}`;
    });

    // Chart stays hidden until user clicks "Preview Ramp"; just store data for later use
    _segmentsChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Capacity %',
                data: allPoints,
                fill: true,
                tension: 0.2,
                borderColor: 'rgb(108, 92, 231)',
                backgroundColor: 'rgba(108, 92, 231, 0.1)',
                pointRadius: 3,
            }],
        },
        options: {
            responsive: true,
            scales: {
                y: { min: 0, max: 100, ticks: { callback: v => v + '%' } },
            },
            plugins: { legend: { display: false } },
        },
    });
}

async function addSegment() {
    if (!_currentPhaseId) { return; }
    const errEl = document.getElementById('as-err');
    errEl.classList.add('d-none');

    const payload = {
        segment_type: document.getElementById('as-type').value,
        start_pct: parseFloat(document.getElementById('as-start-pct').value) || 0,
        end_pct: parseFloat(document.getElementById('as-end-pct').value) || 100,
        progression: document.getElementById('as-progression').value,
        duration: parseInt(document.getElementById('as-duration').value, 10) || 1,
    };
    const stepCountEl = document.getElementById('as-step-count');
    if (!stepCountEl.closest('#as-step-count-group').classList.contains('d-none') && stepCountEl.value) {
        payload.step_count = parseInt(stepCountEl.value, 10);
    }

    const btn = document.getElementById('btn-confirm-add-segment');
    btn.disabled = true;
    try {
        const { method, href } = API_URLS.rp_versions.phases.segments.create(planPk, versionPk, _currentPhaseId);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        document.getElementById('add-segment-form').classList.add('d-none');
        loadPhaseSegmentsTab();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to add segment.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

async function suggestSegments() {
    if (!_currentPhaseId) return;
    try {
        const { method, href } = API_URLS.rp_versions.phases.segments.suggest(planPk, versionPk, _currentPhaseId);
        const suggestions = await apiFetch(href, { method, body: JSON.stringify({}) });
        if (!suggestions?.length) {
            showFlash('No suggestions available for this ramp pattern.', 'info');
            return;
        }
        // Save each suggestion sequentially
        const createUrl = API_URLS.rp_versions.phases.segments.create(planPk, versionPk, _currentPhaseId);
        for (const seg of suggestions) {
            await apiFetch(createUrl.href, { method: createUrl.method, body: JSON.stringify(seg) });
        }
        loadPhaseSegmentsTab();
        showFlash(`${suggestions.length} segment${suggestions.length !== 1 ? 's' : ''} added.`, 'success');
    } catch (err) {
        showFlash(_extractError(err, 'Failed to generate suggestions.'), 'error');
    }
}

async function deleteSegment(segId) {
    try {
        const { method, href } = API_URLS.rp_versions.phases.segments.delete(planPk, versionPk, _currentPhaseId, segId);
        await apiFetch(href, { method });
        // Auto-renumber remaining segments in order
        const remaining = await apiFetch(API_URLS.rp_versions.phases.segments.list(planPk, versionPk, _currentPhaseId).href);
        const segs = Array.isArray(remaining) ? remaining : (remaining.results ?? []);
        if (segs.length > 0) {
            const reorderUrl = API_URLS.rp_versions.phases.segments.reorder(planPk, versionPk, _currentPhaseId);
            await apiFetch(reorderUrl.href, {
                method: reorderUrl.method,
                body: JSON.stringify({ order: segs.map(s => s.id) }),
            });
        }
        loadPhaseSegmentsTab();
    } catch (err) {
        showFlash(_extractError(err, 'Failed to remove segment.'), 'error');
    }
}

// ─── Phase Dependencies Tab ───────────────────────────────────────────────────

async function loadPhaseDependenciesTab() {
    if (!_currentPhaseId) {
        document.getElementById('ph-deps-list').innerHTML =
            '<p class="text-secondary small">Save the phase first to add dependencies.</p>';
        return;
    }
    const listEl = document.getElementById('ph-deps-list');
    listEl.innerHTML = '<p class="text-secondary small">Loading…</p>';

    try {
        const [deps, phaseOptions] = await Promise.all([
            apiFetch(API_URLS.rp_versions.phases.dependencies.list(planPk, versionPk, _currentPhaseId).href),
            apiFetch(API_URLS.rp_versions.phases.options(planPk, versionPk).href).catch(() => []),
        ]);
        const results = Array.isArray(deps) ? deps : (deps.results ?? []);
        document.getElementById('ph-dep-count').textContent = results.length;
        document.getElementById('ph-deps-summary').textContent =
            `${results.length} dependenc${results.length !== 1 ? 'ies' : 'y'}`;

        // Populate predecessor select (grouped by project)
        const predSel = document.getElementById('ad-predecessor');
        const groups = Array.isArray(phaseOptions) ? phaseOptions : (phaseOptions.results ?? phaseOptions ?? []);
        predSel.innerHTML = groups.map(g =>
            `<optgroup label="${escHtml(g.project_name)}">` +
            g.phases
                .filter(ph => ph.id !== Number(_currentPhaseId))
                .map(ph => `<option value="${ph.id}">${escHtml(ph.name)} (${escHtml(ph.team_name)})</option>`)
                .join('') +
            '</optgroup>'
        ).join('') || '<option value="">No phases available</option>';

        if (!results.length) {
            listEl.innerHTML = '<p class="text-secondary small mb-0">No dependencies defined.</p>';
            return;
        }

        listEl.innerHTML = `
            <table class="table table-sm rp-table mb-0">
                <thead>
                    <tr>
                        <th>Predecessor Phase</th>
                        <th>Project</th>
                        <th>Type</th>
                        <th class="text-end">Lag</th>
                        ${_modalIsView ? '' : '<th style="width:36px"></th>'}
                    </tr>
                </thead>
                <tbody>
                    ${results.map(d => `
                    <tr>
                        <td style="font-size:.85rem">${escHtml(d.predecessor_phase_name ?? '—')}</td>
                        <td style="font-size:.82rem;color:var(--bs-secondary-color)">${escHtml(d.predecessor_project_name ?? '—')}</td>
                        <td><span class="rp-badge rp-badge--muted" style="font-size:.72rem">${escHtml(d.dependency_type)}</span></td>
                        <td class="text-end" style="font-size:.82rem">${d.lag_sprints ?? 0}</td>
                        ${_modalIsView ? '' : `<td>
                            <div class="d-flex gap-1">
                                <button class="btn btn-ghost-icon js-edit-dep"
                                    data-dep-id="${d.id}"
                                    data-dep-type="${escHtml(d.dependency_type)}"
                                    data-lag="${d.lag_sprints ?? 0}"
                                    title="Edit">
                                    <i class="bi bi-pencil" style="font-size:.75rem"></i>
                                </button>
                                <button class="btn btn-ghost-icon btn-ghost-icon--danger js-del-dep"
                                    data-dep-id="${d.id}" title="Remove">
                                    <i class="bi bi-trash" style="font-size:.75rem"></i>
                                </button>
                            </div>
                        </td>`}
                    </tr>`).join('')}
                </tbody>
            </table>`;

        listEl.querySelectorAll('.js-del-dep').forEach(btn => {
            btn.addEventListener('click', () => deleteDependency(btn.dataset.depId));
        });
        listEl.querySelectorAll('.js-edit-dep').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('ed-dep-id').value = btn.dataset.depId;
                document.getElementById('ed-dep-type').value = btn.dataset.depType;
                document.getElementById('ed-lag').value = btn.dataset.lag;
                document.getElementById('ed-err').classList.add('d-none');
                document.getElementById('edit-dep-form').classList.remove('d-none');
                btn.closest('tr').querySelector('.js-del-dep')?.setAttribute('disabled', '');
            });
        });
    } catch {
        listEl.innerHTML = '<p class="text-danger small">Failed to load dependencies.</p>';
    }
}

async function addDependency() {
    if (!_currentPhaseId) return;
    const errEl = document.getElementById('ad-err');
    errEl.classList.add('d-none');

    const predecessorId = document.getElementById('ad-predecessor').value;
    const depType = document.getElementById('ad-type').value;
    const lag = parseInt(document.getElementById('ad-lag').value, 10) || 0;

    if (!predecessorId) {
        errEl.textContent = 'Please select a predecessor phase.';
        errEl.classList.remove('d-none');
        return;
    }

    const btn = document.getElementById('btn-confirm-add-dep');
    btn.disabled = true;
    try {
        const { method, href } = API_URLS.rp_versions.phases.dependencies.create(planPk, versionPk, _currentPhaseId);
        await apiFetch(href, { method, body: JSON.stringify({ predecessor_phase: predecessorId, dependency_type: depType, lag_sprints: lag }) });
        document.getElementById('add-dep-form').classList.add('d-none');
        loadPhaseDependenciesTab();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to add dependency.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

async function deleteDependency(depId) {
    try {
        const { method, href } = API_URLS.rp_versions.phases.dependencies.delete(planPk, versionPk, _currentPhaseId, depId);
        await apiFetch(href, { method });
        loadPhaseDependenciesTab();
    } catch (err) {
        showFlash(_extractError(err, 'Failed to remove dependency.'), 'error');
    }
}

async function updateDependency() {
    const depId = document.getElementById('ed-dep-id').value;
    const depType = document.getElementById('ed-dep-type').value;
    const lag = parseInt(document.getElementById('ed-lag').value, 10) || 0;
    const errEl = document.getElementById('ed-err');
    errEl.classList.add('d-none');

    const btn = document.getElementById('btn-confirm-edit-dep');
    btn.disabled = true;
    try {
        const { method, href } = API_URLS.rp_versions.phases.dependencies.update(planPk, versionPk, _currentPhaseId, depId);
        await apiFetch(href, { method, body: JSON.stringify({ dependency_type: depType, lag_sprints: lag }) });
        document.getElementById('edit-dep-form').classList.add('d-none');
        loadPhaseDependenciesTab();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to update dependency.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

// ─── Phase Pauses Tab ─────────────────────────────────────────────────────────

async function loadPhasePausesTab() {
    if (!_currentPhaseId) {
        document.getElementById('ph-pauses-list').innerHTML =
            '<p class="text-secondary small">Save the phase first to add pauses.</p>';
        return;
    }
    const listEl = document.getElementById('ph-pauses-list');
    listEl.innerHTML = '<p class="text-secondary small">Loading…</p>';

    try {
        const data = await apiFetch(API_URLS.rp_versions.phases.pauses.list(planPk, versionPk, _currentPhaseId).href);
        const results = Array.isArray(data) ? data : (data.results ?? []);
        document.getElementById('ph-pause-count').textContent = results.length;
        document.getElementById('ph-pauses-summary').textContent =
            `${results.length} pause${results.length !== 1 ? 's' : ''}`;

        if (!results.length) {
            listEl.innerHTML = '<p class="text-secondary small mb-0">No pauses defined.</p>';
            return;
        }

        listEl.innerHTML = `
            <table class="table table-sm rp-table mb-0">
                <thead>
                    <tr>
                        <th>Pause From</th>
                        <th>Mode</th>
                        <th>Until / Count</th>
                        <th>Resume Sprint</th>
                        <th></th>
                        ${_modalIsView ? '' : '<th style="width:36px"></th>'}
                    </tr>
                </thead>
                <tbody>
                    ${results.map(p => `
                    <tr>
                        <td style="font-size:.85rem">${escHtml(p.pause_from_name ?? '—')}</td>
                        <td style="font-size:.82rem"><span class="rp-badge rp-badge--muted">${escHtml(p.input_mode)}</span></td>
                        <td style="font-size:.82rem">${p.input_mode === 'SPRINT' ? escHtml(p.pause_until_sprint_name ?? '—') : (p.pause_sprint_count ?? '—') + ' sprints'}</td>
                        <td style="font-size:.82rem">${p.resume_sprint_name ? escHtml(p.resume_sprint_name) : '<span class="text-secondary">—</span>'}</td>
                        <td>${p.is_beyond_fy ? '<span class="rp-badge rp-badge--warning" style="font-size:.7rem">Beyond FY</span>' : ''}</td>
                        ${_modalIsView ? '' : `<td>
                            <div class="d-flex gap-1">
                                <button class="btn btn-ghost-icon js-edit-pause"
                                    data-pause-id="${p.id}"
                                    data-mode="${escHtml(p.input_mode)}"
                                    data-until="${p.pause_until_sprint ?? ''}"
                                    data-count="${p.pause_sprint_count ?? ''}"
                                    title="Edit">
                                    <i class="bi bi-pencil" style="font-size:.75rem"></i>
                                </button>
                                <button class="btn btn-ghost-icon btn-ghost-icon--danger js-del-pause"
                                    data-pause-id="${p.id}" title="Remove">
                                    <i class="bi bi-trash" style="font-size:.75rem"></i>
                                </button>
                            </div>
                        </td>`}
                    </tr>`).join('')}
                </tbody>
            </table>`;

        listEl.querySelectorAll('.js-del-pause').forEach(btn => {
            btn.addEventListener('click', () => deletePause(btn.dataset.pauseId));
        });
        listEl.querySelectorAll('.js-edit-pause').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('ep2-pause-id').value = btn.dataset.pauseId;
                document.getElementById('ep2-mode').value = btn.dataset.mode;
                const isSprint = btn.dataset.mode === 'SPRINT';
                document.getElementById('ep2-until').value = btn.dataset.until;
                document.getElementById('ep2-count').value = btn.dataset.count;
                document.getElementById('ep2-until-group').classList.toggle('d-none', !isSprint);
                document.getElementById('ep2-count-group').classList.toggle('d-none', isSprint);
                document.getElementById('ep2-err').classList.add('d-none');
                document.getElementById('edit-pause-form').classList.remove('d-none');
            });
        });
    } catch {
        listEl.innerHTML = '<p class="text-danger small">Failed to load pauses.</p>';
    }
}

async function addPause() {
    if (!_currentPhaseId) return;
    const errEl = document.getElementById('ap-err');
    errEl.classList.add('d-none');

    const fromId = document.getElementById('ap-from').value;
    const mode = document.getElementById('ap-mode').value;
    if (!fromId) {
        errEl.textContent = 'Please select a sprint to pause from.';
        errEl.classList.remove('d-none');
        return;
    }

    const payload = { pause_from: fromId, input_mode: mode };
    if (mode === 'SPRINT') {
        const untilId = document.getElementById('ap-until').value;
        if (!untilId) {
            errEl.textContent = 'Please select the pause until sprint.';
            errEl.classList.remove('d-none');
            return;
        }
        payload.pause_until_sprint = untilId;
    } else {
        const count = parseInt(document.getElementById('ap-count').value, 10);
        if (!count || count < 1) {
            errEl.textContent = 'Sprint count must be at least 1.';
            errEl.classList.remove('d-none');
            return;
        }
        payload.pause_sprint_count = count;
    }

    const btn = document.getElementById('btn-confirm-add-pause');
    btn.disabled = true;
    try {
        const { method, href } = API_URLS.rp_versions.phases.pauses.create(planPk, versionPk, _currentPhaseId);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        document.getElementById('add-pause-form').classList.add('d-none');
        loadPhasePausesTab();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to add pause.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

async function deletePause(pauseId) {
    try {
        const { method, href } = API_URLS.rp_versions.phases.pauses.delete(planPk, versionPk, _currentPhaseId, pauseId);
        await apiFetch(href, { method });
        loadPhasePausesTab();
    } catch (err) {
        showFlash(_extractError(err, 'Failed to remove pause.'), 'error');
    }
}

async function updatePause() {
    const pauseId = document.getElementById('ep2-pause-id').value;
    const mode = document.getElementById('ep2-mode').value;
    const errEl = document.getElementById('ep2-err');
    errEl.classList.add('d-none');

    const payload = { input_mode: mode };
    if (mode === 'SPRINT') {
        const untilId = document.getElementById('ep2-until').value;
        if (!untilId) {
            errEl.textContent = 'Please select the pause until sprint.';
            errEl.classList.remove('d-none');
            return;
        }
        payload.pause_until_sprint = untilId;
    } else {
        const count = parseInt(document.getElementById('ep2-count').value, 10);
        if (!count || count < 1) {
            errEl.textContent = 'Sprint count must be at least 1.';
            errEl.classList.remove('d-none');
            return;
        }
        payload.pause_sprint_count = count;
    }

    const btn = document.getElementById('btn-confirm-edit-pause');
    btn.disabled = true;
    try {
        const { method, href } = API_URLS.rp_versions.phases.pauses.update(planPk, versionPk, _currentPhaseId, pauseId);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        document.getElementById('edit-pause-form').classList.add('d-none');
        loadPhasePausesTab();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to update pause.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

// ─── Phase Event Bindings ─────────────────────────────────────────────────────

function bindPhaseEvents() {
    document.getElementById('btn-save-phase')?.addEventListener('click', savePhase);

    document.getElementById('ph-tab-segments')?.addEventListener('shown.bs.tab', loadPhaseSegmentsTab);
    document.getElementById('ph-tab-deps')?.addEventListener('shown.bs.tab', loadPhaseDependenciesTab);
    document.getElementById('ph-tab-pauses')?.addEventListener('shown.bs.tab', loadPhasePausesTab);
    document.getElementById('ph-tab-assignments')?.addEventListener('shown.bs.tab', loadPhaseAssignmentsTab);

    // Segment form
    document.getElementById('btn-preview-ramp')?.addEventListener('click', () => {
        const wrap = document.getElementById('ph-segments-chart-wrap');
        const btn = document.getElementById('btn-preview-ramp');
        if (!wrap) return;
        const isHidden = wrap.classList.contains('d-none');
        wrap.classList.toggle('d-none', !isHidden);
        if (isHidden && _segmentsChart) _segmentsChart.resize();
        if (btn) btn.innerHTML = isHidden
            ? '<i class="bi bi-eye-slash me-1"></i>Hide Chart'
            : '<i class="bi bi-graph-up me-1"></i>Preview Ramp';
    });

    document.getElementById('btn-add-segment')?.addEventListener('click', () => {
        document.getElementById('add-segment-form').classList.remove('d-none');
    });
    document.getElementById('btn-cancel-add-segment')?.addEventListener('click', () => {
        document.getElementById('add-segment-form').classList.add('d-none');
        document.getElementById('as-err').classList.add('d-none');
    });
    document.getElementById('btn-confirm-add-segment')?.addEventListener('click', addSegment);
    document.getElementById('btn-suggest-segments')?.addEventListener('click', suggestSegments);

    // Split mode hint
    document.getElementById('ph-split-mode')?.addEventListener('change', e => {
        _updateSplitModeHint(e.target.value);
    });

    // Ramp pattern change → update suggest button
    document.getElementById('ph-ramp-pattern')?.addEventListener('change', e => {
        _updateSuggestButton(e.target.value);
    });

    // Show step_count field only for STEPPED progression
    document.getElementById('as-progression')?.addEventListener('change', e => {
        document.getElementById('as-step-count-group')
            .classList.toggle('d-none', e.target.value !== 'STEPPED');
    });

    // Dependency form
    document.getElementById('btn-add-dep')?.addEventListener('click', () => {
        document.getElementById('add-dep-form').classList.remove('d-none');
    });
    document.getElementById('btn-cancel-add-dep')?.addEventListener('click', () => {
        document.getElementById('add-dep-form').classList.add('d-none');
        document.getElementById('ad-err').classList.add('d-none');
    });
    document.getElementById('btn-confirm-add-dep')?.addEventListener('click', addDependency);
    document.getElementById('btn-confirm-edit-dep')?.addEventListener('click', updateDependency);
    document.getElementById('btn-cancel-edit-dep')?.addEventListener('click', () => {
        document.getElementById('edit-dep-form').classList.add('d-none');
    });

    // Pause form
    document.getElementById('btn-add-pause')?.addEventListener('click', () => {
        document.getElementById('add-pause-form').classList.remove('d-none');
    });
    document.getElementById('btn-cancel-add-pause')?.addEventListener('click', () => {
        document.getElementById('add-pause-form').classList.add('d-none');
        document.getElementById('ap-err').classList.add('d-none');
    });
    document.getElementById('btn-confirm-add-pause')?.addEventListener('click', addPause);
    document.getElementById('btn-confirm-edit-pause')?.addEventListener('click', updatePause);
    document.getElementById('btn-cancel-edit-pause')?.addEventListener('click', () => {
        document.getElementById('edit-pause-form').classList.add('d-none');
    });

    document.getElementById('ap-mode')?.addEventListener('change', e => {
        const isSprint = e.target.value === 'SPRINT';
        document.getElementById('ap-until-group').classList.toggle('d-none', !isSprint);
        document.getElementById('ap-count-group').classList.toggle('d-none', isSprint);
    });

    document.getElementById('ep2-mode')?.addEventListener('change', e => {
        const isSprint = e.target.value === 'SPRINT';
        document.getElementById('ep2-until-group').classList.toggle('d-none', !isSprint);
        document.getElementById('ep2-count-group').classList.toggle('d-none', isSprint);
    });

    // Assignment form
    document.getElementById('btn-add-assignment')?.addEventListener('click', () => {
        _resetAddAssignForm();
        document.getElementById('add-assign-form').classList.remove('d-none');
    });
    document.getElementById('btn-cancel-add-assign')?.addEventListener('click', () => {
        document.getElementById('add-assign-form').classList.add('d-none');
        document.getElementById('aa-err').classList.add('d-none');
    });
    document.getElementById('btn-confirm-add-assign')?.addEventListener('click', addAssignment);
    document.getElementById('btn-confirm-edit-assign')?.addEventListener('click', updateAssignment);
    document.getElementById('btn-cancel-edit-assign')?.addEventListener('click', () => {
        document.getElementById('edit-assign-form').classList.add('d-none');
    });
    document.getElementById('aa-type')?.addEventListener('change', e => _onAssignTypeChange('aa', e.target.value));
    document.getElementById('ea-type')?.addEventListener('change', e => _onAssignTypeChange('ea', e.target.value));
    document.getElementById('aa-auto')?.addEventListener('change', e => {
        document.getElementById('aa-member-group').classList.toggle('d-none', e.target.checked);
    });
    document.getElementById('aa-member')?.addEventListener('change', () => {
        if (document.getElementById('aa-type')?.value === 'INTERIM') _updateReplacesOptions();
    });

    // Clean up chart on modal close; restore parent modal if it was hidden
    document.getElementById('phaseModal')?.addEventListener('hidden.bs.modal', () => {
        if (_segmentsChart) {
            _segmentsChart.destroy();
            _segmentsChart = null;
        }
        _currentPhaseId = null;
        _phaseTeamEntryId = null;
        _phaseEntryId = null;
        document.getElementById('ph-segments-chart-wrap')?.classList.add('d-none');
        document.getElementById('add-segment-form')?.classList.add('d-none');
        document.getElementById('add-dep-form')?.classList.add('d-none');
        document.getElementById('edit-dep-form')?.classList.add('d-none');
        document.getElementById('add-pause-form')?.classList.add('d-none');
        document.getElementById('edit-pause-form')?.classList.add('d-none');
        document.getElementById('add-assign-form')?.classList.add('d-none');
        document.getElementById('edit-assign-form')?.classList.add('d-none');
        _assignOptions = { available: [], all: [], split_mode: 'AUTO', allow_multiple: false };

        if (_parentModalHiddenForPhase) {
            _parentModalHiddenForPhase = false;
            const parentModalEl = document.getElementById('editProjectModal');
            if (parentModalEl) {
                bootstrap.Modal.getOrCreateInstance(parentModalEl).show();
            }
        }
    });
}

// ─── Phase Assignments Tab ────────────────────────────────────────────────────

async function loadPhaseAssignmentsTab() {
    if (!_currentPhaseId) {
        document.getElementById('ph-assign-list').innerHTML =
            '<p class="text-secondary small">Save the phase first to add assignments.</p>';
        return;
    }
    const listEl = document.getElementById('ph-assign-list');
    listEl.innerHTML = '<p class="text-secondary small">Loading…</p>';

    try {
        const [assignments, opts] = await Promise.all([
            apiFetch(API_URLS.rp_versions.phases.assignments.list(planPk, versionPk, _currentPhaseId).href),
            apiFetch(API_URLS.rp_versions.phases.assignments.options(planPk, versionPk, _currentPhaseId).href).catch(() => ({
                available: [], all: [], split_mode: 'AUTO', allow_multiple: false,
            })),
        ]);

        _assignOptions = opts;

        const results = Array.isArray(assignments) ? assignments : (assignments.results ?? []);
        document.getElementById('ph-assign-count').textContent = results.length;
        document.getElementById('ph-assign-summary').textContent =
            `${results.length} assignment${results.length !== 1 ? 's' : ''}`;

        // Populate member selects from options
        const available = opts.available ?? [];
        const all = opts.all ?? [];
        const memberOpts = available.length
            ? available.map(m => `<option value="${m.id}">${escHtml(m.name)}</option>`).join('')
            : '<option value="">No available members</option>';
        const allOpts = all.length
            ? all.map(m => `<option value="${m.id}">${escHtml(m.name)}</option>`).join('')
            : '<option value="">No members</option>';

        const memberEl = document.getElementById('aa-member');
        memberEl.innerHTML = memberOpts;
        memberEl.multiple = !!opts.allow_multiple;
        memberEl.size = opts.allow_multiple ? Math.min(available.length || 1, 5) : 1;
        document.getElementById('aa-replaces').innerHTML = allOpts;
        document.getElementById('ea-replaces').innerHTML = allOpts;

        // Update split value hint
        const splitMode = opts.split_mode ?? 'AUTO';
        const splitHint = splitMode === 'PERCENT'
            ? 'Enter % of phase time for this engineer (e.g. 50 = 50%)'
            : splitMode === 'DAYS'
            ? 'Enter days allocated to this engineer'
            : '';
        document.getElementById('aa-split-hint').textContent = splitHint;
        document.getElementById('ea-split-hint').textContent = splitHint;

        // Show/hide Add button based on allow_multiple and existing count
        const addBtn = document.getElementById('btn-add-assignment');
        if (addBtn) {
            const isFull = !opts.allow_multiple && results.length >= 1 && splitMode === 'AUTO';
            addBtn.disabled = _isReadOnly || (isFull);
        }

        if (!results.length) {
            listEl.innerHTML = '<p class="text-secondary small mb-0">No assignments yet.</p>';
            return;
        }

        const typeBadge = type => {
            const map = {
                ENGINEER: 'rp-badge--success',
                ARCHITECT: 'rp-badge--info',
                ADHOC: 'rp-badge--muted',
                INTERIM: 'rp-badge--warning',
            };
            return `<span class="rp-badge ${map[type] || 'rp-badge--muted'}" style="font-size:.7rem">${escHtml(type)}</span>`;
        };

        listEl.innerHTML = `
            <table class="table table-sm rp-table mb-0">
                <thead>
                    <tr>
                        <th>Member</th>
                        <th>Type</th>
                        <th>Split</th>
                        <th>Details</th>
                        <th>Budget</th>
                        ${_modalIsView ? '' : '<th style="width:60px"></th>'}
                    </tr>
                </thead>
                <tbody>
                    ${results.map(a => {
                        const isInterim = a.assignment_type === 'INTERIM';
                        const isSecondary = ['ARCHITECT', 'ADHOC', 'INTERIM'].includes(a.assignment_type);
                        const nameStyle = isSecondary ? 'font-style:italic;color:var(--bs-secondary-color)' : '';
                        const memberName = a.auto_assign
                            ? '<span class="text-secondary fst-italic">Auto</span>'
                            : escHtml(a.team_member_name ?? '—');
                        const splitVal = a.split_value != null ? escHtml(String(a.split_value)) : '—';
                        const details = isInterim && a.replaces_member_name
                            ? `Covers ${escHtml(a.replaces_member_name)}${a.interim_sprint_count ? ` · ${a.interim_sprint_count} spr` : ''}`
                            : (a.notes ? escHtml(a.notes) : '—');
                        return `
                    <tr>
                        <td style="font-size:.85rem;${nameStyle}">${memberName}</td>
                        <td>${typeBadge(a.assignment_type)}</td>
                        <td style="font-size:.82rem">${splitVal}</td>
                        <td style="font-size:.82rem">${details}</td>
                        <td style="font-size:.82rem">${a.includes_in_budget ? '<span class="rp-badge rp-badge--success" style="font-size:.7rem">Yes</span>' : '<span class="rp-badge rp-badge--muted" style="font-size:.7rem">No</span>'}</td>
                        ${_modalIsView ? '' : `<td>
                            <div class="d-flex gap-1">
                                <button class="btn btn-ghost-icon js-edit-assign"
                                    data-assign-id="${a.id}"
                                    data-type="${escHtml(a.assignment_type)}"
                                    data-split="${a.split_value ?? ''}"
                                    data-replaces="${a.replaces_member ?? ''}"
                                    data-interim-count="${a.interim_sprint_count ?? ''}"
                                    data-notes="${escHtml(a.notes ?? '')}"
                                    title="Edit">
                                    <i class="bi bi-pencil" style="font-size:.75rem"></i>
                                </button>
                                <button class="btn btn-ghost-icon btn-ghost-icon--danger js-del-assign"
                                    data-assign-id="${a.id}" title="Remove">
                                    <i class="bi bi-trash" style="font-size:.75rem"></i>
                                </button>
                            </div>
                        </td>`}
                    </tr>`;
                    }).join('')}
                </tbody>
            </table>`;

        listEl.querySelectorAll('.js-del-assign').forEach(btn => {
            btn.addEventListener('click', () => deleteAssignment(btn.dataset.assignId));
        });
        listEl.querySelectorAll('.js-edit-assign').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('ea-assign-id').value = btn.dataset.assignId;
                document.getElementById('ea-type').value = btn.dataset.type;
                document.getElementById('ea-split-value').value = btn.dataset.split;
                document.getElementById('ea-replaces').value = btn.dataset.replaces;
                document.getElementById('ea-interim-count').value = btn.dataset.interimCount;
                document.getElementById('ea-notes').value = btn.dataset.notes;
                _onAssignTypeChange('ea', btn.dataset.type);
                document.getElementById('ea-err').classList.add('d-none');
                document.getElementById('edit-assign-form').classList.remove('d-none');
            });
        });
    } catch {
        listEl.innerHTML = '<p class="text-danger small">Failed to load assignments.</p>';
    }
}

function _resetAddAssignForm() {
    document.getElementById('aa-type').value = 'ENGINEER';
    const memberEl = document.getElementById('aa-member');
    memberEl.selectedIndex = 0;
    memberEl.multiple = false;
    memberEl.size = 1;
    document.getElementById('aa-auto').checked = true;
    document.getElementById('aa-member-group').classList.add('d-none');
    document.getElementById('aa-split-value').value = '';
    document.getElementById('aa-replaces').selectedIndex = 0;
    document.getElementById('aa-interim-count').value = '1';
    document.getElementById('aa-notes').value = '';
    document.getElementById('aa-err').classList.add('d-none');
    _onAssignTypeChange('aa', 'ENGINEER');
}

function _onAssignTypeChange(prefix, type) {
    const splitMode = _assignOptions.split_mode ?? 'AUTO';
    const isInterim = type === 'INTERIM';
    const showSplit = splitMode !== 'AUTO';

    document.getElementById(`${prefix}-split-group`)?.classList.toggle('d-none', !showSplit);
    document.getElementById(`${prefix}-replaces-group`)?.classList.toggle('d-none', !isInterim);
    document.getElementById(`${prefix}-interim-count-group`)?.classList.toggle('d-none', !isInterim);

    if (prefix === 'aa' && isInterim) _updateReplacesOptions();
}

function _updateReplacesOptions() {
    const memberEl = document.getElementById('aa-member');
    const replacesEl = document.getElementById('aa-replaces');
    if (!memberEl || !replacesEl) return;
    const selectedIds = new Set(Array.from(memberEl.selectedOptions).map(o => o.value).filter(Boolean));
    const all = _assignOptions.all ?? [];
    replacesEl.innerHTML = all.length
        ? all.filter(m => !selectedIds.has(String(m.id)))
              .map(m => `<option value="${m.id}">${escHtml(m.name)}</option>`).join('')
        : '<option value="">No members</option>';
}

async function addAssignment() {
    if (!_currentPhaseId) return;
    const errEl = document.getElementById('aa-err');
    errEl.classList.add('d-none');

    const type = document.getElementById('aa-type').value;
    const autoAssign = document.getElementById('aa-auto').checked;
    const memberEl = document.getElementById('aa-member');
    const splitValue = document.getElementById('aa-split-value').value;
    const replacesId = document.getElementById('aa-replaces').value;
    const interimCount = document.getElementById('aa-interim-count').value;
    const notes = document.getElementById('aa-notes').value.trim();

    const selectedIds = autoAssign
        ? [null]
        : Array.from(memberEl.selectedOptions).map(o => parseInt(o.value, 10)).filter(Boolean);

    if (!autoAssign && !selectedIds.length) {
        errEl.textContent = 'Please select a team member or enable Auto-assign.';
        errEl.classList.remove('d-none');
        return;
    }

    if (type === 'INTERIM' && !autoAssign && replacesId && selectedIds.includes(parseInt(replacesId, 10))) {
        errEl.textContent = 'The assigned engineer and the replaced engineer cannot be the same person.';
        errEl.classList.remove('d-none');
        return;
    }

    const splitMode = _assignOptions.split_mode ?? 'AUTO';
    const btn = document.getElementById('btn-confirm-add-assign');
    btn.disabled = true;
    try {
        const { method, href } = API_URLS.rp_versions.phases.assignments.create(planPk, versionPk, _currentPhaseId);
        for (const memberId of selectedIds) {
            const payload = {
                phase: _currentPhaseId,
                assignment_type: type,
                auto_assign: autoAssign,
                team_member: memberId ?? null,
                notes: notes || null,
            };
            if (splitMode !== 'AUTO' && splitValue !== '') {
                payload.split_value = parseFloat(splitValue);
            }
            if (type === 'INTERIM') {
                if (replacesId) payload.replaces_member = parseInt(replacesId, 10);
                if (interimCount) payload.interim_sprint_count = parseInt(interimCount, 10);
            }
            await apiFetch(href, { method, body: JSON.stringify(payload) });
        }
        document.getElementById('add-assign-form').classList.add('d-none');
        loadPhaseAssignmentsTab();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to add assignment.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

async function updateAssignment() {
    const assignId = document.getElementById('ea-assign-id').value;
    const errEl = document.getElementById('ea-err');
    errEl.classList.add('d-none');

    const type = document.getElementById('ea-type').value;
    const splitValue = document.getElementById('ea-split-value').value;
    const replacesId = document.getElementById('ea-replaces').value;
    const interimCount = document.getElementById('ea-interim-count').value;
    const notes = document.getElementById('ea-notes').value.trim();

    const payload = {
        assignment_type: type,
        notes: notes || null,
    };

    const splitMode = _assignOptions.split_mode ?? 'AUTO';
    if (splitMode !== 'AUTO') {
        payload.split_value = splitValue !== '' ? parseFloat(splitValue) : null;
    }

    if (type === 'INTERIM') {
        payload.replaces_member = replacesId ? parseInt(replacesId, 10) : null;
        payload.interim_sprint_count = interimCount ? parseInt(interimCount, 10) : null;
    } else {
        payload.replaces_member = null;
        payload.interim_sprint_count = null;
    }

    const btn = document.getElementById('btn-confirm-edit-assign');
    btn.disabled = true;
    try {
        const { method, href } = API_URLS.rp_versions.phases.assignments.update(planPk, versionPk, _currentPhaseId, assignId);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        document.getElementById('edit-assign-form').classList.add('d-none');
        loadPhaseAssignmentsTab();
    } catch (err) {
        errEl.textContent = _extractError(err, 'Failed to update assignment.');
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

async function deleteAssignment(assignId) {
    try {
        const { method, href } = API_URLS.rp_versions.phases.assignments.delete(planPk, versionPk, _currentPhaseId, assignId);
        await apiFetch(href, { method });
        loadPhaseAssignmentsTab();
    } catch (err) {
        showFlash(_extractError(err, 'Failed to remove assignment.'), 'error');
    }
}

// ─── Jobs Tab (version-scoped) ────────────────────────────────────────────────

let _vcJobsPage = 1;

async function _vcRenderJobs(page) {
    if (page !== undefined) _vcJobsPage = page;
    const listEl = document.getElementById('vc-jobs-list');
    if (!listEl) return;
    listEl.innerHTML = '<p class="text-secondary small">Loading…</p>';
    try {
        let url = API_URLS.resource_plans.engine.jobs(planPk).href
            + `?page=${_vcJobsPage}&page_size=20&version_id=${versionPk}`;
        const data = await apiFetch(url);
        const results = Array.isArray(data) ? data : (data.results ?? []);
        const count = data.count ?? results.length;
        const numPages = data.num_pages ?? 1;

        let html = `<span class="text-secondary small d-block mb-2">${count} job${count !== 1 ? 's' : ''} for this version</span>`;

        if (!results.length) {
            html += '<p class="text-secondary small mb-0">No engine jobs found for this version.</p>';
            listEl.innerHTML = html;
            return;
        }

        const statusBadge = (s) => {
            const map = { PENDING: 'secondary', RUNNING: 'primary', COMPLETE: 'success', FAILED: 'danger' };
            return `<span class="badge bg-${map[s] ?? 'secondary'}">${s}</span>`;
        };
        const fmtMs = (ms) => {
            if (ms == null) return '—';
            if (ms < 1000) return `${ms}ms`;
            return `${(ms / 1000).toFixed(1)}s`;
        };

        html += `
        <div class="rp-table-wrap" style="overflow-x:auto">
        <table class="table table-sm rp-table mb-0">
            <thead>
                <tr>
                    <th style="width:28px"></th>
                    <th>Mode</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th class="text-end">Duration</th>
                    <th>Result</th>
                </tr>
            </thead>
            <tbody>
                ${results.map(j => {
                    const hasSteps = (j.steps_log?.length ?? 0) > 0;
                    const dur = j.duration_seconds != null ? `${j.duration_seconds}s` : '—';
                    const errCount = j.validation_result?.error_count ?? 0;
                    const warnCount = j.validation_result?.warning_count ?? 0;
                    const result = j.status === 'COMPLETE'
                        ? `<span class="${errCount ? 'text-danger' : 'text-success'}">${errCount}E / ${warnCount}W</span>`
                        : (j.status === 'FAILED' ? '<span class="text-danger">Failed</span>' : '—');
                    const stepsHtml = hasSteps ? j.steps_log.map(s => `
                        <div class="d-flex align-items-center gap-3 py-1 border-bottom" style="font-size:.78rem">
                            <span class="flex-grow-1 text-secondary ps-2">
                                <i class="bi bi-check2-circle text-success me-1"></i>${escHtml(s.step ?? s.name ?? '')}
                            </span>
                            <span class="text-secondary text-nowrap" style="min-width:50px;text-align:right">${fmtMs(s.duration_ms)}</span>
                        </div>`).join('') : '';
                    return `
                    <tr class="js-vc-job-row" data-job-id="${j.id}" data-has-steps="${hasSteps ? 1 : 0}"
                        style="cursor:${hasSteps ? 'pointer' : 'default'}">
                        <td class="text-center">
                            ${hasSteps ? `<i class="bi bi-chevron-right js-vc-job-toggle-icon" style="font-size:.7rem"></i>` : ''}
                        </td>
                        <td><span class="badge bg-secondary">${j.mode}</span></td>
                        <td>${statusBadge(j.status)}</td>
                        <td class="text-secondary" style="font-size:.78rem">${j.started_at ? j.started_at.slice(0, 16).replace('T', ' ') : '—'}</td>
                        <td class="text-end text-secondary" style="font-size:.78rem">${dur}</td>
                        <td>${result}</td>
                    </tr>
                    ${hasSteps ? `<tr id="vc-job-steps-${j.id}" class="d-none">
                        <td colspan="6" class="p-0" style="background:var(--bs-tertiary-bg,#f8f9fa)">
                            <div class="px-4 py-2">
                                <div class="text-secondary fw-semibold mb-1" style="font-size:.74rem">
                                    <i class="bi bi-list-check me-1"></i>Steps
                                </div>
                                ${stepsHtml}
                            </div>
                        </td>
                    </tr>` : ''}`;
                }).join('')}
            </tbody>
        </table>
        </div>`;

        if (numPages > 1) {
            html += '<nav class="mt-2"><ul class="pagination pagination-sm mb-0">';
            for (let p = 1; p <= numPages; p++) {
                html += `<li class="page-item ${p === _vcJobsPage ? 'active' : ''}">
                    <button class="page-link js-vc-jobs-page" data-page="${p}">${p}</button></li>`;
            }
            html += '</ul></nav>';
        }

        listEl.innerHTML = html;

        listEl.querySelectorAll('.js-vc-job-row').forEach(tr => {
            tr.addEventListener('click', () => {
                if (tr.dataset.hasSteps !== '1') return;
                const jobId = tr.dataset.jobId;
                listEl.querySelector(`#vc-job-steps-${jobId}`)?.classList.toggle('d-none');
                const icon = tr.querySelector('.js-vc-job-toggle-icon');
                if (icon) {
                    icon.classList.toggle('bi-chevron-right');
                    icon.classList.toggle('bi-chevron-down');
                }
            });
        });

        listEl.querySelectorAll('.js-vc-jobs-page').forEach(btn => {
            btn.addEventListener('click', () => _vcRenderJobs(parseInt(btn.dataset.page, 10)));
        });
    } catch {
        listEl.innerHTML = '<p class="text-danger small">Failed to load jobs.</p>';
    }
}

// ─── Engine Modal (version configure) ────────────────────────────────────────

let _vcEngineJobId = null;
let _vcEnginePoller = null;

function _vcStopEnginePoller() {
    if (_vcEnginePoller) { clearInterval(_vcEnginePoller); _vcEnginePoller = null; }
}

async function _vcResetEngineModal() {
    _vcStopEnginePoller();
    _vcEngineJobId = null;
    document.getElementById('vc-engine-run-form').classList.remove('d-none');
    document.getElementById('vc-engine-progress-section').classList.add('d-none');
    document.getElementById('vc-engine-result-section').classList.add('d-none');
    document.getElementById('vc-engine-error-log-section').classList.add('d-none');
    document.getElementById('vc-engine-run-err').classList.add('d-none');
    document.getElementById('vc-btn-engine-submit').classList.remove('d-none');
    document.getElementById('vc-btn-engine-submit').disabled = false;
    document.getElementById('vc-engine-submit-spinner').classList.add('d-none');
    document.getElementById('vc-mode-validate').checked = true;
    document.getElementById('vc-engine-include-current').checked = false;
    const overridesEl = document.getElementById('vc-engine-remove-overrides');
    if (overridesEl) overridesEl.checked = false;
    // Show override warning if version has overrides
    const hasOverrides = _versionData?.has_pl_overrides ?? false;
    document.getElementById('vc-engine-overrides-section')?.classList.toggle('d-none', !hasOverrides);
}

async function _vcSubmitEngineRun() {
    const mode = document.querySelector('input[name="vc-engine-mode"]:checked')?.value ?? 'VALIDATE';
    const includeCurrent = document.getElementById('vc-engine-include-current').checked;
    const removeOverrides = document.getElementById('vc-engine-remove-overrides')?.checked ?? false;
    const errEl = document.getElementById('vc-engine-run-err');
    errEl.classList.add('d-none');

    const submitBtn = document.getElementById('vc-btn-engine-submit');
    const spinner = document.getElementById('vc-engine-submit-spinner');
    submitBtn.disabled = true;
    spinner.classList.remove('d-none');

    try {
        const { method, href } = API_URLS.resource_plans.engine.run(planPk);
        const result = await apiFetch(href, {
            method,
            body: JSON.stringify({
                mode,
                include_current_sprint: includeCurrent,
                version_id: versionPk,
                remove_overrides: removeOverrides,
            }),
        });

        _vcEngineJobId = result.job_id;
        document.getElementById('vc-engine-run-form').classList.add('d-none');
        document.getElementById('vc-engine-progress-section').classList.remove('d-none');
        document.getElementById('vc-btn-engine-submit').classList.add('d-none');
        _vcStartEnginePoller();
    } catch (err) {
        if (err?.status === 409 || err?.data?.running_job_id) {
            const runningId = err?.data?.running_job_id;
            errEl.textContent = `A job is already running${runningId ? ` (#${runningId})` : ''}.`;
        } else {
            errEl.textContent = _extractError(err, 'Failed to start engine run.');
        }
        errEl.classList.remove('d-none');
        submitBtn.disabled = false;
        spinner.classList.add('d-none');
    }
}

function _vcStartEnginePoller() {
    _vcEnginePoller = setInterval(async () => {
        if (!_vcEngineJobId) { _vcStopEnginePoller(); return; }
        try {
            const { href } = API_URLS.resource_plans.engine.job_status(planPk, _vcEngineJobId);
            const job = await apiFetch(href);
            const stepEl = document.getElementById('vc-engine-current-step');
            const bar = document.getElementById('vc-engine-progress-bar');
            const badge = document.getElementById('vc-engine-status-badge');
            if (stepEl) stepEl.textContent = job.current_step ?? '…';
            if (bar) { bar.style.width = `${job.progress_pct ?? 0}%`; bar.setAttribute('aria-valuenow', job.progress_pct ?? 0); }
            if (badge) badge.innerHTML = `<span class="badge bg-${job.status === 'COMPLETE' ? 'success' : job.status === 'FAILED' ? 'danger' : 'primary'}">${job.status}</span>`;
            if (job.status === 'COMPLETE' || job.status === 'FAILED') {
                _vcStopEnginePoller();
                if (job.status === 'COMPLETE') {
                    // Refresh version data to get updated has_pl_overrides
                    const ver = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href).catch(() => null);
                    if (ver) _versionData = ver;
                }
            }
        } catch { _vcStopEnginePoller(); }
    }, 2000);
}
