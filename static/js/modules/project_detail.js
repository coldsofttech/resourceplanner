'use strict';

import { initFetch } from './../list/fetch.js';
import { initRenderer } from './../list/render.js';
import { initSorting } from './../list/sort.js';
import {
    apiFetch,
    escAttr,
    escHtml,
    formatDate,
    formatDateTime,
    getPkFromUrl,
    setPageTitle,
    showFlash,
} from './../main.js';
import { API_URLS } from './../urls.js';

const projectPk = getPkFromUrl('projects');

document.addEventListener('DOMContentLoaded', () => {
    if (!projectPk) return;
    initDetailView();
});

let options = null;
let _allSubStatuses = [];
let commentPage = 1;
let codesPage = 1;
let estimatesTableFetcher = null;
let linksTableFetcher = null;
let _estimateHistoryPage = 1;
let _currentHistoryEstimateId = null;
let _budgetHistoryPage = 1;
let _currentHistoryBudgetId = null;
let _budgetFyOptions = [];
let _budgetEstimateOptions = [];
let _suggestTimeout = null;
let _selectedContactId = null;

async function initDetailView() {
    try {
        const project = await fetchProject();
        options = await fetchOptions();
        setPageTitle(project.name);
        bindTabEvents();
        renderHeader(project);
        renderGeneral();
        populateEditDropdowns(options);
        bindEditButtons();
    } catch (err) {
        console.error('[initDetailView] Failed to load project.', err);
        _showBanner('Failed to load project data. Please refresh the page.', 'danger');
    }
}

function bindTabEvents() {
    document.getElementById('tab-general').addEventListener('shown.bs.tab', function () {
        renderGeneral();
    });
    document.getElementById('tab-operational').addEventListener('shown.bs.tab', function () {
        renderOperational();
    });
    document.getElementById('tab-teams').addEventListener('shown.bs.tab', function () {
        renderTeams();
    });
    document.getElementById('tab-labels').addEventListener('shown.bs.tab', function () {
        renderLabels();
    });
    document.getElementById('tab-history').addEventListener('shown.bs.tab', function () {
        renderStatusHistory();
    });
    document.getElementById('tab-estimates').addEventListener('shown.bs.tab', function () {
        renderEstimates();
    });
    document.getElementById('tab-budgets').addEventListener('shown.bs.tab', function () {
        renderBudgets();
    });
    document.getElementById('tab-contacts').addEventListener('shown.bs.tab', function () {
        renderContacts('PROJECT');
        renderContacts('FINANCE');
    });
    document.getElementById('tab-links').addEventListener('shown.bs.tab', function () {
        renderLinks();
    });
    document.getElementById('tab-actuals')?.addEventListener('shown.bs.tab', function () {
        renderActualsTab();
    });
}

async function fetchOptions() {
    const { method, href } = API_URLS.projects.options;
    const res = await apiFetch(href, { method });
    return res;
}

async function fetchProject() {
    const { method, href } = API_URLS.projects.detail(projectPk);
    const res = await apiFetch(href, { method });
    return res;
}

async function fetchEstimateOptions() {
    const { method, href } = API_URLS.projects.estimates.options(projectPk);
    const res = await apiFetch(href, { method });
    return res;
}

async function fetchOperational() {
    const { method, href } = API_URLS.projects.get_operational(projectPk);
    const res = await apiFetch(href, { method });
    return res;
}

async function fetchTags() {
    const { method, href } = API_URLS.projects.tags.get(projectPk);
    const res = await apiFetch(href, { method });
    return res;
}

async function fetchComments(page = 1) {
    const { method, href } = API_URLS.projects.comments.list(projectPk);
    const res = await apiFetch(`${href}?page=${page}`, { method });
    return res;
}

async function fetchTeams() {
    const { method, href } = API_URLS.projects.get_teams(projectPk);
    const res = await apiFetch(href, { method });
    return res;
}

async function fetchLabels() {
    const { method, href } = API_URLS.projects.list_labels(projectPk);
    const res = await apiFetch(`${href}?page_size=200`, { method });
    return res;
}

async function fetchLatestCode() {
    const { method, href } = API_URLS.projects.codes.active(projectPk);
    const res = await apiFetch(href, { method });
    return res;
}

async function fetchCodeHistory(page = 1) {
    const { method, href } = API_URLS.projects.codes.history(projectPk);
    const res = await apiFetch(`${href}?page=${page}`, { method });
    return res;
}

async function fetchStatusHistory() {
    const { method, href } = API_URLS.projects.status.history(projectPk);
    const res = await apiFetch(`${href}?page_size=10`, { method });
    return res;
}

async function fetchContacts(role) {
    const { method, href } = API_URLS.projects.contacts.list(projectPk);
    const res = await apiFetch(`${href}?role=${role}`, { method });
    return res;
}

async function renderHeader(project) {
    document.getElementById('project-detail-name').textContent = project.display_name;
    document.getElementById('proj-active-badge').innerHTML = project.is_active
        ? '<span class="rp-badge rp-badge--success">Active</span>'
        : '<span class="rp-badge rp-badge--muted">Inactive</span>';
}

async function renderGeneral() {
    try {
        exitEditMode('general');
        const project = await fetchProject();

        document.getElementById('view-name').textContent = project.name;
        document.getElementById('view-project-type-id').textContent = project.project_type;
        document.getElementById('view-project-type').textContent = project.project_type_name ?? '-';
        document.getElementById('view-programme-id').textContent = project.programme;
        document.getElementById('view-programme').textContent = project.programme_name ?? '-';
        document.getElementById('view-status-id').textContent = project.status;
        document.getElementById('view-status').innerHTML =
            _statusBadge(project.status, project.status_display) ?? '-';
        document.getElementById('view-sub-status-id').textContent = project.sub_status;
        document.getElementById('view-sub-status').textContent = project.sub_status_name ?? '-';
        document.getElementById('view-confidence-id').textContent = project.confidence;
        document.getElementById('view-confidence').innerHTML =
            _levelBadge(project.confidence, project.confidence_display) ?? '-';
        document.getElementById('view-priority-id').textContent = project.priority;
        document.getElementById('view-priority').innerHTML =
            _levelBadge(project.priority, project.priority_display) ?? '-';
        document.getElementById('view-tentative-start').textContent =
            formatDate(project.tentative_start_date) ?? '-';
        document.getElementById('view-tentative-end').textContent =
            formatDate(project.tentative_end_date) ?? '-';

        document.getElementById('meta-created').textContent =
            formatDateTime(project.created_at) ?? '-';
        document.getElementById('meta-updated').textContent =
            formatDateTime(project.updated_at) ?? '-';

        renderComments(commentPage);
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderGeneral] Failed to load project general information.', err);
    }
}

async function renderComments(page = 1) {
    commentPage = page;
    const container = document.getElementById('comments-container');
    const pinnedContainer = document.getElementById('comments-pinned-container');
    const paginationEl = document.getElementById('comments-pagination');
    if (!container) return;

    try {
        const data = await fetchComments(page);
        renderPinnedComments(data.pinned ?? [], pinnedContainer);
        renderCommentList(data.results ?? [], container);
        renderCommentPagination(data, paginationEl, renderComments);
    } catch (err) {
        container.innerHTML = '<p class="text-secondary small">Failed to load comments.</p>';
        console.error('[renderComments] Failed to load comments.', err);
    }
}

function renderPinnedComments(pinned, container) {
    if (!container) return;
    if (!pinned.length) {
        container.innerHTML = '';
        return;
    }
    container.innerHTML = pinned.map((c) => _commentCardHtml(c, true)).join('');
    _bindCommentCardActions(container);
}

function renderCommentList(comments, container, opts = {}) {
    if (!container) return;
    if (!comments.length) {
        container.innerHTML = '<p class="text-secondary small mb-0">No comments yet.</p>';
        return;
    }
    container.innerHTML = comments.map((c) => _commentCardHtml(c, opts.showPin ?? false)).join('');
    _bindCommentCardActions(container);
}

function _commentCardHtml(c, showPin) {
    const pinnedCls = c.is_pinned ? 'rp-comment-card--pinned' : '';
    const pinnedBadge = c.is_pinned
        ? '<span class="rp-comment-pin-badge"><i class="bi bi-pin-angle-fill"></i>Pinned</span>'
        : '';
    const editedBadge = c.is_edited ? '<span class="rp-comment-edited">edited</span>' : '';
    const pinActionLabel = c.is_pinned ? 'Unpin' : 'Pin';

    return `
    <div class="rp-comment-card ${pinnedCls}" data-comment-id="${c.id}">
        <p class="rp-comment-body">${escHtml(c.comment)}</p>
        <div class="rp-comment-meta">
            ${pinnedBadge}
            <span>${escHtml(c.posted_by)}</span>
            <span>·</span>
            <span>${formatDateTime(c.created_at)}</span>
            ${editedBadge}
            <div class="rp-comment-actions">
                <button class="btn btn-ghost-icon btn-sm js-pin-comment" data-id="${c.id}" data-pinned="${c.is_pinned}" title="${pinActionLabel}">
                    <i class="bi bi-pin${c.is_pinned ? '-angle-fill' : ''}"></i>
                </button>
                <button class="btn btn-ghost-icon btn-sm js-edit-comment" data-id="${c.id}" data-comment="${escHtml(c.comment)}" title="Edit">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm js-delete-comment" data-id="${c.id}" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </div>
    </div>`;
}

function _bindCommentCardActions(container) {
    container.querySelectorAll('.js-edit-comment').forEach((btn) => {
        btn.addEventListener('click', () =>
            openEditCommentModal(btn.dataset.id, btn.dataset.comment),
        );
    });
    container.querySelectorAll('.js-delete-comment').forEach((btn) => {
        btn.addEventListener('click', () => openDeleteCommentModal(btn.dataset.id));
    });
    container.querySelectorAll('.js-pin-comment').forEach((btn) => {
        btn.addEventListener('click', () =>
            togglePinComment(btn.dataset.id, btn.dataset.pinned === 'true'),
        );
    });
}

function renderCommentPagination(data, el, loadFn) {
    if (!el) return;
    const { current_page, total_pages } = data;
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

    el.querySelector('#comments-prev')?.addEventListener('click', () => loadFn(current_page - 1));
    el.querySelector('#comments-next')?.addEventListener('click', () => loadFn(current_page + 1));
}

