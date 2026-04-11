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
    saveBtn.textContent = 'Saving…';

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
    saveBtn.textContent = 'Saving…';

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
    saveBtn.textContent = 'Saving…';

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
