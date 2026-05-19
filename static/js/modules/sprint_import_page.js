'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch, showFlash, getCsrfToken } from '../main.js';

let _teams = [];
let _reviewComplete = null;
let _financeTypes = [];

let _sprintId = null;
let _apiNs = null;
let _detailUrlFn = null;

// ── Public init ──────────────────────────────────────────────────────────────

/**
 * @param {{ sprintId: number, apiNs: object, detailUrlFn: (id: number) => string }} config
 */
export function initImportPage(config) {
    _sprintId = config.sprintId;
    _apiNs = config.apiNs;
    _detailUrlFn = config.detailUrlFn;

    document.addEventListener('DOMContentLoaded', () => {
        _loadFinanceTypes().then(_loadPage);

        document.getElementById('review-complete-btn').addEventListener('click', _openReviewCompleteModal);
        document.getElementById('rc-override-check').addEventListener('change', _onOverrideCheckChange);
        document.getElementById('rc-confirm-btn').addEventListener('click', _submitReviewComplete);
    });
}

// ── Bootstrap ────────────────────────────────────────────────────────────────

async function _loadFinanceTypes() {
    try {
        const data = await apiFetch(API_URLS.finance_types.options.href);
        _financeTypes = data || [];
    } catch (_) { /* non-critical */ }
}

async function _loadPage() {
    try {
        const data = await apiFetch(_apiNs.sprint_status(_sprintId).href);
        _teams = data.teams || [];
        _reviewComplete = data.review_complete || null;
        _renderPage();
    } catch (e) {
        document.getElementById('forecast-loading').innerHTML =
            '<span class="text-danger">Failed to load data.</span>';
    }
}

// ── Page render ──────────────────────────────────────────────────────────────

function _renderPage() {
    const loading = document.getElementById('forecast-loading');
    const teamsEl = document.getElementById('forecast-teams');
    loading.style.display = 'none';
    teamsEl.style.display = '';

    const sprintClosed = window.SPRINT_CLOSED === true;
    const rcBtn = document.getElementById('review-complete-btn');

    if (sprintClosed && rcBtn) {
        rcBtn.disabled = true;
        rcBtn.title = 'Sprint is closed and locked.';
    }

    if (_reviewComplete) {
        document.getElementById('review-complete-badge').classList.remove('d-none');
        const by = _reviewComplete.completed_by_name || '';
        const at = _fmtDate(_reviewComplete.completed_at);
        document.getElementById('review-complete-info').textContent =
            `Completed${by ? ' by ' + by : ''} on ${at}`;
        document.getElementById('review-complete-info').classList.remove('d-none');
        if (!sprintClosed) {
            const hasAnyImports = _teams.some(ts => ts.has_imports);
            if (rcBtn) rcBtn.disabled = !hasAnyImports;
        }
    }

    teamsEl.innerHTML = _teams.map((ts, idx) => _renderTeamAccordion(ts, idx)).join('');
    _bindAccordionImportButtons();
}

