import { API_URLS, URLS } from './../urls.js';
import { apiFetch, escAttr, escHtml, setPageTitle, showFlash, hasPerm } from './../main.js';
import { initRenderer } from '../list/render.js';
import { initFetch } from '../list/fetch.js';
import { initSorting } from '../list/sort.js';

document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('plan-tbody')) return;
    initListView();
});

async function initListView() {
    setPageTitle('Resource Plans');
    // await loadStats();
    await populateFilterOptions();
    renderPlans();
    bindButtonActions();
    bindModalDropdowns();
}

function bindButtonActions() {
    document.getElementById('add-plan-btn')?.addEventListener('click', openAddModal);
    document.getElementById('modal-plan-type')?.addEventListener('change', showAddModalDropdowns);
    document.getElementById('modal-save-btn')?.addEventListener('click', savePlan);
    document.getElementById('modal-clone-btn')?.addEventListener('click', clonePlan);
    document.getElementById('confirm-active-btn')?.addEventListener('click', handleConfirmActive);
    document.getElementById('confirm-delete-btn')?.addEventListener('click', handleDelete);
}

async function bindModalDropdowns() {
    try {
        const { method, href } = API_URLS.resource_plans.options;
        const opts = await apiFetch(href, { method });

        // Add Modal dropdowns
        _populateSelect('modal-plan-type', opts.plan_type_choices ?? [], '', 'Select type...');
        _populateSelect('modal-fy', opts.financial_years ?? [], '', 'Select FY...', {
            labelKey: 'short_fy',
        });
        _populateSelect('modal-project', opts.projects ?? [], '', 'Select project...');
        _populateSelect('modal-programme', opts.programmes ?? [], '', 'Select programme...');
        _populateSelect('modal-team', opts.teams ?? [], '', 'Select team...');
    } catch (err) {
        showFlash(err);
    }
}

function showAddModalDropdowns() {
    const typeVal = document.getElementById('modal-plan-type').value;
    const projEl = document.getElementById('scope-project');
    const progEl = document.getElementById('scope-programme');
    const teamEl = document.getElementById('scope-team');
    const hintEl = document.getElementById('scope-fy-hint');

    if (!typeVal) {
        hintEl.classList.add('d-none');
        projEl.classList.add('d-none');
        progEl.classList.add('d-none');
        teamEl.classList.add('d-none');
    } else if (typeVal === 'FY') {
        hintEl.classList.remove('d-none');
        projEl.classList.add('d-none');
        progEl.classList.add('d-none');
        teamEl.classList.add('d-none');
    } else if (typeVal === 'PROJECT') {
        hintEl.classList.add('d-none');
        projEl.classList.remove('d-none');
        progEl.classList.add('d-none');
        teamEl.classList.add('d-none');
    } else if (typeVal === 'PROGRAMME') {
        hintEl.classList.add('d-none');
        projEl.classList.add('d-none');
        progEl.classList.remove('d-none');
        teamEl.classList.add('d-none');
    } else if (typeVal === 'TEAM') {
        hintEl.classList.add('d-none');
        projEl.classList.add('d-none');
        progEl.classList.add('d-none');
        teamEl.classList.remove('d-none');
    }
}

async function populateFilterOptions() {
    try {
        const { method, href } = API_URLS.resource_plans.options;
        const opts = await apiFetch(href, { method });

        _populateSelect('type-filter', opts.plan_type_choices ?? [], '', 'All types', {
            useIdAsValue: true,
        });
        _populateSelect('status-filter', opts.status_choices ?? [], '', 'All statuses', {
            useIdAsValue: true,
        });
        _populateSelect('fy-filter', opts.financial_years ?? [], '', 'All FYs', {
            useIdAsValue: true,
            labelKey: 'short_fy',
        });
    } catch (err) {
        showFlash(err);
    }
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
        const labelKey = opts.labelKey || 'label';
        opt.textContent = item[labelKey] ?? item.name;
        if (String(opt.value) === String(defaultValue)) opt.selected = true;
        el.appendChild(opt);
    });
}

async function loadStats() {
    try {
        const { method, href } = API_URLS.resource_plans.stats;
        const stats = await apiFetch(href, { method });
        document.getElementById('stat-total').textContent = stats.total_plans;
        document.getElementById('stat-active').textContent = stats.active_plans;
        document.getElementById('stat-draft').textContent = stats.draft_plans;
        document.getElementById('stat-locked').textContent = stats.locked_plans;
    } catch (err) {
        console.error(err);
    }
}

