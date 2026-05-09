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

// Versions tab state
let _versionsFetcher = null;
let _planIsActive = true;
const _versionDataCache = new Map(); // versionId (string) → version object

// Comments state
let _commentsPage = 1;
let _commentsInitialized = false;

// Engine state
let _enginePollTimer = null;
let _engineJobId = null;

// Jobs tab state
let _jobsPage = 1;
let _jobsModeFilter = '';
let _jobsVersionFilter = '';

document.addEventListener('DOMContentLoaded', () => {
    if (!planPk) return;
    initDetailView();
});

async function initDetailView() {
    try {
        const plan = await fetchPlan();
        _planIsActive = plan.is_active;
        setPageTitle(plan.name);
        bindTabEvents();
        renderHeader(plan);
        renderGeneral();
        bindEditButtons();
        _bindEngineEvents();
    } catch (err) {
        console.error('[initDetailView] Failed to load plan.', err);
        _showBanner('Failed to load plan data. Please refresh the page.', 'danger');
    }
}

function bindTabEvents() {
    document.getElementById('tab-general').addEventListener('shown.bs.tab', function () {
        renderGeneral();
    });
    document.getElementById('tab-versions').addEventListener('shown.bs.tab', function () {
        renderVersions();
    });
    document.getElementById('tab-jobs').addEventListener('shown.bs.tab', function () {
        renderJobs();
    });
}

function bindEditButtons() {
    // General tab
    document
        .getElementById('btn-edit-general')
        ?.addEventListener('click', () => enterEditMode('general'));
    document
        .getElementById('btn-cancel-general')
        ?.addEventListener('click', () => exitEditMode('general'));
    document.getElementById('btn-save-general')?.addEventListener('click', saveGeneral);

    // Versions tab
    document.getElementById('btn-new-version')?.addEventListener('click', openNewVersionModal);
    document.getElementById('btn-save-version-edit')?.addEventListener('click', saveVersionEdit);
    document
        .getElementById('btn-confirm-version-action')
        ?.addEventListener('click', executeVersionConfirm);
}

async function fetchPlan() {
    const { method, href } = API_URLS.resource_plans.detail(planPk);
    return apiFetch(href, { method });
}

function _showBanner(message, type = 'danger', bannerId = 'plan-detail-banner') {
    const banner = document.getElementById(bannerId);
    if (!banner) return;
    banner.textContent = message;
    banner.className = `alert alert-${type} mb-3`;
}

async function enterEditMode(tab) {
    document.getElementById(`${tab}-view-mode`).classList.add('d-none');
    document.getElementById(`${tab}-edit-mode`).classList.remove('d-none');
    document.getElementById('plan-detail-banner').classList.add('d-none');

    if (tab === 'general') {
        const plan = await fetchPlan();
        document.getElementById('edit-name').value = plan.name;
        document.getElementById('edit-description').value = plan.description ?? '';
        document.getElementById('edit-is-active').checked = plan.is_active;
    }
}

function exitEditMode(tab) {
    document.getElementById(`${tab}-edit-mode`).classList.add('d-none');
    document.getElementById(`${tab}-view-mode`).classList.remove('d-none');
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

function renderHeader(plan) {
    document.getElementById('plan-detail-name').textContent = plan.name;
    document.getElementById('plan-active-badge').innerHTML = plan.is_active
        ? '<span class="rp-badge rp-badge--success">Active</span>'
        : '<span class="rp-badge rp-badge--muted">Inactive</span>';
}

async function renderGeneral() {
    try {
        exitEditMode('general');
        const plan = await fetchPlan();
        _planIsActive = plan.is_active;

        document.getElementById('view-name').textContent = plan.name;
        document.getElementById('view-description').textContent = plan.description ?? '-';
        document.getElementById('view-plan-type').innerHTML = getPlanTypeBadge(plan.plan_type);
        document.getElementById('view-plan-status').innerHTML = getPlanStatusBadge(plan.status);
        document.getElementById('view-plan-latest-version').innerHTML = `
            <span class="rp-badge rp-badge--muted">v${plan.version_info.version}</span>
        `;
        document.getElementById('view-plan-threshold-pct').innerHTML = `
            <span class="rp-code" style="font-size: 0.75rem;">${escHtml(plan.version_info.threshold_pct)} %</span>
        `;
        initComments();

        document.getElementById('view-plan-fy-id').textContent = plan.scope.financial_year;
        document.getElementById('view-plan-fy').textContent = plan.scope.financial_year_long;
        document.getElementById('view-plan-scope').innerHTML = 'FY';
        document.getElementById('view-plan-scope-type').textContent = 'FY';
        document.getElementById('view-plan-scope-id').textContent = plan.scope.financial_year;
        if (plan.scope.programme) {
            document.getElementById('view-plan-scope-type').textContent = 'PROGRAMME';
            document.getElementById('view-plan-scope-id').textContent = plan.scope.programme;
            document.getElementById('view-plan-scope').innerHTML = `
                <span class="me-2">PROGRAMME</span>
                <a href="/programmes/${plan.scope.programme}/" target="_blank" rel="noopener noreferrer" class="rp-link">
                    (<i class="bi bi-arrow-up-right"></i> ${plan.scope.programme_name})
                </a>
            `;
        }
        if (plan.scope.project) {
            document.getElementById('view-plan-scope-type').textContent = 'PROJECT';
            document.getElementById('view-plan-scope-id').textContent = plan.scope.project;
            document.getElementById('view-plan-scope').innerHTML = `
                <a href="/projects/${plan.scope.project}/" target="_blank" rel="noopener noreferrer" class="rp-link">
                    <span class="me-2">PROJECT</span>
                    (<i class="bi bi-arrow-up-right"></i> ${plan.scope.project_name})
                </a>
            `;
        }
        if (plan.scope.team) {
            document.getElementById('view-plan-scope-type').textContent = 'TEAM';
            document.getElementById('view-plan-scope-id').textContent = plan.scope.team;
            document.getElementById('view-plan-scope').innerHTML = `
                <a href="/delivery-teams/${plan.scope.team}/" target="_blank" rel="noopener noreferrer" class="rp-link">
                    <span class="me-2">TEAM</span>
                    (<i class="bi bi-arrow-up-right"></i> ${plan.scope.team_name})
                </a>
            `;
        }

        if (plan.cloned_from) {
            document.getElementById('view-clone-block').classList.remove('d-none');
            document.getElementById('view-clone-from').innerHTML = `
                <a href="/resource-plans/${plan.cloned_from}/" target="_blank" rel="noopener noreferrer" class="rp-link">
                    <i class="bi bi-arrow-up-right me-2"></i> ${plan.cloned_from_name}
                </a>
            `;
        } else {
            document.getElementById('view-clone-block').classList.add('d-none');
            document.getElementById('view-clone-from').innerHTML = '';
        }

        document.getElementById('meta-created').textContent =
            formatDateTime(plan.created_at) ?? '-';
        document.getElementById('meta-updated').textContent =
            formatDateTime(plan.updated_at) ?? '-';
    } catch (err) {
        _showBanner('Failed to load plan information. Please refresh the page.', 'danger');
        console.error('[renderGeneral] Failed to load plan general information.', err);
    }
}

async function saveGeneral() {
    const nameEl = document.getElementById('edit-name');
    const name = nameEl.value.trim();

    if (!name) {
        nameEl.classList.add('is-invalid');
        document.getElementById('edit-name-err').textContent = 'Name is required.';
        return;
    }
    nameEl.classList.remove('is-invalid');
    document.getElementById('edit-name-err').textContent = '';

    const payload = {
        name,
        description: document.getElementById('edit-description').value.trim(),
        is_active: document.getElementById('edit-is-active').checked,
    };

    try {
        const { method, href } = API_URLS.resource_plans.partial_edit(planPk);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        showFlash('Plan details updated successfully.', 'success');
        const plan = await fetchPlan();
        _planIsActive = plan.is_active;
        renderHeader(plan);
        renderGeneral();
        exitEditMode('general');
    } catch (err) {
        const msg = _extractError(err, 'Failed to save changes. Please try again.');
        _showBanner(msg, 'danger');
    }
}

// ─── Comments ────────────────────────────────────────────────────────────────

function initComments() {
    if (!_commentsInitialized) {
        document.getElementById('btn-post-comment')?.addEventListener('click', postComment);
        document.getElementById('new-comment-input')?.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') postComment();
        });
        _commentsInitialized = true;
    }
    loadComments(1);
}