async function handlePostComment() {
    const btn = document.getElementById('btn-post-comment');
    const input = document.getElementById('new-comment-input');
    const text = input.value.trim();
    if (!text) {
        input.classList.add('is-invalid');
        return;
    }
    input.classList.remove('is-invalid');

    const prevHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    try {
        const { method, href } = API_URLS.projects.comments.create(projectPk);
        await apiFetch(href, { method, body: JSON.stringify({ comment: text }) });
        input.value = '';
        showFlash('Comment posted.', 'success');
        renderComments(1);
    } catch (err) {
        showFlash(_extractError(err, 'Failed to post comment.'), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = prevHtml;
    }
}

function openEditCommentModal(commentId, currentText) {
    document.getElementById('edit-comment-input').value = currentText;
    document.getElementById('confirm-edit-comment-btn').dataset.commentId = commentId;
    document.getElementById('proj-edit-comment-banner').classList.add('d-none');
    _showModal('projEditCommentModal');
}

function openDeleteCommentModal(commentId) {
    document.getElementById('confirm-delete-comment-btn').dataset.commentId = commentId;
    document.getElementById('proj-delete-comment-banner').classList.add('d-none');
    _showModal('projDeleteCommentModal');
}

async function handleSaveEditComment() {
    const btn = document.getElementById('confirm-edit-comment-btn');
    const commentId = btn.dataset.commentId;
    const text = document.getElementById('edit-comment-input').value.trim();
    if (!text) {
        document.getElementById('edit-comment-input').classList.add('is-invalid');
        return;
    }

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        const { method, href } = API_URLS.projects.comments.patch(projectPk, commentId);
        await apiFetch(href, { method, body: JSON.stringify({ comment: text }) });
        _hideModal('projEditCommentModal');
        showFlash('Comment updated.', 'success');
        renderComments(commentPage);
    } catch (err) {
        const msg = _extractError(err, 'Failed to update comment.');
        document.getElementById('proj-edit-comment-banner').textContent = msg;
        document.getElementById('proj-edit-comment-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function handleDeleteComment() {
    const btn = document.getElementById('confirm-delete-comment-btn');
    const commentId = btn.dataset.commentId;
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        const { method, href } = API_URLS.projects.comments.delete(projectPk, commentId);
        await apiFetch(href, { method });
        _hideModal('projDeleteCommentModal');
        showFlash('Comment deleted.', 'success');
        renderComments(commentPage);
    } catch (err) {
        const msg = _extractError(err, 'Failed to delete comment.');
        document.getElementById('proj-delete-comment-banner').textContent = msg;
        document.getElementById('proj-delete-comment-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function togglePinComment(commentId, currentlyPinned) {
    try {
        const { method, href } = API_URLS.projects.comments.patch(projectPk, commentId);
        await apiFetch(href, { method, body: JSON.stringify({ is_pinned: !currentlyPinned }) });
        showFlash(currentlyPinned ? 'Comment unpinned.' : 'Comment pinned.', 'success');
        renderComments(commentPage);
    } catch (err) {
        showFlash(_extractError(err, 'Failed to update pin status.'), 'error');
    }
}

async function renderOperational() {
    try {
        exitEditMode('operational');
        const operational = await fetchOperational();

        const effortsIssuedBadge = operational.efforts_issued
            ? '<span class="rp-badge rp-badge--success">Yes</span>'
            : '<span class="rp-badge rp-badge--warning">No</span>';
        const runCostApplies = operational.run_cost_applies
            ? '<span class="rp-badge rp-badge--success">Yes</span>'
            : '<span class="rp-badge rp-badge--muted">No</span>';
        document.getElementById('view-efforts-issued').innerHTML = effortsIssuedBadge;
        document.getElementById('view-effort-issue-commitment-date').textContent =
            formatDate(operational.effort_issue_commitment_date) ?? '-';
        document.getElementById('view-run-cost').innerHTML = runCostApplies;

        const tags = await fetchTags();
        const tagsContainer = document.getElementById('proj-tags-container');
        if (!tags.length) {
            tagsContainer.innerHTML =
                '<p class="text-secondary small mb-0">No tags. Use the "Add" button to add one.';
        } else {
            tagsContainer.innerHTML = tags
                .map(
                    (t) => `
                <a href="#" class="rp-link rp-tag-chip me-1 mb-1" data-tag-id="${t.id}" data-tag-name="${escHtml(t.name)}">
                    <span class="rp-tag-prefix">#</span>${escHtml(t.name.slice(1))}
                </a>
            `,
                )
                .join('');

            tagsContainer.querySelectorAll('.rp-tag-chip').forEach((chip) => {
                chip.addEventListener('click', () => {
                    showDeleteTagModal(chip.dataset.tagId, chip.dataset.tagName);
                });
            });
        }
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderOperational] Failed to load project operational information.', err);
    }
}

async function renderTeams() {
    try {
        exitEditMode('teams');
        const teams = await fetchTeams();

        document.getElementById('view-assigned-team-id').textContent = teams.assigned_team;
        document.getElementById('view-assigned-team').textContent = teams.assigned_team_name ?? '-';

        const listEl = document.getElementById('view-collaborators-list');

        const collabs = teams.collaborators ?? [];
        if (!collabs.length) {
            listEl.innerHTML =
                '<span class="text-muted" style="font-size: 13px;">No collaborating teams</span>';
        } else {
            listEl.innerHTML = collabs
                .map(
                    (c) =>
                        `<span class="rp-badge rp-badge--muted me-1 mb-1">${escHtml(c.name)}</span>`,
                )
                .join('');
        }
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderTeams] Failed to load project teams information.', err);
    }
}

async function renderCodeHistory(page = 1) {
    codesPage = page;
    const container = document.getElementById('code-history-container');
    const paginationEl = document.getElementById('code-history-pagination');
    if (!container) return;

    try {
        const history = await fetchCodeHistory(codesPage);
        const items = history.results ?? [];
        const isPaginated = !!history.pagination?.total_pages;

        if (!items.length) {
            container.innerHTML = `
                <div class="d-flex flex-column align-items-center justify-content-center py-4 text-secondary">
                    <i class="bi bi-clock-history fs-3 mb-2 opacity-50"></i>
                    <span class="small">No code history recorded yet.</span>
                </div>`;
            if (paginationEl) paginationEl.innerHTML = '';
            return;
        }

        container.innerHTML = `<div class="rp-timeline d-flex flex-column">${_buildCodeHistoryItems(items, codesPage)}</div>`;

        if (paginationEl && isPaginated) {
            _renderCodeHistoryPagination(history.pagination, paginationEl);
        } else if (paginationEl) {
            paginationEl.innerHTML = '';
        }
    } catch (err) {
        container.innerHTML = '<p class="text-secondary small">Failed to load code history.</p>';
        console.error('[renderCodeHistory] Failed to load code history.', err);
    }
}

function _buildCodeHistoryItems(entries, page = 1) {
    return entries
        .map((entry, i) => {
            const isLatest = page === 1 && i === 0;
            const dotClass = isLatest ? 'rp-timeline-dot--success' : 'rp-timeline-dot--muted';
            const notes = entry.notes
                ? `<p class="text-secondary small mb-0 mt-1">${escHtml(entry.notes)}</p>`
                : '';
            const currentBadge = isLatest
                ? '<span class="rp-badge rp-badge--info ms-1">Current</span>'
                : '';

            return `
            <div class="rp-timeline-item">
                <div class="rp-timeline-marker">
                    <div class="rp-timeline-dot ${dotClass}"></div>
                    ${i < entries.length - 1 ? '<div class="rp-timeline-line"></div>' : ''}
                </div>
                <div class="rp-timeline-body pb-4">
                    <div class="rp-timeline-meta">
                        <i class="bi bi-calendar3"></i> ${formatDateTime(entry.created_at)}
                    </div>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        <span class="rp-code">${escHtml(entry.code)}</span>
                        ${currentBadge}
                    </div>
                    ${notes}
                </div>
            </div>`;
        })
        .join('');
}

function _renderCodeHistoryPagination(data, el) {
    const { current_page, total_pages } = data;
    if (total_pages <= 1) {
        el.innerHTML = '';
        return;
    }
    const prevDisabled = current_page <= 1 ? 'disabled' : '';
    const nextDisabled = current_page >= total_pages ? 'disabled' : '';
    el.innerHTML = `
        <div class="d-flex align-items-center gap-2 mt-2">
            <button class="btn btn-outline-secondary btn-sm" ${prevDisabled} id="codes-prev">
                <i class="bi bi-chevron-left"></i> Prev
            </button>
            <span class="text-secondary small">Page ${current_page} of ${total_pages}</span>
            <button class="btn btn-outline-secondary btn-sm" ${nextDisabled} id="codes-next">
                Next <i class="bi bi-chevron-right"></i>
            </button>
        </div>`;
    el.querySelector('#codes-prev')?.addEventListener('click', () =>
        renderCodeHistory(current_page - 1),
    );
    el.querySelector('#codes-next')?.addEventListener('click', () =>
        renderCodeHistory(current_page + 1),
    );
}

async function renderLabels() {
    try {
        exitEditMode('labels');
        const labels = await fetchLabels();

        const primaryLabel = labels['results'].find((l) => l.is_primary === true);
        const primaryLabelEl = document.getElementById('view-project-label');
        if (primaryLabel) {
            primaryLabelEl.innerHTML = `
                <a href="#" class="rp-badge rp-badge--primary-label" style="text-decoration: none;">${primaryLabel.label}</a>
            `;
            primaryLabelEl.dataset.id = primaryLabel.id;
            primaryLabelEl.dataset.label = primaryLabel.label;
            primaryLabelEl.addEventListener('click', (e) => {
                e.preventDefault();
                showDeleteLabelModal(primaryLabel.id, primaryLabel.label, primaryLabel.is_primary);
            });
        } else {
            primaryLabelEl.innerHTML = `<span class="rp-badge rp-badge--muted">-</span>`;
        }

        const secondaryLabels = labels['results'].filter((l) => l.is_primary !== true);
        const secondaryLabelsEl = document.getElementById('view-secondary-labels');
        secondaryLabelsEl.innerHTML = '';
        secondaryLabels.forEach((l) => {
            const el = document.createElement('a');
            el.href = '#';
            el.classList.add('rp-link', 'rp-badge', 'rp-badge--muted', 'me-1', 'mb-1');
            el.dataset.id = l.id;
            el.dataset.label = l.label;
            el.textContent = l.label;
            secondaryLabelsEl.appendChild(el);

            el.addEventListener('click', (e) => {
                e.preventDefault();
                showDeleteLabelModal(l.id, l.label, l.is_primary);
            });
        });

        const active_code = await fetchLatestCode();
        document.getElementById('view-project-code').textContent = active_code?.code ?? '-';

        renderCodeHistory(codesPage);
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderLabels] Failed to load project labels information.', err);
    }
}

async function renderEstimates() {
    try {
        exitEditMode('estimates');

        const renderer = initRenderer({
            tbodyId: 'estimates-tbody',
            colspan: 6,
            itemLabel: 'estimates',
            rowTemplate: renderEstimateRow,
            emptyState: {
                message: 'No estimates yet.',
                link: {
                    href: '#',
                    label: 'Create the first one.',
                    onclick: '_showModal("projAddEstimateModal")',
                },
            },
            filterEmptyState: {},
            paginationBarId: 'estimates-pagination-bar',
            paginationInfoId: 'estimates-pagination-info',
            paginationControlsId: 'estimates-pagination-controls',
            onPageChange: (page) => estimatesTableFetcher.goToPage(page),
        });

        estimatesTableFetcher = initFetch({
            apiUrl: API_URLS.projects.estimates.list(projectPk).href,
            pageSize: 20,
            searchInputId: '',
            filters: [],
            onLoadStart: () => renderer.renderLoading('Loading estimate versions...'),
            onSuccess: ({ results, pagination, state }) => {
                const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
                renderer.renderRows(results, hasFilters);
                renderer.renderPagination(pagination);
                _loadEstimateHistoryVersionDropdown();
            },
            onError: () =>
                renderer.renderError('Failed to load estimate versions. Please refresh the page.'),
        });

        initSorting({
            tableId: 'estimates-table',
            fetcher: estimatesTableFetcher,
        });

        estimatesTableFetcher.refresh();
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderEstimates] Failed to load project estimates information.', err);
    }
}

function renderEstimateRow(estimate) {
    const isApproved = estimate.status === 'APPROVED';
    const isSuperseded = estimate.status === 'SUPERSEDED';
    const canEdit = !isApproved && !isSuperseded;

    const versionCell = estimate.estimate_link
        ? `<a href="${escHtml(estimate.estimate_link)}" target="_blank" rel="noopener noreferrer" class="rp-link fw-semibold">${escHtml(estimate.version_label)}</a>`
        : `<span class="fw-semibold">${escHtml(estimate.version_label)}</span>`;

    const days = parseFloat(estimate.estimate_days);
    const daysFormatted = isNaN(days)
        ? '—'
        : days.toLocaleString('en-GB', { minimumFractionDigits: 0, maximumFractionDigits: 2 });

    const pct = parseFloat(estimate.contingency_pct);
    const pctFormatted = isNaN(pct) ? '—' : `${pct.toFixed(2)}%`;

    const cost = parseFloat(estimate.total_cost);
    const costFormatted = isNaN(cost)
        ? '—'
        : `£${cost.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    return `
        <tr data-estimate-id="${estimate.id}">
            <td>${versionCell}</td>
            <td class="text-center">
                <span class="rp-metric-value">${daysFormatted}</span>
                <span class="text-secondary" style="font-size:.75rem"> d</span>
            </td>
            <td class="text-center">
                <span class="rp-metric-value">${pctFormatted}</span>
            </td>
            <td class="text-end">
                <span class="rp-basis-amount">${costFormatted}</span>
            </td>
            <td class="text-center">
                <span class="rp-badge rp-badge--muted">${escHtml(estimate.tshirt_size)}</span>
            </td>
            <td>${_estimateStatusBadge(estimate.status, estimate.status_display)}</td>
            <td>
                <div class="d-flex gap-1">
                    <button class="btn btn-ghost-icon js-view-estimate" data-id="${estimate.id}" title="View">
                        <i class="bi bi-eye"></i>
                    </button>
                    ${
                        canEdit
                            ? `
                    <button class="btn btn-ghost-icon js-edit-estimate" data-id="${estimate.id}" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>`
                            : ''
                    }
                    ${
                        canEdit
                            ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger js-delete-estimate" data-id="${estimate.id}" data-label="${escHtml(estimate.version_label)}" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>`
                            : ''
                    }
                </div>
            </td>
        </tr>
    `;
}

function _estimateStatusBadge(status, label) {
    const map = {
        DRAFT: 'rp-badge--muted',
        REVIEWED: 'rp-badge--warning',
        SHARED: 'rp-badge--warning',
        APPROVED: 'rp-badge--success',
        SUPERSEDED: 'rp-badge--muted',
    };
    return `<span class="rp-badge ${map[status] || 'rp-badge--muted'}">${escHtml(label || status)}</span>`;
}

function _bindEstimateTableActions() {
    const tbody = document.getElementById('estimates-tbody');
    if (!tbody) return;

    tbody.addEventListener('click', (e) => {
        const viewBtn = e.target.closest('.js-view-estimate');
        const editBtn = e.target.closest('.js-edit-estimate');
        const deleteBtn = e.target.closest('.js-delete-estimate');

        if (viewBtn) openViewEstimateModal(viewBtn.dataset.id);
        if (editBtn) openEditEstimateModal(editBtn.dataset.id);
        if (deleteBtn) openDeleteEstimateModal(deleteBtn.dataset.id, deleteBtn.dataset.label);
    });
}

async function openAddEstimateModal() {
    [
        'est-create-days',
        'est-create-contingency',
        'est-create-link',
        'est-create-shared-by',
        'est-create-reviewed-by',
        'est-create-notes',
    ].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = id === 'est-create-contingency' ? '0' : '';
    });

    try {
        const options = await fetchEstimateOptions();
        const items = options?.status ?? [];
        const dropDownEl = document.getElementById('est-create-status');
        dropDownEl.innerHTML = '';

        items.forEach((s) => {
            const option = document.createElement('option');
            option.value = s.value;
            option.textContent = s.label;
            dropDownEl.appendChild(option);
        });
        if (dropDownEl) dropDownEl.value = 'DRAFT';
    } catch (err) {
        console.error(err);
    }

    document.getElementById('proj-add-estimate-banner')?.classList.add('d-none');
    _showModal('projAddEstimateModal');
}

async function saveEstimate() {
    const btn = document.getElementById('est-create-save-btn');
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    const payload = {
        estimate_days: document.getElementById('est-create-days').value,
        contingency_pct: document.getElementById('est-create-contingency').value || '0',
        status: document.getElementById('est-create-status').value,
        estimate_link: document.getElementById('est-create-link').value || null,
        shared_by: document.getElementById('est-create-shared-by').value,
        reviewed_by: document.getElementById('est-create-reviewed-by').value,
        notes: document.getElementById('est-create-notes').value,
    };

    try {
        const { method, href } = API_URLS.projects.estimates.create(projectPk);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        _hideModal('projAddEstimateModal');
        showFlash('Estimate created.', 'success');
        estimatesTableFetcher?.refresh();
    } catch (err) {
        const msg = _extractError(err, 'Failed to create estimate.');
        const banner = document.getElementById('proj-add-estimate-banner');
        if (banner) {
            banner.textContent = msg;
            banner.classList.remove('d-none');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function openViewEstimateModal(estimateId) {
    const container = document.getElementById('proj-view-estimate-body');
    container.innerHTML = `<div class="text-center py-4"><div class="spinner-border spinner-border-sm"></div></div>`;
    _showModal('projViewEstimateModal');

    try {
        const { method, href } = API_URLS.projects.estimates.detail(projectPk, estimateId);
        const e = await apiFetch(href, { method });

        const cost = parseFloat(e.total_cost);
        const costFmt = isNaN(cost)
            ? '—'
            : `£${cost.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        const dayRate = parseFloat(e.day_rate);
        const dayRateFmt = isNaN(dayRate)
            ? '—'
            : `£${dayRate.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        container.innerHTML = `
            <div class="rp-view-field">
                <span class="rp-view-label">Version</span>
                <span class="rp-view-value rp-code">${escHtml(e.version_label)}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Status</span>
                <span class="rp-view-value">${_estimateStatusBadge(e.status, e.status_display)}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Estimate Days</span>
                <span class="rp-view-value">${parseFloat(e.estimate_days).toLocaleString('en-GB', { maximumFractionDigits: 2 })} d</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Contingency</span>
                <span class="rp-view-value">${parseFloat(e.contingency_pct).toFixed(2)}%</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Day Rate</span>
                <span class="rp-view-value">${dayRateFmt}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Total Cost</span>
                <span class="rp-view-value"><strong>${costFmt}</strong></span>
                <span class="rp-hint">
                    Formula: estimate days * day rate * (1 + contigency % / 100)
                </span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">T-Shirt Size</span>
                <span class="rp-view-value"><span class="rp-badge rp-badge--muted">${escHtml(e.tshirt_size)}</span></span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Shared By</span>
                <span class="rp-view-value">${escHtml(e.shared_by || '-')}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Reviewed By</span>
                <span class="rp-view-value">${escHtml(e.reviewed_by || '-')}</span>
            </div>
            ${
                e.estimate_link
                    ? `<div class="rp-view-field rp-view-field--block">
                    <span class="rp-view-label">Estimate Link</span>
                    <span class="rp-view-value rp-view-description">
                        <a href="${escHtml(e.estimate_link)}" target="_blank" rel="noopener noreferrer" class="rp-link">${escHtml(e.estimate_link)}</a>
                    </span>
                </div>`
                    : ''
            }
            <div class="rp-view-field">
                <span class="rp-view-label">Created</span>
                <span class="rp-view-value">${formatDateTime(e.created_at)}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Updated</span>
                <span class="rp-view-value">${formatDateTime(e.updated_at)}</span>
            </div>`;
    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger py-2">Failed to load estimate.</div>`;
    }
}