function renderPlans() {
    const { method, href } = API_URLS.resource_plans.list;

    const renderer = initRenderer({
        tbodyId: 'plan-tbody',
        colspan: 9,
        itemLabel: 'plans',
        rowTemplate: renderPlanRow,
        emptyState: {
            message: 'No plans yet.',
            link: { href: '#', label: 'Create the first one.', onClick: 'openAddModal()' },
        },
        filterEmptyState: {
            message: 'No plans match your filters.',
            link: { href: '#', label: 'Create a new one.', onClick: 'openAddModal()' },
        },
        paginationBarId: 'plan-pagination-bar',
        paginationInfoId: 'plan-pagination-info',
        paginationControlsId: 'plan-pagination-controls',
        onPageChange: (page) => fetcher.goToPage(page),
    });

    const fetcher = initFetch({
        apiUrl: href,
        pageSize: 20,
        searchInputId: 'plan-search',
        filters: [
            { id: 'type-filter', param: 'plan_type' },
            { id: 'status-filter', param: 'status' },
            { id: 'fy-filter', param: 'financial_year' },
            { id: 'active-filter', param: 'is_active' },
        ],
        onLoadStart: () => renderer.renderLoading('Loading plans...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load plans. Please refresh the page.'),
    });

    initSorting({
        tableId: 'plan-table',
        fetcher,
    });
    fetcher.refresh();

    window._planFetcher = fetcher;

    loadStats();
}

function getPlanTypeBadge(type) {
    if (!type) return `<span class="rp-badge rp-badge--muted">-</span>`;

    if (type === 'FY')
        return `<span class="rp-badge rp-badge-plan-type--fy">${escHtml(type)}</span>`;
    if (type === 'PROJECT')
        return `<span class="rp-badge rp-badge-plan-type--project">${escHtml(type)}</span>`;
    if (type === 'PROGRAMME')
        return `<span class="rp-badge rp-badge-plan-type--programme">${escHtml(type)}</span>`;
    if (type === 'TEAM')
        return `<span class="rp-badge rp-badge-plan-type--team">${escHtml(type)}</span>`;
}

function getPlanStatusBadge(status) {
    if (!status) return `<span class="rp-badge rp-badge--muted">-</span>`;

    if (status === 'ACTIVE')
        return `<span class="rp-badge rp-badge--success">${escHtml(status)}</span>`;
    if (status === 'DRAFT')
        return `<span class="rp-badge rp-badge--muted">${escHtml(status)}</span>`;
    if (status === 'LOCKED')
        return `<span class="rp-badge rp-badge--warning">${escHtml(status)}</span>`;
    if (status === 'SUPERSEDED')
        return `<span class="rp-badge rp-badge--muted">${escHtml(status)}</span>`;
    if (status === 'EXPIRED')
        return `<span class="rp-badge rp-badge--danger">${escHtml(status)}</span>`;
}

function getPlanActiveBadge(status) {
    return status
        ? '<span class="rp-badge rp-badge--success">Active</span>'
        : '<span class="rp-badge rp-badge--muted">Inactive</span>';
}

function renderPlanRow(plan) {
    const detailUrl = URLS.resource_plans.detail(plan.id);

    return `
        <tr data-plan-id="${plan.id}">
            <td>
                <a href="${detailUrl}" class="rp-link fw-500">${escHtml(plan.name)}</a>
            </td>
            <td>
                <span class="rp-truncate">${escHtml(plan.description ?? '')}</span>
            </td>
            <td class="text-center">${getPlanTypeBadge(plan.plan_type)}</td>
            <td class="text-center">${plan.scope.financial_year_short}</td>
            <td class="text-center"><span class="rp-badge rp-badge--muted">v${plan.version_number}</span></td>
            <td class="text-center"><span class="rp-code" style="font-size: 0.75rem;">${escHtml(plan.threshold_pct)} %</span></td>
            <td class="text-center">${getPlanStatusBadge(plan.status)}</td>
            <td class="text-center">${getPlanActiveBadge(plan.is_active)}</td>
            <td class="text-center">
                <a href="${detailUrl}" class="btn btn-ghost-icon" title="View plan">
                    <i class="bi bi-eye"></i>
                </a>
                ${hasPerm('resource_plans.add_resourceplan') ? `
                <button class="btn btn-ghost-icon"
                        title="Clone plan"
                        onclick="openCloneModal(${plan.id})">
                    <i class="bi bi-files"></i>
                </button>` : ''}
                ${hasPerm('resource_plans.change_resourceplan') ? `
                <button class="btn btn-ghost-icon ${plan.is_active ? 'btn-ghost-icon--danger' : 'btn-ghost-icon--success'}"
                        title="${plan.is_active ? 'Deactivate' : 'Activate'} plan"
                        onclick="openActiveModal(${plan.id}, '${escAttr(plan.name)}', ${plan.is_active})">
                    <i class="bi bi-check-circle"></i>
                </button>` : ''}
                ${hasPerm('resource_plans.delete_resourceplan') ? `
                <button class="btn btn-ghost-icon btn-ghost-icon--danger" title="Delete plan"
                        onclick="openDeleteModal(${plan.id}, '${escAttr(plan.name)}')">
                    <i class="bi bi-trash"></i>
                </button>` : ''}
            </td>
        </tr>
    `;
}