async function loadComments(page = 1) {
    _commentsPage = page;
    const container = document.getElementById('comments-container');
    if (!container) return;
    container.innerHTML = '<p class="text-secondary small">Loading comments...</p>';

    try {
        const { method, href } = API_URLS.resource_plans.comments.list(planPk);
        const data = await apiFetch(`${href}?page=${page}&page_size=20`, { method });
        renderCommentList(data.results, data.pagination);
    } catch {
        container.innerHTML = '<p class="text-danger small">Failed to load comments.</p>';
    }
}

function renderCommentList(results, pagination) {
    const container = document.getElementById('comments-container');
    if (!results.length) {
        container.innerHTML = '<p class="text-secondary small mb-0">No comments yet.</p>';
        document.getElementById('comments-pagination').innerHTML = '';
        return;
    }
    container.innerHTML = results.map(_commentCardHtml).join('');
    renderCommentsPagination(pagination);
}

function _commentCardHtml(c) {
    return `
    <div class="rp-comment-card" data-comment-id="${c.id}">
        <p class="rp-comment-body">${escHtml(c.comment)}</p>
        <div class="rp-comment-meta">
            <span>${escHtml(c.posted_by)}</span>
            <span>·</span>
            <span>${formatDateTime(c.created_at)}</span>
        </div>
    </div>`;
}

function renderCommentsPagination(pagination) {
    const el = document.getElementById('comments-pagination');
    if (!el) return;
    const { current_page, total_pages } = pagination;
    if (total_pages <= 1) {
        el.innerHTML = '';
        return;
    }
    const prevDisabled = current_page <= 1 ? 'disabled' : '';
    const nextDisabled = current_page >= total_pages ? 'disabled' : '';
    el.innerHTML = `
        <button class="btn btn-outline-secondary btn-sm" ${prevDisabled} id="comments-prev">
            <i class="bi bi-chevron-left"></i> Prev
        </button>
        <span class="text-secondary small">Page ${current_page} of ${total_pages}</span>
        <button class="btn btn-outline-secondary btn-sm" ${nextDisabled} id="comments-next">
            Next <i class="bi bi-chevron-right"></i>
        </button>`;
    el.querySelector('#comments-prev')?.addEventListener('click', () => loadComments(_commentsPage - 1));
    el.querySelector('#comments-next')?.addEventListener('click', () => loadComments(_commentsPage + 1));
}