async function openEditEstimateModal(estimateId) {
    document.getElementById('proj-edit-estimate-banner')?.classList.add('d-none');
    document.getElementById('est-edit-id').value = estimateId;

    try {
        const options = await fetchEstimateOptions();
        const items = options?.status ?? [];
        const dropDownEl = document.getElementById('est-edit-status');
        dropDownEl.innerHTML = '';

        items.forEach((s) => {
            const option = document.createElement('option');
            option.value = s.value;
            option.textContent = s.label;
            dropDownEl.appendChild(option);
        });

        const { method, href } = API_URLS.projects.estimates.detail(projectPk, estimateId);
        const e = await apiFetch(href, { method });

        document.getElementById('est-edit-days').value = e.estimate_days;
        document.getElementById('est-edit-contingency').value = e.contingency_pct;
        document.getElementById('est-edit-days')._originalValue = e.estimate_days;
        document.getElementById('est-edit-contingency')._originalValue = e.contingency_pct;
        document.getElementById('est-edit-status').value = e.status;
        document.getElementById('est-edit-link').value = e.estimate_link || '';
        document.getElementById('est-edit-shared-by').value = e.shared_by || '';
        document.getElementById('est-edit-reviewed-by').value = e.reviewed_by || '';
        document.getElementById('est-edit-notes').value = '';

        const locked = e.status === 'APPROVED' || e.status === 'SUPERSEDED';
        const notice = document.getElementById('est-edit-locked-notice');
        if (notice) notice.classList.toggle('d-none', !locked);

        ['est-edit-days', 'est-edit-contingency'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.disabled = locked;
        });

        _showModal('projEditEstimateModal');
    } catch (err) {
        showFlash('Could not load estimate.', 'danger');
    }
}