function _showModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id), { focus: false }).show();
}

function _hideModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).hide();
}

function openAddModal() {
    clearAddModalErrors();
    resetAddModal();
    _showModal('planAddModal');
}

function resetAddModal() {
    document.getElementById('modal-name').value = '';
    document.getElementById('modal-description').value = '';
    document.getElementById('modal-plan-type').value = '';
    document.getElementById('modal-fy').value = '';
    document.getElementById('modal-threshold').value = 10;
    document.getElementById('modal-project').value = '';
    document.getElementById('modal-programme').value = '';
    document.getElementById('modal-team').value = '';
}

function clearAddModalErrors() {
    document.getElementById('modal-form-errors').classList.add('d-none');
    [
        'modal-name',
        'modal-fy',
        'modal-plan-type',
        'modal-project',
        'modal-programme',
        'modal-team',
        'modal-threshold',
    ].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('is-invalid');
    });
}

function openCloneModal(id) {
    document.getElementById('clone-source-pk').value = id;
    document.getElementById('clone-name-input').value = '';
    document.getElementById('clone-errors').classList.add('d-none');
    const cfgCheck = document.getElementById('clone-include-config');
    if (cfgCheck) cfgCheck.checked = false;
    _showModal('cloneModal');
}

async function clonePlan() {
    const id = document.getElementById('clone-source-pk').value;
    const nameEl = document.getElementById('clone-name-input');
    const name = nameEl.value.trim();
    const includeConfig = document.getElementById('clone-include-config')?.checked ?? false;

    if (!name) {
        document.getElementById('clone-errors').textContent = 'Name is required.';
        document.getElementById('clone-errors').classList.remove('d-none');
        return;
    }

    try {
        const { method, href } = API_URLS.resource_plans.clone(id);
        const body = { name, include_config: includeConfig };
        await apiFetch(href, { method, body: JSON.stringify(body) });
        _hideModal('cloneModal');
        showFlash(`Cloned to ${name}.`, 'success');
        window._planFetcher?.refresh();
        loadStats();
    } catch (err) {
        console.error(err);
        showFlash(err, 'error');
    }
}

function openActiveModal(id, name, isActive) {
    const titleEl = document.getElementById('active-modal-title');
    const messageEl = document.getElementById('active-message');
    const confirmBtn = document.getElementById('confirm-active-btn');

    const action = isActive ? 'deactivated' : 'activated';
    titleEl.textContent = isActive ? 'Deactivate plan' : 'Activate plan';
    confirmBtn.textContent = isActive ? 'Deactivate' : 'Activate';
    confirmBtn.className = `btn btn-sm ${isActive ? 'btn-danger' : 'btn-success'}`;
    confirmBtn.dataset.id = id;
    confirmBtn.dataset.isActive = isActive;

    messageEl.innerHTML = `<strong>${escHtml(name)}</strong> will be ${action}. Do you want to proceed?`;
    document.getElementById('active-modal-banner').classList.add('d-none');
    _showModal('activeModal');
}

async function handleConfirmActive() {
    const btn = document.getElementById('confirm-active-btn');
    const id = btn.dataset.id;
    const isActive = btn.dataset.isActive;

    try {
        const { method, href } =
            isActive === 'true'
                ? API_URLS.resource_plans.archive(id)
                : API_URLS.resource_plans.unarchive(id);
        await apiFetch(href, { method });
        _hideModal('activeModal');
        const message = isActive === 'true' ? 'Plan deactivated.' : 'Plan activated.';
        showFlash(message, 'success');
        window._planFetcher?.refresh();
        loadStats();
    } catch (err) {
        console.error(err);
        showFlash(err, 'error');
    }
}