async function postComment() {
    const input = document.getElementById('new-comment-input');
    const text = input.value.trim();
    if (!text) {
        input.classList.add('is-invalid');
        return;
    }
    input.classList.remove('is-invalid');

    const btn = document.getElementById('btn-post-comment');
    const prevHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    try {
        const { method, href } = API_URLS.resource_plans.comments.create(planPk);
        await apiFetch(href, { method, body: JSON.stringify({ comment: text }) });
        input.value = '';
        showFlash('Comment posted.', 'success');
        loadComments(1);
    } catch (err) {
        const msg = _extractError(err, 'Failed to post comment. Please try again.');
        showFlash(msg, 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = prevHtml;
    }
}

// ─── Versions Tab ────────────────────────────────────────────────────────────

async function renderVersions() {
    try {
        const plan = await fetchPlan();
        _planIsActive = plan.is_active;

        // Toggle inactive notice and new-version button
        document
            .getElementById('versions-inactive-notice')
            .classList.toggle('d-none', _planIsActive);
        document
            .getElementById('btn-new-version')
            .classList.toggle('d-none', !_planIsActive);

        if (_versionsFetcher) {
            _versionsFetcher.refresh();
            return;
        }

        const renderer = initRenderer({
            tbodyId: 'versions-tbody',
            colspan: 4,
            itemLabel: 'versions',
            rowTemplate: renderVersionRow,
            emptyState: { message: 'No versions found for this plan.' },
            filterEmptyState: {},
            paginationBarId: 'versions-pagination-bar',
            paginationInfoId: 'versions-pagination-info',
            paginationControlsId: 'versions-pagination-controls',
            onPageChange: (page) => _versionsFetcher.goToPage(page),
        });

        _versionsFetcher = initFetch({
            apiUrl: API_URLS.resource_plans.versions(planPk).href,
            pageSize: 20,
            searchInputId: '',
            filters: [],
            onLoadStart: () => renderer.renderLoading('Loading versions...'),
            onSuccess: ({ results, pagination }) => {
                _versionDataCache.clear();
                results.forEach((v) => _versionDataCache.set(String(v.id), v));
                renderer.renderRows(results, false);
                renderer.renderPagination(pagination);
                _bindVersionTableActions();
                _renderVersionHistoryTimeline();
            },
            onError: () =>
                renderer.renderError('Failed to load versions. Please refresh the page.'),
        });

        _versionsFetcher.refresh();
    } catch (err) {
        console.error('[renderVersions] Failed to load versions.', err);
    }
}

function renderVersionRow(v) {
    const canEdit = v.status === 'DRAFT' && _planIsActive;
    const canActivate = (v.status === 'DRAFT' || v.status === 'LOCKED') && _planIsActive;
    const canLock = v.status === 'ACTIVE' && _planIsActive;
    const canRestore = _planIsActive;
    const canClone = _planIsActive;
    const canDelete = v.status === 'DRAFT' && _planIsActive;

    const thPct = parseFloat(v.threshold_pct);
    const thFormatted = isNaN(thPct) ? '—' : `${thPct.toFixed(2)} %`;

    return `
        <tr data-version-id="${v.id}" data-plan-id="${v.plan_id}">
            <td><span class="rp-badge rp-badge--muted">v${escHtml(String(v.version))}</span></td>
            <td class="text-center">
                <span class="rp-code" style="font-size:0.75rem">${thFormatted}</span>
            </td>
            <td class="text-center">${_versionStatusBadge(v.status)}</td>
            <td>
                <div class="d-flex gap-1 justify-content-center flex-wrap">
                    <a class="btn btn-ghost-icon" href="/resource-plans/${planPk}/versions/${v.id}/"
                        title="Configure">
                        <i class="bi bi-gear"></i>
                    </a>
                    ${canEdit ? `
                    <button class="btn btn-ghost-icon js-version-edit"
                        data-id="${v.id}" data-plan-id="${v.plan_id}" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>` : ''}
                    ${canActivate ? `
                    <button class="btn btn-ghost-icon js-version-activate"
                        data-id="${v.id}" data-plan-id="${v.plan_id}" data-version="${v.version}"
                        title="Activate Version">
                        <i class="bi bi-play-circle"></i>
                    </button>` : ''}
                    ${canLock ? `
                    <button class="btn btn-ghost-icon js-version-lock"
                        data-id="${v.id}" data-plan-id="${v.plan_id}" data-version="${v.version}"
                        title="Lock Version">
                        <i class="bi bi-lock"></i>
                    </button>` : ''}
                    ${canRestore ? `
                    <button class="btn btn-ghost-icon js-version-restore"
                        data-id="${v.id}" data-plan-id="${v.plan_id}" data-version="${v.version}"
                        title="Restore Version">
                        <i class="bi bi-arrow-counterclockwise"></i>
                    </button>` : ''}
                    ${canClone ? `
                    <button class="btn btn-ghost-icon js-version-clone"
                        data-id="${v.id}" data-plan-id="${v.plan_id}" data-version="${v.version}"
                        title="Clone Version">
                        <i class="bi bi-copy"></i>
                    </button>` : ''}
                    ${canDelete ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger js-version-delete"
                        data-id="${v.id}" data-plan-id="${v.plan_id}" data-version="${v.version}"
                        title="Delete Version">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

function _versionStatusBadge(status) {
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
    return `<span class="rp-badge rp-badge--muted">${escHtml(status)}</span>`;
}

function _bindVersionTableActions() {
    const tbody = document.getElementById('versions-tbody');
    if (!tbody) return;
    tbody.onclick = (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        const row = btn.closest('tr');
        const versionId = row?.dataset.versionId;
        const planId = btn.dataset.planId;
        const versionNum = btn.dataset.version;

        if (btn.classList.contains('js-version-edit')) {
            openVersionEdit(versionId, planId);
        } else if (btn.classList.contains('js-version-activate')) {
            openVersionConfirm('activate', planId, versionNum);
        } else if (btn.classList.contains('js-version-lock')) {
            openVersionConfirm('lock', planId, versionNum);
        } else if (btn.classList.contains('js-version-restore')) {
            openVersionConfirm('restore', planId, versionNum);
        } else if (btn.classList.contains('js-version-clone')) {
            openVersionConfirm('clone', planId, versionNum);
        } else if (btn.classList.contains('js-version-delete')) {
            openVersionConfirm('delete', planId, versionNum);
        }
    };
}

// ─── Version History Sidebar ──────────────────────────────────────────────────

function _renderVersionHistoryTimeline() {
    const container = document.getElementById('version-history-timeline');
    if (!container) return;

    const versions = Array.from(_versionDataCache.values()).sort(
        (a, b) => b.version - a.version
    );

    if (!versions.length) {
        container.innerHTML =
            '<p class="text-secondary small mb-0">No versions found.</p>';
        return;
    }

    container.innerHTML = `<div class="rp-timeline d-flex flex-column">${_buildVersionTimelineItems(versions)}</div>`;
}

function _buildVersionTimelineItems(versions) {
    const statusIconMap = {
        DRAFT: { icon: 'bi-pencil-fill', cls: 'text-secondary' },
        ACTIVE: { icon: 'bi-check-circle-fill', cls: 'text-success' },
        LOCKED: { icon: 'bi-lock-fill', cls: 'text-warning' },
        SUPERSEDED: { icon: 'bi-arrow-counterclockwise', cls: 'text-secondary' },
        EXPIRED: { icon: 'bi-x-circle-fill', cls: 'text-danger' },
    };

    return versions
        .map((v, i) => {
            const { icon, cls } = statusIconMap[v.status] || {
                icon: 'bi-circle',
                cls: 'text-secondary',
            };
            const isLatest = i === 0;
            const thPct = parseFloat(v.threshold_pct);
            const thDisplay = isNaN(thPct) ? '—' : `${thPct.toFixed(2)} %`;

            return `
            <div class="rp-timeline-item">
                <div class="rp-timeline-marker">
                    <div class="rp-timeline-dot ${isLatest ? 'rp-timeline-dot--success' : 'rp-timeline-dot--muted'}">
                        <i class="bi ${icon} ${cls}" style="font-size:.65rem; line-height:1;"></i>
                    </div>
                    ${i < versions.length - 1 ? '<div class="rp-timeline-line"></div>' : ''}
                </div>
                <div class="rp-timeline-body pb-3">
                    ${v.plan_created_at ? `<div class="rp-timeline-meta"><i class="bi bi-calendar3"></i> ${formatDateTime(v.plan_created_at)}</div>` : ''}
                    <div class="d-flex align-items-center gap-2 flex-wrap mb-1">
                        <span class="fw-semibold" style="font-size:.85rem">
                            <span class="rp-badge rp-badge--muted">v${escHtml(String(v.version))}</span>
                        </span>
                        ${_versionStatusBadge(v.status)}
                    </div>
                    <div class="text-secondary" style="font-size:.8rem">
                        Threshold: <span class="rp-code" style="font-size:.75rem">${escHtml(thDisplay)}</span>
                    </div>
                    ${v.cloned_from_plan_name ? `<div class="text-secondary mt-1" style="font-size:.75rem">Based on: ${escHtml(v.cloned_from_plan_name)}</div>` : ''}
                </div>
            </div>`;
        })
        .join('');
}

// ─── Version Modals ───────────────────────────────────────────────────────────

function openVersionView(versionId) {
    const v = _versionDataCache.get(String(versionId));
    if (!v) return;

    document.getElementById('version-view-title').textContent = `Version ${v.version} Details`;
    document.getElementById('vv-version').innerHTML = `<span class="rp-badge rp-badge--muted">v${escHtml(String(v.version))}</span>`;
    document.getElementById('vv-plan-name').textContent = v.plan_name;
    const thPct = parseFloat(v.threshold_pct);
    document.getElementById(
        'vv-threshold'
    ).innerHTML = `<span class="rp-code" style="font-size:0.75rem">${isNaN(thPct) ? '—' : thPct.toFixed(2)} %</span>`;
    document.getElementById('vv-status').innerHTML = _versionStatusBadge(v.status);

    const clonedBlock = document.getElementById('vv-cloned-block');
    if (v.cloned_from_plan_name) {
        clonedBlock.classList.remove('d-none');
        document.getElementById('vv-cloned-from').textContent = v.cloned_from_plan_name;
    } else {
        clonedBlock.classList.add('d-none');
    }

    bootstrap.Modal.getOrCreateInstance(document.getElementById('versionViewModal')).show();
}

function openVersionEdit(versionId, planId) {
    const v = _versionDataCache.get(String(versionId));
    if (!v) return;

    document.getElementById('version-edit-title').textContent = `Edit Version ${v.version}`;
    document.getElementById('ve-plan-id').value = planId;
    document.getElementById('ve-threshold').value = parseFloat(v.threshold_pct).toFixed(2);
    document.getElementById('version-edit-banner').classList.add('d-none');
    document.getElementById('ve-threshold').classList.remove('is-invalid');
    document.getElementById('ve-threshold-err').textContent = '';

    bootstrap.Modal.getOrCreateInstance(document.getElementById('versionEditModal')).show();
}

async function saveVersionEdit() {
    const planId = document.getElementById('ve-plan-id').value;
    const thresholdEl = document.getElementById('ve-threshold');
    const threshold = parseFloat(thresholdEl.value);

    if (isNaN(threshold) || threshold < 0 || threshold > 100) {
        thresholdEl.classList.add('is-invalid');
        document.getElementById('ve-threshold-err').textContent =
            'Threshold must be between 0 and 100.';
        return;
    }
    thresholdEl.classList.remove('is-invalid');
    document.getElementById('ve-threshold-err').textContent = '';

    const spinner = document.getElementById('ve-spinner');
    const btn = document.getElementById('btn-save-version-edit');
    spinner.classList.remove('d-none');
    btn.disabled = true;

    try {
        const { method, href } = API_URLS.resource_plans.version_edit(planId);
        await apiFetch(href, { method, body: JSON.stringify({ threshold_pct: threshold }) });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('versionEditModal')).hide();
        showFlash('Version updated successfully.', 'success');
        _versionsFetcher?.refresh();
    } catch (err) {
        const msg = _extractError(err, 'Failed to update version. Please try again.');
        document.getElementById('version-edit-banner').textContent = msg;
        document.getElementById('version-edit-banner').classList.remove('d-none');
    } finally {
        spinner.classList.add('d-none');
        btn.disabled = false;
    }
}

function openVersionConfirm(action, planId, versionNum) {
    document.getElementById('vconf-action').value = action;
    document.getElementById('vconf-plan-id').value = planId;
    document.getElementById('vconf-banner').classList.add('d-none');
    document.getElementById('vconf-threshold-group').classList.add('d-none');
    document.getElementById('vconf-threshold').classList.remove('is-invalid');
    document.getElementById('vconf-threshold-err').textContent = '';

    const confirmBtn = document.getElementById('btn-confirm-version-action');

    const configs = {
        activate: {
            title: `Activate v${versionNum}`,
            message: `Setting version ${versionNum} as ACTIVE. Any existing ACTIVE version in this group will be superseded.`,
            label: 'Activate',
            btnClass: 'btn btn-sm btn-primary',
        },
        lock: {
            title: `Lock v${versionNum}`,
            message: `Locking version ${versionNum}. Locked plans cannot be modified.`,
            label: 'Lock',
            btnClass: 'btn btn-sm btn-warning',
        },
        restore: {
            title: `Restore v${versionNum}`,
            message: `A new DRAFT version will be created based on v${versionNum}.`,
            label: 'Restore',
            btnClass: 'btn btn-sm btn-primary',
        },
        clone: {
            title: `Clone v${versionNum}`,
            message: `A copy of v${versionNum} will be created as a new DRAFT version within this plan.`,
            label: 'Clone',
            btnClass: 'btn btn-sm btn-primary',
        },
        delete: {
            title: `Delete v${versionNum}`,
            message: `Version ${versionNum} will be permanently removed. This cannot be undone.`,
            label: 'Delete',
            btnClass: 'btn btn-sm btn-danger',
        },
    };

    const cfg = configs[action] || {
        title: 'Confirm',
        message: 'Are you sure?',
        label: 'Confirm',
        btnClass: 'btn btn-sm btn-primary',
    };

    document.getElementById('vconf-title').textContent = cfg.title;
    document.getElementById('vconf-message').textContent = cfg.message;
    document.getElementById('vconf-label').textContent = cfg.label;
    confirmBtn.className = cfg.btnClass;

    // Show "include config" checkbox only for clone/restore actions
    const cfgGroup = document.getElementById('vconf-include-config-group');
    const cfgCheck = document.getElementById('vconf-include-config');
    if (cfgGroup && cfgCheck) {
        const showCfg = action === 'clone' || action === 'restore';
        cfgGroup.classList.toggle('d-none', !showCfg);
        if (showCfg) cfgCheck.checked = false;
    }

    // Hide threshold group for non-new_version actions
    document.getElementById('vconf-threshold-group')?.classList.add('d-none');

    bootstrap.Modal.getOrCreateInstance(document.getElementById('versionConfirmModal')).show();
}

function openNewVersionModal() {
    document.getElementById('vconf-action').value = 'new_version';
    document.getElementById('vconf-plan-id').value = planPk;
    document.getElementById('vconf-banner').classList.add('d-none');
    document.getElementById('vconf-title').textContent = 'Create New Version';
    document.getElementById('vconf-message').textContent =
        'A new DRAFT version will be created in this plan group.';
    document.getElementById('vconf-label').textContent = 'Create';
    document.getElementById('btn-confirm-version-action').className = 'btn btn-sm btn-primary';

    // Show threshold input, pre-fill with latest version's threshold
    const thGroup = document.getElementById('vconf-threshold-group');
    const thInput = document.getElementById('vconf-threshold');
    thGroup.classList.remove('d-none');
    thInput.classList.remove('is-invalid');
    document.getElementById('vconf-threshold-err').textContent = '';
    document.getElementById('vconf-include-config-group')?.classList.add('d-none');
    const versions = Array.from(_versionDataCache.values()).sort((a, b) => b.version - a.version);
    thInput.value = versions.length > 0
        ? parseFloat(versions[0].threshold_pct).toFixed(2)
        : '10.00';

    bootstrap.Modal.getOrCreateInstance(document.getElementById('versionConfirmModal')).show();
}

async function executeVersionConfirm() {
    const action = document.getElementById('vconf-action').value;
    const planId = document.getElementById('vconf-plan-id').value;
    const spinner = document.getElementById('vconf-spinner');
    const btn = document.getElementById('btn-confirm-version-action');

    spinner.classList.remove('d-none');
    btn.disabled = true;

    try {
        let method, href;

        if (action === 'activate') {
            ({ method, href } = API_URLS.resource_plans.version_activate(planId));
        } else if (action === 'lock') {
            ({ method, href } = API_URLS.resource_plans.version_lock(planId));
        } else if (action === 'restore' || action === 'clone') {
            ({ method, href } = API_URLS.resource_plans.restore(planPk, planId));
        } else if (action === 'delete') {
            ({ method, href } = API_URLS.resource_plans.version_delete(planId));
        } else if (action === 'new_version') {
            ({ method, href } = API_URLS.resource_plans.new_version(planId));
        } else {
            return;
        }

        let body;
        if (action === 'new_version') {
            const thEl = document.getElementById('vconf-threshold');
            const thVal = parseFloat(thEl.value);
            if (isNaN(thVal) || thVal < 0 || thVal > 100) {
                thEl.classList.add('is-invalid');
                document.getElementById('vconf-threshold-err').textContent =
                    'Threshold must be between 0 and 100.';
                spinner.classList.add('d-none');
                btn.disabled = false;
                return;
            }
            thEl.classList.remove('is-invalid');
            document.getElementById('vconf-threshold-err').textContent = '';
            body = JSON.stringify({ threshold_pct: thVal });
        } else if (action === 'clone' || action === 'restore') {
            const includeConfig = document.getElementById('vconf-include-config')?.checked ?? false;
            body = JSON.stringify({ include_config: includeConfig });
        }
        await apiFetch(href, { method, body });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('versionConfirmModal')).hide();

        const labels = {
            activate: 'activated',
            lock: 'locked',
            restore: 'restored as new DRAFT version',
            clone: 'cloned as new DRAFT version',
            delete: 'deleted',
            new_version: 'created',
        };
        showFlash(`Version ${labels[action] || action} successfully.`, 'success');

        _versionsFetcher?.refresh();

        // Refresh header if status of the current plan's version may have changed
        if (action === 'activate' || action === 'delete') {
            const plan = await fetchPlan();
            renderHeader(plan);
        }
    } catch (err) {
        const msg = _extractError(err, 'Failed to perform action. Please try again.');
        document.getElementById('vconf-banner').textContent = msg;
        document.getElementById('vconf-banner').classList.remove('d-none');
    } finally {
        spinner.classList.add('d-none');
        btn.disabled = false;
    }
}

// ─── Jobs Tab ─────────────────────────────────────────────────────────────────

async function renderJobs(page, mode, versionId) {
    if (page !== undefined) _jobsPage = page;
    if (mode !== undefined) _jobsModeFilter = mode;
    if (versionId !== undefined) _jobsVersionFilter = versionId;

    const listEl = document.getElementById('jobs-list');
    const runBtn = document.getElementById('btn-run-engine');
    if (!listEl) return;

    listEl.innerHTML = '<p class="text-secondary small">Loading…</p>';

    // Ensure versions are loaded for the filter dropdown
    if (!_engineVersions.length) {
        try {
            const { href } = API_URLS.resource_plans.versions(planPk);
            const data = await apiFetch(href);
            _engineVersions = Array.isArray(data) ? data : (data.results ?? []);
        } catch { /* ignore — filter will just show "All Versions" */ }
    }

    try {
        let url = API_URLS.resource_plans.engine.jobs(planPk).href + `?page=${_jobsPage}&page_size=20`;
        if (_jobsModeFilter) url += `&mode=${_jobsModeFilter}`;
        if (_jobsVersionFilter) url += `&version_id=${_jobsVersionFilter}`;
        const data = await apiFetch(url);
        const results = Array.isArray(data) ? data : (data.results ?? []);
        const count = data.count ?? results.length;
        const numPages = data.num_pages ?? 1;

        const isRunning = results.some(j => j.status === 'PENDING' || j.status === 'RUNNING');
        if (runBtn) {
            runBtn.disabled = isRunning;
            runBtn.title = isRunning ? 'A job is already running' : 'Run the plan engine';
        }

        const versionsForFilter = _engineVersions.length ? _engineVersions : [];
        let html = `
        <div class="d-flex align-items-center justify-content-between gap-2 mb-2 flex-wrap">
            <span class="text-secondary small">${count} job${count !== 1 ? 's' : ''}</span>
            <div class="d-flex gap-2">
                <select class="form-select form-select-sm" id="jobs-version-filter" style="width:auto">
                    <option value="" ${!_jobsVersionFilter ? 'selected' : ''}>All Versions</option>
                    ${versionsForFilter.map(v => `<option value="${v.id}" ${String(v.id) === String(_jobsVersionFilter) ? 'selected' : ''}>v${v.version}</option>`).join('')}
                </select>
                <select class="form-select form-select-sm" id="jobs-mode-filter" style="width:auto">
                    <option value="" ${!_jobsModeFilter ? 'selected' : ''}>All Modes</option>
                    <option value="FULL" ${_jobsModeFilter === 'FULL' ? 'selected' : ''}>FULL</option>
                    <option value="VALIDATE" ${_jobsModeFilter === 'VALIDATE' ? 'selected' : ''}>VALIDATE</option>
                </select>
            </div>
        </div>`;

        if (!results.length) {
            html += '<p class="text-secondary small mb-0">No engine jobs found.</p>';
            listEl.innerHTML = html;
        } else {
            html += `
            <div class="rp-table-wrap" style="overflow-x:auto">
            <table class="table table-sm rp-table mb-0">
                <thead>
                    <tr>
                        <th style="width:28px"></th>
                        <th>Mode</th>
                        <th>Status</th>
                        <th>Version</th>
                        <th>Started</th>
                        <th class="text-end">Duration</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    ${results.map(j => _jobRowHtml(j) + _jobStepsRowHtml(j)).join('')}
                </tbody>
            </table>
            </div>
            ${numPages > 1 ? _renderJobsPagination(_jobsPage, numPages) : ''}`;

            listEl.innerHTML = html;

            document.getElementById('jobs-version-filter')?.addEventListener('change', e => {
                renderJobs(1, _jobsModeFilter, e.target.value);
            });
            document.getElementById('jobs-mode-filter')?.addEventListener('change', e => {
                renderJobs(1, e.target.value, _jobsVersionFilter);
            });

            listEl.querySelectorAll('.js-job-row').forEach(tr => {
                tr.style.cursor = tr.dataset.hasSteps === '1' ? 'pointer' : 'default';
                tr.addEventListener('click', e => {
                    if (e.target.closest('.js-view-job')) return;
                    if (tr.dataset.hasSteps !== '1') return;
                    const jobId = tr.dataset.jobId;
                    const stepsRow = listEl.querySelector(`#job-steps-${jobId}`);
                    if (stepsRow) stepsRow.classList.toggle('d-none');
                    const icon = tr.querySelector('.js-job-toggle-icon');
                    if (icon) {
                        icon.classList.toggle('bi-chevron-right');
                        icon.classList.toggle('bi-chevron-down');
                    }
                });
            });

            listEl.querySelectorAll('.js-view-job').forEach(btn => {
                btn.addEventListener('click', () => openJobDetailModal(btn.dataset.jobId));
            });

            listEl.querySelectorAll('.js-jobs-page').forEach(btn => {
                btn.addEventListener('click', () => renderJobs(parseInt(btn.dataset.page, 10), _jobsModeFilter));
            });
        }
    } catch {
        listEl.innerHTML = '<p class="text-danger small">Failed to load engine jobs.</p>';
    }
}