function _renderTeamAccordion(ts, idx) {
    const collapseId = `team-collapse-${ts.team_id}`;
    const headId = `team-head-${ts.team_id}`;
    const statusBadge = ts.confirmed
        ? '<span class="rp-badge rp-badge--success ms-2">Confirmed</span>'
        : ts.has_imports
            ? '<span class="rp-badge rp-badge--warning ms-2">Pending</span>'
            : '<span class="rp-badge rp-badge--muted ms-2">No Imports</span>';

    const versionChips = ts.versions.map(v => {
        const cls = v.status === 'confirmed'
            ? 'btn-success'
            : v.status === 'superseded'
                ? 'btn-outline-secondary text-decoration-line-through'
                : 'btn-outline-primary';
        return `<a class="btn btn-sm ${cls}"
            href="${_detailUrlFn(v.id)}"
            title="${_esc(v.status)}">
            v${v.version_number}
        </a>`;
    }).join(' ');

    const importDropdown = `
    <div class="dropdown">
        <button class="btn btn-sm btn-outline-secondary dropdown-toggle"
                type="button" data-bs-toggle="dropdown">
            <i class="bi bi-upload me-1"></i>Import
        </button>
        <ul class="dropdown-menu">
            <li><a class="dropdown-item import-jira-btn" href="#"
                data-team-id="${ts.team_id}">
                <i class="bi bi-kanban me-2"></i>Jira
            </a></li>
            <li><a class="dropdown-item import-upload-btn" href="#"
                data-team-id="${ts.team_id}">
                <i class="bi bi-file-earmark-spreadsheet me-2"></i>Upload CSV
            </a></li>
            <li><hr class="dropdown-divider my-1"></li>
            <li><a class="dropdown-item download-template-btn" href="#">
                <i class="bi bi-file-earmark-arrow-down me-2"></i>Download Template
            </a></li>
        </ul>
    </div>
    <input type="file" accept=".csv" class="d-none csv-file-input" data-team-id="${ts.team_id}">`;

    return `
    <div class="accordion-item rp-card mb-2 border-0">
        <h2 class="accordion-header" id="${headId}">
            <button class="accordion-button collapsed rp-card-heading py-3" type="button"
                    data-bs-toggle="collapse" data-bs-target="#${collapseId}"
                    style="background:transparent;box-shadow:none;">
                <span class="fw-500">${_esc(ts.team_name)}</span>
                ${statusBadge}
                <span class="ms-auto me-3 text-secondary small">
                    ${ts.versions.length ? ts.versions.length + ' version(s)' : 'No imports yet'}
                </span>
            </button>
        </h2>
        <div id="${collapseId}" class="accordion-collapse collapse" data-team-id="${ts.team_id}">
            <div class="accordion-body pt-0">
                <div class="d-flex align-items-center gap-2 mb-3 flex-wrap">
                    <div class="d-flex gap-1 flex-wrap" id="version-chips-${ts.team_id}">
                        ${versionChips || '<span class="text-secondary small">No versions yet</span>'}
                    </div>
                    <div class="ms-auto">${importDropdown}</div>
                </div>
            </div>
        </div>
    </div>`;
}

function _bindAccordionImportButtons() {
    document.querySelectorAll('.import-jira-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            new bootstrap.Modal(document.getElementById('jiraInfoModal')).show();
        });
    });

    document.querySelectorAll('.import-upload-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            const teamId = btn.dataset.teamId;
            const input = document.querySelector(`.csv-file-input[data-team-id="${teamId}"]`);
            if (input) input.click();
        });
    });

    document.querySelectorAll('.csv-file-input').forEach(input => {
        input.addEventListener('change', async () => {
            if (!input.files.length) return;
            await _uploadCsv(input.dataset.teamId, input.files[0]);
            input.value = '';
        });
    });

    document.querySelectorAll('.download-template-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            _downloadCsvTemplate();
        });
    });
}

// ── CSV Template Download ────────────────────────────────────────────────────

function _downloadCsvTemplate() {
    const headers = ['Story Type', 'Jira ID', 'Title/Description', 'Assignee', 'Efforts (s)', 'Sprint', 'Label', 'Mapping'];
    const sample = ['Story', 'PROJ-123', 'Example story description', 'john.doe@example.com', '252000', 'Sprint 1', 'MY-PROJECT-LABEL', 'PROJECT'];
    const csv = [headers.join(','), sample.map(v => `"${v}"`).join(',')].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sprint_import_template.csv';
    a.click();
    URL.revokeObjectURL(url);
}

// ── CSV Upload ───────────────────────────────────────────────────────────────