function openDeleteModal(id, name) {
    document.getElementById('delete-name').textContent = name;
    document.getElementById('confirm-delete-btn').dataset.id = id;
    document.getElementById('confirm-delete-btn').dataset.name = name;
    document.getElementById('delete-modal-banner').classList.add('d-none');
    _showModal('deleteModal');
}

async function handleDelete() {
    const btn = document.getElementById('confirm-delete-btn');
    const id = btn.dataset.id;
    const name = btn.dataset.name;

    try {
        const { method, href } = API_URLS.resource_plans.delete(id);
        await apiFetch(href, { method });
        showFlash(`${name} deleted.`, 'success');
        _hideModal('deleteModal');
        window._planFetcher?.refresh();
        loadStats();
    } catch (err) {
        console.error(err);
        showFlash(err, 'error');
    }
}

function _setFieldError(inputId, errId, message) {
    document.getElementById(inputId)?.classList.add('is-invalid');
    const errEl = document.getElementById(errId);
    if (errEl) errEl.textContent = message;
}

async function savePlan() {
    clearAddModalErrors();
    const nameEl = document.getElementById('modal-name');
    const name = nameEl.value.trim();
    const description = document.getElementById('modal-description').value.trim();
    const planTypeEl = document.getElementById('modal-plan-type');
    const plan_type = planTypeEl.value;
    const financialYearEl = document.getElementById('modal-fy');
    const financial_year = financialYearEl.value;
    const thresholdEl = document.getElementById('modal-threshold');
    const threshold_pct = thresholdEl.value;
    const projectEl = document.getElementById('modal-project');
    const project = projectEl.value || null;
    const programmeEl = document.getElementById('modal-programme');
    const programme = programmeEl.value || null;
    const teamEl = document.getElementById('modal-team');
    const team = teamEl.value || null;

    setModalSubmitting(true);

    let hasErrors = false;
    if (!name) {
        _setFieldError(nameEl.id, `${nameEl.id}-error`, 'Name is required.');
        hasErrors = true;
    }
    if (!plan_type) {
        _setFieldError(planTypeEl.id, `${planTypeEl.id}-error`, 'Plan type is required.');
        hasErrors = true;
    }
    if (!financial_year) {
        _setFieldError(
            financialYearEl.id,
            `${financialYearEl.id}-error`,
            'Financial year is required.',
        );
        hasErrors = true;
    }

    if (plan_type === 'PROJECT') {
        if (!project) {
            _setFieldError(projectEl.id, `${projectEl.id}-error`, 'Project is required.');
            hasErrors = true;
        }
    } else if (plan_type === 'PROGRAMME') {
        if (!programme) {
            _setFieldError(programmeEl.id, `${programmeEl.id}-error`, 'Programme is required.');
            hasErrors = true;
        }
    } else if (plan_type === 'TEAM') {
        if (!team) {
            _setFieldError(teamEl.id, `${teamEl.id}-error`, 'Team is required.');
            hasErrors = true;
        }
    }

    if (hasErrors) {
        setModalSubmitting(false);
        return;
    }

    try {
        const body = { name, description, plan_type, threshold_pct };
        if (financial_year) body.financial_year = parseInt(financial_year);
        if (project) body.project = parseInt(project);
        if (programme) body.programme = parseInt(programme);
        if (team) body.team = parseInt(team);

        const { method, href } = API_URLS.resource_plans.create;
        const result = await apiFetch(href, { method, body: JSON.stringify(body) });
        _hideModal('planAddModal');
        showFlash(`Plan ${result.name} created.`, 'success');
        window._planFetcher?.refresh();
        loadStats();
    } catch (err) {
        console.error(err);
        showFlash(err, 'danger');
    } finally {
        setModalSubmitting(false);
    }
}

function setModalSubmitting(on) {
    document.getElementById('modal-save-spinner').classList.toggle('d-none', !on);
    document.getElementById('modal-save-btn').disabled = on;
}

window.openAddModal = openAddModal;
window.openCloneModal = openCloneModal;
window.openActiveModal = openActiveModal;
window.openDeleteModal = openDeleteModal;
