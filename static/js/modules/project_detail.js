'use strict';

import {
    apiFetch,
    escHtml,
    formatDate,
    formatDateTime,
    getPkFromUrl,
    setPageTitle,
    showFlash,
} from './../main.js';
import { API_URLS, URLS } from './../urls.js';

const projectPk = getPkFromUrl('projects');

document.addEventListener('DOMContentLoaded', () => {
    if (!projectPk) return;
    initDetailView();
});

let options = null;
let _allSubStatuses = [];

const STATUS_ICON = {
    NEW: { icon: 'bi-circle', cls: 'text-secondary' },
    IN_PROGRESS: { icon: 'bi-play-circle-fill', cls: 'text-success' },
    ON_HOLD: { icon: 'bi-pause-circle-fill', cls: 'text-warning' },
    CANCELLED: { icon: 'bi-x-circle-fill', cls: 'text-danger' },
    COMPLETED: { icon: 'bi-check-circle-fill', cls: 'text-primary' },
};

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

async function fetchOperational() {
    const { method, href } = API_URLS.projects.get_operational(projectPk);
    const res = await apiFetch(href, { method });
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

async function fetchStatusHistory() {
    const { method, href } = API_URLS.projects.status_history(projectPk);
    const res = await apiFetch(`${href}?page_size=10`, { method });
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
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderGeneral] Failed to load project general information.', err);
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
    } catch (err) {
        _showBanner('Failed to load project information. Please refresh the page.', 'error');
        console.error('[renderLabels] Failed to load project labels information.', err);
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

function statusMeta(code) {
    return STATUS_ICON[code] || { icon: 'bi-record-circle', cls: 'text-muted' };
}

function formatStatus(code) {
    if (!code) return '—';
    return code.replace(/_/g, ' ');
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
}

function _showModal(id) {
    if (id === 'projAddLabelModal') resetAddLabelModal();
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

function clearAddLabelModalErrors() {
    document.getElementById('proj-add-label-banner').classList.add('d-none');
    ['add-project-label'].forEach((id) => {
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
            renderOperational();
        } else if (tab === 'teams') {
            renderTeams();
        } else if (tab === 'labels') {
            _hideModal('projAddLabelModal');
            _hideModal('projUpdateLabelModal');
            renderLabels();
        }

        exitEditMode(tab);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save changes. Please try again.');
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

    const { method, href } = API_URLS.programmes.new;
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

function _showBanner(message, type = 'danger') {
    const banner = document.getElementById('proj-detail-banner');
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