function _renderJobsPagination(currentPage, numPages) {
    const prevDisabled = currentPage <= 1 ? 'disabled' : '';
    const nextDisabled = currentPage >= numPages ? 'disabled' : '';
    return `
    <div class="rp-pagination-bar d-flex align-items-center justify-content-between px-1 pt-3 flex-wrap gap-2">
        <span class="rp-pagination-info text-secondary small">Page ${currentPage} of ${numPages}</span>
        <nav>
            <ul class="rp-pagination-controls pagination pagination-sm mb-0">
                <li class="page-item ${prevDisabled}">
                    <button class="page-link js-jobs-page" data-page="${currentPage - 1}" ${prevDisabled}>
                        <i class="bi bi-chevron-left"></i>
                    </button>
                </li>
                <li class="page-item ${nextDisabled}">
                    <button class="page-link js-jobs-page" data-page="${currentPage + 1}" ${nextDisabled}>
                        <i class="bi bi-chevron-right"></i>
                    </button>
                </li>
            </ul>
        </nav>
    </div>`;
}

function _jobStatusBadge(status) {
    const map = {
        PENDING: 'rp-badge--muted',
        RUNNING: 'rp-badge--info',
        COMPLETE: 'rp-badge--success',
        FAILED: 'rp-badge--danger',
    };
    return `<span class="rp-badge ${map[status] || 'rp-badge--muted'}">${escHtml(status)}</span>`;
}