async function _uploadCsv(teamId, file) {
    const formData = new FormData();
    formData.append('sprint_id', _sprintId);
    formData.append('team_id', teamId);
    formData.append('file', file);

    try {
        const res = await fetch(_apiNs.import.href, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw err;
        }
        const fi = await res.json();
        const headers = fi.detected_headers || [];
        const KNOWN = ['story_type','issue_type','jira_id','jira','issue_key','key',
                       'title_description','title','summary','description',
                       'assignee','assignee_name','efforts_s','efforts_ms','efforts','original_estimate',
                       'sprint','sprint_name','label','labels','mapping','finance_type'];
        const norm = h => h.trim().toLowerCase().replace(/[()]/g,'').replace(/[ /]/g,'_').replace(/^_+|_+$/g,'');
        const unrecognised = headers.filter(h => h && !KNOWN.includes(norm(h)));
        if (unrecognised.length) {
            console.warn('CSV import: unrecognised column headers:', unrecognised);
            showFlash(
                `CSV imported — some columns were not recognised: ${unrecognised.map(h => `"${h}"`).join(', ')}. Check the import detail for blank fields.`,
                'warning',
            );
        } else {
            showFlash('CSV imported successfully.', 'success');
        }
        await _loadPage();
        window.location.href = _detailUrlFn(fi.id);
    } catch (e) {
        showFlash(e.error || 'Import failed.', 'danger');
    }
}

// ── Review Complete ──────────────────────────────────────────────────────────

async function _openReviewCompleteModal() {
    const rcModal = new bootstrap.Modal(document.getElementById('reviewCompleteModal'));
    document.getElementById('rc-errors-section').classList.add('d-none');
    document.getElementById('rc-warnings-section').classList.add('d-none');
    document.getElementById('rc-no-warnings').classList.add('d-none');
    document.getElementById('rc-override-check').checked = false;
    document.getElementById('rc-override-notes-section').classList.add('d-none');
    document.getElementById('rc-confirm-btn').disabled = true;
    rcModal.show();

    try {
        const data = await apiFetch(_apiNs.review_warnings(_sprintId).href);

        if (data.has_errors) {
            // Hard errors — show and keep Complete disabled regardless
            const list = document.getElementById('rc-errors-list');
            list.innerHTML = data.errors.map(e => `<li>${_esc(e)}</li>`).join('');
            document.getElementById('rc-errors-section').classList.remove('d-none');
            // Still show warnings below errors if any exist
            if (data.has_warnings) {
                document.getElementById('rc-warnings-list').innerHTML =
                    data.warnings.map(w => `<li>${_esc(w)}</li>`).join('');
                document.getElementById('rc-warnings-section').classList.remove('d-none');
            }
            // Complete button stays disabled — errors must be fixed first
            return;
        }

        if (data.has_warnings) {
            const list = document.getElementById('rc-warnings-list');
            list.innerHTML = data.warnings.map(w => `<li>${_esc(w)}</li>`).join('');
            document.getElementById('rc-warnings-section').classList.remove('d-none');
        } else {
            document.getElementById('rc-no-warnings').classList.remove('d-none');
            document.getElementById('rc-confirm-btn').disabled = false;
        }
    } catch (e) {
        showFlash('Failed to load warnings.', 'danger');
        rcModal.hide();
    }
}

function _onOverrideCheckChange() {
    const checked = document.getElementById('rc-override-check').checked;
    document.getElementById('rc-override-notes-section').classList.toggle('d-none', !checked);
    document.getElementById('rc-confirm-btn').disabled = !checked;
}

async function _submitReviewComplete() {
    const override = document.getElementById('rc-override-check').checked;
    const notes = document.getElementById('rc-override-notes').value;
    document.getElementById('rc-confirm-btn').disabled = true;

    try {
        await apiFetch(_apiNs.review_complete.href, {
            method: 'POST',
            body: JSON.stringify({ sprint_id: _sprintId, override, override_notes: notes }),
        });
        bootstrap.Modal.getInstance(document.getElementById('reviewCompleteModal'))?.hide();
        showFlash('Review marked as complete.', 'success');
        await _loadPage();
    } catch (e) {
        if (e.data?.has_errors) {
            showFlash('Review blocked: fix the listed project code errors first.', 'danger');
        } else if (e.data?.warnings) {
            showFlash('Warnings found. Check the override box to proceed.', 'warning');
        } else {
            showFlash(e.data?.error || 'Failed to complete review.', 'danger');
        }
        document.getElementById('rc-confirm-btn').disabled = false;
    }
}

// ── Utilities ────────────────────────────────────────────────────────────────

function _esc(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