async function saveEditEstimate() {
    const btn = document.getElementById('est-edit-save-btn');
    const estimateId = document.getElementById('est-edit-id').value;
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    const daysEl = document.getElementById('est-edit-days');
    const contingencyEl = document.getElementById('est-edit-contingency');

    const payload = {
        status: document.getElementById('est-edit-status').value,
        estimate_link: document.getElementById('est-edit-link').value || null,
        shared_by: document.getElementById('est-edit-shared-by').value,
        reviewed_by: document.getElementById('est-edit-reviewed-by').value,
        notes: document.getElementById('est-edit-notes').value,
    };

    if (daysEl._originalValue !== daysEl.value) payload.estimate_days = daysEl.value;
    if (contingencyEl._originalValue !== contingencyEl.value)
        payload.contingency_pct = contingencyEl.value;

    try {
        const { method, href } = API_URLS.projects.estimates.edit(projectPk, estimateId);
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        _hideModal('projEditEstimateModal');
        showFlash('Estimate updated.', 'success');
        estimatesTableFetcher?.refresh();
        if (_currentHistoryEstimateId == estimateId) {
            renderEstimateHistory(estimateId, 1);
        }
    } catch (err) {
        const msg = _extractError(err, 'Failed to update estimate.');
        const banner = document.getElementById('proj-edit-estimate-banner');
        if (banner) {
            banner.textContent = msg;
            banner.classList.remove('d-none');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

function openDeleteEstimateModal(estimateId, label) {
    document.getElementById('est-delete-id').value = estimateId;
    document.getElementById('est-delete-label').textContent = label;
    _showModal('projDeleteEstimateModal');
}

async function confirmDeleteEstimate() {
    const btn = document.getElementById('est-delete-confirm-btn');
    const estimateId = document.getElementById('est-delete-id').value;
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        const { method, href } = API_URLS.projects.estimates.delete(projectPk, estimateId);
        await apiFetch(href, { method });
        _hideModal('projDeleteEstimateModal');
        showFlash('Estimate deleted.', 'success');
        estimatesTableFetcher?.refresh();
        if (_currentHistoryEstimateId == estimateId) {
            _currentHistoryEstimateId = null;
            document.getElementById('estimate-history-timeline').innerHTML = '';
            document.getElementById('estimate-history-version-select').value = '';
        }
    } catch (err) {
        showFlash(_extractError(err, 'Failed to delete estimate.'), 'danger');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function _loadEstimateHistoryVersionDropdown() {
    const sel = document.getElementById('estimate-history-version-select');
    if (!sel) return;

    try {
        const { method, href } = API_URLS.projects.estimates.options(projectPk);
        const data = await apiFetch(href, { method });
        const versions = Array.isArray(data) ? data : data.versions || [];

        const prevId = _currentHistoryEstimateId || (versions[0] && versions[0].id);

        sel.innerHTML =
            `<option value="">Select version</option>` +
            versions
                .map(
                    (v) =>
                        `<option value="${v.id}">${escHtml(v.version_label)}${v.status ? ' · ' + escHtml(v.status) : ''}</option>`,
                )
                .join('');

        if (prevId) {
            sel.value = prevId;
            renderEstimateHistory(prevId, 1);
        }
    } catch (_) {}
}

async function renderEstimateHistory(estimateId, page = 1) {
    if (!estimateId) {
        document.getElementById('estimate-history-timeline').innerHTML = '';
        document.getElementById('estimate-history-pagination').innerHTML = '';
        return;
    }
    _currentHistoryEstimateId = estimateId;
    _estimateHistoryPage = page;

    const container = document.getElementById('estimate-history-timeline');
    const paginationEl = document.getElementById('estimate-history-pagination');
    container.innerHTML = `<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary"></div></div>`;

    try {
        const { method, href } = API_URLS.projects.estimates.history(projectPk, estimateId);
        const data = await apiFetch(`${href}?page=${page}&page_size=15`, { method });
        const items = data.results || [];

        if (!items.length) {
            container.innerHTML = `<p class="text-secondary small mb-0">No history for this version.</p>`;
            if (paginationEl) paginationEl.innerHTML = '';
            return;
        }

        container.innerHTML = `<div class="rp-timeline d-flex flex-column">${_buildEstimateHistoryItems(items)}</div>`;

        if (paginationEl) _renderEstimateHistoryPagination(data, paginationEl, estimateId);
    } catch (err) {
        container.innerHTML = `<p class="text-secondary small mb-0">Failed to load history.</p>`;
    }
}

function _buildEstimateHistoryItems(entries) {
    const iconMap = {
        CREATED: { icon: 'bi-plus-circle-fill', cls: 'text-success' },
        UPDATED: { icon: 'bi-pencil-fill', cls: 'text-primary' },
        APPROVED: { icon: 'bi-check-circle-fill', cls: 'text-success' },
        SUPERSEDED: { icon: 'bi-arrow-counterclockwise', cls: 'text-secondary' },
    };

    return entries
        .map((h, i) => {
            const { icon, cls } = iconMap[h.action] || { icon: 'bi-circle', cls: 'text-secondary' };
            const statusChange = h.previous_status
                ? `<span class="rp-badge rp-badge--muted">${escHtml(h.previous_status)}</span>
                   <i class="bi bi-arrow-right mx-1 text-secondary" style="font-size:.7rem"></i>
                   <span class="rp-badge rp-badge--muted">${escHtml(h.new_status)}</span>`
                : `<span class="rp-badge rp-badge--muted">${escHtml(h.new_status)}</span>`;

            return `
            <div class="rp-timeline-item">
                <div class="rp-timeline-marker">
                    <div class="rp-timeline-dot ${i === 0 ? 'rp-timeline-dot--success' : 'rp-timeline-dot--muted'}">
                        <i class="bi ${icon} ${cls}" style="font-size:.65rem; line-height:1;"></i>
                    </div>
                    ${i < entries.length - 1 ? '<div class="rp-timeline-line"></div>' : ''}
                </div>
                <div class="rp-timeline-body pb-3">
                    <div class="rp-timeline-meta">
                        <i class="bi bi-calendar3"></i> ${formatDateTime(h.created_at)}
                    </div>
                    <div class="d-flex align-items-center gap-2 flex-wrap mb-1">
                        <span class="fw-semibold" style="font-size:.85rem">${escHtml(h.action_display)}</span>
                        ${statusChange}
                    </div>
                    ${h.notes ? `<p class="text-secondary small mb-0">${escHtml(h.notes)}</p>` : ''}
                </div>
            </div>`;
        })
        .join('');
}

function _renderEstimateHistoryPagination(data, el, estimateId) {
    const totalPages = data.num_pages || 1;
    if (totalPages <= 1) {
        el.innerHTML = '';
        return;
    }
    const prev = _estimateHistoryPage > 1 ? 'disabled' : '';
    const next = _estimateHistoryPage >= totalPages ? 'disabled' : '';
    el.innerHTML = `
        <div class="d-flex align-items-center gap-2 mt-2">
            <button class="btn btn-outline-secondary btn-sm" ${prev ? '' : ''} id="est-hist-prev"
                ${_estimateHistoryPage <= 1 ? 'disabled' : ''}>
                <i class="bi bi-chevron-left"></i>
            </button>
            <span class="text-secondary small">Page ${_estimateHistoryPage} of ${totalPages}</span>
            <button class="btn btn-outline-secondary btn-sm" id="est-hist-next"
                ${_estimateHistoryPage >= totalPages ? 'disabled' : ''}>
                <i class="bi bi-chevron-right"></i>
            </button>
        </div>`;
    el.querySelector('#est-hist-prev')?.addEventListener('click', () =>
        renderEstimateHistory(estimateId, _estimateHistoryPage - 1),
    );
    el.querySelector('#est-hist-next')?.addEventListener('click', () =>
        renderEstimateHistory(estimateId, _estimateHistoryPage + 1),
    );
}

async function renderContacts(role) {
    try {
        exitEditMode('contacts');

        const tbodyId = role === 'PROJECT' ? 'project-contacts-tbody' : 'finance-contacts-tbody';
        const tbody = document.getElementById(tbodyId);
        const countId = role === 'PROJECT' ? 'js-project-count' : 'js-finance-count';
        const countEl = document.getElementById(countId);
        try {
            const rows = await fetchContacts(role);
            if (!rows.length) {
                tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4">No ${role.toLowerCase()} contacts yet.</td></tr>`;
                return;
            }
            tbody.innerHTML = rows.map((pc) => renderContactRow(pc)).join('');
            countEl.textContent = `${rows.length} / 10`;
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-danger py-3">${e.message}</td></tr>`;
            countEl.textContent = '0 / 10';
        }
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderContacts] Failed to load project contacts information.', err);
    }
}

function renderContactRow(pc) {
    const statusBadge = pc.is_active
        ? `<span class="rp-badge rp-badge--success">Active</span>`
        : `<span class="rp-badge rp-badge--muted">Inactive</span>`;

    const actions = pc.is_active
        ? `<button class="btn-ghost-icon btn-ghost-icon--danger" title="Remove"
              onclick="openRemoveContactModal(${pc.id}, '${escAttr(pc.contact.name)}')">
         <i class="bi bi-x-circle"></i>
       </button>`
        : `<button class="btn-ghost-icon" title="Restore"
              onclick="unarchive(${pc.id})">
         <i class="bi bi-arrow-counterclockwise"></i>
       </button>`;

    return `<tr>
    <td><a class="rp-link" href="/contacts/${pc.contact.id}/">${escHtml(pc.contact.name)}</a></td>
    <td><a class="rp-link" href="mailto:${escHtml(pc.contact.email)}">${escHtml(pc.contact.email)}</a></td>
    <td>${statusBadge}</td>
    <td class="text-end">${actions}</td>
  </tr>`;
}

async function renderLinks() {
    try {
        exitEditMode('links');

        const renderer = initRenderer({
            tbodyId: 'links-tbody',
            colspan: 3,
            itemLabel: 'links',
            rowTemplate: renderLinkRow,
            emptyState: {
                message: 'No links yet.',
                link: {
                    href: '#',
                    label: 'Create the first one.',
                    onclick: '_showModal("projAddEstimateModal")',
                },
            },
            filterEmptyState: {},
            paginationBarId: 'links-pagination-bar',
            paginationInfoId: 'links-pagination-info',
            paginationControlsId: 'links-pagination-controls',
            onPageChange: (page) => linksTableFetcher.goToPage(page),
        });

        linksTableFetcher = initFetch({
            apiUrl: API_URLS.projects.links.list(projectPk).href,
            pageSize: 20,
            searchInputId: '',
            filters: [],
            onLoadStart: () => renderer.renderLoading('Loading project links...'),
            onSuccess: ({ results, pagination, state }) => {
                const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
                renderer.renderRows(results, hasFilters);
                renderer.renderPagination(pagination);
            },
            onError: () =>
                renderer.renderError('Failed to load project links. Please refresh the page.'),
        });

        initSorting({
            tableId: 'links-table',
            fetcher: linksTableFetcher,
        });

        linksTableFetcher.refresh();
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderLinks] Failed to load project links information.', err);
    }
}

function renderLinkRow(link) {
    return `
        <tr data-link-id="${link.id}">
            <td>${escHtml(link.title)}</td>
            <td>
                <a href="${escHtml(link.url)}" target="_blank" rel="noopener noreferrer"
                class="rp-link text-truncate d-block" style="max-width:420px;" onclick="event.stopPropagation()">
                ${escHtml(link.url)}</a>
            </td>
            <td>
                <div class="d-flex gap-1">
                    <button class="btn btn-ghost-icon js-edit-link" data-id="${link.id}" data-title="${link.title}" data-url="${link.url}" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-ghost-icon js-delete-link" data-id="${link.id}" data-title="${link.title}" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function _bindLinkTableActions() {
    const tbody = document.getElementById('links-tbody');
    if (!tbody) return;

    tbody.addEventListener('click', (e) => {
        const editBtn = e.target.closest('.js-edit-link');
        const deleteBtn = e.target.closest('.js-delete-link');

        if (editBtn) {
            openEditLinkModal(editBtn.dataset.id, editBtn.dataset.title, editBtn.dataset.url);
        }
        if (deleteBtn) {
            openDeleteLinkModal(deleteBtn.dataset.id, deleteBtn.dataset.title);
        }
    });
}

function openAddLinkModal() {
    document.getElementById('link-title').value = '';
    document.getElementById('link-url').value = '';
    document.getElementById('link-id').value = '';
    document.getElementById('link-form-error').classList.add('d-none');
    document.getElementById('link-save-btn').dataset.mode = 'add';
    _showModal('linkModal');
}

function openEditLinkModal(id, title, url) {
    document.getElementById('linkModalLabel').textContent = id ? 'Edit Link' : 'Add Link';
    document.getElementById('link-title').value = title;
    document.getElementById('link-url').value = url;
    document.getElementById('link-id').value = id;
    document.getElementById('link-form-error').classList.add('d-none');
    _showModal('linkModal');
    document.getElementById('link-save-btn').dataset.mode = 'edit';
    document.getElementById('link-title').focus();
}

function openDeleteLinkModal(id, title) {
    document.getElementById('link-delete-title').textContent = title;
    document.getElementById('link-delete-btn').dataset.id = id;
    _showModal('linkDeleteModal');
}

async function saveLink() {
    const btn = document.getElementById('link-save-btn');
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving...';

    const payload = {
        title: document.getElementById('link-title').value,
        url: document.getElementById('link-url').value,
    };

    try {
        if (btn.dataset.mode == 'add') {
            const { method, href } = API_URLS.projects.links.new(projectPk);
            const body = JSON.stringify(payload);
            await apiFetch(href, { method, body });
            showFlash('Project link created.', 'success');
        } else if (btn.dataset.mode == 'edit') {
            const { method, href } = API_URLS.projects.links.update(
                projectPk,
                document.getElementById('link-id').value,
            );
            const body = JSON.stringify(payload);
            await apiFetch(href, { method, body });
            showFlash('Project link updated.', 'success');
        }
        _hideModal('linkModal');
        await renderLinks();
    } catch (err) {
        const msg = _extractError(err, 'Failed to create/update link.');
        const banner = document.getElementById('link-form-error');
        if (banner) {
            banner.textContent = msg;
            banner.classList.remove('d-none');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function deleteLink() {
    const btn = document.getElementById('link-delete-btn');
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Deleting...';

    try {
        const { method, href } = API_URLS.projects.links.delete(projectPk, btn.dataset.id);
        await apiFetch(href, { method });
        showFlash('Project link deleted.', 'success');
        _hideModal('linkDeleteModal');
        await renderLinks();
    } catch (err) {
        const msg = _extractError(err, 'Failed to delete link.');
        const banner = document.getElementById('link-form-error');
        if (banner) {
            banner.textContent = msg;
            banner.classList.remove('d-none');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function renderStatusHistory() {
    try {
        exitEditMode('history');
        const history = await fetchStatusHistory();
        const items = history.results || history;

        const countBtn = document.getElementById('status-history-count');
        if (countBtn && items.length) {
            const n = items.length;
            countBtn.textContent = `${n} record${n !== 1 ? 's' : ''}`;
            countBtn.style.display = '';
        }

        const container = document.getElementById('status-history-container');
        if (!items.length) {
            container.innerHTML = `
                <div class="d-flex flex-column align-items-center justify-content-center py-4 text-secondary">
                    <i class="bi bi-clock-history fs-3 mb-2 opacity-50"></i>
                    <span class="small">No status history recorded yet.</span>
                </div>`;
            return;
        }

        container.innerHTML = `<div class="rp-timeline d-flex flex-column">${_buildStatusHistoryItems(items, items.length > 20)}</div>`;
    } catch (err) {
        _showBanner('Failed to load history information. Please refresh the page.', 'error');
        console.error('[renderStatusHistory] Failed to load project history information.', err);
    }
}

function _buildStatusHistoryItems(entries, addEllipsis = false) {
    const items = entries.map((entry, i) => {
        const fromStatus = entry.previous_status
            ? `<strong>${escHtml(entry.previous_status_display)}</strong>`
            : '<span class="text-secondary fst-italic">—</span>';
        const toStatus = `<strong>${escHtml(entry.new_status_display)}</strong>`;

        const fromSub = entry.previous_sub_status_name
            ? `<span class="rp-badge rp-badge--muted ms-1">${escHtml(entry.previous_sub_status_name)}</span>`
            : '';
        const toSub = entry.new_sub_status_name
            ? `<span class="rp-badge rp-badge--muted ms-1">${escHtml(entry.new_sub_status_name)}</span>`
            : '';

        const reason = entry.reason
            ? `<p class="text-secondary small mb-0 mt-1">${escHtml(entry.reason)}</p>`
            : '';
        const isLatest = i === 0;
        const dotClass = isLatest ? 'rp-timeline-dot--success' : 'rp-timeline-dot--muted';

        return `
            <div class="rp-timeline-item">
                <div class="rp-timeline-marker">
                    <div class="rp-timeline-dot ${dotClass}"></div>
                    ${i < entries.length - 1 || addEllipsis ? '<div class="rp-timeline-line"></div>' : ''}
                </div>
                <div class="rp-timeline-body pb-4">
                    <div class="rp-timeline-meta">
                        <i class="bi bi-calendar3"></i> ${formatDateTime(entry.created_at)}
                    </div>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        ${fromStatus}${fromSub}
                        <i class="bi bi-arrow-right text-secondary small"></i>
                        ${toStatus}${toSub}
                        ${isLatest ? '<span class="rp-badge rp-badge--info ms-1">Current</span>' : ''}
                    </div>
                    ${reason}
                </div>
            </div>`;
    });

    if (addEllipsis) {
        items.push(`
            <div class="rp-timeline-item">
                <div class="rp-timeline-marker">
                    <div class="rp-timeline-dot rp-timeline-dot--muted"></div>
                </div>
                <div class="rp-timeline-body pb-2">
                    <span class="text-secondary small fst-italic">
                        Older records — click the record count above to view all.
                    </span>
                </div>
            </div>`);
    }

    return items.join('');
}

function populateEditDropdowns(opts) {
    _fillSelect('edit-project-type', opts.project_types ?? [], '', 'Select…', {
        useIdAsValue: true,
    });
    _fillSelect('edit-status', opts.status ?? [], '', null);
    _fillSelect('edit-confidence', opts.confidence ?? [], '', 'Not set');
    _fillSelect('edit-priority', opts.priority ?? [], '', 'Not set');
    _fillSelect('edit-assigned-team', opts.delivery_teams ?? [], '', 'Not set (unassign)');

    _allSubStatuses = opts.sub_statuses ?? [];
    _cascadeSubStatus('edit-status', 'edit-sub-status', {
        emptyLabel: 'All sub-statuses',
        showAllWhenBlank: false,
    });

    window._progOptions = opts.programmes ?? [];
    document.getElementById('edit-status')?.addEventListener('change', () => {
        _cascadeSubStatus('edit-status', 'edit-sub-status', {
            emptyLabel: 'All sub-statuses',
            showAllWhenBlank: false,
        });
    });
    _bindProgrammeAutocomplete('edit-programme', 'edit-programme-id', 'edit-programme-suggestions');
    _buildCollaboratorCheckboxes(opts.delivery_teams ?? []);
}

function _cascadeSubStatus(statusSelectId, subStatusSelectId, { emptyLabel, showAllWhenBlank }) {
    const statusEl = document.getElementById(statusSelectId);
    const subStatusEl = document.getElementById(subStatusSelectId);
    if (!statusEl || !subStatusEl) return;

    const selectedStatus = statusEl.value;
    const currentVal = subStatusEl.value;

    let matching;
    if (!selectedStatus) {
        matching = showAllWhenBlank ? _allSubStatuses : [];
    } else {
        matching = _allSubStatuses.filter((s) => s.main_status === selectedStatus);
    }

    while (subStatusEl.options.length) subStatusEl.remove(0);

    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = emptyLabel;
    subStatusEl.appendChild(ph);

    matching.forEach((s) => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name;
        if (String(s.id) === currentVal) opt.selected = true;
        subStatusEl.appendChild(opt);
    });

    if (currentVal && !matching.find((s) => String(s.id) === currentVal)) {
        subStatusEl.value = '';
    }
}

function _buildCollaboratorCheckboxes(teams) {
    const container = document.getElementById('edit-collaborators-list');
    if (!container) return;
    container.innerHTML = '';
    teams.forEach((t) => {
        const label = document.createElement('label');
        label.className = 'rp-collab-chip';
        label.dataset.teamId = t.id;
        label.innerHTML = `
            <input type="checkbox" class="rp-collab-check" value="${t.id}" style="display:none;">
            <span class="rp-badge rp-badge--muted" style="cursor:pointer;">${escHtml(t.name)}</span>
        `;
        label.addEventListener('click', () => {
            const cb = label.querySelector('input');
            cb.checked = !cb.checked;
            label.querySelector('.rp-badge').classList.toggle('rp-badge--info', cb.checked);
            label.querySelector('.rp-badge').classList.toggle('rp-badge--muted', !cb.checked);
        });
        container.appendChild(label);
    });
}

function _fillSelect(id, items, defaultValue, emptyLabel, opts = {}) {
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

async function _syncTeamsEditMode() {
    const teams = await fetchTeams();
    const assignedEl = document.getElementById('edit-assigned-team');
    if (assignedEl) assignedEl.value = teams?.assigned_team ?? '';

    const currentCollab = new Set((teams?.collaborators ?? []).map((c) => String(c.id)));
    const assignedId = String(teams?.assigned_team ?? '');

    document.querySelectorAll('#edit-collaborators-list .rp-collab-chip').forEach((label) => {
        const cb = label.querySelector('input');
        const badge = label.querySelector('.rp-badge');
        const teamId = String(label.dataset.teamId);

        const isAssigned = teamId === assignedId;
        const isCollab = currentCollab.has(teamId);

        label.style.display = isAssigned ? 'none' : '';
        cb.checked = isCollab && !isAssigned;
        badge.classList.toggle('rp-badge--info', cb.checked);
        badge.classList.toggle('rp-badge--muted', !cb.checked);
    });
}

function _bindAssignedTeamSync() {
    document.getElementById('edit-assigned-team')?.addEventListener('change', (e) => {
        const selectedId = String(e.target.value);
        document.querySelectorAll('#edit-collaborators-list .rp-collab-chip').forEach((label) => {
            const isAssigned = String(label.dataset.teamId) === selectedId;
            label.style.display = isAssigned ? 'none' : '';
            if (isAssigned) {
                label.querySelector('input').checked = false;
                label
                    .querySelector('.rp-badge')
                    .classList.replace('rp-badge--info', 'rp-badge--muted');
            }
        });
    });
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
                     data-id="${p.id}" data-name="${escHtml(p.name)}">${escHtml(p.name)}</button>`,
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

function bindEditButtons() {
    // General tab
    document
        .getElementById('btn-edit-general')
        ?.addEventListener('click', () => enterEditMode('general'));
    document
        .getElementById('btn-cancel-general')
        ?.addEventListener('click', () => exitEditMode('general'));
    document.getElementById('btn-save-general')?.addEventListener('click', () => saveGeneral());
    document.getElementById('btn-post-comment')?.addEventListener('click', handlePostComment);
    document.getElementById('new-comment-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault();
            handlePostComment();
        }
    });
    document
        .getElementById('confirm-edit-comment-btn')
        ?.addEventListener('click', handleSaveEditComment);
    document
        .getElementById('confirm-delete-comment-btn')
        ?.addEventListener('click', handleDeleteComment);

    // Operational tab
    document
        .getElementById('btn-edit-operational')
        ?.addEventListener('click', () => enterEditMode('operational'));
    document
        .getElementById('btn-cancel-operational')
        ?.addEventListener('click', () => exitEditMode('operational'));
    document
        .getElementById('btn-save-operational')
        ?.addEventListener('click', () => saveOperational());
    document
        .getElementById('btn-add-tag')
        ?.addEventListener('click', () => _showModal('projAddTagModal'));
    document.getElementById('confirm-add-tag-btn')?.addEventListener('click', () => saveTag());
    document.getElementById('confirm-delete-tag-btn')?.addEventListener('click', () => deleteTag());

    // Teams tab
    document
        .getElementById('btn-edit-teams')
        ?.addEventListener('click', () => enterEditMode('teams'));
    document
        .getElementById('btn-cancel-teams')
        ?.addEventListener('click', () => exitEditMode('teams'));
    document.getElementById('btn-save-teams')?.addEventListener('click', () => saveTeams());

    _bindAssignedTeamSync();

    // Labels tab
    document
        .getElementById('btn-add-label')
        ?.addEventListener('click', () => _showModal('projAddLabelModal'));
    document
        .getElementById('suggest-project-label-btn')
        ?.addEventListener('click', () => suggestLabel());
    document.getElementById('add-project-label-btn')?.addEventListener('click', () => saveLabel());
    document.getElementById('delete-label-btn')?.addEventListener('click', () => deleteLabel());
    document.getElementById('primary-label-btn')?.addEventListener('click', () => updateLabel());
    document
        .getElementById('btn-add-code')
        ?.addEventListener('click', () => _showModal('projAddCodeModal'));
    document.getElementById('add-project-code-btn')?.addEventListener('click', () => saveCode());

    // Estimates tab
    document.getElementById('btn-add-estimate')?.addEventListener('click', openAddEstimateModal);
    document.getElementById('est-create-save-btn')?.addEventListener('click', saveEstimate);
    document.getElementById('est-edit-save-btn')?.addEventListener('click', saveEditEstimate);
    document
        .getElementById('est-delete-confirm-btn')
        ?.addEventListener('click', confirmDeleteEstimate);
    document
        .getElementById('estimate-history-version-select')
        ?.addEventListener('change', (e) => renderEstimateHistory(e.target.value, 1));

    _bindEstimateTableActions();

    // Budgets tab
    document.getElementById('bud-create-save-btn')?.addEventListener('click', saveBudget);
    document.getElementById('bud-edit-save-btn')?.addEventListener('click', saveEditBudget);
    document
        .getElementById('bud-delete-confirm-btn')
        ?.addEventListener('click', confirmDeleteBudget);

    // Contacts tab
    document
        .getElementById('btn-add-project-contact')
        ?.addEventListener('click', openAddProjectContactModal);
    document
        .getElementById('btn-add-finance-contact')
        ?.addEventListener('click', openAddFinanceContactModal);

    // Links tab
    document.getElementById('btn-add-link')?.addEventListener('click', openAddLinkModal);
    document.getElementById('link-save-btn')?.addEventListener('click', saveLink);
    document.getElementById('link-delete-btn')?.addEventListener('click', deleteLink);

    _bindLinkTableActions();
}

function _showModal(id) {
    if (id === 'projAddLabelModal') resetAddLabelModal();
    if (id === 'projAddTagModal') resetAddTagModal();
    if (id === 'projAddCodeModal') resetAddCodeModal();
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id), { focus: false }).show();
}