function _fmtMs(ms) {
    if (ms == null) return '—';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

function _jobRowHtml(j) {
    const hasSteps = !!(j.steps_log?.length);
    const duration = j.duration_seconds != null ? `${j.duration_seconds}s` : '—';
    const errCount = j.validation_result?.error_count ?? '—';
    const warnCount = j.validation_result?.warning_count ?? '—';
    const resultSummary = j.status === 'COMPLETE'
        ? `<span class="${errCount > 0 ? 'text-danger' : 'text-success'}" style="font-size:.8rem">${errCount} err · ${warnCount} warn</span>`
        : j.status === 'FAILED'
        ? `<span class="text-danger" style="font-size:.8rem">Failed</span>`
        : '—';
    return `
        <tr class="js-job-row" data-job-id="${j.id}" data-has-steps="${hasSteps ? '1' : '0'}">
            <td class="text-center" style="width:28px">
                ${hasSteps ? `<i class="bi bi-chevron-right js-job-toggle-icon" style="font-size:.7rem;color:var(--bs-secondary-color)"></i>` : ''}
            </td>
            <td><span class="rp-badge rp-badge--muted" style="font-size:.7rem">${escHtml(j.mode)}</span></td>
            <td>${_jobStatusBadge(j.status)}</td>
            <td style="font-size:.82rem">v${j.version_number ?? '—'}</td>
            <td style="font-size:.82rem">${j.started_at ? formatDateTime(j.started_at) : '—'}</td>
            <td class="text-end" style="font-size:.82rem">${duration}</td>
            <td>
                ${resultSummary}
                ${(j.status === 'COMPLETE' || j.status === 'FAILED') ? `
                <button class="btn btn-ghost-icon js-view-job ms-1" data-job-id="${j.id}" title="View details" style="padding:1px 4px">
                    <i class="bi bi-eye" style="font-size:.75rem"></i>
                </button>` : ''}
            </td>
        </tr>`;
}

function _jobStepsRowHtml(j) {
    const steps = j.steps_log;
    if (!steps?.length) return '';
    const stepsHtml = steps.map(s => `
        <div class="d-flex align-items-center gap-3 py-1 border-bottom" style="font-size:.78rem">
            <span class="flex-grow-1 text-secondary ps-2">
                <i class="bi bi-check2-circle text-success me-1"></i>${escHtml(s.step ?? s.name ?? '')}
            </span>
            <span class="text-secondary text-nowrap" style="min-width:140px">
                <i class="bi bi-clock me-1"></i>${s.started_at ? formatDateTime(s.started_at) : '—'}
            </span>
            <span class="fw-medium text-nowrap" style="min-width:50px;text-align:right">
                ${_fmtMs(s.duration_ms)}
            </span>
        </div>`).join('');
    return `
        <tr id="job-steps-${j.id}" class="d-none">
            <td colspan="7" class="p-0" style="background:var(--bs-tertiary-bg,#f8f9fa)">
                <div class="px-4 py-2">
                    <div class="text-secondary fw-semibold mb-1" style="font-size:.74rem">
                        <i class="bi bi-list-check me-1"></i>Steps
                    </div>
                    ${stepsHtml}
                </div>
            </td>
        </tr>`;
}

async function openJobDetailModal(jobId) {
    try {
        const job = await apiFetch(API_URLS.resource_plans.engine.job_detail(planPk, jobId).href);
        _showJobResultInModal(job);
        bootstrap.Modal.getOrCreateInstance(document.getElementById('runEngineModal')).show();
    } catch {
        showFlash('Failed to load job details.', 'danger');
    }
}

function _showJobResultInModal(job) {
    document.getElementById('engine-run-form').classList.add('d-none');
    document.getElementById('engine-progress-section').classList.remove('d-none');
    document.getElementById('btn-engine-submit').classList.add('d-none');

    _updateEngineProgress(job);

    if (job.status === 'COMPLETE' && job.validation_result) {
        _renderValidationResult(job.validation_result);
    } else if (job.status === 'FAILED' && job.error_log) {
        document.getElementById('engine-error-log').textContent = job.error_log;
        document.getElementById('engine-error-log-section').classList.remove('d-none');
    }
}

// Run Engine button opens modal
function _bindEngineEvents() {
    document.getElementById('btn-run-engine')?.addEventListener('click', async () => {
        await _resetEngineModal();
        bootstrap.Modal.getOrCreateInstance(document.getElementById('runEngineModal')).show();
    });

    document.getElementById('btn-engine-submit')?.addEventListener('click', submitEngineRun);

    document.getElementById('runEngineModal')?.addEventListener('hidden.bs.modal', () => {
        _stopEnginePoller();
    });
}

async function _resetEngineModal() {
    _stopEnginePoller();
    _engineJobId = null;
    document.getElementById('engine-run-form').classList.remove('d-none');
    document.getElementById('engine-progress-section').classList.add('d-none');
    document.getElementById('engine-result-section').classList.add('d-none');
    document.getElementById('engine-error-log-section').classList.add('d-none');
    document.getElementById('engine-run-err').classList.add('d-none');
    document.getElementById('btn-engine-submit').classList.remove('d-none');
    document.getElementById('btn-engine-submit').disabled = false;
    document.getElementById('engine-submit-spinner').classList.add('d-none');
    document.getElementById('mode-validate').checked = true;
    document.getElementById('engine-include-current').checked = false;
    const overridesEl = document.getElementById('engine-remove-overrides');
    if (overridesEl) overridesEl.checked = false;
    document.getElementById('engine-overrides-section')?.classList.add('d-none');
    await _loadEngineVersionOptions();
}

let _engineVersions = [];

async function _loadEngineVersionOptions() {
    const select = document.getElementById('engine-version');
    if (!select) return;
    select.innerHTML = '<option value="">Loading…</option>';
    try {
        const { href } = API_URLS.resource_plans.versions(planPk);
        const data = await apiFetch(href);
        _engineVersions = Array.isArray(data) ? data : (data.results ?? []);
        if (!_engineVersions.length) {
            select.innerHTML = '<option value="">No versions available</option>';
            return;
        }
        select.innerHTML = _engineVersions.map(v =>
            `<option value="${v.id}">v${v.version} — ${escHtml(v.status)}${v.plan_name ? ` (${escHtml(v.plan_name)})` : ''}</option>`
        ).join('');
        _updateEngineOverridesSection();
    } catch {
        select.innerHTML = '<option value="">Failed to load versions</option>';
    }
    select.addEventListener('change', _updateEngineOverridesSection);
}

function _updateEngineOverridesSection() {
    const select = document.getElementById('engine-version');
    const section = document.getElementById('engine-overrides-section');
    const checkbox = document.getElementById('engine-remove-overrides');
    if (!select || !section) return;
    const selectedId = parseInt(select.value, 10);
    const ver = _engineVersions.find(v => v.id === selectedId);
    const hasOverrides = ver?.has_pl_overrides ?? false;
    section.classList.toggle('d-none', !hasOverrides);
    if (checkbox && !hasOverrides) checkbox.checked = false;
}

async function submitEngineRun() {
    const mode = document.querySelector('input[name="engine-mode"]:checked')?.value ?? 'VALIDATE';
    const includeCurrent = document.getElementById('engine-include-current').checked;
    const removeOverrides = document.getElementById('engine-remove-overrides')?.checked ?? false;
    const versionId = document.getElementById('engine-version')?.value || null;
    const errEl = document.getElementById('engine-run-err');
    errEl.classList.add('d-none');

    if (!versionId) {
        errEl.textContent = 'Please select a version to run against.';
        errEl.classList.remove('d-none');
        return;
    }

    const submitBtn = document.getElementById('btn-engine-submit');
    const spinner = document.getElementById('engine-submit-spinner');
    submitBtn.disabled = true;
    spinner.classList.remove('d-none');

    try {
        const { method, href } = API_URLS.resource_plans.engine.run(planPk);
        const result = await apiFetch(href, {
            method,
            body: JSON.stringify({
                mode,
                include_current_sprint: includeCurrent,
                version_id: versionId,
                remove_overrides: removeOverrides,
            }),
        });

        _engineJobId = result.job_id;

        // Switch modal to progress view
        document.getElementById('engine-run-form').classList.add('d-none');
        document.getElementById('engine-progress-section').classList.remove('d-none');
        document.getElementById('btn-engine-submit').classList.add('d-none');

        _startEnginePoller();
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

function _startEnginePoller() {
    _stopEnginePoller();
    _pollEngineStatus();
    _enginePollTimer = setInterval(_pollEngineStatus, 3000);
}

function _stopEnginePoller() {
    if (_enginePollTimer) {
        clearInterval(_enginePollTimer);
        _enginePollTimer = null;
    }
}

async function _pollEngineStatus() {
    if (!_engineJobId) return;
    try {
        const job = await apiFetch(API_URLS.resource_plans.engine.job_status(planPk, _engineJobId).href);
        _updateEngineProgress(job);

        if (job.status === 'COMPLETE' || job.status === 'FAILED') {
            _stopEnginePoller();
            // Fetch full job for validation_result / error_log
            const fullJob = await apiFetch(API_URLS.resource_plans.engine.job_detail(planPk, _engineJobId).href);
            if (fullJob.status === 'COMPLETE' && fullJob.validation_result) {
                _renderValidationResult(fullJob.validation_result);
            } else if (fullJob.status === 'FAILED') {
                document.getElementById('engine-error-log').textContent = fullJob.error_log ?? 'Unknown error.';
                document.getElementById('engine-error-log-section').classList.remove('d-none');
            }
            // Re-enable Run button and reload job history
            document.getElementById('btn-run-engine').disabled = false;
            renderJobs();
        }
    } catch {
        // Ignore transient poll errors
    }
}

function _updateEngineProgress(job) {
    const pct = job.progress_pct ?? 0;
    const bar = document.getElementById('engine-progress-bar');
    if (bar) {
        bar.style.width = `${pct}%`;
        bar.setAttribute('aria-valuenow', pct);
        const isComplete = job.status === 'COMPLETE';
        const isFailed = job.status === 'FAILED';
        bar.className = `progress-bar${isFailed ? ' bg-danger' : isComplete ? ' bg-success' : ''}`;
    }
    const stepEl = document.getElementById('engine-current-step');
    if (stepEl) stepEl.textContent = job.current_step ?? (job.status === 'PENDING' ? 'Queued…' : '');

    const badge = document.getElementById('engine-status-badge');
    if (badge) badge.innerHTML = _jobStatusBadge(job.status);
}

function _validationItemContext(item) {
    const parts = [];
    if (item.name) parts.push(item.name);
    else if (item.phase_name) parts.push(item.phase_name);
    else if (item.team_name) parts.push(item.team_name);
    if (item.project_name) parts.push(item.project_name);
    else if (item.project) parts.push(item.project);
    return parts;
}

function _renderValidationItem(item, colorClass) {
    const ctx = _validationItemContext(item);
    const entityLabel = { version: 'Version', project: 'Project', team: 'Team', phase: 'Phase', pause: 'Pause', dependency: 'Dependency' }[item.entity] ?? (item.entity ?? '—');
    const entityBadge = `<span class="rp-badge rp-badge--muted" style="font-size:.66rem;flex-shrink:0;text-transform:uppercase">${escHtml(entityLabel)}</span>`;
    const ctxHtml = ctx.length
        ? `<div class="text-secondary" style="font-size:.75rem">${ctx.map(escHtml).join(' · ')}</div>`
        : '';
    return `
        <div class="d-flex align-items-start gap-2 py-2 border-bottom">
            <div class="mt-1">${entityBadge}</div>
            <div class="flex-grow-1">
                <div style="font-size:.8rem">${escHtml(item.message)}</div>
                ${ctxHtml}
            </div>
        </div>`;
}

function _renderValidationResult(result) {
    const section = document.getElementById('engine-result-section');
    if (!section) return;

    const errors = result.errors ?? [];
    const warnings = result.warnings ?? [];
    const errorCount = result.error_count ?? errors.length;
    const warnCount = result.warning_count ?? warnings.length;

    const summaryBadge = errorCount > 0
        ? `<span class="rp-badge rp-badge--danger">${errorCount} error${errorCount !== 1 ? 's' : ''}</span>`
        : `<span class="rp-badge rp-badge--success">No errors</span>`;
    const warnSummaryBadge = warnCount > 0
        ? `<span class="rp-badge rp-badge--warning">${warnCount} warning${warnCount !== 1 ? 's' : ''}</span>`
        : '';

    let html = `<div class="d-flex align-items-center gap-2 mb-3">${summaryBadge}${warnSummaryBadge}</div>`;

    if (errors.length) {
        html += `<div class="mb-3">
            <div class="fw-semibold text-danger mb-1" style="font-size:.82rem">
                <i class="bi bi-x-circle me-1"></i>Errors
            </div>
            <div class="border rounded px-2">
                ${errors.map(e => _renderValidationItem(e, 'danger')).join('')}
            </div>
        </div>`;
    }

    if (warnings.length) {
        html += `<div>
            <div class="fw-semibold" style="font-size:.82rem;color:var(--bs-warning-text-emphasis,#664d03)">
                <i class="bi bi-exclamation-triangle me-1"></i>Warnings
            </div>
            <div class="border rounded px-2 mt-1">
                ${warnings.map(w => _renderValidationItem(w, 'warning')).join('')}
            </div>
        </div>`;
    }

    if (!errors.length && !warnings.length) {
        html += `<p class="text-success small mb-0"><i class="bi bi-check-circle me-1"></i>All checks passed.</p>`;
    }

    section.innerHTML = html;
    section.classList.remove('d-none');
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function _extractError(err, fallback) {
    if (err?.data?.details) {
        const d = err.data.details;
        if (typeof d === 'string') return d;
        if (Array.isArray(d)) return d.join(' ');
        if (typeof d === 'object') return Object.values(d).flat().join(' ');
    }
    if (err?.data?.error) return err.data.error;
    if (err?.data?.detail) return err.data.detail;
    return fallback;
}