function _hideModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).hide();
}

function resetAddLabelModal() {
    ['add-project-label', 'add-project-label-primary'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    clearAddLabelModalErrors();
}

function resetAddTagModal() {
    ['add-tag-input'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    clearAddTagModalErrors();
}

function resetAddCodeModal() {
    ['add-project-code', 'add-project-code-notes'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    clearAddCodeModalErrors();
}

function clearAddLabelModalErrors() {
    document.getElementById('proj-add-label-banner').classList.add('d-none');
    ['add-project-label'].forEach((id) => {
        document.getElementById(id)?.classList.remove('is-invalid');
        const errEl = document.getElementById(`${id}-err`);
        if (errEl) errEl.textContent = '';
    });
}

function clearAddTagModalErrors() {
    document.getElementById('proj-add-tag-banner').classList.add('d-none');
    ['add-tag-input'].forEach((id) => {
        document.getElementById(id)?.classList.remove('is-invalid');
        const errEl = document.getElementById(`${id}-err`);
        if (errEl) errEl.textContent = '';
    });
}

function clearAddCodeModalErrors() {
    document.getElementById('proj-add-code-banner').classList.add('d-none');
    ['add-project-code', 'add-project-code-notes'].forEach((id) => {
        document.getElementById(id)?.classList.remove('is-invalid');
        const errEl = document.getElementById(`${id}-err`);
        if (errEl) errEl.textContent = '';
    });
}

function showDeleteLabelModal(id, label, isPrimary) {
    const messageEl = document.getElementById('update-label-message');
    const deleteBtn = document.getElementById('delete-label-btn');
    const activeBtn = document.getElementById('primary-label-btn');
    messageEl.innerHTML = `
        <strong>${label}</strong>: Click <strong>${
            isPrimary ? 'Set as Secondary' : 'Set as Primary'
        }</strong> to make it the ${isPrimary ? 'secondary' : 'primary'} label, or click <strong>Delete</strong> to remove this label.
    `;
    deleteBtn.dataset.id = id;
    activeBtn.dataset.id = id;
    activeBtn.dataset.mode = isPrimary;
    if (isPrimary) {
        activeBtn.textContent = 'Set as Secondary';
        activeBtn.classList.remove('btn-outline-success');
        activeBtn.classList.add('btn-outline-danger');
    } else {
        activeBtn.textContent = 'Set as Primary';
        activeBtn.classList.add('btn-outline-success');
        activeBtn.classList.remove('btn-outline-danger');
    }
    _showModal('projUpdateLabelModal');
}

function showDeleteTagModal(id, name) {
    document.getElementById('delete-tag-name').textContent = name;
    const deleteBtn = document.getElementById('confirm-delete-tag-btn');
    deleteBtn.dataset.id = id;
    deleteBtn.dataset.name = name;
    _showModal('projDeleteTagModal');
}

async function suggestLabel() {
    try {
        const { method, href } = API_URLS.projects.suggest_label(projectPk);
        const res = await apiFetch(href, { method });
        document.getElementById('add-project-label').value = res.suggestion ?? '-';
    } catch (err) {
        const msg = _extractError(err, 'Failed to suggest project label. Please try again.');
        _showBanner(msg, 'error');
    }
}

async function enterEditMode(tab) {
    document.getElementById(`${tab}-view-mode`).classList.add('d-none');
    document.getElementById(`${tab}-edit-mode`).classList.remove('d-none');
    document.getElementById('proj-detail-banner').classList.add('d-none');

    if (tab === 'general') {
        const project = await fetchProject();
        const programmeEl = document.getElementById('edit-programme');
        const suggestionsEl = document.getElementById('edit-programme-suggestions');
        const width = programmeEl.getBoundingClientRect().width;
        suggestionsEl.style.width = width + 'px';
        document.getElementById('edit-name').value = project.name ?? '';
        document.getElementById('edit-project-type').value = project.project_type ?? '';
        document.getElementById('edit-programme-id').value = project.programme;
        programmeEl.value = project.programme_name ?? '';
        document.getElementById('edit-status').value = project.status ?? '';
        document.getElementById('edit-sub-status').value = project.sub_status ?? '';
        document.getElementById('edit-confidence').value = project.confidence ?? '';
        document.getElementById('edit-priority').value = project.priority ?? '';
        document.getElementById('edit-tentative-start').value = project.tentative_start_date ?? '';
        document.getElementById('edit-tentative-end').value = project.tentative_end_date ?? '';
        document.getElementById('edit-is-active').checked = project.is_active ?? true;
        setTimeout(() => document.getElementById('edit-name').focus(), 300);
    } else if (tab === 'operational') {
        const operational = await fetchOperational();
        document.getElementById('edit-effort-issue-commitment-date').value =
            operational.effort_issue_commitment_date ?? '';
        document.getElementById('edit-efforts-issued').checked =
            operational.efforts_issued ?? false;
        document.getElementById('edit-run-cost').checked = operational.run_cost_applies ?? false;
    } else if (tab === 'teams') {
        _syncTeamsEditMode();
    }
}

function exitEditMode(tab) {
    document.getElementById(`${tab}-edit-mode`).classList.add('d-none');
    document.getElementById(`${tab}-view-mode`).classList.remove('d-none');
}

async function saveGeneral() {
    const saveBtn = document.getElementById('btn-save-general');
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const progInput = document.getElementById('edit-programme').value.trim();
    const progId = document.getElementById('edit-programme-id').value;

    let programme = progId || null;
    if (!programme && progInput) {
        try {
            programme = await _resolveOrCreateProgramme(progInput);
        } catch (err) {
            _showBanner('Failed to resolve programme. Please try again.', 'danger');
            return;
        }
    }

    const payload = {
        name: document.getElementById('edit-name').value.trim(),
        project_type: parseInt(document.getElementById('edit-project-type').value) || null,
        programme: programme ? parseInt(programme) : null,
        status: document.getElementById('edit-status').value || 'NEW',
        sub_status: document.getElementById('edit-sub-status').value || null,
        confidence: document.getElementById('edit-confidence').value || '',
        priority: document.getElementById('edit-priority').value || '',
        tentative_start_date: document.getElementById('edit-tentative-start').value || null,
        tentative_end_date: document.getElementById('edit-tentative-end').value || null,
        is_active: document.getElementById('edit-is-active').checked,
    };

    try {
        const { method, href } = API_URLS.projects.partial_edit(projectPk);
        await saveTab(saveBtn, payload, 'general', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save project. Please try again.');
        _showBanner(msg, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function saveOperational() {
    const saveBtn = document.getElementById('btn-save-operational');
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const payload = {
        efforts_issued: document.getElementById('edit-efforts-issued').checked,
        effort_issue_commitment_date:
            document.getElementById('edit-effort-issue-commitment-date').value || null,
        run_cost_applies: document.getElementById('edit-run-cost').checked,
    };

    try {
        const { method, href } = API_URLS.projects.edit_operational(projectPk);
        await saveTab(saveBtn, payload, 'operational', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save operational information. Please try again.');
        _showBanner(msg, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function saveTeams() {
    const saveBtn = document.getElementById('btn-save-teams');
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const assignedTeamRaw = document.getElementById('edit-assigned-team').value;
    const collaboratorIds = Array.from(
        document.querySelectorAll('#edit-collaborators-list .rp-collab-check:checked'),
    ).map((cb) => parseInt(cb.value));

    const payload = {
        assigned_team: assignedTeamRaw ? parseInt(assignedTeamRaw) : null,
        collaborator_ids: collaboratorIds,
    };

    try {
        const { method, href } = API_URLS.projects.edit_teams(projectPk);
        await saveTab(saveBtn, payload, 'teams', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save operational information. Please try again.');
        _showBanner(msg, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function saveLabel() {
    const saveBtn = document.getElementById('add-project-label-btn');
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const payload = {
        label: document.getElementById('add-project-label').value,
        is_primary: document.getElementById('add-project-label-primary').checked,
    };

    try {
        const { method, href } = API_URLS.projects.create_label(projectPk);
        await saveTab(saveBtn, payload, 'labels', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save labels information. Please try again.');
        _showBanner(msg, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function saveCode() {
    const saveBtn = document.getElementById('add-project-code-btn');
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const payload = {
        code: document.getElementById('add-project-code').value,
        notes: document.getElementById('add-project-code-notes').value,
    };

    try {
        const { method, href } = API_URLS.projects.codes.create(projectPk);
        await saveTab(saveBtn, payload, 'labels', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save code information. Please try again.');
        _showBanner(msg, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function saveTag() {
    const saveBtn = document.getElementById('confirm-add-tag-btn');
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const payload = {
        name: document.getElementById('add-tag-input').value,
    };

    try {
        const { method, href } = API_URLS.projects.tags.create(projectPk);
        await saveTab(saveBtn, payload, 'operational', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save tags information. Please try again.');
        _showBanner(msg, 'error', 'proj-add-tag-banner');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function deleteLabel() {
    const deleteBtn = document.getElementById('delete-label-btn');
    const prevText = deleteBtn.textContent;
    deleteBtn.disabled = true;
    deleteBtn.textContent = 'Deleting...';

    const labelId = deleteBtn.dataset.id;
    try {
        const { method, href } = API_URLS.projects.delete_label(projectPk, labelId);
        await saveTab(deleteBtn, null, 'labels', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to delete label information. Please try again.');
        _showBanner(msg, 'error');
    } finally {
        deleteBtn.disabled = false;
        deleteBtn.textContent = prevText;
    }
}

async function deleteTag() {
    const deleteBtn = document.getElementById('confirm-delete-tag-btn');
    const prevText = deleteBtn.textContent;
    deleteBtn.disabled = true;
    deleteBtn.textContent = 'Deleting...';

    const tagId = deleteBtn.dataset.id;
    try {
        const { method, href } = API_URLS.projects.tags.delete(projectPk, tagId);
        await saveTab(deleteBtn, null, 'operational', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to delete tag information. Please try again.');
        _showBanner(msg, 'error');
    } finally {
        deleteBtn.disabled = false;
        deleteBtn.textContent = prevText;
    }
}

async function updateLabel() {
    const updateBtn = document.getElementById('primary-label-btn');
    const prevText = updateBtn.textContent;
    updateBtn.disabled = true;
    updateBtn.textContent = 'Updating...';

    const labelId = updateBtn.dataset.id;
    const isPrimary = updateBtn.dataset.mode === 'true';

    const payload = {
        is_primary: !isPrimary,
    };

    try {
        const { method, href } = API_URLS.projects.edit_label(projectPk, labelId);
        await saveTab(updateBtn, payload, 'labels', method, href);
    } catch (err) {
        const msg = _extractError(err, 'Failed to update label information. Please try again.');
        _showBanner(msg, 'error');
    } finally {
        updateBtn.disabled = false;
        updateBtn.textContent = prevText;
    }
}

async function saveTab(saveBtn, payload, tab, method, apiUrl) {
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        await apiFetch(apiUrl, { method, body: JSON.stringify(payload) });
        showFlash(`${tab}: Project details updated successfully.`, 'success');

        if (tab === 'general') {
            const project = await fetchProject();
            renderHeader(project);
            renderGeneral();
        } else if (tab === 'operational') {
            _hideModal('projAddTagModal');
            _hideModal('projDeleteTagModal');
            renderOperational();
        } else if (tab === 'teams') {
            renderTeams();
        } else if (tab === 'labels') {
            _hideModal('projAddLabelModal');
            _hideModal('projUpdateLabelModal');
            _hideModal('projAddCodeModal');
            renderLabels();
        }

        exitEditMode(tab);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save changes. Please try again.');
        if (tab === 'operational' && method === 'POST' && apiUrl.includes('tags')) {
            _showBanner(msg, 'danger', 'proj-add-tag-banner');
            return;
        }
        _showBanner(msg, 'danger');
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

    const { method, href } = API_URLS.programmes.create;
    const created = await apiFetch(href, {
        method,
        body: JSON.stringify({ name }),
    });
    if (!window._progOptions) window._progOptions = [];
    window._progOptions.push({ id: created.id, name: created.name });
    return created.id;
}

function _statusBadge(status, label) {
    if (!status) return '—';
    return `<span class="rp-badge rp-badge-status--${status.toLowerCase()}">${escHtml(label || status)}</span>`;
}

function _levelBadge(value, label) {
    if (!value) return '<span class="text-muted">—</span>';
    const key = value.toLowerCase().replace('_', '-');
    return `<span class="rp-badge rp-badge-level--${key}">${escHtml(label || value)}</span>`;
}

const _fmtAmt = (v, fallback = '—') =>
    v == null
        ? fallback
        : `£${parseFloat(v).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const _fmtAmtCell = (v) =>
    v == null
        ? '<span class="text-muted">—</span>'
        : `<span class="rp-basis-amount">${_fmtAmt(v)}</span>`;

// function _budgetRiskBadge(risk, display, short) {
//     if (!risk) return '';
//     const map = { GREEN: 'rp-badge--success', AMBER: 'rp-badge--warning', RED: 'rp-badge--danger' };
//     const cls = map[risk] || 'rp-badge--muted';
//     const label = short || display || risk;
//     return `<span class="rp-badge ${cls}" title="${escHtml(display || risk)}">${escHtml(label)}</span>`;
// }

async function renderBudgets() {
    await Promise.all([renderBudgetLifetime(), renderBudgetTable()]);
    _bindBudgetTableActions();
    await _loadBudgetHistoryFyDropdown();
    document.getElementById('btn-add-budget')?.addEventListener('click', openAddBudgetModal);
    document.getElementById('budget-history-fy-select')?.addEventListener('change', function () {
        const budgetId = this.value;
        if (budgetId) renderBudgetHistory(budgetId, 1);
        else {
            document.getElementById('budget-history-timeline').innerHTML =
                '<p class="text-secondary small mb-0">Select a financial year to view its history.</p>';
            document.getElementById('budget-history-pagination').innerHTML = '';
        }
    });
}

async function renderBudgetLifetime() {
    try {
        const { href, method } = API_URLS.projects.budgets.lifetime(projectPk);
        const data = await apiFetch(href, { method });

        document.getElementById('lt-total-budget').textContent = _fmtAmt(data.total_actual_budget);
        document.getElementById('lt-total-cost').textContent = _fmtAmt(data.total_estimate_cost);
        document.getElementById('lt-remaining').textContent = _fmtAmt(data.remaining_budget);

        const riskEl = document.getElementById('lt-risk-badge');
        riskEl.innerHTML = data.budget_risk
            ? _budgetRiskBadge(data.budget_risk, data.budget_risk_display, data.budget_risk_short)
            : '';

        const riskPctEl = document.getElementById('lt-risk-pct');
        if (riskPctEl) {
            riskPctEl.textContent = data.budget_risk_pct != null ? `${data.budget_risk_pct}%` : '';
        }
        document
            .getElementById('budget-partial-warning')
            ?.classList.toggle('d-none', !data.partial_budget_warning);
    } catch (err) {
        console.error('[renderBudgetLifetime]', err);
    }
}

async function renderBudgetTable() {
    const tbody = document.getElementById('budgets-tbody');
    if (!tbody) return;
    tbody.innerHTML =
        '<tr><td colspan="7" class="text-center text-secondary py-3"><div class="spinner-border spinner-border-sm"></div></td></tr>';

    try {
        const url = API_URLS.projects.budgets.list(projectPk);
        const budgets = await apiFetch(url.href, { method: url.method });

        if (!budgets.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-4">
                        <div class="text-secondary small d-flex flex-column align-items-center gap-2">
                            <i class="bi bi-cash-stack fs-3 opacity-50"></i>
                            No budget records yet.
                            <a href="#" class="rp-link" onclick="_showModal('projAddBudgetModal');return false;">
                                Add the first one.
                            </a>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = budgets.map(_renderBudgetRow).join('');
        _budgetFyOptions = budgets.map((b) => ({
            id: b.id,
            label: b.financial_year_display,
            fy_id: b.financial_year,
        }));
    } catch (err) {
        tbody.innerHTML =
            '<tr><td colspan="7" class="text-center text-danger py-3">Failed to load budgets.</td></tr>';
        console.error('[renderBudgetTable]', err);
    }
}

function _renderBudgetRow(b) {
    const riskPct =
        b.budget_risk_pct != null
            ? `<span class="rp-code" style="font-size:.75rem">${escHtml(b.budget_risk_pct)}%</span>`
            : '<span class="text-muted">—</span>';

    return `
        <tr data-budget-id="${b.id}">
            <td class="fw-semibold">${escHtml(b.financial_year_long || b.financial_year_display)}</td>
            <td class="text-end">${_fmtAmtCell(b.actual_budget)}</td>
            <td class="text-end">${_fmtAmtCell(b.estimate_total_cost)}</td>
            <td class="text-end">${_fmtAmtCell(b.remaining_budget)}</td>
            <td class="text-end">${riskPct}</td>
            <td>${b.budget_risk ? _budgetRiskBadge(b.budget_risk, b.budget_risk_display, b.budget_risk_short) : '<span class="text-muted">—</span>'}</td>
            <td>
                <div class="d-flex gap-1">
                    <button class="btn btn-ghost-icon btn-sm js-view-budget" data-id="${b.id}" title="View">
                        <i class="bi bi-eye"></i>
                    </button>
                    <button class="btn btn-ghost-icon btn-sm js-edit-budget" data-id="${b.id}" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm js-delete-budget"
                        data-id="${b.id}" data-label="${escHtml(b.financial_year_display)}" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>`;
}

function _budgetRiskBadge(risk, display, short) {
    if (!risk) return '';
    const map = {
        GREEN: 'rp-badge--success',
        AMBER: 'rp-badge--warning',
        RED: 'rp-badge--danger',
    };
    return `<span class="rp-badge ${map[risk] || 'rp-badge--muted'}" title="${escHtml(display)}">${escHtml(short || display)}</span>`;
}

function _bindBudgetTableActions() {
    const tbody = document.getElementById('budgets-tbody');
    if (!tbody) return;
    tbody.addEventListener('click', (e) => {
        const viewBtn = e.target.closest('.js-view-budget');
        const editBtn = e.target.closest('.js-edit-budget');
        const deleteBtn = e.target.closest('.js-delete-budget');
        if (viewBtn) openViewBudgetModal(viewBtn.dataset.id);
        if (editBtn) openEditBudgetModal(editBtn.dataset.id);
        if (deleteBtn) openDeleteBudgetModal(deleteBtn.dataset.id, deleteBtn.dataset.label);
    });
}

async function _fetchBudgetCreateOptions() {
    const [fyRes, estRes] = await Promise.all([
        apiFetch(API_URLS.financial_years.list.href, {
            method: API_URLS.financial_years.list.method,
        }),
        apiFetch(API_URLS.projects.estimates.list(projectPk).href, {
            method: API_URLS.projects.estimates.list(projectPk).method,
        }),
    ]);
    _budgetFyOptions = (fyRes.results || fyRes).map((fy) => ({ id: fy.id, label: fy.short_fy }));
    _budgetEstimateOptions = (estRes.results || estRes).map((e) => ({
        id: e.id,
        label: e.version_label,
    }));
    return { fyOptions: _budgetFyOptions, estimateOptions: _budgetEstimateOptions };
}

function _populateBudgetFySelect(selectEl, options, selectedId = '') {
    selectEl.innerHTML = '<option value="">Select financial year…</option>';
    options.forEach((fy) => {
        const opt = document.createElement('option');
        opt.value = fy.id;
        opt.textContent = fy.label;
        if (String(fy.id) === String(selectedId)) opt.selected = true;
        selectEl.appendChild(opt);
    });
}

function _populateBudgetEstimateSelect(selectEl, options, selectedId = '') {
    selectEl.innerHTML = '<option value="">None</option>';
    options.forEach((e) => {
        const opt = document.createElement('option');
        opt.value = e.id;
        opt.textContent = e.label;
        if (String(e.id) === String(selectedId)) opt.selected = true;
        selectEl.appendChild(opt);
    });
}

async function openAddBudgetModal() {
    ['bud-create-allocated', 'bud-create-refined', 'bud-create-notes'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    document.getElementById('proj-add-budget-banner')?.classList.add('d-none');

    try {
        const { fyOptions, estimateOptions } = await _fetchBudgetCreateOptions();
        _populateBudgetFySelect(document.getElementById('bud-create-fy'), fyOptions);
        _populateBudgetEstimateSelect(
            document.getElementById('bud-create-estimate'),
            estimateOptions,
        );
    } catch (err) {
        console.error('[openAddBudgetModal]', err);
    }

    _showModal('projAddBudgetModal');
}

async function saveBudget() {
    const btn = document.getElementById('bud-create-save-btn');
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    const payload = {
        financial_year: document.getElementById('bud-create-fy').value || null,
        allocated_budget: document.getElementById('bud-create-allocated').value || null,
        refined_budget: document.getElementById('bud-create-refined').value || null,
        estimate_version: document.getElementById('bud-create-estimate').value || null,
        notes: document.getElementById('bud-create-notes').value || null,
    };

    try {
        const url = API_URLS.projects.budgets.create(projectPk);
        await apiFetch(url.href, { method: url.method, body: JSON.stringify(payload) });
        _hideModal('projAddBudgetModal');
        showFlash('Budget created.', 'success');
        await renderBudgets();
    } catch (err) {
        const msg = _extractError(err, 'Failed to create budget.');
        const banner = document.getElementById('proj-add-budget-banner');
        if (banner) {
            banner.textContent = msg;
            banner.classList.remove('d-none');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function openViewBudgetModal(budgetId) {
    const container = document.getElementById('proj-view-budget-body');
    container.innerHTML =
        '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-secondary"></div></div>';
    _showModal('projViewBudgetModal');

    try {
        const url = API_URLS.projects.budgets.detail(projectPk, budgetId);
        const b = await apiFetch(url.href, { method: url.method });
        const riskPctDisplay =
            b.budget_risk_pct != null
                ? `<span class="rp-code" style="font-size:.8rem">${escHtml(b.budget_risk_pct)}%</span>`
                : '-';

        container.innerHTML = `
            <div class="rp-view-field">
                <span class="rp-view-label">Financial Year</span>
                <span class="rp-view-value fw-semibold">${escHtml(b.financial_year_long || b.financial_year_display)}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Allocated Budget</span>
                <span class="rp-view-value">${_fmtAmt(b.allocated_budget)}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Refined Budget</span>
                <span class="rp-view-value">${_fmtAmt(b.refined_budget)}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Actual Budget</span>
                <span class="rp-view-value"><strong>${_fmtAmt(b.actual_budget)}</strong></span>
                <span class="rp-hint">Refined if set, otherwise allocated.</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Estimate Version</span>
                <span class="rp-view-value">${b.estimate_version_label ? escHtml(b.estimate_version_label) : '<span class="text-muted">None</span>'}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Estimate Cost</span>
                <span class="rp-view-value">${_fmtAmt(b.estimate_total_cost)}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Remaining</span>
                <span class="rp-view-value d-flex align-items-center gap-2">
                    <strong>${_fmtAmt(b.remaining_budget)}</strong>
                    ${_budgetRiskBadge(b.budget_risk, b.budget_risk_display, b.budget_risk_short)}
                </span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Risk %</span>
                <span class="rp-view-value">${riskPctDisplay}</span>
            </div>
            ${
                b.notes
                    ? `<div class="rp-view-field rp-view-field--block">
                <span class="rp-view-label">Notes</span>
                <span class="rp-view-value rp-view-description">${escHtml(b.notes)}</span>
            </div>`
                    : ''
            }
            <div class="rp-view-field">
                <span class="rp-view-label">Created</span>
                <span class="rp-view-value">${formatDateTime(b.created_at)}</span>
            </div>
            <div class="rp-view-field">
                <span class="rp-view-label">Updated</span>
                <span class="rp-view-value">${formatDateTime(b.updated_at)}</span>
            </div>`;
    } catch (err) {
        container.innerHTML =
            '<div class="alert alert-danger py-2">Failed to load budget details.</div>';
    }
}

async function openEditBudgetModal(budgetId) {
    document.getElementById('proj-edit-budget-banner')?.classList.add('d-none');
    document.getElementById('bud-edit-id').value = budgetId;

    try {
        const { href, method } = API_URLS.projects.budgets.detail(projectPk, budgetId);
        const b = await apiFetch(href, { method });

        document.getElementById('bud-edit-fy-label').textContent =
            b.financial_year_long || b.financial_year_display;
        document.getElementById('bud-edit-allocated').value = b.allocated_budget ?? '';
        document.getElementById('bud-edit-refined').value = b.refined_budget ?? '';
        document.getElementById('bud-edit-notes').value = b.notes ?? '';

        const { estimateOptions } = await _fetchBudgetCreateOptions();
        _populateBudgetEstimateSelect(
            document.getElementById('bud-edit-estimate'),
            estimateOptions,
            b.estimate_version,
        );

        _showModal('projEditBudgetModal');
    } catch (err) {
        showFlash('Could not load budget.', 'danger');
    }
}

async function saveEditBudget() {
    const btn = document.getElementById('bud-edit-save-btn');
    const budgetId = document.getElementById('bud-edit-id').value;
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    const payload = {
        allocated_budget: document.getElementById('bud-edit-allocated').value || null,
        refined_budget: document.getElementById('bud-edit-refined').value || null,
        estimate_version: document.getElementById('bud-edit-estimate').value || null,
        notes: document.getElementById('bud-edit-notes').value || null,
    };

    try {
        const url = API_URLS.projects.budgets.edit(projectPk, budgetId);
        await apiFetch(url.href, { method: url.method, body: JSON.stringify(payload) });
        _hideModal('projEditBudgetModal');
        showFlash('Budget updated.', 'success');
        await renderBudgets();
        if (_currentHistoryBudgetId == budgetId) renderBudgetHistory(budgetId, 1);
    } catch (err) {
        const msg = _extractError(err, 'Failed to update budget.');
        const banner = document.getElementById('proj-edit-budget-banner');
        if (banner) {
            banner.textContent = msg;
            banner.classList.remove('d-none');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

function openDeleteBudgetModal(budgetId, label) {
    document.getElementById('bud-delete-id').value = budgetId;
    document.getElementById('bud-delete-label').textContent = label;
    _showModal('projDeleteBudgetModal');
}

async function confirmDeleteBudget() {
    const btn = document.getElementById('bud-delete-confirm-btn');
    const budgetId = document.getElementById('bud-delete-id').value;
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        const url = API_URLS.projects.budgets.delete(projectPk, budgetId);
        await apiFetch(url.href, { method: url.method });
        _hideModal('projDeleteBudgetModal');
        showFlash('Budget deleted.', 'success');
        await renderBudgets();
    } catch (err) {
        showFlash(_extractError(err, 'Failed to delete budget.'), 'danger');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function _loadBudgetHistoryFyDropdown() {
    const sel = document.getElementById('budget-history-fy-select');
    if (!sel) return;
    const prevId = _currentHistoryBudgetId;

    try {
        const [budgetsRes, activeFyRes] = await Promise.all([
            apiFetch(API_URLS.projects.budgets.list(projectPk).href, {
                method: API_URLS.projects.budgets.list(projectPk).method,
            }),
            apiFetch(API_URLS.financial_years.active.href, {
                method: API_URLS.financial_years.active.method,
            }).catch(() => null),
        ]);

        if (!budgetsRes.length) return;

        sel.innerHTML =
            '<option value="">Select FY</option>' +
            budgetsRes
                .map((b) => `<option value="${b.id}">${escHtml(b.financial_year_display)}</option>`)
                .join('');

        let defaultBudget = budgetsRes[0];
        if (activeFyRes?.short_fy) {
            const match = budgetsRes.find((b) => b.financial_year_display === activeFyRes.short_fy);
            if (match) defaultBudget = match;
        }

        const targetId = _currentHistoryBudgetId || defaultBudget?.id;
        if (targetId) {
            sel.value = targetId;
            renderBudgetHistory(targetId, 1);
        }
    } catch (_) {}
}

async function renderBudgetHistory(budgetId, page = 1) {
    if (!budgetId) {
        document.getElementById('budget-history-timeline').innerHTML = '';
        document.getElementById('budget-history-pagination').innerHTML = '';
        return;
    }
    _currentHistoryBudgetId = budgetId;
    _budgetHistoryPage = page;

    const container = document.getElementById('budget-history-timeline');
    const paginationEl = document.getElementById('budget-history-pagination');
    container.innerHTML =
        '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary"></div></div>';

    try {
        const url = API_URLS.projects.budgets.history(projectPk, budgetId);
        const data = await apiFetch(`${url.href}?page=${page}&page_size=15`, {
            method: url.method,
        });
        const items = data.results || [];

        if (!items.length) {
            container.innerHTML =
                '<p class="text-secondary small mb-0">No history for this record.</p>';
            if (paginationEl) paginationEl.innerHTML = '';
            return;
        }

        container.innerHTML = `<div class="rp-timeline d-flex flex-column">${_buildBudgetHistoryItems(items)}</div>`;
        if (paginationEl) _renderBudgetHistoryPagination(data, paginationEl, budgetId);
    } catch (err) {
        container.innerHTML = '<p class="text-secondary small mb-0">Failed to load history.</p>';
    }
}

function _buildBudgetHistoryItems(entries) {
    const iconMap = {
        CREATED: { icon: 'bi-plus-circle-fill', cls: 'text-success' },
        UPDATED: { icon: 'bi-pencil-fill', cls: 'text-primary' },
    };

    const fmtAmt = (v) =>
        v == null
            ? '—'
            : `£${parseFloat(v).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    return entries
        .map((h, i) => {
            const { icon, cls } = iconMap[h.action] || { icon: 'bi-circle', cls: 'text-secondary' };

            const budgetChange =
                h.action === 'CREATED'
                    ? `<div class="small text-secondary mt-1">
                            Allocated: <strong>${fmtAmt(h.new_allocated_budget)}</strong>
                            · Refined: <strong>${fmtAmt(h.new_refined_budget)}</strong>
                            ${h.new_estimate_label ? `· Estimate: <strong>${escHtml(h.new_estimate_label)}</strong>` : ''}
                            ${h.new_total_cost != null ? `· Cost: <strong>${fmtAmt(h.new_total_cost)}</strong>` : ''}
                       </div>`
                    : `<div class="small text-secondary mt-1">
                            ${h.previous_allocated_budget !== h.new_allocated_budget ? `Allocated: <span class="rp-badge rp-badge--muted">${fmtAmt(h.previous_allocated_budget)}</span> <i class="bi bi-arrow-right mx-1" style="font-size:.7rem"></i> <span class="rp-badge rp-badge--muted">${fmtAmt(h.new_allocated_budget)}</span><br>` : ''}
                            ${h.previous_refined_budget !== h.new_refined_budget ? `Refined: <span class="rp-badge rp-badge--muted">${fmtAmt(h.previous_refined_budget)}</span> <i class="bi bi-arrow-right mx-1" style="font-size:.7rem"></i> <span class="rp-badge rp-badge--muted">${fmtAmt(h.new_refined_budget)}</span><br>` : ''}
                            ${h.previous_estimate_version !== h.new_estimate_version ? `Estimate: <span class="rp-badge rp-badge--muted">${escHtml(h.previous_estimate_label || '—')}</span> <i class="bi bi-arrow-right mx-1" style="font-size:.7rem"></i> <span class="rp-badge rp-badge--muted">${escHtml(h.new_estimate_label || '—')}</span>` : ''}
                       </div>`;

            return `
            <div class="rp-timeline-item">
                <div class="rp-timeline-marker">
                    <div class="rp-timeline-dot ${i === 0 ? 'rp-timeline-dot--success' : 'rp-timeline-dot--muted'}">
                        <i class="bi ${icon} ${cls}" style="font-size:.65rem; line-height:1;"></i>
                    </div>
                    ${i < entries.length - 1 ? '<div class="rp-timeline-line"></div>' : ''}
                </div>
                <div class="rp-timeline-body pb-3">
                    <div class="rp-timeline-meta">
                        <i class="bi bi-calendar3"></i> ${formatDateTime(h.created_at)}
                    </div>
                    <div class="d-flex align-items-center gap-2 flex-wrap mb-1">
                        <span class="fw-semibold" style="font-size:.85rem">${escHtml(h.action_display)}</span>
                    </div>
                    ${budgetChange}
                    ${h.notes ? `<p class="text-secondary small mb-0 mt-1">${escHtml(h.notes)}</p>` : ''}
                </div>
            </div>`;
        })
        .join('');
}

function _renderBudgetHistoryPagination(data, el, budgetId) {
    const totalPages = data.num_pages || 1;
    if (totalPages <= 1) {
        el.innerHTML = '';
        return;
    }
    el.innerHTML = `
        <div class="d-flex align-items-center gap-2 mt-2">
            <button class="btn btn-outline-secondary btn-sm" id="bud-hist-prev"
                ${_budgetHistoryPage <= 1 ? 'disabled' : ''}>
                <i class="bi bi-chevron-left"></i>
            </button>
            <span class="text-secondary small">Page ${_budgetHistoryPage} of ${totalPages}</span>
            <button class="btn btn-outline-secondary btn-sm" id="bud-hist-next"
                ${_budgetHistoryPage >= totalPages ? 'disabled' : ''}>
                <i class="bi bi-chevron-right"></i>
            </button>
        </div>`;
    el.querySelector('#bud-hist-prev')?.addEventListener('click', () =>
        renderBudgetHistory(budgetId, _budgetHistoryPage - 1),
    );
    el.querySelector('#bud-hist-next')?.addEventListener('click', () =>
        renderBudgetHistory(budgetId, _budgetHistoryPage + 1),
    );
}

function openAddProjectContactModal() {
    const role = 'PROJECT';
    document.getElementById('modal-role').value = role;
    document.getElementById('addContactModalLabel').textContent =
        `Add ${role === 'PROJECT' ? 'Project' : 'Finance'} Contact`;
    document.getElementById('contact-name-input').value = '';
    document.getElementById('contact-email-input').value = '';
    document.getElementById('contact-id-input').value = '';
    document.getElementById('add-contact-error').classList.add('d-none');
    hideSuggest();
    _selectedContactId = null;
    _showModal('addContactModal');
}

function openAddFinanceContactModal() {
    const role = 'FINANCE';
    document.getElementById('modal-role').value = role;
    document.getElementById('addContactModalLabel').textContent =
        `Add ${role === 'PROJECT' ? 'Project' : 'Finance'} Contact`;
    document.getElementById('contact-name-input').value = '';
    document.getElementById('contact-email-input').value = '';
    document.getElementById('contact-id-input').value = '';
    document.getElementById('add-contact-error').classList.add('d-none');
    hideSuggest();
    _selectedContactId = null;
    _showModal('addContactModal');
}

function openRemoveContactModal(pcId, name) {
    document.getElementById('remove-pc-id').value = pcId;
    document.getElementById('remove-contact-name').textContent = name;
    document.getElementById('remove-reason').value = '';
    document.getElementById('remove-contact-error').classList.add('d-none');
    _showModal('removeContactModal');
}

async function submitAddContact() {
    const role = document.getElementById('modal-role').value;
    const name = document.getElementById('contact-name-input').value.trim();
    const email = document.getElementById('contact-email-input').value.trim();
    const contactId = document.getElementById('contact-id-input').value;
    const errEl = document.getElementById('add-contact-error');
    const spinner = document.getElementById('add-contact-spinner');

    errEl.classList.add('d-none');
    if (!name || !email) {
        _showBanner('Name and email are required', 'error', 'add-contact-error');
        return;
    }

    spinner.classList.remove('d-none');
    try {
        const body = contactId ? { contact_id: parseInt(contactId), role } : { name, email, role };
        const { method, href } = API_URLS.projects.contacts.new(projectPk);
        await apiFetch(href, { method, body: JSON.stringify(body) });
        _hideModal('addContactModal');
        showFlash('Contact added.', 'success');
        renderContacts(role);
    } catch (e) {
        _showBanner(e.message || 'Failed to add contact', 'error', 'add-contact-error');
    } finally {
        spinner.classList.add('d-none');
    }
}

async function submitRemoveContact() {
    const pcId = document.getElementById('remove-pc-id').value;
    const reason = document.getElementById('remove-reason').value.trim();
    const errEl = document.getElementById('remove-contact-error');
    const spinner = document.getElementById('remove-contact-spinner');

    errEl.classList.add('d-none');
    spinner.classList.remove('d-none');
    try {
        const { method, href } = API_URLS.projects.contacts.archive(projectPk, pcId);
        await apiFetch(href, { method, body: JSON.stringify({ reason }) });
        _hideModal('removeContactModal');
        showFlash('Contact removed.', 'success');
        renderContacts('PROJECT');
        renderContacts('FINANCE');
    } catch (e) {
        _showBanner(e.message || 'Failed to remove contact.', 'error', 'remove-contact-error');
    } finally {
        spinner.classList.add('d-none');
    }
}

function hideSuggest() {
    document.getElementById('contact-suggest-list').style.display = 'none';
}

function _showBanner(message, type = 'danger', bannerId = 'proj-detail-banner') {
    const banner = document.getElementById(bannerId);
    if (!banner) return;
    banner.textContent = message;
    banner.className = `alert alert-${type} mb-3`;
}

function _extractError(err, fallback) {
    if (err?.data?.details) {
        const d = err.data.details;
        if (typeof d === 'string') return d;
        if (Array.isArray(d)) return d.join(' ');
        if (typeof d === 'object') return Object.values(d).flat().join(' ');
    }
    if (err?.data?.error) return err.data.error;
    return fallback;
}

document.getElementById('contact-name-input').addEventListener('input', function () {
    const q = this.value.trim();
    clearTimeout(_suggestTimeout);
    _selectedContactId = null;
    document.getElementById('contact-id-input').value = '';
    if (q.length < 2) {
        hideSuggest();
        return;
    }
    _suggestTimeout = setTimeout(() => fetchSuggestions(q), 250);
});

document.getElementById('contact-email-input').addEventListener('input', function () {
    _selectedContactId = null;
    document.getElementById('contact-id-input').value = '';
});

async function fetchSuggestions(q) {
    try {
        const { method, href } = API_URLS.contacts.suggest;
        const results = await apiFetch(`${href}?q=${encodeURIComponent(q)}`, { method });
        renderSuggestions(results);
    } catch (_) {}
}

function renderSuggestions(items) {
    const list = document.getElementById('contact-suggest-list');
    if (!items.length) {
        hideSuggest();
        return;
    }
    list.innerHTML = items
        .map(
            (c) =>
                `<li class="list-group-item list-group-item-action" style="cursor:pointer"
         data-id="${c.id}" data-name="${escAttr(c.name)}" data-email="${escAttr(c.email)}">
       <strong>${escHtml(c.name)}</strong>
       <small class="text-muted ms-2">${escHtml(c.email)}</small>
     </li>`,
        )
        .join('');
    list.style.display = 'block';
    list.querySelectorAll('li').forEach((li) => {
        li.addEventListener('click', () => {
            document.getElementById('contact-name-input').value = li.dataset.name;
            document.getElementById('contact-email-input').value = li.dataset.email;
            document.getElementById('contact-id-input').value = li.dataset.id;
            _selectedContactId = li.dataset.id;
            hideSuggest();
        });
    });
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('#addContactModal')) hideSuggest();
});

window.submitAddContact = submitAddContact;
window.openRemoveContactModal = openRemoveContactModal;
window.submitRemoveContact = submitRemoveContact;

// ── Actuals Tab ───────────────────────────────────────────────────────────────

let _actualsTabData      = null;
let _actualsTabChart     = null;
let _actualsTabFySprints = [];  // all sprints for selected/active FY

async function renderActualsTab() {
    if (_actualsTabData !== null) {
        _renderActualsTabContent(_actualsTabData);
        return;
    }
    const loadingEl = document.getElementById('actuals-tab-loading');
    const emptyEl   = document.getElementById('actuals-tab-empty');
    const contentEl = document.getElementById('actuals-tab-content');
    loadingEl?.classList.remove('d-none');
    emptyEl?.classList.add('d-none');
    contentEl?.classList.add('d-none');

    try {
        const results = await apiFetch(`${API_URLS.project_actuals.list.href}?project_id=${projectPk}`);
        _actualsTabData = (results || [])[0] || null;

        if (_actualsTabData) {
            await _populateActualsFyFilter(_actualsTabData);
            await _loadActualsTabFySprints();

            document.getElementById('actuals-tab-fy')?.addEventListener('change', async () => {
                await _loadActualsTabFySprints();
                _renderActualsTabContent(_actualsTabData);
            });
        }

        _renderActualsTabContent(_actualsTabData);
    } catch (_) {
        if (loadingEl) loadingEl.innerHTML = '<span class="text-danger">Failed to load actuals.</span>';
    }
}

async function _populateActualsFyFilter(a) {
    const fySel = document.getElementById('actuals-tab-fy');
    if (!fySel) return;
    try {
        const [fys, activeFy] = await Promise.all([
            apiFetch(API_URLS.project_actuals.fy_options.href).catch(() => []),
            apiFetch(API_URLS.financial_years.active.href).catch(() => null),
        ]);
        const fyIds    = new Set((a.sprint_actuals || []).map(sa => String(sa.sprint_fy_id)));
        const activeFyId = activeFy?.id ? String(activeFy.id) : null;

        // Show FYs with actuals for this project; also include active FY even if it has none yet
        const fyList = (fys || []).filter(f => fyIds.has(String(f.id)));
        if (activeFy && !fyList.some(f => String(f.id) === activeFyId)) {
            fyList.unshift(activeFy);
        }
        fyList.forEach(f => {
            const o = document.createElement('option');
            o.value = f.id;
            o.textContent = f.short_fy;
            fySel.appendChild(o);
        });

        // Auto-select active FY if present
        if (activeFyId && [...fySel.options].some(o => o.value === activeFyId)) {
            fySel.value = activeFyId;
        } else if (fySel.options.length > 1) {
            fySel.selectedIndex = 1;
        }
    } catch (_) { /* non-critical */ }
}

async function _loadActualsTabFySprints() {
    const fyId = document.getElementById('actuals-tab-fy')?.value || null;
    if (!fyId) { _actualsTabFySprints = []; return; }
    try {
        _actualsTabFySprints = await apiFetch(API_URLS.project_actuals.fy_sprints(fyId).href) || [];
    } catch (_) { _actualsTabFySprints = []; }
}

function _renderActualsTabContent(a) {
    const loadingEl = document.getElementById('actuals-tab-loading');
    const emptyEl   = document.getElementById('actuals-tab-empty');
    const contentEl = document.getElementById('actuals-tab-content');

    loadingEl?.classList.add('d-none');

    if (!a) {
        emptyEl?.classList.remove('d-none');
        contentEl?.classList.add('d-none');
        return;
    }

    contentEl?.classList.remove('d-none');
    emptyEl?.classList.add('d-none');

    const fyId = document.getElementById('actuals-tab-fy')?.value || null;

    // Build rows: all FY sprints merged with actuals data (shows "—" for missing sprints)
    let rows;
    if (_actualsTabFySprints.length) {
        const costBySprint = {};
        (a.sprint_actuals || [])
            .filter(sa => !fyId || String(sa.sprint_fy_id) === String(fyId))
            .forEach(sa => { costBySprint[sa.sprint] = sa; });
        rows = _actualsTabFySprints.map(s => ({
            sprint:         s.id,
            sprint_name:    s.sprint_name,
            sprint_number:  s.sprint_number,
            sprint_fy_short: '',
            total_cost:     costBySprint[s.id]?.total_cost  ?? null,
            total_days:     costBySprint[s.id]?.total_days  ?? null,
        }));
    } else {
        rows = (a.sprint_actuals || [])
            .filter(sa => !fyId || String(sa.sprint_fy_id) === String(fyId))
            .sort((x, y) => x.sprint_number - y.sprint_number);
    }

    const estimateWC  = parseFloat(a.estimate_value_with_contingency) || 0;
    const estimateVal = parseFloat(a.estimate_value) || 0;
    const estimatePct = estimateWC > 0 ? (estimateVal / estimateWC) * 100 : 0;

    // Summary cards
    const risk    = a.risk || 'NEUTRAL';
    const riskCls = risk === 'RISK' ? 'rp-badge--danger' : risk === 'WARNING' ? 'rp-badge--warning' : 'rp-badge--muted';
    document.getElementById('actuals-tab-summary').innerHTML = `
        <div class="col-sm-6 col-md-3">
            <div class="rp-card rp-card--muted p-3 text-center">
                <div class="rp-view-label mb-1">Estimate</div>
                <div class="rp-metric-value fs-5">${_actualsTabFmt(a.estimate_value)}</div>
            </div>
        </div>
        <div class="col-sm-6 col-md-3">
            <div class="rp-card rp-card--muted p-3 text-center">
                <div class="rp-view-label mb-1">Est. + Contingency</div>
                <div class="rp-metric-value fs-5">${_actualsTabFmt(a.estimate_value_with_contingency)}</div>
            </div>
        </div>
        <div class="col-sm-6 col-md-3">
            <div class="rp-card rp-card--muted p-3 text-center">
                <div class="rp-view-label mb-1">Total Cost</div>
                <div class="rp-metric-value fs-5 fw-600">${_actualsTabFmt(a.total_cost_till_date)}</div>
            </div>
        </div>
        <div class="col-sm-6 col-md-3">
            <div class="rp-card rp-card--muted p-3 text-center">
                <div class="rp-view-label mb-1">Remaining</div>
                <div class="rp-metric-value fs-5 ${parseFloat(a.remaining_amount) >= 0 ? 'text-success' : 'text-danger'}">${_actualsTabFmt(a.remaining_amount)}</div>
                <span class="rp-badge ${riskCls} mt-1">${risk.charAt(0) + risk.slice(1).toLowerCase()}</span>
                ${a.ignore_risk ? '<span class="rp-badge rp-badge--muted mt-1 ms-1"><i class="bi bi-eye-slash"></i> Ignored</span>' : ''}
            </div>
        </div>
    `;

    // Sprint breakdown table
    let cumCost = 0;
    const tbody = document.getElementById('actuals-tab-sprint-tbody');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-3">No sprint data for the selected FY.</td></tr>';
    } else {
        tbody.innerHTML = rows.map(r => {
            const hasActuals = r.total_cost !== null;
            const cost = hasActuals ? (parseFloat(r.total_cost) || 0) : 0;
            if (hasActuals) cumCost += cost;
            const cumPct = (hasActuals && estimateWC > 0) ? ((cumCost / estimateWC) * 100).toFixed(1) : null;
            const pctCls = cumCost > estimateWC ? 'text-danger' : cumCost > estimateVal ? 'text-warning' : '';
            return `<tr${!hasActuals ? ' class="text-secondary"' : ''}>
                <td style="font-size:12px">${escHtml(r.sprint_fy_short || '—')}</td>
                <td>${escHtml(r.sprint_name)}</td>
                <td class="text-end">${hasActuals ? parseFloat(r.total_days || 0).toFixed(2) : '—'}</td>
                <td class="text-end">${hasActuals ? _actualsTabFmt(cost) : '—'}</td>
                <td class="text-end fw-500">${hasActuals ? _actualsTabFmt(cumCost) : '—'}</td>
                <td class="text-end ${pctCls}">${cumPct !== null ? cumPct + '%' : '—'}</td>
            </tr>`;
        }).join('');
    }

    // Chart — include all FY sprints; use 0 for those without actuals
    if (_actualsTabChart) { _actualsTabChart.destroy(); _actualsTabChart = null; }
    const ctx = document.getElementById('actuals-tab-chart')?.getContext('2d');
    if (!ctx || !rows.length) return;

    const labels   = rows.map(r => r.sprint_name);
    const costData = rows.map(r => r.total_cost !== null ? (parseFloat(r.total_cost) || 0) : 0);

    // Cumulative cost for right axis
    const cumulativeData = [];
    let _cumSum = 0;
    costData.forEach(v => { _cumSum += v; cumulativeData.push(_cumSum); });

    const _cumColor = v => {
        if (estimateWC > 0 && v > estimateWC) return 'rgba(239,68,68,1)';
        if (estimateVal > 0 && v > estimateVal) return 'rgba(245,158,11,1)';
        return 'rgba(34,197,94,1)';
    };

    const yMax  = Math.max(...costData, 1) * 1.2;
    const y1Max = Math.max(estimateWC > 0 ? estimateWC : 0, ...cumulativeData, 1) * 1.15;

    const datasets = [
        {
            type: 'bar',
            label: 'Sprint Cost',
            data: costData,
            backgroundColor: 'rgba(99,102,241,0.7)',
            borderColor: 'rgba(99,102,241,1)',
            borderWidth: 1,
            yAxisID: 'y',
            order: 3,
        },
        {
            type: 'line',
            label: 'Cumulative Cost',
            data: cumulativeData,
            borderWidth: 2.5,
            pointRadius: 3,
            pointBackgroundColor: cumulativeData.map(_cumColor),
            fill: false,
            yAxisID: 'y1',
            order: 0,
            segment: {
                borderColor: ctx => _cumColor(ctx.p1.parsed.y),
            },
        },
    ];

    if (estimateVal > 0) {
        datasets.push({
            type: 'line',
            label: 'Estimate',
            data: Array(labels.length).fill(estimateVal),
            borderColor: '#d1d5db',
            borderWidth: 1.5,
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
            yAxisID: 'y1',
            order: 2,
        });
    }
    if (estimateWC > 0) {
        datasets.push({
            type: 'line',
            label: 'Est. + Contingency',
            data: Array(labels.length).fill(estimateWC),
            borderColor: '#6b7280',
            borderWidth: 1.5,
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
            yAxisID: 'y1',
            order: 1,
        });
    }

    _actualsTabChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${_actualsTabFmt(ctx.parsed.y)}`,
                    },
                },
            },
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    min: 0,
                    max: yMax,
                    title: { display: true, text: 'Sprint Cost (£)' },
                    ticks: {
                        callback: v => v >= 1_000_000 ? `£${(v/1_000_000).toFixed(1)}M`
                            : v >= 1_000 ? `£${(v/1_000).toFixed(0)}k`
                            : `£${v}`,
                    },
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    min: 0,
                    max: y1Max,
                    title: { display: true, text: 'Cumulative Cost (£)' },
                    ticks: {
                        callback: v => v >= 1_000_000 ? `£${(v/1_000_000).toFixed(1)}M`
                            : v >= 1_000 ? `£${(v/1_000).toFixed(0)}k`
                            : `£${v}`,
                    },
                    grid: { drawOnChartArea: false },
                },
                x: { ticks: { maxRotation: 45, minRotation: 0 } },
            },
        },
    });
}

function _actualsTabFmt(val) {
    const n = parseFloat(val);
    if (isNaN(n)) return '—';
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'GBP', minimumFractionDigits: 2 }).format(n);
}
